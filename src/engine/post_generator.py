import uuid
import logging
import urllib.parse
from typing import List, Optional, Dict
import httpx

from src.domain.events import DomainEvent, DomainEventType
from src.domain.models import Match, GeneratedPost, PostStatus, Language, NewsVoiceStyle, EventImportance
from src.config import TargetPlatform, settings

logger = logging.getLogger(__name__)

# Number translation map for Bangla digits
BANGLA_DIGITS = {
    '0': '০', '1': '১', '2': '২', '3': '৩', '4': '৪',
    '5': '৫', '6': '৬', '7': '৭', '8': '৮', '9': '৯'
}


def to_bangla_digits(text: str) -> str:
    """Convert western numerals to Bangla numerals."""
    res = []
    for ch in str(text):
        res.append(BANGLA_DIGITS.get(ch, ch))
    return "".join(res)


# Common team name transliterations into Bangla
TEAM_BANGLA_MAP = {
    "Arsenal": "আর্সেনাল",
    "Chelsea": "চেলসি",
    "Liverpool": "লিভারপুল",
    "Liverpool FC": "লিভারপুল",
    "Manchester City": "ম্যানচেস্টার সিটি",
    "Manchester United": "ম্যানচেস্টার ইউনাইটেড",
    "Real Madrid": "রিয়াল মাদ্রিদ",
    "Barcelona": "বার্সেলোনা",
    "Paris Saint-Germain": "পিএসজি",
    "Bayern Munich": "বায়ার্ন মিউনিখ",
    "Juventus": "জুভেন্টাস",
    "Inter": "ইন্টার মিলান",
    "AC Milan": "এসি মিলান",
    "Atletico Madrid": "অ্যাটলেটিকো মাদ্রিদ",
    "Borussia Dortmund": "বরুশিয়া ডর্টমুন্ড",
    "Ipswich Town": "ইপসউইচ টাউন",
    "Genoa": "জেনোয়া",
    "Como": "কোমো",
    "Real Betis": "রিয়াল বেটিস"
}


def get_team_name(team_name: str, lang: Language) -> str:
    if lang == Language.BANGLA:
        return TEAM_BANGLA_MAP.get(team_name, team_name)
    return team_name


