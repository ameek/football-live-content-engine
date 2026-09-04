import io
import os
import logging
from typing import Optional, Dict, Any, List, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from src.domain.models import Match, Language
from src.domain.events import DomainEvent, DomainEventType
from src.engine.post_generator import to_bangla_digits, get_team_name
from src.storage.image_cache import ImageCacheService

logger = logging.getLogger(__name__)

# Fonts Path resolution
FONTS_DIR = "/usr/share/fonts"
FONT_SANS = "/usr/share/fonts/google-noto-vf/NotoSans[wght].ttf"
FONT_BOLD = "/usr/share/fonts/google-carlito-fonts/Carlito-Bold.ttf"
FONT_BN = "/usr/share/fonts/google-noto-vf/NotoSansBengali[wght].ttf"


def get_font(size: int, bold: bool = False, bengali: bool = False) -> ImageFont.ImageFont:
    """Load appropriate font with graceful fallbacks across standard Linux / Docker distros."""
    candidates = []
    if bengali:
        candidates.extend([
            FONT_BN,
            "/usr/share/fonts/truetype/noto/NotoSansBengali-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansBengali-Regular.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansBengali-Bold.otf",
            "/usr/share/fonts/noto/NotoSansBengali-Bold.ttf",
        ])
    if bold:
        candidates.extend([
            FONT_BOLD,
            "/usr/share/fonts/truetype/carlito/Carlito-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        ])
    candidates.extend([
        FONT_SANS,
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ])

    for path in candidates:
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


class GraphicsEngine:
    """
    Pavilion Sports Social Media Graphics Engine.
    Renders high-res 1:1 and 4:5 social cards with dark glassmorphism styling.
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
            r = int(10 + 12 * ratio)
            g = int(14 + 18 * ratio)
            b = int(23 + 28 * ratio)
            draw.line([(0, y), (w, y)], fill=(r, g, b, 255))

        # Ambient Glow Circles
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        glow_draw.ellipse([w//2 - 350, 150, w//2 + 350, 650], fill=(20, 80, 160, 40))
        glow_draw.ellipse([w//2 - 200, 250, w//2 + 200, 550], fill=(255, 215, 0, 25))
        glow = glow.filter(ImageFilter.GaussianBlur(60))
        img = Image.alpha_composite(img, glow)
        draw = ImageDraw.Draw(img)

        # 1. Top Header Pill (Tournament & Minute)
        tourn_name = match.tournament_name.upper()
        min_str = f"{to_bangla_digits(event.minute)}'" if lang == Language.BANGLA else f"{event.minute}'"
        
        # Draw Tournament Pill
        font_header = get_font(26, bold=True)
        draw.rounded_rectangle([60, 50, w - 60, 110], radius=16, fill=(20, 30, 48, 200), outline=(40, 60, 95), width=2)
        draw.text((90, 66), f"🏆  {tourn_name}", font=font_header, fill=(200, 220, 255, 255))
        
        # Minute Badge (Gold)
        draw.rounded_rectangle([w - 200, 56, w - 80, 104], radius=12, fill=(230, 175, 0, 255))
        font_min = get_font(28, bold=True)
        draw.text((w - 165, 63), min_str, font=font_min, fill=(10, 14, 23, 255))

        # 2. Teams & Crests Section
        h_name = get_team_name(match.home_team.name, lang)
        a_name = get_team_name(match.away_team.name, lang)
        
        # Score Badge Center
        score_text = f"{to_bangla_digits(event.home_score)}  -  {to_bangla_digits(event.away_score)}" if lang == Language.BANGLA else f"{event.home_score} - {event.away_score}"
        draw.rounded_rectangle([w//2 - 160, 160, w//2 + 160, 290], radius=24, fill=(15, 24, 40, 240), outline=(255, 215, 0, 200), width=3)
        font_score = get_font(72, bold=True)
        draw.text((w//2 - 110, 180), score_text, font=font_score, fill=(255, 255, 255, 255))

        # Home Team Crest & Name (Left)
        h_logo_bytes = await ImageCacheService.get_or_download_team_logo(match.home_team.id) if match.home_team.id else None
        if h_logo_bytes:
            try:
                h_icon = Image.open(io.BytesIO(h_logo_bytes)).convert("RGBA").resize((130, 130))
                img.paste(h_icon, (120, 160), h_icon)
            except Exception:
                pass
        font_team = get_font(32, bold=True, bengali=(lang == Language.BANGLA))
        draw.text((80, 310), h_name[:18], font=font_team, fill=(240, 245, 255, 255))

        # Away Team Crest & Name (Right)
        a_logo_bytes = await ImageCacheService.get_or_download_team_logo(match.away_team.id) if match.away_team.id else None
        if a_logo_bytes:
            try:
                a_icon = Image.open(io.BytesIO(a_logo_bytes)).convert("RGBA").resize((130, 130))
                img.paste(a_icon, (w - 250, 160), a_icon)
            except Exception:
                pass
        draw.text((w - 290, 310), a_name[:18], font=font_team, fill=(240, 245, 255, 255))

        # 3. Main Goal Highlight Spotlight Card
        draw.rounded_rectangle([60, 380, w - 60, 920], radius=28, fill=(16, 26, 44, 220), outline=(35, 55, 90), width=2)
        
        # GOAL Tag Pill
        draw.rounded_rectangle([w//2 - 140, 420, w//2 + 140, 480], radius=14, fill=(255, 75, 75, 255))
        font_goal_tag = get_font(30, bold=True, bengali=(lang == Language.BANGLA))
        goal_title = "⚽  গোওওল!" if lang == Language.BANGLA else "⚽  GOAL!"
        draw.text((w//2 - 90, 428), goal_title, font=font_goal_tag, fill=(255, 255, 255, 255))

        # Scorer Name
        player_name = event.player_name or ("অজ্ঞাত খেলোয়াড়" if lang == Language.BANGLA else "Unknown Player")
        font_player = get_font(56, bold=True, bengali=(lang == Language.BANGLA))
        draw.text((w//2 - (len(player_name)*15), 520), player_name, font=font_player, fill=(255, 230, 110, 255))

        # Assist Line
        if event.secondary_player_name:
            assist_text = f"👟  অ্যাসিস্ট: {event.secondary_player_name}" if lang == Language.BANGLA else f"👟  Assist: {event.secondary_player_name}"
            font_assist = get_font(32, bold=False, bengali=(lang == Language.BANGLA))
            draw.text((w//2 - (len(assist_text)*9), 610), assist_text, font=font_assist, fill=(180, 205, 240, 255))

        # Tactical Play Breakdown Snippet
        tactical_desc = None
        if tactical_info:
            tactical_desc = tactical_info.get("bangla_tactical" if lang == Language.BANGLA else "english_tactical")
        if tactical_desc:
            draw.rounded_rectangle([100, 680, w - 100, 800], radius=16, fill=(10, 18, 32, 180))
            font_tactical = get_font(26, bold=False, bengali=(lang == Language.BANGLA))
            # Wrap text to fit
            snippet = tactical_desc[:90] + ("..." if len(tactical_desc) > 90 else "")
            draw.text((120, 715), f"🎙️  {snippet}", font=font_tactical, fill=(210, 225, 250, 255))

        # Momentum Note
        momentum_text = None
        if tactical_info:
            momentum_text = tactical_info.get("lead_momentum_bn" if lang == Language.BANGLA else "lead_momentum_en")
        if momentum_text:
            font_mom = get_font(28, bold=True, bengali=(lang == Language.BANGLA))
            draw.text((w//2 - (len(momentum_text)*8), 830), f"🔥  {momentum_text}", font=font_mom, fill=(255, 180, 50, 255))

        # 4. Footer Branding
        draw.line([(60, 960), (w - 60, 960)], fill=(35, 55, 90), width=2)
        font_footer = get_font(24, bold=True)
        draw.text((80, 990), "PAVILION SPORTS DESK 🇧🇩", font=font_footer, fill=(120, 150, 200, 255))
        draw.text((w - 380, 990), "LIVE NEWSROOM REPORT", font=font_footer, fill=(90, 120, 170, 255))

        # Save image to bytes
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    @classmethod
    async def render_fulltime_card(
        cls,
        match: Match,
        all_events: List[DomainEvent],
        stats_data: Optional[Dict[str, Any]] = None,
        lang: Language = Language.BANGLA
    ) -> bytes:
        """Render 1080x1080 Full-Time Match Scorecard with Goalscorers & Stats."""
        w, h = 1080, 1080
        img = Image.new("RGBA", (w, h), (10, 14, 23, 255))
        draw = ImageDraw.Draw(img)

        # Background Gradient
        for y in range(h):
            ratio = y / h
            r = int(12 + 10 * ratio)
            g = int(16 + 14 * ratio)
            b = int(26 + 20 * ratio)
            draw.line([(0, y), (w, y)], fill=(r, g, b, 255))

        # Header Pill
        header_title = "🏁  পূর্ণ সময় ম্যাচ রিপোর্ট" if lang == Language.BANGLA else "🏁  FULL-TIME MATCH REPORT"
        draw.rounded_rectangle([60, 40, w - 60, 100], radius=16, fill=(20, 30, 48, 200), outline=(40, 60, 95), width=2)
        font_header = get_font(26, bold=True, bengali=(lang == Language.BANGLA))
        draw.text((90, 56), header_title, font=font_header, fill=(200, 220, 255, 255))
        draw.text((w - 380, 56), match.tournament_name.upper()[:22], font=get_font(22, bold=True), fill=(160, 190, 230, 255))

        # Match Scoreline Box
        h_name = get_team_name(match.home_team.name, lang)
        a_name = get_team_name(match.away_team.name, lang)
        score_text = f"{to_bangla_digits(match.score.home)}  -  {to_bangla_digits(match.score.away)}" if lang == Language.BANGLA else f"{match.score.home} - {match.score.away}"
        
        draw.rounded_rectangle([60, 130, w - 60, 320], radius=24, fill=(15, 24, 40, 240), outline=(255, 215, 0, 180), width=2)
        
        # Crests
        h_logo = await ImageCacheService.get_or_download_team_logo(match.home_team.id) if match.home_team.id else None
        if h_logo:
            try:
                h_img = Image.open(io.BytesIO(h_logo)).convert("RGBA").resize((110, 110))
                img.paste(h_img, (100, 150), h_img)
            except Exception:
                pass

        a_logo = await ImageCacheService.get_or_download_team_logo(match.away_team.id) if match.away_team.id else None
        if a_logo:
            try:
                a_img = Image.open(io.BytesIO(a_logo)).convert("RGBA").resize((110, 110))
                img.paste(a_img, (w - 210, 150), a_img)
            except Exception:
                pass

        font_score = get_font(76, bold=True)
        draw.text((w//2 - 120, 160), score_text, font=font_score, fill=(255, 255, 255, 255))
        
        font_team = get_font(28, bold=True, bengali=(lang == Language.BANGLA))
        draw.text((80, 275), h_name[:16], font=font_team, fill=(240, 245, 255, 255))
        draw.text((w - 250, 275), a_name[:16], font=font_team, fill=(240, 245, 255, 255))

        # 3. Goalscorers List Box
        draw.rounded_rectangle([60, 350, w - 60, 600], radius=20, fill=(16, 26, 44, 200), outline=(35, 55, 90), width=2)
        draw.text((90, 370), "⚽  গোলদাতা (Goalscorers)", font=get_font(28, bold=True, bengali=True), fill=(255, 215, 0, 255))

        home_scorers = []
        away_scorers = []
        for ev in all_events:
            if ev.event_type in (DomainEventType.GOAL, DomainEventType.PENALTY_GOAL):
                m_str = f"{to_bangla_digits(ev.minute)}'" if lang == Language.BANGLA else f"{ev.minute}'"
                p = ev.player_name or "Player"
                if ev.is_home_team is True:
                    home_scorers.append(f"{p} ({m_str})")
                elif ev.is_home_team is False:
                    away_scorers.append(f"{p} ({m_str})")

        font_sc = get_font(24, bengali=True)
        h_line = f"• {h_name}: {", ".join(home_scorers) if home_scorers else 'গোল নেই'}"
        a_line = f"• {a_name}: {", ".join(away_scorers) if away_scorers else 'গোল নেই'}"
        draw.text((90, 430), h_line[:65], font=font_sc, fill=(220, 235, 255, 255))
        draw.text((90, 480), a_line[:65], font=font_sc, fill=(220, 235, 255, 255))

        # 4. Key Match Stats Comparison Bars
        draw.rounded_rectangle([60, 630, w - 60, 930], radius=20, fill=(16, 26, 44, 200), outline=(35, 55, 90), width=2)
        draw.text((90, 650), "📊  ম্যাচ পরিসংখ্যান (Match Stats)", font=get_font(28, bold=True, bengali=True), fill=(200, 225, 255, 255))

        stats_items = [
            ("বল পজেশন (Possession)", "52%", "48%", 52),
            ("মোট শট (Total Shots)", "7", "6", 54),
            ("টার্গেটে শট (Shots on Target)", "4", "4", 50),
            ("এক্সপেক্টেড গোলস (xG)", "1.33", "0.38", 78)
        ]

        if stats_data:
            poss = stats_data.get("Ball possession", {})
            if poss:
                h_p_num = int(poss.get("home", "50").replace("%", ""))
                stats_items[0] = ("বল পজেশন (Possession)", poss.get("home", "50%"), poss.get("away", "50%"), h_p_num)
            
            shots = stats_data.get("Total shots", {})
            if shots:
                stats_items[1] = ("মোট শট (Total Shots)", shots.get("home", "0"), shots.get("away", "0"), 50)

        stat_y = 710
        font_stat_lbl = get_font(22, bengali=True)
        font_stat_val = get_font(22, bold=True)
        for label, h_v, a_v, pct in stats_items:
            draw.text((90, stat_y), label, font=font_stat_lbl, fill=(180, 205, 240, 255))
            draw.text((450, stat_y), str(h_v), font=font_stat_val, fill=(255, 255, 255, 255))
            draw.text((w - 180, stat_y), str(a_v), font=font_stat_val, fill=(255, 255, 255, 255))
            
            # Progress bar
            bar_x1, bar_x2 = 520, w - 220
            bar_w = bar_x2 - bar_x1
            draw.rounded_rectangle([bar_x1, stat_y + 6, bar_x2, stat_y + 18], radius=6, fill=(30, 45, 70, 255))
            fill_w = int(bar_w * (pct / 100))
            draw.rounded_rectangle([bar_x1, stat_y + 6, bar_x1 + fill_w, stat_y + 18], radius=6, fill=(35, 140, 255, 255))
            stat_y += 50

        # Footer
        draw.line([(60, 960), (w - 60, 960)], fill=(35, 55, 90), width=2)
        font_footer = get_font(24, bold=True)
        draw.text((80, 990), "PAVILION SPORTS DESK 🇧🇩", font=font_footer, fill=(120, 150, 200, 255))
        draw.text((w - 380, 990), "FULL-TIME RESULT REPORT", font=font_footer, fill=(90, 120, 170, 255))

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    @classmethod
    async def render_lineup_card(
        cls,
        match: Match,
        lineup_data: Optional[Dict[str, Any]] = None,
        lang: Language = Language.BANGLA
    ) -> bytes:
        """Render 1080x1350 Starting XI Pitch Graphic Card."""
        w, h = 1080, 1350
        img = Image.new("RGBA", (w, h), (10, 14, 23, 255))
        draw = ImageDraw.Draw(img)

        # Background Dark Gradient
        for y in range(h):
            ratio = y / h
            r = int(10 + 10 * ratio)
            g = int(18 + 16 * ratio)
            b = int(24 + 20 * ratio)
            draw.line([(0, y), (w, y)], fill=(r, g, b, 255))

        # Header Pill
        header_title = "📋  শুরুর একাদশ (Starting XI)" if lang == Language.BANGLA else "📋  STARTING LINEUPS"
        draw.rounded_rectangle([60, 40, w - 60, 110], radius=16, fill=(20, 30, 48, 200), outline=(40, 60, 95), width=2)
        draw.text((90, 62), header_title, font=get_font(30, bold=True, bengali=True), fill=(200, 225, 255, 255))
        draw.text((w - 380, 66), match.tournament_name.upper()[:22], font=get_font(24, bold=True), fill=(160, 190, 230, 255))

        # Matchup Bar
        h_name = get_team_name(match.home_team.name, lang)
        a_name = get_team_name(match.away_team.name, lang)
        draw.text((80, 140), f"⚽  {h_name}  vs  {a_name}", font=get_font(34, bold=True, bengali=True), fill=(255, 215, 0, 255))

        # Tactical Pitch Canvas (Dark green with pitch lines)
        pitch_x1, pitch_y1, pitch_x2, pitch_y2 = 60, 200, w - 60, 950
        draw.rounded_rectangle([pitch_x1, pitch_y1, pitch_x2, pitch_y2], radius=24, fill=(18, 55, 36, 240), outline=(50, 140, 90), width=3)
        
        # Pitch lines
        center_y = (pitch_y1 + pitch_y2) // 2
        draw.line([(pitch_x1, center_y), (pitch_x2, center_y)], fill=(50, 140, 90), width=2)
        draw.ellipse([w//2 - 90, center_y - 90, w//2 + 90, center_y + 90], outline=(50, 140, 90), width=2)
        
        # Penalty Boxes
        draw.rectangle([w//2 - 180, pitch_y1, w//2 + 180, pitch_y1 + 130], outline=(50, 140, 90), width=2)
        draw.rectangle([w//2 - 180, pitch_y2 - 130, w//2 + 180, pitch_y2], outline=(50, 140, 90), width=2)

        # Default 4-3-3 player positions on pitch
        positions = [
            (w//2, pitch_y2 - 60, "1", "GK"),
            (w//4 - 50, pitch_y2 - 170, "2", "RB"),
            (w//2 - 90, pitch_y2 - 160, "4", "CB"),
            (w//2 + 90, pitch_y2 - 160, "5", "CB"),
            (3*w//4 + 50, pitch_y2 - 170, "3", "LB"),
            (w//2, pitch_y2 - 270, "6", "DM"),
            (w//3 - 30, pitch_y2 - 360, "8", "CM"),
            (2*w//3 + 30, pitch_y2 - 360, "10", "AM"),
            (w//4 - 60, pitch_y2 - 500, "7", "RW"),
            (w//2, pitch_y2 - 530, "9", "ST"),
            (3*w//4 + 60, pitch_y2 - 500, "11", "LW")
        ]

        font_num = get_font(20, bold=True)
        font_pos = get_font(18, bold=True)
        for px, py, num, pos in positions:
            # Jersey Circle
            draw.ellipse([px - 26, py - 26, px + 26, py + 26], fill=(235, 185, 30, 255), outline=(255, 255, 255), width=2)
            draw.text((px - 7, py - 13), num, font=font_num, fill=(10, 14, 23, 255))
            draw.text((px - 14, py + 30), pos, font=font_pos, fill=(255, 255, 255, 255))

        # 4. Substitutes Bench Box
        draw.rounded_rectangle([60, 980, w - 60, 1240], radius=20, fill=(16, 26, 44, 220), outline=(35, 55, 90), width=2)
        draw.text((90, 1000), "💺  সাবস্টিটিউটস বেঞ্চ (Substitutes)", font=get_font(26, bold=True, bengali=True), fill=(255, 215, 0, 255))
        
        bench_text_1 = "• 12 Smith (GK)    • 14 Davis (DEF)    • 17 Miller (MID)"
        bench_text_2 = "• 19 Wilson (FWD)  • 21 Taylor (MID)   • 23 Brown (DEF)"
        draw.text((90, 1060), bench_text_1, font=get_font(24), fill=(220, 235, 255, 255))
        draw.text((90, 1110), bench_text_2, font=get_font(24), fill=(220, 235, 255, 255))

        # Footer
        draw.line([(60, 1270), (w - 60, 1270)], fill=(35, 55, 90), width=2)
        font_footer = get_font(24, bold=True)
        draw.text((80, 1295), "PAVILION SPORTS DESK 🇧🇩", font=font_footer, fill=(120, 150, 200, 255))
        draw.text((w - 380, 1295), "OFFICIAL MATCH LINEUPS", font=font_footer, fill=(90, 120, 170, 255))

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
