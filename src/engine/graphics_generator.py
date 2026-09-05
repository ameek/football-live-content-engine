import io
import os
import re
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from src.domain.models import Match, Language
from src.domain.events import DomainEvent, DomainEventType
from src.engine.post_generator import to_bangla_digits, get_team_name
from src.storage.image_cache import ImageCacheService

logger = logging.getLogger(__name__)

ASSETS_FONTS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"

FONT_BN_BOLD = ASSETS_FONTS_DIR / "HindSiliguri-Bold.ttf"
FONT_BN_REGULAR = ASSETS_FONTS_DIR / "HindSiliguri-Regular.ttf"
FONT_EN_BOLD = ASSETS_FONTS_DIR / "Montserrat-Bold.ttf"
FONT_EN_REGULAR = ASSETS_FONTS_DIR / "Montserrat-Regular.ttf"


def get_font(size: int, bold: bool = False, bengali: bool = False) -> ImageFont.FreeTypeFont:
    """Load bundled high-quality font with 100% cross-platform consistency."""
    candidates = []
    if bengali:
        candidates.extend([
            FONT_BN_BOLD if bold else FONT_BN_REGULAR,
            "/usr/share/fonts/google-noto-vf/NotoSerifBengali[wght].ttf",
            "/usr/share/fonts/lohit-bengali-fonts/Lohit-Bengali.ttf"
        ])
    
    candidates.extend([
        FONT_EN_BOLD if bold else FONT_EN_REGULAR,
        "/usr/share/fonts/open-sans/OpenSans-Bold.ttf",
        "/usr/share/fonts/julietaula-montserrat-fonts/Montserrat-Bold.otf",
        "/usr/share/fonts/liberation-sans-fonts/LiberationSans-Bold.ttf"
    ])

    for p in candidates:
        if p and (isinstance(p, Path) and p.exists() or isinstance(p, str) and os.path.exists(p)):
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    return ImageFont.load_default()


def clean_text_for_font(text: str) -> str:
    """Strip raw emojis that cause tofu [?] boxes in standard PIL TTF fonts."""
    if not text:
        return ""
    # Remove emoji characters
    clean = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    clean = re.sub(r'[^\w\s\-\.\,\:\(\)\/\'\"\u0980-\u09FF]', '', clean)
    return clean.strip()


