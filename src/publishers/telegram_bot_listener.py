import asyncio
import io
import json
import logging
import os
from typing import Optional, Dict, Any, List
import httpx

from src.domain.models import CoverageProfile, Language, NewsVoiceStyle, MatchStatus
from src.engine.graphics_generator import GraphicsEngine
from src.storage.image_cache import ImageCacheService

logger = logging.getLogger(__name__)


class TelegramBotListener:
    """
    Interactive Telegram Bot Controller & Two-Way Command/Callback Processor.
    Listens for user commands (/status, /live, /track, /stats, /lineups) and
    processes interactive inline button callbacks (translation toggle, stats popup, card generator).
    """

    def __init__(self, monitor: Any, bot_token: Optional[str] = None):
        self.monitor = monitor
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.offset = 0
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token)

    async def start(self):
        """Start background Telegram bot polling loop."""
        if not self.is_configured:
            logger.warning("TelegramBotListener skipped: TELEGRAM_BOT_TOKEN not configured.")
            return
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_updates())
        logger.info("🤖 TelegramBotListener interactive command loop started.")

    async def stop(self):
        """Stop bot listener loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("🤖 TelegramBotListener stopped.")

    async def _poll_updates(self):
        """Async long-polling loop for Telegram getUpdates."""
        while self._running:
            try:
                url = f"{self.base_url}/getUpdates?offset={self.offset}&timeout=15"
                async with httpx.AsyncClient(timeout=25.0) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        updates = data.get("result", [])
                        for u in updates:
                            self.offset = max(self.offset, u.get("update_id", 0) + 1)
                            await self._handle_update(u)
                    elif resp.status_code == 429:
                        await asyncio.sleep(3.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Telegram listener poll error: {e}")
                await asyncio.sleep(3.0)

    async def _handle_update(self, update: Dict[str, Any]):
        """Route incoming message or callback query."""
        msg = (
            update.get("message")
            or update.get("channel_post")
            or update.get("edited_message")
            or update.get("edited_channel_post")
        )
        if msg:
            text = (msg.get("text") or msg.get("caption") or "").strip()
            chat_id = msg.get("chat", {}).get("id")
            if text.startswith("/") and chat_id:
                await self._handle_command(text, chat_id, msg)
        elif "callback_query" in update:
            cb = update["callback_query"]
            await self._handle_callback_query(cb)

    async def _handle_command(self, text: str, chat_id: int, msg: Dict[str, Any]):
        """Handle direct bot commands (/start, /status, /live, /track, /stats, /lineups, /nightshift)."""
        parts = text.split()
        cmd = parts[0].lower().replace("@football_post_bot", "")

        if cmd == "/start" or cmd.startswith("/start") or cmd in ("/help", "/list", "/commands"):
            help_text = (
                "⚽ <b>Pavilion Football Remote Desk Controller</b> 📡\n\n"
                "Welcome to the automated sports newsroom controller bot!\n\n"
                "<b>Available Commands:</b>\n"
                "• <code>/status</code> — Check active monitored matches & night shift state\n"
                "• <code>/live</code> — List top worldwide live matches with 1-tap track buttons\n"
                "• <code>/track &lt;match_id&gt;</code> — Arm a match on the remote desk\n"
                "• <code>/untrack &lt;match_id&gt;</code> — Stop tracking a match\n"
                "• <code>/stats &lt;match_id&gt;</code> — Pull live match statistics snapshot\n"
                "• <code>/lineups &lt;match_id&gt;</code> — Render Starting XI pitch tactical board\n"
                "• <code>/nightshift on|off</code> — Toggle autonomous night shift mode\n\n"
                "<i>Use the buttons below for quick actions:</i>"
            )
            keyboard = {
                "inline_keyboard": [
                    [{"text": "📊 ডেস্কে স্ট্যাটাস", "callback_data": "cmd_status"}, {"text": "⚽ লাইভ ম্যাচ তালিকা", "callback_data": "cmd_live"}],
                    [{"text": "🌙 নাইট শিফট টগল", "callback_data": "cmd_nightshift"}]
                ]
            }
            await self._send_message(chat_id, help_text, keyboard)

        elif cmd == "/status":
            await self._reply_status(chat_id)

        elif cmd == "/live":
            await self._reply_live_matches(chat_id)

        elif cmd == "/track":
            if len(parts) < 2:
                await self._send_message(chat_id, "❌ Usage: <code>/track &lt;match_id&gt;</code> (e.g. <code>/track 15526264</code>)")
                return
            m_id = parts[1]
            match = await self.monitor.provider.get_match_by_id(m_id)
            if not match:
                await self._send_message(chat_id, f"❌ Match <code>{m_id}</code> not found.")
                return
            self.monitor.add_match(match, coverage=CoverageProfile.STANDARD, auto_generate=True, auto_publish=True, lang=Language.BANGLA)
            await self._send_message(chat_id, f"✅ <b>Armed Match:</b> {match.home_team.name} vs {match.away_team.name} (ID: {m_id})")

        elif cmd == "/untrack":
            if len(parts) < 2:
                await self._send_message(chat_id, "❌ Usage: <code>/untrack &lt;match_id&gt;</code>")
                return
            m_id = parts[1]
            self.monitor.remove_match(m_id)
            await self._send_message(chat_id, f"✅ Removed match <code>{m_id}</code> from monitor roster.")

        elif cmd == "/nightshift":
            action = parts[1].lower() if len(parts) > 1 else ("off" if self.monitor.night_shift.active else "on")
            if action == "on":
                self.monitor.start_night_shift()
                await self._send_message(chat_id, "🌙 <b>Night Shift ACTIVATED</b> — Overnight autonomous desk is armed!")
            else:
                self.monitor.stop_night_shift()
                await self._send_message(chat_id, "☀️ <b>Night Shift DEACTIVATED</b>.")

        elif cmd == "/stats":
            m_id = parts[1] if len(parts) > 1 else (list(self.monitor.monitored_matches.keys())[0] if self.monitor.monitored_matches else None)
            if not m_id:
                await self._send_message(chat_id, "❌ No active matches tracked. Use <code>/stats &lt;match_id&gt;</code>")
                return
            await self._reply_stats(chat_id, m_id)

        elif cmd in ("/lineups", "/lineup"):
            m_id = parts[1] if len(parts) > 1 else (list(self.monitor.monitored_matches.keys())[0] if self.monitor.monitored_matches else None)
            if not m_id:
                await self._send_message(chat_id, "❌ Use <code>/lineups &lt;match_id&gt;</code>")
                return
            await self._reply_lineup_graphic(chat_id, m_id)

    async def _handle_callback_query(self, cb: Dict[str, Any]):
        """Handle inline button clicks."""
        cb_id = cb.get("id")
        data = cb.get("data", "")
        msg = cb.get("message", {})
        chat_id = msg.get("chat", {}).get("id")
        message_id = msg.get("message_id")

        await self._answer_callback(cb_id)

        if data == "cmd_status":
            await self._reply_status(chat_id)
        elif data == "cmd_live":
            await self._reply_live_matches(chat_id)
        elif data == "cmd_nightshift":
            if self.monitor.night_shift.active:
                self.monitor.stop_night_shift()
                await self._send_message(chat_id, "☀️ Night Shift turned OFF.")
            else:
                self.monitor.start_night_shift()
                await self._send_message(chat_id, "🌙 Night Shift turned ON!")

        elif data.startswith("track:"):
            m_id = data.split("track:")[-1]
            match = await self.monitor.provider.get_match_by_id(m_id)
            if match:
                self.monitor.add_match(match, coverage=CoverageProfile.STANDARD, auto_generate=True, auto_publish=True, lang=Language.BANGLA)
                await self._send_message(chat_id, f"✅ <b>Tracking Started:</b> {match.home_team.name} vs {match.away_team.name}")

        elif data.startswith("stats:"):
            m_id = data.split("stats:")[-1]
            await self._reply_stats(chat_id, m_id)

        elif data.startswith("lineup:"):
            m_id = data.split("lineup:")[-1]
            await self._reply_lineup_graphic(chat_id, m_id)

        elif data.startswith("card:"):
            m_id = data.split("card:")[-1]
            await self._reply_match_card(chat_id, m_id)

        elif data.startswith("toggle_lang:"):
            post_id = data.split("toggle_lang:")[-1]
            await self._toggle_post_language(chat_id, message_id, msg, post_id)

        elif data.startswith("delete_post"):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(f"{self.base_url}/deleteMessage", json={"chat_id": chat_id, "message_id": message_id})
            except Exception as e:
                logger.debug(f"Error deleting message: {e}")

    async def _reply_status(self, chat_id: int):
        ns_status = "🟢 ACTIVE (সক্রিয়)" if self.monitor.night_shift.active else "⚪ INACTIVE (নিষ্ক্রিয়)"
        tracked = list(self.monitor.monitored_matches.values())
        
        matches_lines = []
        for idx, m in enumerate(tracked, 1):
            score = f"{m.score.home}-{m.score.away}"
            matches_lines.append(f"{idx}. ⚽ <b>{m.home_team.name} vs {m.away_team.name}</b>\n   🏆 {m.tournament_name} | 📊 {score} | ⏱️ {m.status_detail}")

        tracked_text = "\n\n".join(matches_lines) if matches_lines else "<i>কোন ম্যাচ বর্তমানে ট্র্যাক করা হচ্ছে না।</i>"

        status_text = (
            f"📊 <b>রিমোট ডেস্ক মনিটর স্ট্যাটাস</b> 📡\n\n"
            f"🌙 <b>নাইট শিফট:</b> {ns_status}\n"
            f"🎯 <b>ট্র্যাক করা মোট ম্যাচ:</b> {len(tracked)}\n"
            f"📝 <b>মোট জেনারেট করা পোস্ট:</b> {len(self.monitor.generated_posts)}\n\n"
            f"<b>সক্রিয় ম্যাচ রস্টার:</b>\n{tracked_text}"
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": "🔄 রিফ্রেশ স্ট্যাটাস", "callback_data": "cmd_status"}, {"text": "⚽ লাইভ ম্যাচ খুঁজুন", "callback_data": "cmd_live"}]
            ]
        }
        await self._send_message(chat_id, status_text, keyboard)

    async def _reply_live_matches(self, chat_id: int):
        matches = await self.monitor.provider.get_live_matches()
        if not matches:
            await self._send_message(chat_id, "⚽ বর্তমানে কোন লাইভ ম্যাচ পাওয়া যায়নি।")
            return

        buttons = []
        text_lines = ["⚽ <b>চলতি শীর্ষ লাইভ ম্যাচসমূহ (Top Live Matches):</b>\n"]
        for m in matches[:6]:
            tracked_marker = " [✅ Tracked]" if m.id in self.monitor.monitored_matches else ""
            text_lines.append(f"• <b>{m.home_team.name} {m.score.home}-{m.score.away} {m.away_team.name}</b>{tracked_marker}\n  🏆 {m.tournament_name} (ID: <code>{m.id}</code>)")
            if m.id not in self.monitor.monitored_matches:
                buttons.append([{"text": f"+ Track {m.home_team.name[:12]} vs {m.away_team.name[:12]}", "callback_data": f"track:{m.id}"}])

        buttons.append([{"text": "📊 ডেস্কে স্ট্যাটাস", "callback_data": "cmd_status"}])
        keyboard = {"inline_keyboard": buttons}
        await self._send_message(chat_id, "\n".join(text_lines), keyboard)

    async def _reply_stats(self, chat_id: int, match_id: str):
        stats = await self.monitor.provider.get_match_statistics(match_id)
        match = await self.monitor.provider.get_match_by_id(match_id)
        if not match:
            await self._send_message(chat_id, f"❌ Match {match_id} data unavailable.")
            return

        h_name = match.home_team.name
        a_name = match.away_team.name
        score = f"{match.score.home} - {match.score.away}"
        
        stat_lines = []
        if stats:
            poss = stats.get("Ball possession", {})
            if poss:
                stat_lines.append(f"• <b>বল পজেশন:</b> {h_name} {poss.get("home", "50%")} - {poss.get("away", "50%")} {a_name}")
            shots = stats.get("Total shots", {})
            sot = stats.get("Shots on target", {})
            if shots:
                stat_lines.append(f"• <b>শট (অন টার্গেট):</b> {shots.get("home", "0")} ({sot.get("home", "0")}) - {shots.get("away", "0")} ({sot.get("away", "0")})")
            xg = stats.get("Expected goals", {})
            if xg:
                stat_lines.append(f"• <b>এক্সপেক্টেড গোলস (xG):</b> {xg.get("home", "0.0")} - {xg.get("away", "0.0")}")

        body = "\n".join(stat_lines) if stat_lines else "<i>ম্যাচ স্ট্যাটস এখনো আপডেট হচ্ছে...</i>"
        text = f"📈 <b>লাইভ ম্যাচ পরিসংখ্যান</b>\n⚽ <b>{h_name} {score} {a_name}</b>\n🏆 {match.tournament_name}\n\n{body}"
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "📋 শুরুর একাদশ", "callback_data": f"lineup:{match_id}"}, {"text": "🖼️ ম্যাচ কার্ড", "callback_data": f"card:{match_id}"}]
            ]
        }
        await self._send_message(chat_id, text, keyboard)

    async def _reply_lineup_graphic(self, chat_id: int, match_id: str):
        match = await self.monitor.provider.get_match_by_id(match_id)
        if not match:
            await self._send_message(chat_id, f"❌ Match {match_id} not found.")
            return

        card_bytes = await GraphicsEngine.render_lineup_card(match, {}, Language.BANGLA)
        caption = (
            f"📋 <b>শুরুর একাদশ ও ফরমেশন বোর্ড (Starting XI)</b>\n\n"
            f"⚽ <b>{match.home_team.name} vs {match.away_team.name}</b>\n"
            f"🏆 {match.tournament_name}\n\n"
            f"#Lineups #FootballNews #Pavilion"
        )
        await self._send_photo(chat_id, card_bytes, caption)

    async def _reply_match_card(self, chat_id: int, match_id: str):
        match = await self.monitor.provider.get_match_by_id(match_id)
        if not match:
            await self._send_message(chat_id, f"❌ Match {match_id} not found.")
            return

        events = await self.monitor.provider.get_match_events(match_id)
        stats = await self.monitor.provider.get_match_statistics(match_id)
        card_bytes = await GraphicsEngine.render_fulltime_card(match, events, stats, Language.BANGLA)
        caption = (
            f"🏁 <b>ম্যাচ স্কোরকার্ড গ্রাফিক (Match Scorecard)</b>\n\n"
            f"⚽ <b>{match.home_team.name} {match.score.home}-{match.score.away} {match.away_team.name}</b>\n"
            f"🏆 {match.tournament_name}\n\n"
            f"#Scorecard #FootballNews #Pavilion"
        )
        await self._send_photo(chat_id, card_bytes, caption)

    async def _toggle_post_language(self, chat_id: int, message_id: int, msg: Dict[str, Any], post_id: str):
        target_post = None
        for p in self.monitor.generated_posts:
            if p.post_id == post_id:
                target_post = p
                break

        if not target_post:
            return

        current_caption = msg.get("caption") or msg.get("text") or ""
        
        if target_post.english_translation and target_post.english_translation[:30] in current_caption:
            new_text = f"🚨 <b>{target_post.headline}</b>\n\n{target_post.content}\n\n#FootballNews #RemoteDesk"
        else:
            new_text = f"🚨 <b>{target_post.headline}</b>\n\n{target_post.english_translation or target_post.content}\n\n#FootballNews #RemoteDesk"

        keyboard = {
            "inline_keyboard": [
                [{"text": "🔁 বাংলা / English", "callback_data": f"toggle_lang:{post_id}"}, {"text": "📊 লাইভ স্ট্যাটস", "callback_data": f"stats:{target_post.match_id}"}],
                [{"text": "🖼️ স্কোরকার্ড", "callback_data": f"card:{target_post.match_id}"}, {"text": "❌ ডিলিট", "callback_data": "delete_post"}]
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if "caption" in msg:
                    await client.post(f"{self.base_url}/editMessageCaption", json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "caption": new_text,
                        "parse_mode": "HTML",
                        "reply_markup": keyboard
                    })
                else:
                    await client.post(f"{self.base_url}/editMessageText", json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "text": new_text,
                        "parse_mode": "HTML",
                        "reply_markup": keyboard
                    })
        except Exception as e:
            logger.debug(f"Error toggling language: {e}")

    async def _send_message(self, chat_id: int, text: str, reply_markup: Optional[Dict[str, Any]] = None):
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(url, json=payload)
        except Exception as e:
            logger.debug(f"Error sending bot message: {e}")

    async def _send_photo(self, chat_id: int, photo_bytes: bytes, caption: str):
        url = f"{self.base_url}/sendPhoto"
        files = {"photo": ("card.png", photo_bytes, "image/png")}
        data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.post(url, data=data, files=files)
        except Exception as e:
            logger.debug(f"Error sending bot photo: {e}")

    async def _answer_callback(self, callback_query_id: str):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(f"{self.base_url}/answerCallbackQuery", json={"callback_query_id": callback_query_id})
        except Exception:
            pass
