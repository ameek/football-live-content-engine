import os
import json
import logging
from typing import Optional, Dict, Any, List
import httpx

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Prioritize 500 Requests-Per-Day tier (Gemini 3.5 Flash Lite) to maximize free usage
MODELS_TO_TRY = ["gemini-3.5-flash-lite", "gemini-flash-lite-latest"]


class GeminiEnricher:
    """
    Google AI Studio (Gemini) Sports Newsroom Copilot.
    Enriches posts with journalistic Bengali & English prose, tactical insights, and match reports.
    Guaranteed zero-drop fail-safe to deterministic templates.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", GEMINI_API_KEY)

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    async def _call_gemini(self, prompt: str, timeout: float = 3.5) -> Optional[str]:
        """Make a resilient async call to Google AI Studio REST API across available models."""
        if not self.is_available:
            return None

        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": self.api_key
        }
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 800
            }
        }

        for model in MODELS_TO_TRY:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    res = await client.post(endpoint, headers=headers, json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                return parts[0].get("text", "").strip()
            except Exception as e:
                logger.debug(f"Gemini {model} call skipped: {e}")
                continue

        return None

    async def enrich_incident_narrative(
        self,
        event_type: str,
        team_name: str,
        opponent_name: str,
        score: str,
        minute: int,
        player_name: str,
        assist_name: Optional[str],
        momentum_phrase: str,
        tactical_desc: Optional[str],
        lang: str = "bn"
    ) -> Optional[Dict[str, str]]:
        """
        Generate rich, journalistic Bengali/English headlines and lead paragraphs.
        Returns dict with {"headline": "...", "lead_paragraph": "..."} or None on fallback.
        """
        if not self.is_available:
            return None

        target_lang = "Bengali (বাংলা)" if lang == "bn" else "English"
        prompt = (
            f"You are a Senior Football Journalist at a top sports desk (Pavilion Sports).\n"
            f"Write a sports news update in {target_lang}.\n\n"
            f"Match Event Details:\n"
            f"- Event: {event_type}\n"
            f"- Match: {team_name} vs {opponent_name}\n"
            f"- Minute: {minute}'\n"
            f"- Hero/Player: {player_name}\n"
            f"- Assist/Provider: {assist_name or 'Solo effort'}\n"
            f"- Current Scoreline: {score}\n"
            f"- Scoreline Momentum Context: {momentum_phrase}\n"
            f"- Tactical/Commentary snippet: {tactical_desc or 'N/A'}\n\n"
            f"Requirements:\n"
            f"1. Headline: 10-15 words max, exciting and punchy with breaking sports emojis.\n"
            f"2. Lead Narrative: 2-3 engaging sentences describing the goal/incident with authentic football emotion and tactical flair.\n"
            f"3. Return ONLY valid JSON with keys \"headline\" and \"lead_paragraph\" without markdown code blocks:\n"
            f'{{"headline": "...", "lead_paragraph": "..."}}'
        )

        raw = await self._call_gemini(prompt, timeout=3.0)
        if not raw:
            return None

        try:
            clean_json = raw.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(clean_json)
            if "headline" in parsed and "lead_paragraph" in parsed:
                return parsed
        except Exception:
            pass
        return None

    async def generate_match_report(
        self,
        home_team: str,
        away_team: str,
        tournament: str,
        score: str,
        events_summary: List[str],
        stats_summary: Dict[str, Any],
        lang: str = "bn"
    ) -> Optional[str]:
        """
        Generate a comprehensive 300-word post-match editorial report.
        """
        if not self.is_available:
            return None

        events_text = "\n".join(f"- {e}" for e in events_summary) if events_summary else "No major incidents recorded."
        target_lang = "Bengali (বাংলা)" if lang == "bn" else "English"
        prompt = (
            f"You are a Lead Sports Columnist.\n"
            f"Write a full post-match editorial report (around 250-350 words) in {target_lang}.\n\n"
            f"Match: {home_team} {score} {away_team}\n"
            f"Tournament: {tournament}\n\n"
            f"Key Incidents:\n{events_text}\n\n"
            f"Stats: {json.dumps(stats_summary, ensure_ascii=False)}\n\n"
            f"Structure:\n"
            f"1. Engaging Title\n"
            f"2. Paragraph 1: Match wrap-up & how the game unfolded.\n"
            f"3. Paragraph 2: Tactical masterclass, turning point, and key standout player.\n"
            f"4. Paragraph 3: Significance of this result on the tournament table.\n\n"
            f"Write with journalistic authority and authentic sports terminology."
        )

        return await self._call_gemini(prompt, timeout=4.5)

global_gemini_enricher = GeminiEnricher()
