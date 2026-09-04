import asyncio
from datetime import datetime
from typing import List, Optional, Dict
from src.domain.models import Match, Team, Score, MatchStatus
from src.domain.events import DomainEvent, DomainEventType
from src.providers.base import FootballDataProvider


class MockFootballProvider(FootballDataProvider):
    """
    Deterministic Mock / Simulation provider.
    Enables instant offline testing, integration tests, and live match replay simulation.
    """

    def __init__(self):
        self._matches: Dict[str, Match] = {
            "match_ars_che": Match(
                id="match_ars_che",
                tournament_name="Premier League",
                tournament_category="England",
                home_team=Team(name="Arsenal", short_name="ARS"),
                away_team=Team(name="Chelsea", short_name="CHE"),
                status=MatchStatus.IN_PROGRESS,
                status_detail="2nd Half",
                minute=67,
                score=Score(home=2, away=1)
            ),
            "match_rm_bar": Match(
                id="match_rm_bar",
                tournament_name="LaLiga",
                tournament_category="Spain",
                home_team=Team(name="Real Madrid", short_name="RMA"),
                away_team=Team(name="Barcelona", short_name="BAR"),
                status=MatchStatus.IN_PROGRESS,
                status_detail="1st Half",
                minute=34,
                score=Score(home=1, away=0)
            )
        }

        self._events: Dict[str, List[DomainEvent]] = {
            "match_ars_che": [
                DomainEvent(
                    event_id="evt_ars_1",
                    match_id="match_ars_che",
                    event_type=DomainEventType.GOAL,
                    minute=23,
                    team_name="Arsenal",
                    player_name="Gabriel Martinelli",
                    secondary_player_name="Declan Rice",
                    home_score=1,
                    away_score=0,
                    description="Goal scored by Gabriel Martinelli, assisted by Declan Rice",
                    is_home_team=True
                ),
                DomainEvent(
                    event_id="evt_che_1",
                    match_id="match_ars_che",
                    event_type=DomainEventType.GOAL,
                    minute=41,
                    team_name="Chelsea",
                    player_name="Cole Palmer",
                    home_score=1,
                    away_score=1,
                    description="Goal scored by Cole Palmer",
                    is_home_team=False
                ),
                DomainEvent(
                    event_id="evt_ars_2",
                    match_id="match_ars_che",
                    event_type=DomainEventType.GOAL,
                    minute=67,
                    team_name="Arsenal",
                    player_name="Bukayo Saka",
                    secondary_player_name="Martin Ødegaard",
                    home_score=2,
                    away_score=1,
                    description="Goal scored by Bukayo Saka, assisted by Martin Ødegaard",
                    is_home_team=True
                )
            ],
            "match_rm_bar": [
                DomainEvent(
                    event_id="evt_rm_1",
                    match_id="match_rm_bar",
                    event_type=DomainEventType.GOAL,
                    minute=18,
                    team_name="Real Madrid",
                    player_name="Jude Bellingham",
                    home_score=1,
                    away_score=0,
                    description="Goal scored by Jude Bellingham",
                    is_home_team=True
                )
            ]
        }

    async def get_live_matches(self) -> List[Match]:
        return list(self._matches.values())

    async def get_scheduled_matches(self, date_str: Optional[str] = None) -> List[Match]:
        return list(self._matches.values())

    async def get_match_by_id(self, match_id: str) -> Optional[Match]:
        return self._matches.get(match_id)

    async def get_match_events(self, match_id: str) -> List[DomainEvent]:
        return self._events.get(match_id, [])

    def add_simulation_event(self, match_id: str, event: DomainEvent):
        """Simulate an event occurring in real-time."""
        if match_id in self._events:
            self._events[match_id].append(event)
            # update score if goal
            match = self._matches.get(match_id)
            if match and event.event_type in (DomainEventType.GOAL, DomainEventType.PENALTY_GOAL):
                match.score = Score(home=event.home_score, away=event.away_score)
                match.minute = event.minute
