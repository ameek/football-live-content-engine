import pytest
from src.domain.events import DomainEvent, DomainEventType
from src.domain.models import Match, Team, Language, NewsVoiceStyle
from src.engine.post_generator import PostGenerator, to_bangla_digits


def test_bangla_digits_conversion():
    assert to_bangla_digits(67) == "৬৭"
    assert to_bangla_digits("2-1") == "২-১"
    assert to_bangla_digits("90+5") == "৯০+৫"


@pytest.mark.asyncio
async def test_pavilion_bangla_goal_generation():
    generator = PostGenerator()
    match = Match(
        id="m_rm_bar",
        tournament_name="LaLiga",
        home_team=Team(name="Real Madrid"),
        away_team=Team(name="Barcelona"),
        language=Language.BANGLA,
        voice_style=NewsVoiceStyle.BREAKING
    )
    event = DomainEvent(
        event_id="e_mbappe",
        match_id="m_rm_bar",
        event_type=DomainEventType.GOAL,
        minute=67,
        team_name="Real Madrid",
        player_name="Kylian Mbappé",
        secondary_player_name="Vinícius Júnior",
        home_score=2,
        away_score=1,
        is_home_team=True
    )

    post = await generator.generate_post(event, match)
    assert post.language == Language.BANGLA
    assert "রিয়াল মাদ্রিদ" in post.headline
    assert "৬৭" in post.content
    assert "Kylian Mbappé" in post.content
    assert "Vinícius Júnior" in post.content
    assert "২-১" in post.content
    assert "প্যাভিলিয়ন" in post.content
