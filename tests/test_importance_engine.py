import pytest
from src.domain.events import DomainEvent, DomainEventType
from src.domain.models import Match, Team, CoverageProfile, EventImportance
from src.engine.importance_engine import EventImportanceEngine


def test_event_importance_classification():
    goal_ev = DomainEvent(event_id="e1", match_id="m1", event_type=DomainEventType.GOAL, minute=20)
    red_card_ev = DomainEvent(event_id="e2", match_id="m1", event_type=DomainEventType.RED_CARD, minute=45)
    yellow_card_ev = DomainEvent(event_id="e3", match_id="m1", event_type=DomainEventType.YELLOW_CARD, minute=30)
    sub_ev = DomainEvent(event_id="e4", match_id="m1", event_type=DomainEventType.SUBSTITUTION, minute=60)

    assert EventImportanceEngine.evaluate_importance(goal_ev) == EventImportance.MUST_POST
    assert EventImportanceEngine.evaluate_importance(red_card_ev) == EventImportance.MUST_POST
    assert EventImportanceEngine.evaluate_importance(yellow_card_ev) == EventImportance.MAYBE_POST
    assert EventImportanceEngine.evaluate_importance(sub_ev) == EventImportance.MAYBE_POST


def test_coverage_profile_filters():
    match_full = Match(
        id="m_full",
        tournament_name="LaLiga",
        home_team=Team(name="Real Madrid"),
        away_team=Team(name="Barcelona"),
        coverage=CoverageProfile.FULL
    )
    match_standard = Match(
        id="m_std",
        tournament_name="LaLiga",
        home_team=Team(name="Sevilla"),
        away_team=Team(name="Valencia"),
        coverage=CoverageProfile.STANDARD
    )
    match_result_only = Match(
        id="m_res",
        tournament_name="LaLiga",
        home_team=Team(name="Getafe"),
        away_team=Team(name="Mallorca"),
        coverage=CoverageProfile.RESULT_ONLY
    )

    yellow_ev = DomainEvent(event_id="e_y", match_id="m", event_type=DomainEventType.YELLOW_CARD, minute=30)
    sub_ev = DomainEvent(event_id="e_s", match_id="m", event_type=DomainEventType.SUBSTITUTION, minute=65)
    goal_ev = DomainEvent(event_id="e_g", match_id="m", event_type=DomainEventType.GOAL, minute=70)

    # Full coverage: accepts yellows, subs, goals
    assert EventImportanceEngine.should_generate_post(yellow_ev, match_full)[0] is True
    assert EventImportanceEngine.should_generate_post(sub_ev, match_full)[0] is True
    assert EventImportanceEngine.should_generate_post(goal_ev, match_full)[0] is True

    # Standard coverage: skips routine yellow, accepts sub and goal
    assert EventImportanceEngine.should_generate_post(yellow_ev, match_standard)[0] is False
    assert EventImportanceEngine.should_generate_post(sub_ev, match_standard)[0] is True
    assert EventImportanceEngine.should_generate_post(goal_ev, match_standard)[0] is True

    # Result only: skips yellow and sub, accepts goal only
    assert EventImportanceEngine.should_generate_post(yellow_ev, match_result_only)[0] is False
    assert EventImportanceEngine.should_generate_post(sub_ev, match_result_only)[0] is False
    assert EventImportanceEngine.should_generate_post(goal_ev, match_result_only)[0] is True
