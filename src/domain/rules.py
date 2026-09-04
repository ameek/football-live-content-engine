from typing import List, Optional
from pydantic import BaseModel, Field
from src.domain.events import DomainEvent, DomainEventType


class ContentRule(BaseModel):
    """User-configured rule specifying which events trigger post generation."""
    id: str
    name: str
    enabled: bool = True
    event_types: List[DomainEventType] = Field(
        default_factory=lambda: [
            DomainEventType.GOAL,
            DomainEventType.RED_CARD,
            DomainEventType.YELLOW_RED_CARD,
            DomainEventType.VAR_OVERTURN,
            DomainEventType.PERIOD_HALF_TIME,
            DomainEventType.PERIOD_FULL_TIME,
        ]
    )
    competitions: Optional[List[str]] = None  # None = all competitions
    teams: Optional[List[str]] = None         # None = all teams
    min_minute: Optional[int] = None
    max_minute: Optional[int] = None
    require_human_review: bool = True

    def matches(self, event: DomainEvent, competition_name: str = "") -> bool:
        """Evaluate if a domain event satisfies this rule's predicates."""
        if not self.enabled:
            return False

        if event.event_type not in self.event_types:
            return False

        if self.competitions and competition_name:
            if not any(c.lower() in competition_name.lower() for c in self.competitions):
                return False

        if self.teams and event.team_name:
            if not any(t.lower() in event.team_name.lower() for t in self.teams):
                return False

        if self.min_minute is not None and event.minute < self.min_minute:
            return False

        if self.max_minute is not None and event.minute > self.max_minute:
            return False

        return True
