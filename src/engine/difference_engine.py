import logging
from typing import List, Set, Dict
from src.domain.events import DomainEvent
from src.domain.models import Match

logger = logging.getLogger(__name__)


class DifferenceEngine:
    """
    Event Deduplicator & State Change Detector.
    Tracks seen events per match and emits only net-new domain events to prevent duplicate posts.
    """

    def __init__(self):
        # match_id -> set of event_ids seen
        self._seen_events: Dict[str, Set[str]] = {}

    def extract_new_events(self, match: Match, all_events: List[DomainEvent]) -> List[DomainEvent]:
        """Filter out already processed events and return only newly occurred events."""
        match_id = match.id
        if match_id not in self._seen_events:
            self._seen_events[match_id] = set()

        new_events: List[DomainEvent] = []
        for ev in all_events:
            if ev.event_id not in self._seen_events[match_id]:
                self._seen_events[match_id].add(ev.event_id)
                new_events.append(ev)
                logger.info(f"⚡ [New Event Detected] Match {match_id}: {ev.event_type.value} at {ev.minute}' - {ev.description}")

        return new_events

    def reset_match(self, match_id: str):
        """Clear memory cache for a specific match."""
        if match_id in self._seen_events:
            del self._seen_events[match_id]
