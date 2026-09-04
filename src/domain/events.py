from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict


class DomainEventType(str, Enum):
    MATCH_STARTED = "MATCH_STARTED"
    GOAL = "GOAL"
    OWN_GOAL = "OWN_GOAL"
    PENALTY_GOAL = "PENALTY_GOAL"
    PENALTY_MISSED = "PENALTY_MISSED"
    YELLOW_CARD = "YELLOW_CARD"
    RED_CARD = "RED_CARD"
    YELLOW_RED_CARD = "YELLOW_RED_CARD"
    SUBSTITUTION = "SUBSTITUTION"
    VAR_DECISION = "VAR_DECISION"
    VAR_OVERTURN = "VAR_OVERTURN"
    PERIOD_HALF_TIME = "PERIOD_HALF_TIME"
    PERIOD_FULL_TIME = "PERIOD_FULL_TIME"
    PERIOD_EXTRA_TIME = "PERIOD_EXTRA_TIME"
    MATCH_ENDED = "MATCH_ENDED"


class DomainEvent(BaseModel):
    """Immutable base domain event emitted by the ingestion pipeline."""
    model_config = ConfigDict(frozen=True)

    event_id: str
    match_id: str
    event_type: DomainEventType
    minute: int
    extra_minute: Optional[int] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    team_name: Optional[str] = None
    player_name: Optional[str] = None
    secondary_player_name: Optional[str] = None  # Assist or Sub Out
    home_score: int = 0
    away_score: int = 0
    description: str = ""
    is_home_team: Optional[bool] = None
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)
