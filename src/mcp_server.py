from typing import List, Optional, Dict, Any
from fastmcp import FastMCP
from src.providers.live_feed_provider import LiveFeedProvider
from src.providers.mock_provider import MockFootballProvider
from src.domain.events import DomainEvent
from src.domain.models import Match, GeneratedPost, PostStatus
from src.engine.post_generator import PostGenerator

mcp = FastMCP(
    name="FootballLiveContentEngine",
    description="Real-Time Football Event Monitor & Social Content Generator MCP Server"
)

provider = LiveFeedProvider()
mock_provider = MockFootballProvider()
post_generator = PostGenerator()


@mcp.tool()
async def list_live_matches() -> List[Dict[str, Any]]:
    """
    Fetch all currently live football matches worldwide.
    Returns match IDs, tournament, home/away teams, current score, and minute.
    """
    matches = await provider.get_live_matches()
    return [m.model_dump(mode="json") for m in matches]


@mcp.tool()
async def get_match_events(match_id: str) -> List[Dict[str, Any]]:
    """
    Fetch all live events (goals, yellow/red cards, substitutions, VAR decisions) for a specific match ID.
    """
    events = await provider.get_match_events(match_id)
    return [e.model_dump(mode="json") for e in events]


@mcp.tool()
async def generate_post_for_event(
    match_id: str,
    event_id: str,
    platform: str = "facebook"
) -> Dict[str, Any]:
    """
    Generate an engaging AI social media post (Facebook/Twitter/Telegram) for a specific verified match event.
    """
    match = await provider.get_match_by_id(match_id)
    if not match:
        return {"error": f"Match {match_id} not found"}

    events = await provider.get_match_events(match_id)
    target_event = next((e for e in events if e.event_id == event_id), None)
    if not target_event:
        return {"error": f"Event {event_id} not found for match {match_id}"}

    post = await post_generator.generate_post(target_event, match)
    return post.model_dump(mode="json")


if __name__ == "__main__":
    mcp.run()
