import logging
from typing import Tuple, List, Dict
from pydantic import BaseModel, Field

from src.domain.events import DomainEvent, DomainEventType
from src.domain.models import CoverageProfile, EventImportance, Match, Language, NewsVoiceStyle

logger = logging.getLogger(__name__)


class CoverageSettings(BaseModel):
    """Configurable event mapping for each coverage intensity level."""
    full_events: List[DomainEventType] = Field(
        default_factory=lambda: [
            DomainEventType.GOAL,
            DomainEventType.OWN_GOAL,
            DomainEventType.PENALTY_GOAL,
            DomainEventType.PENALTY_MISSED,
            DomainEventType.RED_CARD,
            DomainEventType.YELLOW_RED_CARD,
            DomainEventType.YELLOW_CARD,
            DomainEventType.VAR_OVERTURN,
            DomainEventType.VAR_DECISION,
            DomainEventType.SUBSTITUTION,
            DomainEventType.PERIOD_HALF_TIME,
            DomainEventType.PERIOD_FULL_TIME,
            DomainEventType.MATCH_ENDED
        ]
    )
    standard_events: List[DomainEventType] = Field(
        default_factory=lambda: [
            DomainEventType.GOAL,
            DomainEventType.OWN_GOAL,
            DomainEventType.PENALTY_GOAL,
            DomainEventType.RED_CARD,
            DomainEventType.YELLOW_RED_CARD,
            DomainEventType.VAR_OVERTURN,
            DomainEventType.SUBSTITUTION,
            DomainEventType.PERIOD_HALF_TIME,
            DomainEventType.PERIOD_FULL_TIME,
            DomainEventType.MATCH_ENDED
        ]
    )
    result_only_events: List[DomainEventType] = Field(
        default_factory=lambda: [
            DomainEventType.GOAL,
            DomainEventType.OWN_GOAL,
            DomainEventType.PENALTY_GOAL,
            DomainEventType.PERIOD_HALF_TIME,
            DomainEventType.PERIOD_FULL_TIME,
            DomainEventType.MATCH_ENDED
        ]
    )
    default_language: Language = Language.BANGLA
    default_voice_style: NewsVoiceStyle = NewsVoiceStyle.BREAKING
    default_auto_publish: bool = False


# Global active coverage settings instance
global_coverage_settings = CoverageSettings()


class EventImportanceEngine:
    """
    Event Importance & Anti-Spam Classification Engine with customizable rules.
    """

    @staticmethod
    def evaluate_importance(event: DomainEvent) -> EventImportance:
        """Categorize an incoming domain event into its baseline importance level."""
        t = event.event_type

        if t in (
            DomainEventType.GOAL,
            DomainEventType.OWN_GOAL,
            DomainEventType.PENALTY_GOAL,
            DomainEventType.RED_CARD,
            DomainEventType.YELLOW_RED_CARD,
            DomainEventType.VAR_OVERTURN,
            DomainEventType.PERIOD_HALF_TIME,
            DomainEventType.PERIOD_FULL_TIME,
            DomainEventType.MATCH_ENDED
        ):
            return EventImportance.MUST_POST

        if t in (
            DomainEventType.PENALTY_MISSED,
            DomainEventType.SUBSTITUTION,
            DomainEventType.YELLOW_CARD,
            DomainEventType.VAR_DECISION,
            DomainEventType.PERIOD_EXTRA_TIME
        ):
            return EventImportance.MAYBE_POST

        return EventImportance.IGNORE

    @classmethod
    def should_generate_post(
        cls,
        event: DomainEvent,
        match: Match,
        settings: CoverageSettings = None
    ) -> Tuple[bool, EventImportance]:
        """
        Determine if an event warrants generating a post based on active Coverage Settings.
        """
        cfg = settings or global_coverage_settings
        importance = cls.evaluate_importance(event)
        coverage = match.coverage

        if coverage == CoverageProfile.RESULT_ONLY:
            if event.event_type in cfg.result_only_events:
                return True, EventImportance.MUST_POST
            return False, EventImportance.IGNORE

        elif coverage == CoverageProfile.STANDARD:
            if event.event_type in cfg.standard_events:
                return True, importance
            return False, EventImportance.IGNORE

        elif coverage == CoverageProfile.FULL:
            if event.event_type in cfg.full_events:
                return True, importance
            return False, EventImportance.IGNORE

        return False, EventImportance.IGNORE