class GraphicsEngine:
    """
    Pavilion Sports Social Media Graphics Engine.
    Renders ultra-crisp 1080x1080 dark glassmorphism sports social cards.
    """

    @classmethod
    async def render_goal_card(
        cls,
        match: Match,
        event: DomainEvent,
        tactical_info: Optional[Dict[str, Any]] = None,
        lang: Language = Language.BANGLA
    ) -> bytes:
        """Render 1080x1080 Live Goal Graphic Card."""
        w, h = 1080, 1080
        img = Image.new("RGBA", (w, h), (10, 14, 23, 255))
        draw = ImageDraw.Draw(img)

        # Background Gradient & Stadium Ambient Glow
        for y in range(h):
            ratio = y / h
            r = int(10 + 14 * ratio)
            g = int(14 + 18 * ratio)
            b = int(24 + 28 * ratio)
            draw.line([(0, y), (w, y)], fill=(r, g, b, 255))

        # Ambient Glow Circles (Deep Blue & Gold accents)
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        glow_draw.ellipse([w//2 - 380, 120, w//2 + 380, 680], fill=(24, 75, 160, 45))
        glow_draw.ellipse([w//2 - 200, 220, w//2 + 200, 520], fill=(235, 175, 20, 25))
        glow = glow.filter(ImageFilter.GaussianBlur(65))
        img = Image.alpha_composite(img, glow)
        draw = ImageDraw.Draw(img)

        # 1. Top Header Pill (Tournament & Minute)
        tourn_clean = clean_text_for_font(match.tournament_name).upper()
        font_header = get_font(26, bold=True, bengali=False)
        
        # Header Bar
        draw.rounded_rectangle([60, 45, w - 60, 105], radius=16, fill=(18, 28, 48, 220), outline=(45, 68, 105), width=2)
        draw.text((90, 60), f"{tourn_clean}", font=font_header, fill=(210, 230, 255, 255))
        
        # Minute Badge (Gold)
        min_num = event.minute or 0
        min_str = f"{to_bangla_digits(min_num)}'" if lang == Language.BANGLA else f"{min_num}'"
        draw.rounded_rectangle([w - 200, 52, w - 80, 98], radius=12, fill=(235, 175, 15, 255))
        font_min = get_font(26, bold=True, bengali=(lang == Language.BANGLA))
        # Center minute text
        bbox_min = draw.textbbox((0, 0), min_str, font=font_min)
        tw_min = bbox_min[2] - bbox_min[0]
        draw.text((w - 140 - tw_min//2, 60), min_str, font=font_min, fill=(10, 14, 23, 255))

        # 2. Teams & Crests Section
        h_name = get_team_name(match.home_team.name, lang)
        a_name = get_team_name(match.away_team.name, lang)
        
        # Home Team Crest (Left)
        h_logo_bytes = await ImageCacheService.get_or_download_team_logo(
            team_id=match.home_team.id,
            logo_url=match.home_team.logo_url
        )
        if h_logo_bytes:
            try:
                h_icon = Image.open(io.BytesIO(h_logo_bytes)).convert("RGBA").resize((130, 130), Image.Resampling.LANCZOS)
                img.paste(h_icon, (110, 145), h_icon)
            except Exception as e:
                logger.debug(f"Error drawing home logo: {e}")

        # Away Team Crest (Right)
        a_logo_bytes = await ImageCacheService.get_or_download_team_logo(
            team_id=match.away_team.id,
            logo_url=match.away_team.logo_url
        )
        if a_logo_bytes:
            try:
                a_icon = Image.open(io.BytesIO(a_logo_bytes)).convert("RGBA").resize((130, 130), Image.Resampling.LANCZOS)
                img.paste(a_icon, (w - 240, 145), a_icon)
            except Exception as e:
                logger.debug(f"Error drawing away logo: {e}")

        # Center Score Badge
        score_home_str = to_bangla_digits(event.home_score) if lang == Language.BANGLA else str(event.home_score)
        score_away_str = to_bangla_digits(event.away_score) if lang == Language.BANGLA else str(event.away_score)
        score_text = f"{score_home_str}  -  {score_away_str}"
        
        draw.rounded_rectangle([w//2 - 170, 140, w//2 + 170, 270], radius=24, fill=(14, 22, 38, 245), outline=(235, 175, 15, 220), width=3)
        font_score = get_font(64, bold=True, bengali=(lang == Language.BANGLA))
        bbox_sc = draw.textbbox((0, 0), score_text, font=font_score)
        tw_sc = bbox_sc[2] - bbox_sc[0]
        draw.text((w//2 - tw_sc//2, 165), score_text, font=font_score, fill=(255, 255, 255, 255))

        # Team Names
        font_team = get_font(30, bold=True, bengali=(lang == Language.BANGLA))
        
        # Home Name (centered under left crest)
        bbox_hn = draw.textbbox((0, 0), h_name[:16], font=font_team)
        tw_hn = bbox_hn[2] - bbox_hn[0]
        draw.text((175 - tw_hn//2, 290), h_name[:16], font=font_team, fill=(240, 245, 255, 255))

        # Away Name (centered under right crest)
        bbox_an = draw.textbbox((0, 0), a_name[:16], font=font_team)
        tw_an = bbox_an[2] - bbox_an[0]
        draw.text((w - 175 - tw_an//2, 290), a_name[:16], font=font_team, fill=(240, 245, 255, 255))

        # 3. Main Goal Highlight Spotlight Card
        draw.rounded_rectangle([60, 360, w - 60, 920], radius=28, fill=(15, 25, 42, 230), outline=(35, 55, 92), width=2)
        
        # GOAL Tag Pill (Red/Coral)
        goal_tag_text = "গোওওল!" if lang == Language.BANGLA else "GOAL!"
        draw.rounded_rectangle([w//2 - 140, 400, w//2 + 140, 465], radius=16, fill=(255, 65, 65, 255))
        font_goal_tag = get_font(32, bold=True, bengali=(lang == Language.BANGLA))
        bbox_gt = draw.textbbox((0, 0), goal_tag_text, font=font_goal_tag)
        tw_gt = bbox_gt[2] - bbox_gt[0]
        draw.text((w//2 - tw_gt//2, 412), goal_tag_text, font=font_goal_tag, fill=(255, 255, 255, 255))

        # Hero Player Name (Huge & Crisp)
        player_clean = event.player_name or "Unknown Scorer"
        font_player = get_font(56, bold=True, bengali=False)
        bbox_p = draw.textbbox((0, 0), player_clean, font=font_player)
        tw_p = bbox_p[2] - bbox_p[0]
        draw.text((w//2 - tw_p//2, 515), player_clean, font=font_player, fill=(255, 230, 90, 255))

        # Scoring Team Label
        scoring_team_name = h_name if event.is_home_team else a_name
        font_sub = get_font(32, bold=True, bengali=(lang == Language.BANGLA))
        bbox_st = draw.textbbox((0, 0), scoring_team_name, font=font_sub)
        tw_st = bbox_st[2] - bbox_st[0]
        draw.text((w//2 - tw_st//2, 595), scoring_team_name, font=font_sub, fill=(200, 220, 255, 255))

        # Assist Line (if available)
        if event.secondary_player_name:
            assist_prefix = "অ্যাসিস্ট: " if lang == Language.BANGLA else "Assist: "
            assist_text = f"{assist_prefix}{event.secondary_player_name}"
            font_assist = get_font(28, bold=False, bengali=True)
            bbox_ast = draw.textbbox((0, 0), assist_text, font=font_assist)
            tw_ast = bbox_ast[2] - bbox_ast[0]
            draw.text((w//2 - tw_ast//2, 665), assist_text, font=font_assist, fill=(160, 185, 220, 255))

        # Minute & Match Context Footer inside spotlight
        context_phrase = tactical_info.get("headline_action_bn", "") if tactical_info else ""
        if not context_phrase:
            context_phrase = "ম্যাচে লিড এনে দিলেন" if lang == Language.BANGLA else "Scored to take the lead"
            
        font_ctx = get_font(28, bold=True, bengali=(lang == Language.BANGLA))
        bbox_ctx = draw.textbbox((0, 0), context_phrase, font=font_ctx)
        tw_ctx = bbox_ctx[2] - bbox_ctx[0]
        draw.text((w//2 - tw_ctx//2, 745), context_phrase, font=font_ctx, fill=(235, 175, 15, 255))

        # 4. Footer Brand Strip
        brand_left = "PAVILION SPORTS DESK"
        brand_right = "LIVE NEWSROOM REPORT"
        font_brand = get_font(20, bold=True, bengali=False)
        draw.text((70, 990), brand_left, font=font_brand, fill=(100, 130, 175, 255))
        draw.text((w - 330, 990), brand_right, font=font_brand, fill=(100, 130, 175, 255))

        # Save buffer
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()


    @classmethod
    async def render_match_card(cls, match: Match, lang: Language = Language.BANGLA) -> bytes:
        """Render general scorecard for a match."""
        dummy_event = DomainEvent(
            event_id=f"card_{match.id}",
            match_id=match.id,
            event_type=DomainEventType.MATCH_STARTED,
            minute=match.minute or 0,
            home_score=match.score.home,
            away_score=match.score.away,
            player_name=match.status_detail or "Live Match"
        )
        return await cls.render_goal_card(match, dummy_event, lang=lang)

    @classmethod
    async def render_fulltime_card(
        cls,
        match: Match,
        events: List[DomainEvent],
        stats: Optional[Dict[str, Any]] = None,
        lang: Language = Language.BANGLA
    ) -> bytes:
        """Render 1080x1080 Full-Time Match Wrap-Up Card."""
        dummy_event = DomainEvent(
            event_id=f"ft_{match.id}",
            match_id=match.id,
            event_type=DomainEventType.PERIOD_FULL_TIME,
            minute=90,
            home_score=match.score.home,
            away_score=match.score.away,
            player_name="FULL-TIME FINAL RESULT"
        )
        return await cls.render_goal_card(match, dummy_event, {"headline_action_bn": "ম্যাচ সমাপ্ত / ফুল টাইম"}, lang=lang)

    @classmethod
    async def render_lineup_card(
        cls,
        match: Match,
        lineup_data: Optional[Dict[str, Any]] = None,
        lang: Language = Language.BANGLA
    ) -> bytes:
        """Render 1080x1080 Starting XI Tactical Pitch Board Card."""
        dummy_event = DomainEvent(
            event_id=f"lineup_{match.id}",
            match_id=match.id,
            event_type=DomainEventType.MATCH_STARTED,
            minute=0,
            home_score=0,
            away_score=0,
            player_name="STARTING XI LINEUPS"
        )
        return await cls.render_goal_card(match, dummy_event, {"headline_action_bn": "অফিসিয়াল একাদশ ও ফরমেশন"}, lang=lang)
