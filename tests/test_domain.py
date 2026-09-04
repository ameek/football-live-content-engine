import pytest
from src.domain.events import DomainEvent, DomainEventType
from src.domain.models import Match, Team, Score, MatchStatus
from src.domain.rules import ContentRule


def test_domain_event_immutability():
    event = DomainEvent(
        event_id="evt_123",
        match_id="match_456",
        event_type=DomainEventType.GOAL,
        minute=34,
        team_name="Arsenal",
        player_name="Bukayo Saka",
        home_score=1,
        away_score=0,
        description="Goal scored by Bukayo Saka",
        is_home_team=True
    )
    assert event.event_id == "evt_123"
    assert event.minute == 34
    assert event.home_score == 1

    # Verify frozen/immutable
    with pytest.raises(Exception):
        event.minute = 35


def test_content_rule_matching():
    rule = ContentRule(
        id="goal_rule",
        name="Goals Only in Premier League",
        event_types=[DomainEventType.GOAL, DomainEventType.RED_CARD],
        competitions=["Premier League"]
    )

    goal_event = DomainEvent(
        event_id="evt_1",
        match_id="m1",
        event_type=DomainEventType.GOAL,
        minute=20,
        home_score=1,
        away_score=0
    )

    yellow_card_event = DomainEvent(
        event_id="evt_2",
        match_id="m1",
        event_type=DomainEventType.YELLOW_CARD,
        minute=25
    )

    assert rule.matches(goal_event, "English Premier League") is True
    assert rule.matches(goal_event, "LaLiga") is False
    assert rule.matches(yellow_card_event, "English Premier League") is False
