from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from src.domain.models import Match
from src.domain.events import DomainEvent


class FootballDataProvider(ABC):
    """Abstract interface for all football data providers (Adapter Pattern)."""

    @abstractmethod
    async def get_live_matches(self) -> List[Match]:
        """Fetch all currently live matches."""
        pass

    @abstractmethod
    async def get_scheduled_matches(self, date_str: Optional[str] = None) -> List[Match]:
        """Fetch scheduled/upcoming matches for a given date (YYYY-MM-DD)."""
        pass

    @abstractmethod
    async def get_match_by_id(self, match_id: str) -> Optional[Match]:
        """Fetch detailed state for a specific match."""
        pass

    @abstractmethod
    async def get_match_events(self, match_id: str) -> List[DomainEvent]:
        """Fetch all chronological incidents/events for a match."""
        pass