class PostGenerator:
    """
    Pavilion News Desk Content Generator.
    Produces high-accuracy, newsroom-style sports posts in Bangla (বাংলা) and English.
    Template-first architecture ensures 0% hallucination and sub-millisecond execution.
    """

    def __init__(self, platform: TargetPlatform = TargetPlatform.FACEBOOK):
        self.platform = platform

    async def generate_post(
        self,
        event: DomainEvent,
        match: Match,
        importance: EventImportance = EventImportance.MUST_POST,
        lang: Optional[Language] = None,
        style: Optional[NewsVoiceStyle] = None,
        all_match_events: Optional[List[DomainEvent]] = None
    ) -> GeneratedPost:
        """Generate a sports news post for a verified match event."""
        from src.engine.commentary_enrichment import CommentaryEnricher
        target_lang = lang or match.language
        target_style = style or match.voice_style

        tactical_info = await CommentaryEnricher.enrich_incident_details(event, match)

        if target_lang == Language.BANGLA:
            headline, content = self._generate_bangla(event, match, target_style, tactical_info, all_match_events)
            english_copy = self._generate_english(event, match, target_style, tactical_info, all_match_events)[1]
        else:
            headline, content = self._generate_english(event, match, target_style, tactical_info, all_match_events)
            english_copy = content

        hashtags = [
            f"#{match.tournament_name.replace(' ', '')}",
            f"#{match.home_team.name.replace(' ', '')}",
            f"#{match.away_team.name.replace(' ', '')}",
            "#Pavilion",
            "#FootballNews"
        ]

        # Determine team logo for event
        event_team_logo = None
        if event.is_home_team is True and match.home_team.logo_url:
            event_team_logo = match.home_team.logo_url
        elif event.is_home_team is False and match.away_team.logo_url:
            event_team_logo = match.away_team.logo_url
        else:
            event_team_logo = match.home_team.logo_url or match.away_team.logo_url

        primary_image = event_team_logo or match.tournament_logo_url

        return GeneratedPost(
            post_id=f"post_{uuid.uuid4().hex[:8]}",
            event_id=event.event_id,
            match_id=match.id,
            platform=self.platform.value,
            language=target_lang,
            voice_style=target_style,
            importance=importance,
            headline=headline,
            content=content,
            image_url=primary_image,
            team_logo_url=event_team_logo,
            tournament_logo_url=match.tournament_logo_url,
            english_translation=english_copy,
            hashtags=hashtags,
            status=PostStatus.QUEUED_FOR_REVIEW,
            auto_published=match.auto_publish
        )

    def _generate_bangla(
        self,
        event: DomainEvent,
        match: Match,
        style: NewsVoiceStyle,
        tactical_info: Optional[Dict[str, Any]] = None,
        all_events: Optional[List[DomainEvent]] = None
    ) -> Tuple[str, str]:
        """Generate authentic Pavilion Bangla sports news copy with tactical commentary & full match reports."""
        h_name = get_team_name(match.home_team.name, Language.BANGLA)
        a_name = get_team_name(match.away_team.name, Language.BANGLA)
        tourn = match.tournament_name
        min_bn = to_bangla_digits(event.minute)
        score_bn = f"{to_bangla_digits(event.home_score)}-{to_bangla_digits(event.away_score)}"

        player = event.player_name or "অজ্ঞাত খেলোয়াড়"
        assist = event.secondary_player_name
        is_home = event.is_home_team if event.is_home_team is not None else True
        scoring_team = h_name if is_home else a_name

        tactical_bn = tactical_info.get("bangla_tactical") if tactical_info else None
        momentum_bn = tactical_info.get("lead_momentum_bn") if tactical_info else "দলের হয়ে লক্ষ্যভেদ করলেন"
        stats_bn = tactical_info.get("stats_bn_block") if tactical_info else ""

        stats_section = f"\n📈 লাইভ ম্যাচ স্ট্যাটস:\n{stats_bn}\n" if stats_bn else ""

        match_header = f"⚽ {h_name} বনাম {a_name} | 🏆 {tourn}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        if event.event_type == DomainEventType.GOAL:
            headline = f"🚨 ⚽ গোওওল! {scoring_team}-এর লিড! ({min_bn}')"
            tactical_snippet = f"🎙️ খেলার বিবরণ: {tactical_bn}\n\n" if tactical_bn else ""
            assist_line = f"👟 অ্যাসিস্ট: {assist}\n" if assist else ""

            if assist:
                lead_story = f"ম্যাচের {min_bn}তম মিনিটে {assist}-এর দুর্দান্ত পাস থেকে চমৎকার ফিনিশিংয়ে {scoring_team}-এর হয়ে {momentum_bn} {player}!"
            else:
                lead_story = f"ম্যাচের {min_bn}তম মিনিটে একক নৈপুণ্যে লক্ষ্যভেদ করে {scoring_team}-এর হয়ে {momentum_bn} {player}!"

            content = (
                f"{match_header}"
                f"⚽ গোওওল! {scoring_team}-এর দুর্দান্ত মুহূর্ত!\n\n"
                f"{lead_story}\n\n"
                f"{tactical_snippet}"
                f"📌 ম্যাচের তাৎক্ষণিক চিত্র:\n"
                f"⏱️ সময়: {min_bn} মিনিট\n"
                f"🎯 গোলদাতা: {player}\n"
                f"{assist_line}"
                f"📊 চলতি স্কোর: {h_name} {score_bn} {a_name}\n"
                f"🏆 টুর্নামেন্ট: {tourn}\n"
                f"{stats_section}\n"
                f"আজকের ম্যাচে শেষ পর্যন্ত কে হাসবে জয়ের হাসি? কমেন্টে জানান আপনার মতামত! ⚽🔥\n\n"
                f"প্যাভিলিয়ন স্পোর্টস ডেস্ক 🇧🇩"
            )

        elif event.event_type == DomainEventType.OWN_GOAL:
            headline = f"🤦 আত্মঘাতী গোল! বড় ধাক্কা খেল {scoring_team} ({min_bn}')"
            tactical_snippet = f"🎙️ খেলার বিবরণ: {tactical_bn}\n\n" if tactical_bn else ""
            content = (
                f"{match_header}"
                f"🤦 আত্মঘাতী গোলের বড় ধাক্কা!\n\n"
                f"ম্যাচের {min_bn}তম মিনিটে দুর্ভাগ্যের শিকার হলেন {player}। অসাবধানতাবশত নিজের জালেই বল জড়িয়ে দলকে বিপাকে ফেললেন তিনি।\n\n"
                f"{tactical_snippet}"
                f"📌 ম্যাচের চিত্র:\n"
                f"⏱️ সময়: {min_bn} মিনিট\n"
                f"📊 চলতি স্কোর: {h_name} {score_bn} {a_name}\n"
                f"🏆 টুর্নামেন্ট: {tourn}\n"
                f"{stats_section}\n"
                f"প্যাভিলিয়ন স্পোর্টস ডেস্ক 🇧🇩"
            )

        elif event.event_type in (DomainEventType.RED_CARD, DomainEventType.YELLOW_RED_CARD):
            card_team = h_name if is_home else a_name
            headline = f"🟥 লাল কার্ড! ১০ জনের দলে পরিণত হলো {card_team}! ({min_bn}')"
            reason_snippet = f"🎙️ ঘটনার কারণ: {tactical_bn}\n\n" if tactical_bn else ""
            content = (
                f"{match_header}"
                f"🟥 লাল কার্ডের চরম নাটকীয়তা!\n\n"
                f"ম্যাচের {min_bn}তম মিনিটে রেফারি সরাসরি লাল কার্ড দেখিয়ে মাঠ থেকে বের করে দিলেন {player}-কে। বাকি ম্যাচ ১০ জনের দল নিয়ে বড় পরীক্ষার মুখে পড়তে হচ্ছে {card_team}-কে।\n\n"
                f"{reason_snippet}"
                f"📌 ম্যাচের বর্তমান অবস্থা:\n"
                f"⏱️ সময়: {min_bn} মিনিট\n"
                f"📊 চলতি স্কোর: {h_name} {score_bn} {a_name}\n"
                f"🏆 টুর্নামেন্ট: {tourn}\n"
                f"{stats_section}\n"
                f"প্যাভিলিয়ন স্পোর্টস ডেস্ক 🇧🇩"
            )

        elif event.event_type == DomainEventType.YELLOW_CARD:
            headline = f"🟨 হলুদ কার্ড: সতর্ক করা হলো {player}-কে ({min_bn}')"
            reason_snippet = f"🎙️ কারণ: {tactical_bn}\n\n" if tactical_bn else ""
            content = (
                f"{match_header}"
                f"🟨 রেফারির কড়া সতর্কতা!\n\n"
                f"ম্যাচের {min_bn}তম মিনিটে ফাউল করে হলুদ কার্ড দেখলেন {player}।\n\n"
                f"{reason_snippet}"
                f"📊 চলতি স্কোর: {h_name} {score_bn} {a_name}\n"
                f"🏆 টুর্নামেন্ট: {tourn}"
            )

        elif event.event_type == DomainEventType.PENALTY_GOAL:
            headline = f"🎯 পেনাল্টি থেকে গোল! এগিয়ে গেল {scoring_team} ({min_bn}')"
            tactical_snippet = f"🎙️ বিবরণ: {tactical_bn}\n\n" if tactical_bn else ""
            content = (
                f"{match_header}"
                f"🎯 স্পট-কিক থেকে অনবদ্য গোল!\n\n"
                f"ম্যাচের {min_bn}তম মিনিটে পাওয়া পেনাল্টি কাজে লাগিয়ে অত্যন্ত ঠান্ডা মাথায় বল জালে জড়ালেন {player}!\n\n"
                f"{tactical_snippet}"
                f"📌 পেনাল্টি আপডেট:\n"
                f"⏱️ সময়: {min_bn} মিনিট\n"
                f"🎯 স্পট কিকার: {player}\n"
                f"📊 চলতি স্কোর: {h_name} {score_bn} {a_name}\n"
                f"🏆 টুর্নামেন্ট: {tourn}\n"
                f"{stats_section}\n"
                f"প্যাভিলিয়ন স্পোর্টস ডেস্ক 🇧🇩"
            )

        elif event.event_type == DomainEventType.VAR_OVERTURN:
            headline = f"📺 ভিএআর সিদ্ধান্তে বড় নাটকীয়তা! ({min_bn}')"
            detail = tactical_bn or event.description
            content = (
                f"{match_header}"
                f"📺 ভিডিও অ্যাসিস্ট্যান্ট রেফারি (VAR) হস্তক্ষেপ!\n\n"
                f"ম্যাচের {min_bn}তম মিনিটে ভিডিও পর্যালোচনার পর অন-ফিল্ড রেফারির সিদ্ধান্ত পরিবর্তন করা হয়েছে: {detail}।\n\n"
                f"📊 স্কোর: {h_name} {score_bn} {a_name}\n"
                f"🏆 টুর্নামেন্ট: {tourn}\n\n"
                f"প্যাভিলিয়ন স্পোর্টস ডেস্ক 🇧🇩"
            )

        elif event.event_type == DomainEventType.SUBSTITUTION:
            headline = f"🔄 ট্যাকটিকাল পরিবর্তন: {scoring_team} ({min_bn}')"
            content = (
                f"{match_header}"
                f"🔄 গুরুত্বপূর্ণ খেলোয়াড় বদল!\n\n"
                f"ম্যাচের {min_bn}তম মিনিটে {event.secondary_player_name}-এর জায়গায় মাঠে নামলেন {event.player_name}।\n\n"
                f"📊 চলতি স্কোর: {h_name} {score_bn} {a_name}\n"
                f"🏆 টুর্নামেন্ট: {tourn}"
            )

        elif event.event_type == DomainEventType.PERIOD_HALF_TIME:
            headline = f"⏸️ প্রথমার্ধের সমাপ্তি: {h_name} {score_bn} {a_name}"
            content = (
                f"{match_header}"
                f"⏸️ বিরতির বাঁশি বাজালেন রেফারি!\n\n"
                f"প্রথমার্ধের টানটান লড়াই শেষে স্কোরলাইন দাঁড়িয়েছে {h_name} {score_bn} {a_name}।\n\n"
                f"📊 বিরতির স্কোর: {h_name} {score_bn} {a_name}\n"
                f"🏆 টুর্নামেন্ট: {tourn}\n"
                f"{stats_section}\n"
                f"দ্বিতীয়ার্ধে কোন দল এগিয়ে থাকবে বলে মনে করছেন? কমেন্টে জানান! 👇\n\n"
                f"প্যাভিলিয়ন স্পোর্টস ডেস্ক 🇧🇩"
            )

        elif event.event_type in (DomainEventType.PERIOD_FULL_TIME, DomainEventType.MATCH_ENDED):
            # Detailed End-of-Match Match Report
            final_h_score = event.home_score
            final_a_score = event.away_score
            final_score_bn = f"{to_bangla_digits(final_h_score)}-{to_bangla_digits(final_a_score)}"

            if final_h_score > final_a_score:
                headline = f"🏁 শেষ বাঁশি! {h_name} {final_score_bn} {a_name} | {h_name}-এর জয়!"
                winner_text = f"🎉 দুর্দান্ত পারফরম্যান্সে পূর্ণ ৩ পয়েন্ট ছিনিয়ে নিল {h_name}!"
            elif final_a_score > final_h_score:
                headline = f"🏁 শেষ বাঁশি! {h_name} {final_score_bn} {a_name} | {a_name}-এর জয়!"
                winner_text = f"🎉 প্রতিপক্ষের মাঠে অসাধারণ জয় তুলে নিল {a_name}!"
            else:
                headline = f"🏁 শেষ বাঁশি! {h_name} {final_score_bn} {a_name} | রোমাঞ্চকর ড্র!"
                winner_text = "🤝 শ্বাসরুদ্ধকর লড়াই শেষে পয়েন্ট ভাগাভাগি করল দুই দল!"

            home_scorers = []
            away_scorers = []
            red_cards = []

            if all_events:
                for ev in all_events:
                    if ev.event_type in (DomainEventType.GOAL, DomainEventType.PENALTY_GOAL):
                        m_str = f"{to_bangla_digits(ev.minute)}'"
                        p = ev.player_name or "খেলোয়াড়"
                        if ev.is_home_team is True:
                            home_scorers.append(f"{p} ({m_str})")
                        elif ev.is_home_team is False:
                            away_scorers.append(f"{p} ({m_str})")
                    elif ev.event_type == DomainEventType.OWN_GOAL:
                        m_str = f"{to_bangla_digits(ev.minute)}'"
                        p = ev.player_name or "খেলোয়াড়"
                        if ev.is_home_team is True:
                            home_scorers.append(f"{p} [আত্মঘাতী] ({m_str})")
                        else:
                            away_scorers.append(f"{p} [আত্মঘাতী] ({m_str})")
                    elif ev.event_type in (DomainEventType.RED_CARD, DomainEventType.YELLOW_RED_CARD):
                        m_str = f"{to_bangla_digits(ev.minute)}'"
                        p = ev.player_name or "খেলোয়াড়"
                        t = h_name if ev.is_home_team else a_name
                        red_cards.append(f"{p} ({t}, {m_str})")

            scorers_section = ""
            if home_scorers or away_scorers:
                h_line = f"• {h_name}: {', '.join(home_scorers)}" if home_scorers else f"• {h_name}: গোল নেই"
                a_line = f"• {a_name}: {', '.join(away_scorers)}" if away_scorers else f"• {a_name}: গোল নেই"
                scorers_section = f"⚽ গোলদাতা:\n{h_line}\n{a_line}\n\n"

            red_section = f"🟥 লাল কার্ড: {', '.join(red_cards)}\n\n" if red_cards else ""

            content = (
                f"{match_header}"
                f"🏁 পূর্ণ ৯০ মিনিটের লড়াই শেষ!\n\n"
                f"{winner_text}\n\n"
                f"{scorers_section}"
                f"{red_section}"
                f"📊 চূড়ান্ত ফলাফল: {h_name} {final_score_bn} {a_name}\n"
                f"🏆 টুর্নামেন্ট: {tourn}\n"
                f"{stats_section}\n"
                f"আজকের ম্যাচটি কেমন উপভোগ করলেন? আপনার মতামত জানান কমেন্টে! ⚽🔥\n\n"
                f"প্যাভিলিয়ন স্পোর্টস ডেস্ক 🇧🇩"
            )
        else:
            headline = f"📢 ম্যাচের আপডেট ({min_bn}')"
            content = (
                f"{match_header}"
                f"📢 আপডেট: {event.description} ({min_bn}')\n\n"
                f"📊 স্কোর: {h_name} {score_bn} {a_name}\n"
                f"🏆 টুর্নামেন্ট: {tourn}"
            )

        return headline, content

    def _generate_english(
        self,
        event: DomainEvent,
        match: Match,
        style: NewsVoiceStyle,
        tactical_info: Optional[Dict[str, Any]] = None,
        all_events: Optional[List[DomainEvent]] = None
    ) -> Tuple[str, str]:
        """Generate crisp English newsroom post with tactical details & full match reports."""
        h_team = match.home_team.name
        a_team = match.away_team.name
        tourn = match.tournament_name
        score_str = f"{event.home_score}–{event.away_score}"
        min_str = f"{event.minute}'"

        player = event.player_name or "Unknown Player"
        assist = event.secondary_player_name
        is_home = event.is_home_team if event.is_home_team is not None else True
        scoring_team = h_team if is_home else a_team

        tactical_en = tactical_info.get("english_tactical") if tactical_info else None
        momentum_en = tactical_info.get("lead_momentum_en") if tactical_info else "found the back of the net"
        stats_en = tactical_info.get("stats_en_block") if tactical_info else ""

        stats_section = f"\n📈 Live Match Stats:\n{stats_en}\n" if stats_en else ""
        match_header = f"⚽ {h_team} vs {a_team} | 🏆 {tourn}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        if event.event_type == DomainEventType.GOAL:
            headline = f"🚨 ⚽ GOAL! {scoring_team} Take the Lead! ({min_str})"
            tactical_snippet = f"🎙️ Play Breakdown: {tactical_en}\n\n" if tactical_en else ""
            assist_line = f"👟 Assist: {assist}\n" if assist else ""

            if assist:
                lead_story = f"In the {min_str} minute, {player} {momentum_en} for {scoring_team}, brilliantly assisted by {assist}!"
            else:
                lead_story = f"In the {min_str} minute, {player} {momentum_en} for {scoring_team} with a clinical strike!"

            content = (
                f"{match_header}"
                f"⚽ GOAL! A decisive breakthrough for {scoring_team}!\n\n"
                f"{lead_story}\n\n"
                f"{tactical_snippet}"
                f"📌 Match Facts:\n"
                f"⏱️ Minute: {min_str}\n"
                f"🎯 Goalscorer: {player}\n"
                f"{assist_line}"
                f"📊 Current Score: {h_team} {score_str} {a_team}\n"
                f"🏆 Competition: {tourn}\n"
                f"{stats_section}\n"
                f"Who takes all 3 points from here? Drop your thoughts below! ⚽🔥\n\n"
                f"Pavilion Sports Desk 🇬🇧"
            )

        elif event.event_type == DomainEventType.OWN_GOAL:
            headline = f"🤦 OWN GOAL! Disaster for {scoring_team} ({min_str})"
            tactical_snippet = f"🎙️ Incident: {tactical_en}\n\n" if tactical_en else ""
            content = (
                f"{match_header}"
                f"🤦 OWN GOAL DRAMA!\n\n"
                f"A devastating moment in the {min_str} minute as {player} unfortunately turns the ball into their own net.\n\n"
                f"{tactical_snippet}"
                f"📌 Match Situation:\n"
                f"⏱️ Minute: {min_str}\n"
                f"📊 Current Score: {h_team} {score_str} {a_team}\n"
                f"🏆 Competition: {tourn}\n"
                f"{stats_section}\n"
                f"Pavilion Sports Desk 🇬🇧"
            )

        elif event.event_type in (DomainEventType.RED_CARD, DomainEventType.YELLOW_RED_CARD):
            card_team = h_team if is_home else a_team
            headline = f"🟥 RED CARD! {card_team} Down to 10 Men! ({min_str})"
            reason_snippet = f"🎙️ Reason: {tactical_en}\n\n" if tactical_en else ""
            content = (
                f"{match_header}"
                f"🟥 MAJOR MATCH DRAMA!\n\n"
                f"The referee shows a straight red card to {player} in the {min_str} minute! {card_team} must battle the rest of the game with 10 players.\n\n"
                f"{reason_snippet}"
                f"📌 Match Situation:\n"
                f"⏱️ Minute: {min_str}\n"
                f"📊 Current Score: {h_team} {score_str} {a_team}\n"
                f"🏆 Competition: {tourn}\n"
                f"{stats_section}\n"
                f"Pavilion Sports Desk 🇬🇧"
            )

        elif event.event_type == DomainEventType.PERIOD_HALF_TIME:
            headline = f"⏸️ HALF-TIME: {h_team} {score_str} {a_team}"
            content = (
                f"{match_header}"
                f"⏸️ HALF-TIME whistle blows!\n\n"
                f"A competitive 45 minutes of football comes to an end with the scoreline standing at {h_team} {score_str} {a_team}.\n\n"
                f"📊 Score at the break: {h_team} {score_str} {a_team}\n"
                f"🏆 Competition: {tourn}\n"
                f"{stats_section}\n"
                f"Drop your second half predictions below! 👇\n\n"
                f"Pavilion Sports Desk 🇬🇧"
            )

        elif event.event_type in (DomainEventType.PERIOD_FULL_TIME, DomainEventType.MATCH_ENDED):
            final_h_score = event.home_score
            final_a_score = event.away_score
            final_score_str = f"{final_h_score}–{final_a_score}"

            if final_h_score > final_a_score:
                headline = f"🏁 FULL-TIME: {h_team} {final_score_str} {a_team} | Victory for {h_team}!"
                winner_text = f"🎉 Full 3 points secured in emphatic fashion by {h_team}!"
            elif final_a_score > final_h_score:
                headline = f"🏁 FULL-TIME: {h_team} {final_score_str} {a_team} | Victory for {a_team}!"
                winner_text = f"🎉 A fantastic away performance seals the victory for {a_team}!"
            else:
                headline = f"🏁 FULL-TIME: {h_team} {final_score_str} {a_team} | Points Shared!"
                winner_text = "🤝 It ends all square after 90 intense minutes of football!"

            home_scorers = []
            away_scorers = []
            red_cards = []

            if all_events:
                for ev in all_events:
                    if ev.event_type in (DomainEventType.GOAL, DomainEventType.PENALTY_GOAL):
                        m_str = f"{ev.minute}'"
                        p = ev.player_name or "Player"
                        if ev.is_home_team is True:
                            home_scorers.append(f"{p} ({m_str})")
                        elif ev.is_home_team is False:
                            away_scorers.append(f"{p} ({m_str})")
                    elif ev.event_type == DomainEventType.OWN_GOAL:
                        m_str = f"{ev.minute}'"
                        p = ev.player_name or "Player"
                        if ev.is_home_team is True:
                            home_scorers.append(f"{p} [OG] ({m_str})")
                        else:
                            away_scorers.append(f"{p} [OG] ({m_str})")
                    elif ev.event_type in (DomainEventType.RED_CARD, DomainEventType.YELLOW_RED_CARD):
                        m_str = f"{ev.minute}'"
                        p = ev.player_name or "Player"
                        t = h_team if ev.is_home_team else a_team
                        red_cards.append(f"{p} ({t}, {m_str})")

            scorers_section = ""
            if home_scorers or away_scorers:
                h_line = f"• {h_team}: {', '.join(home_scorers)}" if home_scorers else f"• {h_team}: None"
                a_line = f"• {a_team}: {', '.join(away_scorers)}" if away_scorers else f"• {a_team}: None"
                scorers_section = f"⚽ Goalscorers:\n{h_line}\n{a_line}\n\n"

            red_section = f"🟥 Red Cards: {', '.join(red_cards)}\n\n" if red_cards else ""

            content = (
                f"{match_header}"
                f"🏁 FULL-TIME! The referee blows the final whistle.\n\n"
                f"{winner_text}\n\n"
                f"{scorers_section}"
                f"{red_section}"
                f"📊 Final Score: {h_team} {final_score_str} {a_team}\n"
                f"🏆 Competition: {tourn}\n"
                f"{stats_section}\n"
                f"What was your standout moment of the match? Share your thoughts below! 👇\n\n"
                f"Pavilion Sports Desk 🇬🇧"
            )
        else:
            headline = f"📢 Match Update ({min_str})"
            content = (
                f"{match_header}"
                f"📢 Update: {event.description} ({min_str})\n\n"
                f"📊 Score: {h_team} {score_str} {a_team}\n"
                f"🏆 Competition: {tourn}"
            )

        return headline, content

    @staticmethod
    async def translate_text(text: str, source_lang: str = "auto", target_lang: str = "bn") -> str:
        """Free Google Translate endpoint utility for dynamic post translation."""
        try:
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source_lang}&tl={target_lang}&dt=t&q={urllib.parse.quote(text)}"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    translated_chunks = [item[0] for item in data[0] if item and item[0]]
                    return "".join(translated_chunks)
        except Exception as e:
            logger.warning(f"Translation failed: {e}")
        return text
