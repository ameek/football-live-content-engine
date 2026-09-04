import urllib.parse
import logging
import re
import time
from typing import Optional, Dict, Any, List, Tuple
import httpx

from src.domain.events import DomainEvent, DomainEventType
from src.domain.models import Match, Language

logger = logging.getLogger(__name__)

BANGLA_DIGITS = {
    '0': '০', '1': '১', '2': '২', '3': '৩', '4': '৪',
    '5': '৫', '6': '৬', '7': '৭', '8': '৮', '9': '৯'
}


def to_bangla_digits(text: Any) -> str:
    res = []
    for ch in str(text):
        res.append(BANGLA_DIGITS.get(ch, ch))
    return "".join(res)


class GoogleTranslateService:
    """
    Google Translate Service with in-memory caching.
    Uses public Google Translate single-shot API for instantaneous translation.
    """
    _cache: Dict[str, str] = {}

    @classmethod
    async def translate(cls, text: str, target_lang: str = "bn", timeout: float = 4.0) -> str:
        if not text or not text.strip():
            return text

        cache_key = f"{target_lang}:{text.strip()}"
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        encoded = urllib.parse.quote(text.strip())
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_lang}&dt=t&q={encoded}"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
                )
                if response.status_code == 200:
                    data = response.json()
                    translated_segments = []
                    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                        for segment in data[0]:
                            if isinstance(segment, list) and len(segment) > 0 and segment[0]:
                                translated_segments.append(segment[0])
                    if translated_segments:
                        result = "".join(translated_segments).strip()
                        cls._cache[cache_key] = result
                        return result
        except Exception as e:
            logger.debug(f"Google translate error ({e}), using fallback original text.")

        return text


