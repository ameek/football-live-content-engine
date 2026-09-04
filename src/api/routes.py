from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from pydantic import BaseModel

from src.domain.models import (
    Match, GeneratedPost, PostStatus, CoverageProfile,
    Language, NewsVoiceStyle, NightShiftConfig, MatchStatus
)
from src.domain.events import DomainEvent, DomainEventType
from src.engine.monitor import MatchMonitor
from src.engine.importance_engine import CoverageSettings, global_coverage_settings
from src.engine.post_generator import PostGenerator

router = APIRouter()


class ConfigureMatchRequest(BaseModel):
    match_id: str
    tracked: bool = True
    coverage: CoverageProfile = CoverageProfile.STANDARD
    auto_publish: bool = True
    language: Language = Language.BANGLA
    voice_style: NewsVoiceStyle = NewsVoiceStyle.BREAKING


class UpdatePostRequest(BaseModel):
    status: Optional[PostStatus] = None
    headline: Optional[str] = None
    content: Optional[str] = None
    rejection_reason: Optional[str] = None


def get_monitor() -> MatchMonitor:
    from src.api.app import app_state
    return app_state.monitor


@router.get("/matches/live", response_model=List[Match])
async def get_live_matches(league: Optional[str] = None, monitor: MatchMonitor = Depends(get_monitor)):
    """Retrieve all live matches worldwide."""
    matches = await monitor.provider.get_live_matches()

    for m in matches:
        if m.id in monitor.monitored_matches:
            tracked = monitor.monitored_matches[m.id]
            m.auto_generate = True
            m.coverage = tracked.coverage
            m.auto_publish = tracked.auto_publish
            m.language = tracked.language
            m.voice_style = tracked.voice_style
        else:
            m.auto_generate = False
            m.auto_publish = False

    if league and league != "All":
        matches = [m for m in matches if league.lower() in m.tournament_name.lower()]
    return matches


@router.get("/matches/scheduled", response_model=List[Match])
async def get_scheduled_matches(date_str: Optional[str] = None, league: Optional[str] = None, monitor: MatchMonitor = Depends(get_monitor)):
    """Retrieve scheduled / calendar matches for a specific date (YYYY-MM-DD)."""
    # Fetch live matches and scheduled fixtures
    live_matches = await monitor.provider.get_live_matches()
    scheduled = await monitor.provider.get_scheduled_matches(date_str)
    
    combined = scheduled if scheduled else live_matches

    # Mark tracking status
    for m in combined:
        if m.id in monitor.monitored_matches:
            tracked = monitor.monitored_matches[m.id]
            m.auto_generate = True
            m.coverage = tracked.coverage
            m.auto_publish = tracked.auto_publish
            m.language = tracked.language
        else:
            m.auto_generate = False
            m.auto_publish = False

    if league and league != "All":
        combined = [m for m in combined if league.lower() in m.tournament_name.lower()]
    return combined


@router.get("/matches/leagues", response_model=List[str])
async def get_active_leagues(monitor: MatchMonitor = Depends(get_monitor)):
    """Get list of distinct tournament/league names for active matches."""
    matches = await monitor.provider.get_live_matches()
    leagues = sorted(list(set(m.tournament_name for m in matches if m.tournament_name)))
    return ["All"] + leagues


@router.post("/matches/configure")
async def configure_match(req: ConfigureMatchRequest, monitor: MatchMonitor = Depends(get_monitor)):
    """Explicitly toggle tracking and coverage profile for a specific match."""
    import asyncio
    if not req.tracked:
        removed = monitor.monitored_matches.get(req.match_id)
        monitor.remove_match(req.match_id)
        if removed and monitor.telegram_publisher and monitor.telegram_publisher.is_configured:
            asyncio.create_task(monitor.telegram_publisher.send_tracking_alert(removed, False))
        return {"status": "untracked", "match_id": req.match_id}

    match = await monitor.provider.get_match_by_id(req.match_id)
    if not match:
        scheduled = await monitor.provider.get_scheduled_matches()
        for s in scheduled:
            if s.id == req.match_id:
                match = s
                break

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    monitor.add_match(
        match=match,
        coverage=req.coverage,
        auto_generate=True,
        auto_publish=req.auto_publish,
        lang=req.language
    )
    tracked_match = monitor.monitored_matches[req.match_id]
    
    # Send instant Telegram tracking confirmation
    if monitor.telegram_publisher and monitor.telegram_publisher.is_configured:
        asyncio.create_task(monitor.telegram_publisher.send_tracking_alert(tracked_match, True))

    return {"status": "tracked", "match": tracked_match}


