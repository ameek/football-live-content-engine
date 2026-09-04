import pytest
from src.domain.events import DomainEvent, DomainEventType
from src.domain.models import Match, Team, Score, PostStatus, Language
from src.engine.post_generator import PostGenerator


@pytest.mark.asyncio
async def test_goal_post_generation():
    generator = PostGenerator()
    match = Match(
        id="m_ars_che",
        tournament_name="Premier League",
        home_team=Team(name="Arsenal"),
        away_team=Team(name="Chelsea"),
        language=Language.BANGLA
    )
    event = DomainEvent(
        event_id="e_goal",
        match_id="m_ars_che",
        event_type=DomainEventType.GOAL,
        minute=67,
        team_name="Arsenal",
        player_name="Bukayo Saka",
        secondary_player_name="Martin Ødegaard",
        home_score=2,
        away_score=1,
        is_home_team=True
    )

    post = await generator.generate_post(event, match)
    assert post.status == PostStatus.QUEUED_FOR_REVIEW
    assert "Bukayo Saka" in post.content
    assert "Martin Ødegaard" in post.content
    assert "২-১" in post.content
    assert "2–1" in post.english_translation
    assert "#Arsenal" in post.hashtags
