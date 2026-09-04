import pytest
from src.domain.models import Match, Team, Score, Language
from src.domain.events import DomainEvent, DomainEventType
from src.engine.graphics_generator import GraphicsEngine


@pytest.mark.asyncio
async def test_render_goal_card():
    match = Match(
        id='test_m1',
        tournament_name='Premier League',
        home_team=Team(id='17', name='Manchester City'),
        away_team=Team(id='44', name='Liverpool'),
        score=Score(home=1, away=0)
    )
    event = DomainEvent(
        event_id='evt_g1',
        match_id='test_m1',
        event_type=DomainEventType.GOAL,
        minute=23,
        player_name='Erling Haaland',
        secondary_player_name='Kevin De Bruyne',
        home_score=1,
        away_score=0,
        is_home_team=True,
        description='Goal'
    )
    img_bytes = await GraphicsEngine.render_goal_card(match, event, {}, Language.BANGLA)
    assert isinstance(img_bytes, bytes)
    assert len(img_bytes) > 10000


@pytest.mark.asyncio
async def test_render_fulltime_card():
    match = Match(
        id='test_m2',
        tournament_name='LaLiga',
        home_team=Team(id='2817', name='Real Madrid'),
        away_team=Team(id='2818', name='Barcelona'),
        score=Score(home=2, away=1)
    )
    event = DomainEvent(
        event_id='evt_ft1',
        match_id='test_m2',
        event_type=DomainEventType.PERIOD_FULL_TIME,
        minute=90,
        home_score=2,
        away_score=1,
        description='Full-Time'
    )
    img_bytes = await GraphicsEngine.render_fulltime_card(match, [event], {}, Language.BANGLA)
    assert isinstance(img_bytes, bytes)
    assert len(img_bytes) > 10000


@pytest.mark.asyncio
async def test_render_lineup_card():
    match = Match(
        id='test_m3',
        tournament_name='Serie A',
        home_team=Team(id='2697', name='Inter Milan'),
        away_team=Team(id='2687', name='Juventus'),
        score=Score(home=0, away=0)
    )
    img_bytes = await GraphicsEngine.render_lineup_card(match, {}, Language.BANGLA)
    assert isinstance(img_bytes, bytes)
    assert len(img_bytes) > 10000