@router.post("/monitor/poll-now")
async def force_poll_now(monitor: MatchMonitor = Depends(get_monitor)):
    """Force an immediate polling tick of all tracked matches."""
    new_posts = await monitor.poll_once()
    return {
        "status": "success",
        "monitored_matches_count": len(monitor.monitored_matches),
        "new_posts_count": len(new_posts),
        "total_posts_count": len(monitor.generated_posts),
        "total_events_count": len(monitor.all_events_history)
    }


@router.post("/nightshift/start")
async def start_night_shift(monitor: MatchMonitor = Depends(get_monitor)):
    """Arm the overnight autonomous monitoring session."""
    import asyncio
    monitor.start_night_shift()

    if monitor.telegram_publisher and monitor.telegram_publisher.is_configured:
        matches_info = [
            {"name": f"{m.home_team.name} vs {m.away_team.name}", "cov": m.coverage.value if hasattr(m.coverage, "value") else str(m.coverage)}
            for m in monitor.monitored_matches.values()
        ]
        asyncio.create_task(monitor.telegram_publisher.send_nightshift_alert(True, matches_info))

    return {"status": "night_shift_armed", "config": monitor.night_shift}


@router.post("/nightshift/stop")
async def stop_night_shift(monitor: MatchMonitor = Depends(get_monitor)):
    """Disarm overnight night-shift monitoring."""
    import asyncio
    monitor.stop_night_shift()

    if monitor.telegram_publisher and monitor.telegram_publisher.is_configured:
        asyncio.create_task(monitor.telegram_publisher.send_nightshift_alert(False, []))

    return {"status": "night_shift_disarmed", "config": monitor.night_shift}


@router.get("/nightshift/status", response_model=NightShiftConfig)
async def get_night_shift_status(monitor: MatchMonitor = Depends(get_monitor)):
    """Get active night shift session state."""
    return monitor.night_shift


@router.get("/settings/coverage", response_model=CoverageSettings)
async def get_coverage_settings():
    """Retrieve custom coverage levels configuration."""
    return global_coverage_settings


@router.post("/settings/coverage", response_model=CoverageSettings)
async def save_coverage_settings(settings: CoverageSettings):
    """Update custom event triggers for Full, Standard, and Result Only coverage levels."""
    global global_coverage_settings
    global_coverage_settings.full_events = settings.full_events
    global_coverage_settings.standard_events = settings.standard_events
    global_coverage_settings.result_only_events = settings.result_only_events
    global_coverage_settings.default_language = settings.default_language
    global_coverage_settings.default_voice_style = settings.default_voice_style
    global_coverage_settings.default_auto_publish = settings.default_auto_publish
    return global_coverage_settings


@router.get("/posts", response_model=List[GeneratedPost])
async def get_generated_posts(status: Optional[PostStatus] = None, monitor: MatchMonitor = Depends(get_monitor)):
    """Retrieve generated sports posts."""
    if status:
        return [p for p in monitor.generated_posts if p.status == status]
    return monitor.generated_posts


class TelegramConfigRequest(BaseModel):
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None


@router.get("/settings/telegram")
async def get_telegram_settings(monitor: MatchMonitor = Depends(get_monitor)):
    """Get active Telegram configuration."""
    return {
        "is_configured": monitor.telegram_publisher.is_configured,
        "chat_id": monitor.telegram_publisher.chat_id,
        "has_token": bool(monitor.telegram_publisher.bot_token)
    }


@router.post("/settings/telegram")
async def save_telegram_settings(req: TelegramConfigRequest, monitor: MatchMonitor = Depends(get_monitor)):
    """Save or update Telegram bot credentials."""
    if req.bot_token:
        monitor.telegram_publisher.bot_token = req.bot_token
    if req.chat_id:
        monitor.telegram_publisher.chat_id = req.chat_id
    return {
        "status": "success",
        "is_configured": monitor.telegram_publisher.is_configured,
        "chat_id": monitor.telegram_publisher.chat_id
    }


@router.post("/settings/telegram/test")
async def test_telegram_connection(monitor: MatchMonitor = Depends(get_monitor)):
    """Test Telegram bot connection and channel posting."""
    return await monitor.telegram_publisher.test_connection()


