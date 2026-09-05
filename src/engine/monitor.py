import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timezone

from src.domain.models import Match, GeneratedPost, CoverageProfile, Language, NightShiftConfig, PostStatus, MatchStatus
from src.domain.events import DomainEvent, DomainEventType
from src.providers.base import FootballDataProvider
from src.engine.difference_engine import DifferenceEngine
from src.engine.importance_engine import EventImportanceEngine
from src.engine.post_generator import PostGenerator
from src.engine.websocket_manager import WebSocketNotificationManager
from src.publishers.telegram_publisher import TelegramPublisher

logger = logging.getLogger(__name__)


class MatchMonitor:
    """
    Overnight Match Monitoring & News Desk Automation Coordinator.
    Monitors active fixtures, applies coverage intensity filters, triggers Pavilion-style
    post generation, and broadcasts real-time updates over WebSockets.
    """

    def __init__(
        self,
        provider: FootballDataProvider,
        diff_engine: DifferenceEngine,
        post_generator: PostGenerator,
        ws_manager: WebSocketNotificationManager,
        telegram_publisher: Optional[TelegramPublisher] = None,
        poll_interval_seconds: int = 15
    ):
        self.provider = provider
        self.diff_engine = diff_engine
        self.post_generator = post_generator
        self.ws_manager = ws_manager
        self.telegram_publisher = telegram_publisher or TelegramPublisher()
        self.poll_interval = poll_interval_seconds

        # match_id -> Match object with coverage profile
        self.monitored_matches: Dict[str, Match] = {}
        self.generated_posts: List[GeneratedPost] = []
        self.all_events_history: List[DomainEvent] = []
        
        # Night Shift Session state
        self.night_shift = NightShiftConfig()

        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Load persisted desk state on cold start
        self._load_persisted_state()

    def _get_state_file_paths(self) -> List[Path]:
        paths = []
        paths.append(Path("/tmp/desk_state.json"))
        base_dir = Path(__file__).resolve().parent.parent.parent
        paths.append(base_dir / "data" / "desk_state.json")
        return paths

    def _load_persisted_state(self):
        """Restore active monitored matches and Night Shift config across serverless cold starts."""
        for path in self._get_state_file_paths():
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    if "night_shift" in data and isinstance(data["night_shift"], dict):
                        self.night_shift = NightShiftConfig.model_validate(data["night_shift"])

                    if "tracked_matches" in data and isinstance(data["tracked_matches"], dict):
                        for match_id, m_dict in data["tracked_matches"].items():
                            self.monitored_matches[match_id] = Match.model_validate(m_dict)

                    logger.info(f"Loaded persistent desk state from {path} with {len(self.monitored_matches)} tracked matches (Night Shift active: {self.night_shift.active}).")
                    return
                except Exception as e:
                    logger.error(f"Failed to load desk state from {path}: {e}")

    def _save_persisted_state(self):
        """Persist monitored matches and Night Shift status to disk."""
        try:
            state_dict = {
                "night_shift": self.night_shift.model_dump(mode="json"),
                "tracked_matches": {
                    mid: m.model_dump(mode="json") for mid, m in self.monitored_matches.items()
                }
            }
            tmp_path = Path("/tmp/desk_state.json")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state_dict, f, indent=2, ensure_ascii=False)

            base_dir = Path(__file__).resolve().parent.parent.parent
            data_path = base_dir / "data" / "desk_state.json"
            try:
                data_path.parent.mkdir(parents=True, exist_ok=True)
                with open(data_path, "w", encoding="utf-8") as f:
                    json.dump(state_dict, f, indent=2, ensure_ascii=False)
            except OSError:
                pass  # Ignore read-only errors on serverless environments
        except Exception as e:
            logger.error(f"Failed to persist desk state: {e}")

    def add_match(
        self,
        match: Match,
        coverage: CoverageProfile = CoverageProfile.STANDARD,
        auto_generate: bool = True,
        auto_publish: bool = False,
        lang: Language = Language.BANGLA
    ):
        """Add or update a match in the active monitor session with specific coverage profile."""
        match.coverage = coverage
        match.auto_generate = auto_generate
        match.auto_publish = auto_publish
        match.language = lang
        self.monitored_matches[match.id] = match
        if match.id not in self.night_shift.active_match_ids:
            self.night_shift.active_match_ids.append(match.id)
        self._save_persisted_state()
        logger.info(f"🌙 [Monitor Session] Added '{match.home_team.name} vs {match.away_team.name}' (Coverage: {coverage.value}, AutoPub: {auto_publish})")

    def remove_match(self, match_id: str):
        """Remove a match from monitoring."""
        if match_id in self.monitored_matches:
            del self.monitored_matches[match_id]
        if match_id in self.night_shift.active_match_ids:
            self.night_shift.active_match_ids.remove(match_id)
        self._save_persisted_state()
        logger.info(f"Removed match {match_id} from monitor list.")

    def start_night_shift(self, default_coverage: CoverageProfile = CoverageProfile.STANDARD, auto_publish: bool = False):
        """Start the automated Night Shift mode."""
        self.night_shift.active = True
        self.night_shift.started_at = datetime.now(timezone.utc)
        self.night_shift.default_coverage = default_coverage
        self.night_shift.default_auto_publish = auto_publish
        self._save_persisted_state()
        logger.info("🌙 [Night Shift ACTIVATED] Overnight automated newsroom desk is now running.")

    def stop_night_shift(self):
        """Stop Night Shift mode."""
        self.night_shift.active = False
        self._save_persisted_state()
        logger.info("🌙 [Night Shift DEACTIVATED].")

    async def start(self):
        """Start the background async polling loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("MatchMonitor background polling loop started.")

    async def stop(self):
        """Stop the background polling loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("MatchMonitor background loop stopped.")

    async def _poll_loop(self):
        while self._running:
            try:
                await self.poll_once()
            except Exception as e:
                logger.error(f"Error during poll tick: {e}", exc_info=True)
            await asyncio.sleep(self.poll_interval)

    async def poll_once(self) -> List[GeneratedPost]:
        """Perform a single polling cycle across all monitored matches."""
        new_posts_created: List[GeneratedPost] = []

        if not self.monitored_matches:
            return []

        for match_id, match in list(self.monitored_matches.items()):
            # Fetch latest match state
            live_match = await self.provider.get_match_by_id(match_id)
            if not live_match:
                continue

            # Preserve coverage settings
            live_match.coverage = match.coverage
            live_match.auto_generate = match.auto_generate
            live_match.auto_publish = match.auto_publish
            live_match.language = match.language
            live_match.voice_style = match.voice_style
            self.monitored_matches[match_id] = live_match

            # Fetch chronological incidents
            raw_events = await self.provider.get_match_events(match_id)

            # If match is finished, ensure a full-time event is processed
            if live_match.status == MatchStatus.FINISHED:
                has_ft = any(ev.event_type in (DomainEventType.PERIOD_FULL_TIME, DomainEventType.MATCH_ENDED) for ev in raw_events)
                if not has_ft:
                    ft_event = DomainEvent(
                        event_id=f"evt_{match_id}_fulltime",
                        match_id=match_id,
                        event_type=DomainEventType.PERIOD_FULL_TIME,
                        minute=90,
                        home_score=live_match.score.home,
                        away_score=live_match.score.away,
                        description="Full-Time reached",
                        raw_metadata={}
                    )
                    raw_events.append(ft_event)

            # Filter only net-new events via DifferenceEngine
            new_events = self.diff_engine.extract_new_events(live_match, raw_events)

            for event in new_events:
                self.all_events_history.append(event)

                # Broadcast live event over WebSocket
                await self.ws_manager.broadcast("match_event", {
                    "event": event.model_dump(mode="json"),
                    "match": live_match.model_dump(mode="json")
                })

                # Check Event Importance against Match Coverage Profile
                should_post, importance = EventImportanceEngine.should_generate_post(event, live_match)

                if should_post and live_match.auto_generate:
                    # Generate Pavilion Newsroom Post with full match context
                    post = await self.post_generator.generate_post(
                        event=event,
                        match=live_match,
                        importance=importance,
                        lang=live_match.language,
                        style=live_match.voice_style,
                        all_match_events=raw_events
                    )

                    # If auto_publish is enabled, mark directly as published
                    if live_match.auto_publish:
                        post.status = PostStatus.PUBLISHED
                        post.published_at = datetime.now(timezone.utc)
                        logger.info(f"🚀 [AUTO-PUBLISHED] Post {post.post_id}: {post.headline}")
                        
                        # Automated Telegram Dispatch
                        if self.telegram_publisher and self.telegram_publisher.is_configured:
                            try:
                                asyncio.create_task(self.telegram_publisher.send_post(post))
                            except Exception as te:
                                logger.error(f"Error dispatching to Telegram: {te}")

                    self.generated_posts.append(post)
                    new_posts_created.append(post)

                    # Broadcast newly created post over WebSocket
                    await self.ws_manager.broadcast("post_created", {
                        "post": post.model_dump(mode="json"),
                        "event": event.model_dump(mode="json"),
                        "match": live_match.model_dump(mode="json")
                    })

        return new_posts_created
