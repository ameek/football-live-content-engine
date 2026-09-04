from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict


class MatchStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    HALF_TIME = "HALF_TIME"
    EXTRA_TIME = "EXTRA_TIME"
    PENALTIES = "PENALTIES"
    FINISHED = "FINISHED"
    POSTPONED = "POSTPONED"
    CANCELLED = "CANCELLED"


class CoverageProfile(str, Enum):
    FULL = "FULL"          # 🔴 Goals, Assists, Cards, VAR, Subs, Offside, Fouls, Period, Stats
    STANDARD = "STANDARD"  # 🟡 Goals, Red Cards, Penalties, VAR, Subs, Period
    RESULT_ONLY = "RESULT_ONLY" # 🟢 Goals, Half-Time, Full-Time only


class EventImportance(str, Enum):
    MUST_POST = "MUST_POST"     # Always generate post (Goals, Red Cards, Penalties, VAR Overturns, FT)
    MAYBE_POST = "MAYBE_POST"   # Depends on match Coverage Profile (Yellows, Subs, Injuries)
    IGNORE = "IGNORE"           # Routine fouls, offsides (unless in FULL coverage)


class Language(str, Enum):
    BANGLA = "bn"
    ENGLISH = "en"


class NewsVoiceStyle(str, Enum):
    BREAKING = "BREAKING"         # ⚽ ব্রেকিং: গোল! এগিয়ে গেল রিয়াল মাদ্রিদ (৬৭')
    SHORT = "SHORT"               # ⚽ গোল! রিয়াল মাদ্রিদ ২-১ বার্সেলোনা (৬৭')
    REPORT = "REPORT"             # 🏁 ম্যাচ রিপোর্ট / বিস্তারিত প্রতিবেদন


class Score(BaseModel):
    home: int = 0
    away: int = 0


class Team(BaseModel):
    id: Optional[str] = None
    name: str
    bangla_name: Optional[str] = None
    short_name: Optional[str] = None
    logo_url: Optional[str] = None


class Match(BaseModel):
    """Aggregate Root representing a football fixture."""
    id: str
    tournament_name: str
    tournament_category: Optional[str] = "Football"
    tournament_logo_url: Optional[str] = None
    home_team: Team
    away_team: Team
    status: MatchStatus = MatchStatus.NOT_STARTED
    status_detail: str = "Scheduled"
    minute: Optional[int] = None
    score: Score = Field(default_factory=Score)
    start_time: Optional[datetime] = None
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Remote Desk Coverage Configuration
    coverage: CoverageProfile = CoverageProfile.STANDARD
    auto_generate: bool = True
    auto_publish: bool = True
    language: Language = Language.BANGLA
    voice_style: NewsVoiceStyle = NewsVoiceStyle.BREAKING
    incident_ids_seen: List[str] = Field(default_factory=list)


class PostStatus(str, Enum):
    DRAFT = "DRAFT"
    QUEUED_FOR_REVIEW = "QUEUED_FOR_REVIEW"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"


class GeneratedPost(BaseModel):
    """Generated Pavilion sports newsroom post artifact."""
    post_id: str
    event_id: str
    match_id: str
    platform: str = "facebook"
    language: Language = Language.BANGLA
    voice_style: NewsVoiceStyle = NewsVoiceStyle.BREAKING
    importance: EventImportance = EventImportance.MUST_POST
    headline: str
    content: str
    image_url: Optional[str] = None
    team_logo_url: Optional[str] = None
    tournament_logo_url: Optional[str] = None
    english_translation: Optional[str] = None
    hashtags: List[str] = Field(default_factory=list)
    status: PostStatus = PostStatus.QUEUED_FOR_REVIEW
    auto_published: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reviewed_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None


class NightShiftConfig(BaseModel):
    """Configuration for an overnight monitoring session."""
    active: bool = False
    default_language: Language = Language.BANGLA
    default_coverage: CoverageProfile = CoverageProfile.STANDARD
    default_auto_publish: bool = False
    active_match_ids: List[str] = Field(default_factory=list)
    started_at: Optional[datetime] = None