@router.patch("/posts/{post_id}")
async def update_post(post_id: str, req: UpdatePostRequest, monitor: MatchMonitor = Depends(get_monitor)):
    """Edit, Approve, Reject, or Publish a generated post."""
    for post in monitor.generated_posts:
        if post.post_id == post_id:
            if req.status:
                post.status = req.status
                if req.status == PostStatus.PUBLISHED:
                    post.published_at = datetime.now(timezone.utc)
                    if monitor.telegram_publisher and monitor.telegram_publisher.is_configured:
                        import asyncio
                        asyncio.create_task(monitor.telegram_publisher.send_post(post))
            if req.headline:
                post.headline = req.headline
            if req.content:
                post.content = req.content
            if req.rejection_reason:
                post.rejection_reason = req.rejection_reason
            return post
    raise HTTPException(status_code=404, detail="Post not found")


@router.get("/logos/team/{team_id}")
async def get_team_logo(team_id: str):
    """Serve cached team logo locally from disk or download once."""
    from fastapi.responses import Response
    from src.storage.image_cache import ImageCacheService
    img_bytes = await ImageCacheService.get_or_download_team_logo(team_id)
    if not img_bytes:
        raise HTTPException(status_code=404, detail="Logo not found")
    return Response(content=img_bytes, media_type="image/png", headers={"Cache-Control": "public, max-age=604800"})


@router.get("/logos/tournament/{tournament_id}")
async def get_tournament_logo(tournament_id: str):
    """Serve cached tournament logo locally from disk or download once."""
    from fastapi.responses import Response
    from src.storage.image_cache import ImageCacheService
    img_bytes = await ImageCacheService.get_or_download_tournament_logo(tournament_id)
    if not img_bytes:
        raise HTTPException(status_code=404, detail="Logo not found")
    return Response(content=img_bytes, media_type="image/png", headers={"Cache-Control": "public, max-age=604800"})


@router.get("/graphics/goal/{match_id}")
async def get_goal_card(match_id: str, minute: int = 34, player: str = "Goalscorer", assist: Optional[str] = None, monitor: MatchMonitor = Depends(get_monitor)):
    """Render and serve 1080x1080 Goal Graphic Card."""
    from fastapi.responses import Response
    from src.engine.graphics_generator import GraphicsEngine
    match = await monitor.provider.get_match_by_id(match_id)
    if not match:
        scheduled = await monitor.provider.get_scheduled_matches()
        for s in scheduled:
            if s.id == match_id:
                match = s
                break
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    evt = DomainEvent(
        event_id=f"evt_{match_id}_card",
        match_id=match_id,
        event_type=DomainEventType.GOAL,
        minute=minute,
        player_name=player,
        secondary_player_name=assist,
        home_score=match.score.home or 1,
        away_score=match.score.away,
        is_home_team=True,
        description="Goal"
    )
    img_bytes = await GraphicsEngine.render_goal_card(match, evt, lang=match.language)
    return Response(content=img_bytes, media_type="image/png")


@router.get("/graphics/fulltime/{match_id}")
async def get_fulltime_card(match_id: str, monitor: MatchMonitor = Depends(get_monitor)):
    """Render and serve 1080x1080 Full-Time Scorecard."""
    from fastapi.responses import Response
    from src.engine.graphics_generator import GraphicsEngine
    match = await monitor.provider.get_match_by_id(match_id)
    if not match:
        scheduled = await monitor.provider.get_scheduled_matches()
        for s in scheduled:
            if s.id == match_id:
                match = s
                break
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    events = await monitor.provider.get_match_events(match_id)
    stats = await monitor.provider.get_match_statistics(match_id)
    img_bytes = await GraphicsEngine.render_fulltime_card(match, events, stats, lang=match.language)
    return Response(content=img_bytes, media_type="image/png")


@router.get("/graphics/lineup/{match_id}")
async def get_lineup_card(match_id: str, monitor: MatchMonitor = Depends(get_monitor)):
    """Render and serve 1080x1350 Starting XI Tactical Pitch Board."""
    from fastapi.responses import Response
    from src.engine.graphics_generator import GraphicsEngine
    match = await monitor.provider.get_match_by_id(match_id)
    if not match:
        scheduled = await monitor.provider.get_scheduled_matches()
        for s in scheduled:
            if s.id == match_id:
                match = s
                break
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    img_bytes = await GraphicsEngine.render_lineup_card(match, {}, lang=match.language)
    return Response(content=img_bytes, media_type="image/png")


@router.websocket("/ws/live-events")
async def websocket_endpoint(websocket: WebSocket, monitor: MatchMonitor = Depends(get_monitor)):
    """Real-time WebSocket event and post notification stream."""
    await monitor.ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        monitor.ws_manager.disconnect(websocket)
