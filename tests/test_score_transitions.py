import pytest
from src.engine.commentary_enrichment import CommentaryEnricher
from src.engine.post_generator import PostGenerator
from src.domain.events import DomainEvent, DomainEventType
from src.domain.models import Match, Team, Score, MatchStatus, Language, NewsVoiceStyle


@pytest.mark.parametrize("h_score,a_score,is_home,expected_headline_action,expected_verb", [
    # 0–0 -> 1–0 : এগিয়ে গেল
    (1, 0, True, "এগিয়ে গেল", "এগিয়ে নিলেন"),
    # 1–0 -> 2–0 : ব্যবধান দ্বিগুণ করল
    (2, 0, True, "ব্যবধান দ্বিগুণ করল", "ব্যবধান দ্বিগুণ করলেন"),
    # 2–0 -> 3–0 : ব্যবধান আরও বাড়াল
    (3, 0, True, "ব্যবধান আরও বাড়াল", "ব্যবধান আরও বাড়ালেন"),
    # 2–0 -> 2–1 : ব্যবধান কমাল (Away team scores: 0-2 -> 1-2)
    (2, 1, False, "ব্যবধান কমাল", "ব্যবধান কমালেন"),
    # 1–0 -> 1–1 : সমতায় ফিরল (Away team scores to equalize)
    (1, 1, False, "সমতায় ফিরল", "সমতায় ফেরালেন"),
    # 1–1 -> 2–1 : আবার এগিয়ে গেল (Home team scores)
    (2, 1, True, "আবার এগিয়ে গেল", "আবার এগিয়ে নিলেন"),
    # 2–2 -> 3–2 : আবারও এগিয়ে গেল (Home team scores)
    (3, 2, True, "আবারও এগিয়ে গেল", "আবারও এগিয়ে নিলেন"),
])
def test_momentum_transitions(h_score, a_score, is_home, expected_headline_action, expected_verb):
    res = CommentaryEnricher.calculate_momentum(h_score, a_score, is_home)
    assert res["headline_bn"] == expected_headline_action
    assert res["verb_bn"] == expected_verb


@pytest.mark.asyncio
async def test_post_generator_with_score_transitions():
    generator = PostGenerator()
    match = Match(
        id="match_test_transitions",
        tournament_name="MLS Next Pro",
        tournament_category="USA",
        home_team=Team(name="Crown Legacy FC"),
        away_team=Team(name="Chicago Fire FC II"),
        status=MatchStatus.IN_PROGRESS,
        status_detail="1st Half",
        minute=34,
        score=Score(home=1, away=0)
    )

    # 1. 0-0 -> 1-0 Crown Legacy FC scores
    evt1 = DomainEvent(
        event_id="evt_1",
        match_id="match_test_transitions",
        event_type=DomainEventType.GOAL,
        minute=34,
        team_name="Crown Legacy FC",
        player_name="Andrew Johnson",
        secondary_player_name="Nathan Richmond",
        home_score=1,
        away_score=0,
        is_home_team=True,
        description="Goal scored"
    )

    # Test deterministic template generator directly
    h1, c1 = generator._generate_bangla(evt1, match, NewsVoiceStyle.BREAKING, {"headline_action_bn": "এগিয়ে গেল", "lead_momentum_bn": "এগিয়ে নিলেন"})
    assert "এগিয়ে গেল Crown Legacy FC" in h1
    assert "এগিয়ে নিলেন" in c1

    # 2. 1-0 -> 1-1 Chicago Fire FC II equalizes
    evt2 = DomainEvent(
        event_id="evt_2",
        match_id="match_test_transitions",
        event_type=DomainEventType.GOAL,
        minute=50,
        team_name="Chicago Fire FC II",
        player_name="David Poreba",
        home_score=1,
        away_score=1,
        is_home_team=False,
        description="Goal scored"
    )
    h2, c2 = generator._generate_bangla(evt2, match, NewsVoiceStyle.BREAKING, {"headline_action_bn": "সমতায় ফিরল", "lead_momentum_bn": "সমতায় ফেরালেন"})
    assert "সমতায় ফিরল Chicago Fire FC II" in h2
    assert "সমতায় ফেরালেন" in c2

    # 3. 1-1 -> 2-1 Crown Legacy FC takes lead again
    evt3 = DomainEvent(
        event_id="evt_3",
        match_id="match_test_transitions",
        event_type=DomainEventType.GOAL,
        minute=75,
        team_name="Crown Legacy FC",
        player_name="Barzee Blama",
        home_score=2,
        away_score=1,
        is_home_team=True,
        description="Goal scored"
    )
    h3, c3 = generator._generate_bangla(evt3, match, NewsVoiceStyle.BREAKING, {"headline_action_bn": "আবারও এগিয়ে গেল", "lead_momentum_bn": "আবারও এগিয়ে নিলেন"})
    assert "আবারও এগিয়ে গেল Crown Legacy FC" in h3
    assert "আবারও এগিয়ে নিলেন" in c3

    # Also test full async generate_post with Gemini/local enrichment
    post1 = await generator.generate_post(evt1, match, lang=Language.BANGLA)
    assert post1.headline is not None and len(post1.headline) > 5
    assert post1.content is not None
