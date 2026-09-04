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

    post1 = await generator.generate_post(evt1, match, lang=Language.BANGLA)
    assert "এগিয়ে গেল Crown Legacy FC" in post1.headline

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
    post2 = await generator.generate_post(evt2, match, lang=Language.BANGLA)
    assert "সমতায় ফিরল Chicago Fire FC II" in post2.headline

    # 3. 1-1 -> 2-1 Crown Legacy FC takes lead again
    evt3 = DomainEvent(
        event_id="evt_3",
        match_id="match_test_transitions",
        event_type=DomainEventType.GOAL,
        minute=75,
        team_name="Crown Legacy FC",
        player_name="Andrew Johnson",
        home_score=2,
        away_score=1,
        is_home_team=True,
        description="Goal scored"
    )
    post3 = await generator.generate_post(evt3, match, lang=Language.BANGLA)
    assert "আবার এগিয়ে গেল Crown Legacy FC" in post3.headline
