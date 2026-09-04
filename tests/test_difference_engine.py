from src.engine.difference_engine import DifferenceEngine
from src.domain.events import DomainEvent, DomainEventType
from src.domain.models import Match, Team


def test_difference_engine_deduplication():
    engine = DifferenceEngine()
    match = Match(
        id="match_1",
        tournament_name="Premier League",
        home_team=Team(name="Arsenal"),
        away_team=Team(name="Chelsea")
    )

    ev1 = DomainEvent(event_id="e1", match_id="match_1", event_type=DomainEventType.GOAL, minute=10)
    ev2 = DomainEvent(event_id="e2", match_id="match_1", event_type=DomainEventType.YELLOW_CARD, minute=20)

    # First poll: both are new
    new_events_1 = engine.extract_new_events(match, [ev1, ev2])
    assert len(new_events_1) == 2

    # Second poll with same events: 0 new
    new_events_2 = engine.extract_new_events(match, [ev1, ev2])
    assert len(new_events_2) == 0

    # Third poll with 1 new event: returns only the new one
    ev3 = DomainEvent(event_id="e3", match_id="match_1", event_type=DomainEventType.RED_CARD, minute=35)
    new_events_3 = engine.extract_new_events(match, [ev1, ev2, ev3])
    assert len(new_events_3) == 1
    assert new_events_3[0].event_id == "e3"