class CommentaryEnricher:
    """
    Enrichment Engine between Event Ingestion and Newsroom Post Generation.
    Extracts live play-by-play commentary, tactical descriptors (shot type, assist style, card reason),
    match statistics snapshots (possession, shots, xG), and game momentum context.
    """

    BASE_SOFA_URL = "https://api.sofascore.com/api/v1"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*"
    }

    # In-memory cache for live comments & stats: match_id -> (timestamp, data)
    _comments_cache: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
    _stats_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
    CACHE_TTL_SECONDS = 30.0

    BODY_PART_BANGLA = {
        "right-foot": "ডান পায়ের শটে",
        "right_foot": "ডান পায়ের শটে",
        "left-foot": "বাঁ পায়ের শটে",
        "left_foot": "বাঁ পায়ের শটে",
        "header": "দুর্দান্ত হেডে",
        "head": "হেডের সাহায্যে",
        "penalty": "স্পট-কিক থেকে নিখুঁত শটে",
        "direct-freekick": "সরাসরি ফ্রি-কিক থেকে চোখধাঁধানো শটে",
        "freekick": "ফ্রি-কিক থেকে"
    }

    BODY_PART_ENGLISH = {
        "right-foot": "with a right-footed shot",
        "right_foot": "with a right-footed shot",
        "left-foot": "with a left-footed strike",
        "left_foot": "with a left-footed strike",
        "header": "with a powerful header",
        "head": "with a header",
        "penalty": "from the penalty spot",
        "direct-freekick": "from a direct free-kick",
        "freekick": "from a free-kick"
    }

    CARD_REASON_BANGLA = {
        "foul": "ফাউল করার অপরাধে",
        "cynical foul": "প্রতিআক্রমণ ঠেকাতে ইচ্ছাকৃত ফাউলের কারণে",
        "tactical foul": "ট্যাকটিক্যাল ফাউলের জন্য",
        "handball": "হ্যান্ডবলের অপরাধে",
        "dissent": "রেফারির সাথে তর্কের জেরে",
        "argument": "বিতর্কে জড়ানোর কারণে",
        "time wasting": "সময় নষ্ট করার কারণে",
        "timewasting": "দেরি করে খেলা শুরু করায়",
        "rough play": "বিপজ্জনক ট্যাকলের কারণে",
        "unsporting behavior": "অসৌজন্যমূলক আচরণের জন্য"
    }

    @classmethod
    async def fetch_comments(cls, match_id: str) -> List[Dict[str, Any]]:
        """Fetch live play-by-play text comments with 30s caching."""
        now = time.time()
        if match_id in cls._comments_cache:
            ts, data = cls._comments_cache[match_id]
            if now - ts < cls.CACHE_TTL_SECONDS:
                return data

        url = f"{cls.BASE_SOFA_URL}/event/{match_id}/comments"
        try:
            async with httpx.AsyncClient(headers=cls.HEADERS, timeout=6.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    comments = resp.json().get("comments", [])
                    cls._comments_cache[match_id] = (now, comments)
                    return comments
        except Exception as e:
            logger.debug(f"Could not fetch comments for {match_id}: {e}")
        return []

    @classmethod
    async def fetch_statistics(cls, match_id: str) -> Dict[str, Any]:
        """Fetch match statistics (possession, shots, xG) with 30s caching."""
        now = time.time()
        if match_id in cls._stats_cache:
            ts, data = cls._stats_cache[match_id]
            if now - ts < cls.CACHE_TTL_SECONDS:
                return data

        url = f"{cls.BASE_SOFA_URL}/event/{match_id}/statistics"
        try:
            async with httpx.AsyncClient(headers=cls.HEADERS, timeout=6.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json().get("statistics", [])
                    res: Dict[str, Any] = {}
                    for period_data in data:
                        if period_data.get("period") in ("ALL", "1ST", "2ND"):
                            for group in period_data.get("groups", []):
                                for item in group.get("statisticsItems", []):
                                    name = item.get("name")
                                    h = item.get("home")
                                    a = item.get("away")
                                    if name in [
                                        "Ball possession", "Total shots", "Shots on target",
                                        "Expected goals", "Corner kicks", "Big chances", "Fouls"
                                    ]:
                                        if name not in res:
                                            res[name] = {"home": h, "away": a}
                    cls._stats_cache[match_id] = (now, res)
                    return res
        except Exception as e:
            logger.debug(f"Could not fetch stats for {match_id}: {e}")
        return {}

    @classmethod
    def clean_comment_text(cls, raw_text: str) -> str:
        """Strip leading boilerplate like 'Goal! Team 1, Team 0.' and team parentheticals."""
        t = re.sub(r'^(Goal!|Goal\s*—|GOAL!)\s*[^.]+\.\s*', '', raw_text, flags=re.IGNORECASE)
        t = re.sub(r'^[0-9]+\s*-\s*[0-9]+\s*\.\s*', '', t)
        t = re.sub(r'\s*\([^)]*\)', '', t)
        return t.strip()

    @classmethod
    def calculate_momentum(cls, home_score: int, away_score: int, is_home: bool) -> Tuple[str, str]:
        """Calculate dynamic game situation / lead momentum phrasing."""
        scoring_score = home_score if is_home else away_score
        opponent_score = away_score if is_home else home_score
        diff = scoring_score - opponent_score

        if diff == 1 and opponent_score == 0:
            return "ডেডলক ভেঙে দলকে গুরুত্বপূর্ণ লিড এনে দিলেন", "broke the deadlock to give their team the lead"
        elif diff == 0:
            return "ম্যাচে নাটকীয় সমতা ফেরালেন", "struck a dramatic equalizer to level the score"
        elif diff == 1 and opponent_score > 0:
            return "পুনরায় দলকে এগিয়ে নিলেন", "restored their team's advantage"
        elif diff == 2:
            return "দলের লিড দ্বিগুণ করে সুবিধাজনক অবস্থানে নিয়ে গেলেন", "doubled the lead in commanding fashion"
        elif diff >= 3:
            return "ব্যবধান আরও বাড়িয়ে দলের বড় জয় সুসংহত করলেন", "further extended the commanding lead"
        elif diff < 0:
            return "ব্যবধান কমিয়ে ম্যাচে ফেরার জোর লড়াই শুরু করলেন", "pulled one back to ignite the comeback"

        return "দলের হয়ে লক্ষ্যভেদ করলেন", "found the back of the net"

    @classmethod
    async def enrich_incident_details(cls, event: DomainEvent, match: Match) -> Dict[str, Any]:
        """
        Enrich incident with detailed play-by-play commentary, live match statistics snapshot,
        tactical breakdowns, and momentum analysis in both Bangla and English.
        """
        raw = event.raw_metadata or {}
        body_part = raw.get("bodyPart") or raw.get("shotType") or ""
        reason = (raw.get("reason") or "").lower().strip()
        assist_name = event.secondary_player_name
        player_name = event.player_name or "খেলোয়াড়"
        is_home = event.is_home_team if event.is_home_team is not None else True

        # 1. Fetch live comments & match statistics from Sofascore
        comments = await cls.fetch_comments(match.id)
        stats = await cls.fetch_statistics(match.id)

        # 2. Match commentary for this event minute or player
        matched_comment_text = None
        if comments and event.minute:
            for c in comments:
                t = c.get("time")
                txt = c.get("text", "")
                if t == event.minute and (
                    (event.player_name and event.player_name.lower() in txt.lower()) or
                    "goal" in txt.lower() or "card" in txt.lower() or "penalty" in txt.lower()
                ):
                    matched_comment_text = txt
                    break
            if not matched_comment_text and event.player_name:
                for c in comments:
                    t = c.get("time")
                    txt = c.get("text", "")
                    if event.player_name.lower() in txt.lower() and (t is not None and abs(t - event.minute) <= 1):
                        matched_comment_text = txt
                        break

        # 3. Calculate game momentum
        lead_momentum_bn, lead_momentum_en = cls.calculate_momentum(event.home_score, event.away_score, is_home)

        bangla_tactical = None
        english_tactical = None

        if event.event_type in (DomainEventType.GOAL, DomainEventType.PENALTY_GOAL, DomainEventType.OWN_GOAL):
            bp_bn = cls.BODY_PART_BANGLA.get(body_part.lower(), "")
            bp_en = cls.BODY_PART_ENGLISH.get(body_part.lower(), "")

            if matched_comment_text:
                cleaned_action = cls.clean_comment_text(matched_comment_text)
                if cleaned_action:
                    english_tactical = cleaned_action
                    bangla_tactical = await GoogleTranslateService.translate(cleaned_action, target_lang="bn")

            if not bangla_tactical:
                if event.event_type == DomainEventType.PENALTY_GOAL:
                    bangla_tactical = "পেনাল্টি স্পট থেকে নিখুঁত শটে বল জালে জড়ান।"
                    english_tactical = "Calmly slotted the ball home from the penalty spot."
                elif event.event_type == DomainEventType.OWN_GOAL:
                    bangla_tactical = "দুর্ভাগ্যবশত নিজের জালেই বল জড়িয়ে দেন।"
                    english_tactical = "Unfortunately turned the ball into their own net."
                else:
                    parts_bn = []
                    parts_en = []
                    if assist_name:
                        parts_bn.append(f"{assist_name}-এর পাস থেকে")
                        parts_en.append(f"assisted by {assist_name}")
                    if bp_bn:
                        parts_bn.append(bp_bn)
                    if bp_en:
                        parts_en.append(bp_en)

                    if parts_bn:
                        bangla_tactical = f"{' '.join(parts_bn)} দারুণ ফিনিশিংয়ে লক্ষ্যভেদ করেন {player_name}।"
                    if parts_en:
                        english_tactical = f"Finished {' '.join(parts_en)}."

        elif event.event_type in (DomainEventType.YELLOW_CARD, DomainEventType.RED_CARD, DomainEventType.YELLOW_RED_CARD):
            reason_bn = cls.CARD_REASON_BANGLA.get(reason)
            if not reason_bn and reason:
                reason_bn = await GoogleTranslateService.translate(reason, target_lang="bn")

            if matched_comment_text:
                cleaned = cls.clean_comment_text(matched_comment_text)
                if cleaned:
                    english_tactical = cleaned
                    bangla_tactical = await GoogleTranslateService.translate(cleaned, target_lang="bn")

            if not bangla_tactical:
                if reason_bn:
                    bangla_tactical = f"{reason_bn} রেফারি কার্ড প্রদর্শন করেন।"
                if reason:
                    english_tactical = f"Booked for {reason}."

        elif event.event_type in (DomainEventType.VAR_DECISION, DomainEventType.VAR_OVERTURN):
            var_reason = raw.get("varReason") or raw.get("incidentClass") or "ভিএআর রিভিউ"
            var_reason_bn = await GoogleTranslateService.translate(var_reason, target_lang="bn")
            bangla_tactical = f"ভিএআর (VAR) পরীক্ষা শেষে সিদ্ধান্ত: {var_reason_bn}"
            english_tactical = f"VAR review decision: {var_reason}"

        # 4. Build Live Match Statistics Snapshot
        stats_bn_lines = []
        stats_en_lines = []

        if stats:
            poss = stats.get("Ball possession")
            if poss:
                h_p = to_bangla_digits(poss.get("home", "50%"))
                a_p = to_bangla_digits(poss.get("away", "50%"))
                stats_bn_lines.append(f"• বল পজেশন: {match.home_team.name} {h_p} - {a_p} {match.away_team.name}")
                stats_en_lines.append(f"• Possession: {match.home_team.name} {poss.get('home')} - {poss.get('away')} {match.away_team.name}")

            shots = stats.get("Total shots")
            sot = stats.get("Shots on target")
            if shots or sot:
                h_s = to_bangla_digits(shots.get("home", "0")) if shots else "০"
                a_s = to_bangla_digits(shots.get("away", "0")) if shots else "০"
                h_sot = to_bangla_digits(sot.get("home", "0")) if sot else "০"
                a_sot = to_bangla_digits(sot.get("away", "0")) if sot else "০"
                stats_bn_lines.append(f"• শট (অন টার্গেট): {h_s} ({h_sot}) - {a_s} ({a_sot})")
                stats_en_lines.append(f"• Shots (On Target): {shots.get('home', '0') if shots else '0'} ({sot.get('home', '0') if sot else '0'}) - {shots.get('away', '0') if shots else '0'} ({sot.get('away', '0') if sot else '0'})")

            xg = stats.get("Expected goals")
            if xg:
                h_xg = to_bangla_digits(xg.get("home", "0.0"))
                a_xg = to_bangla_digits(xg.get("away", "0.0"))
                stats_bn_lines.append(f"• এক্সপেক্টেড গোলস (xG): {h_xg} - {a_xg}")
                stats_en_lines.append(f"• Expected Goals (xG): {xg.get('home')} - {xg.get('away')}")

        stats_bn_block = "\n".join(stats_bn_lines) if stats_bn_lines else ""
        stats_en_block = "\n".join(stats_en_lines) if stats_en_lines else ""

        return {
            "bangla_tactical": bangla_tactical,
            "english_tactical": english_tactical,
            "lead_momentum_bn": lead_momentum_bn,
            "lead_momentum_en": lead_momentum_en,
            "stats_bn_block": stats_bn_block,
            "stats_en_block": stats_en_block,
            "raw_stats": stats
        }
