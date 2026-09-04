import os
import logging
from pathlib import Path
from typing import Optional
import httpx
from src.domain.models import GeneratedPost

logger = logging.getLogger(__name__)


def _load_env_file():
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

_load_env_file()


class TelegramPublisher:
    """
    Automated Telegram Channel & Group Publisher.
    Dispatches newsroom posts directly to Telegram channels via Telegram Bot API.
    """

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        _load_env_file()
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self.timeout = 10.0

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    async def send_post(self, post: GeneratedPost, custom_card_bytes: Optional[bytes] = None) -> bool:
        """Send formatted post with HD graphic card or logo and interactive action buttons to Telegram."""
        if not self.is_configured:
            logger.warning("Telegram publisher skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured.")
            return False

        # Format message with headline and body
        message_text = f"🚨 <b>{post.headline}</b>\n\n{post.content}\n\n#FootballNews #RemoteDesk"

        # Interactive Inline Keyboard
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "🔁 বাংলা / English", "callback_data": f"toggle_lang:{post.post_id}"},
                    {"text": "📊 লাইভ স্ট্যাটস", "callback_data": f"stats:{post.match_id}"}
                ],
                [
                    {"text": "🖼️ ম্যাচ কার্ড", "callback_data": f"card:{post.match_id}"},
                    {"text": "❌ ডিলিট", "callback_data": "delete_post"}
                ]
            ]
        }

        # Try sending as photo with caption if custom graphic or logo is available
        img_bytes = custom_card_bytes
        img_url = post.image_url or post.team_logo_url or post.tournament_logo_url

        if not img_bytes and img_url:
            try:
                from src.storage.image_cache import ImageCacheService
                if "/api/logos/team/" in img_url:
                    t_id = img_url.split("/api/logos/team/")[-1].split("?")[0]
                    img_bytes = await ImageCacheService.get_or_download_team_logo(t_id)
                elif "/api/logos/tournament/" in img_url:
                    tourn_id = img_url.split("/api/logos/tournament/")[-1].split("?")[0]
                    img_bytes = await ImageCacheService.get_or_download_tournament_logo(tourn_id)
            except Exception as e:
                logger.debug(f"Image resolution error: {e}")

        photo_url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
        if img_bytes:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    files = {"photo": ("graphic.png", img_bytes, "image/png")}
                    data = {
                        "chat_id": self.chat_id,
                        "caption": message_text,
                        "parse_mode": "HTML",
                        "reply_markup": json.dumps(reply_markup)
                    }
                    response = await client.post(photo_url, data=data, files=files)
                    if response.status_code == 200:
                        logger.info(f"✅ [Telegram Photo Published] Post {post.post_id} dispatched to chat {self.chat_id}")
                        return True
                    elif response.status_code == 429:
                        retry_after = float(response.json().get("parameters", {}).get("retry_after", 2))
                        import asyncio
                        await asyncio.sleep(retry_after)
                        retry_resp = await client.post(photo_url, data=data, files=files)
                        if retry_resp.status_code == 200:
                            logger.info(f"✅ [Telegram Photo Published (Retried)] Post {post.post_id}")
                            return True
            except Exception as e:
                logger.warning(f"Telegram photo dispatch error ({e}), falling back to text message")

        # Fallback to standard text message with inline keyboard
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
            "reply_markup": reply_markup
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                if response.status_code == 200:
                    logger.info(f"✅ [Telegram Published] Post {post.post_id} dispatched to chat {self.chat_id}")
                    return True
                elif response.status_code == 429:
                    retry_after = float(response.json().get("parameters", {}).get("retry_after", 2))
                    import asyncio
                    await asyncio.sleep(retry_after)
                    retry_resp = await client.post(url, json=payload)
                    if retry_resp.status_code == 200:
                        logger.info(f"✅ [Telegram Published (Retried)] Post {post.post_id}")
                        return True
                logger.error(f"❌ Telegram send failed (HTTP {response.status_code}): {response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ Error sending Telegram message: {e}")
            return False

    async def send_tracking_alert(self, match: "Match", tracked: bool = True) -> bool:
        """Send instant match tracking confirmation alert with logos to Telegram channel."""
        if not self.is_configured:
            return False

        cov_value = match.coverage.value if hasattr(match.coverage, "value") else str(match.coverage)
        cov_labels = {
            "FULL": "🔴 Full Coverage (সবকিছু: গোল, কার্ড, ভার, সাবস)",
            "STANDARD": "🟡 Standard Coverage (প্রধান ঘটনা: গোল, রেড কার্ড, ভার)",
            "RESULT_ONLY": "🟢 Result Only (গোল ও ফলাফল)"
        }
        cov_name = cov_labels.get(cov_value, "🟡 Standard")
        lang_str = "🇧🇩 বাংলা (Bangla)" if (getattr(match, 'language', 'bn') == 'bn' or str(getattr(match, 'language', 'bn')) == 'Language.BANGLA') else "🇬🇧 English"
        auto_pub_str = "✅ সক্রিয় (Direct to Telegram)" if match.auto_publish else "📝 রিভিউ কিউ (Manual Review)"

        if tracked:
            text = (
                f"📋 <b>ম্যাচ ট্র্যাকিং কনফার্মেশন</b> 📡\n\n"
                f"⚽ <b>{match.home_team.name} vs {match.away_team.name}</b>\n"
                f"🏆 <b>টুর্নামেন্ট:</b> {match.tournament_name}\n"
                f"🎛️ <b>কভারেজ লেভেল:</b> {cov_name}\n"
                f"🚀 <b>টেলিগ্রাম ডিসপ্যাচ:</b> {auto_pub_str}\n"
                f"🌐 <b>পোস্টের ভাষা:</b> {lang_str}\n"
                f"⏱️ <b>স্ট্যাটাস:</b> {match.status_detail}\n\n"
                f"<i>এই ম্যাচের লাইভ আপডেট স্বয়ংক্রিয়ভাবে রিমোট ডেস্কে পর্যবেক্ষণ করা হবে।</i>"
            )
        else:
            text = (
                f"✕ <b>ম্যাচ ট্র্যাকিং বাতিল করা হয়েছে</b>\n\n"
                f"⚽ <b>{match.home_team.name} vs {match.away_team.name}</b>\n"
                f"🏆 {match.tournament_name}\n\n"
                f"<i>এই ম্যাচটি মনিটরিং রস্টার থেকে সরিয়ে দেওয়া হয়েছে।</i>"
            )

        # If team/tournament logo is available, send as photo with caption
        logo_to_send = match.home_team.logo_url or match.tournament_logo_url or match.away_team.logo_url
        if logo_to_send and tracked:
            photo_url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
            try:
                from src.storage.image_cache import ImageCacheService
                img_bytes = None
                if "/api/logos/team/" in logo_to_send:
                    t_id = logo_to_send.split("/api/logos/team/")[-1].split("?")[0]
                    img_bytes = await ImageCacheService.get_or_download_team_logo(t_id)
                elif "/api/logos/tournament/" in logo_to_send:
                    tourn_id = logo_to_send.split("/api/logos/tournament/")[-1].split("?")[0]
                    img_bytes = await ImageCacheService.get_or_download_tournament_logo(tourn_id)

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    if img_bytes:
                        files = {"photo": ("crest.png", img_bytes, "image/png")}
                        data = {"chat_id": self.chat_id, "caption": text, "parse_mode": "HTML"}
                        res = await client.post(photo_url, data=data, files=files)
                    else:
                        photo_payload = {
                            "chat_id": self.chat_id,
                            "photo": logo_to_send,
                            "caption": text,
                            "parse_mode": "HTML"
                        }
                        res = await client.post(photo_url, json=photo_payload)
                    if res.status_code == 200:
                        return True
            except Exception as e:
                logger.warning(f"Telegram photo tracking alert error ({e}), falling back to text")

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"❌ Error sending tracking alert: {e}")
            return False

    async def send_nightshift_alert(self, active: bool, matches_info: list) -> bool:
        """Send Remote Desk arm/disarm status with list of tracked matches."""
        if not self.is_configured:
            return False

        if active:
            lines = [f"• ⚽ <b>{m.get('name')}</b> — {m.get('cov')}" for m in matches_info]
            matches_text = "\n".join(lines) if lines else "<i>(কোনো ম্যাচ এখনও সিলেক্ট করা হয়নি)</i>"
            text = (
                f"📡 <b>রিমোট ডেস্ক সক্রিয় করা হয়েছে! (Remote Desk Armed)</b> ⚽\n\n"
                f"📋 <b>মোট অ্যাক্টিভ রস্টার:</b> {len(matches_info)}টি ম্যাচ\n"
                f"{matches_text}\n\n"
                f"<i>ম্যাচগুলোর লাইভ আপডেট সরাসরি এই চ্যানেলে পাঠানো হবে।</i>"
            )
        else:
            text = "☀️ <b>রিমোট ডেস্ক মনিটরিং বন্ধ করা হয়েছে। (Remote Desk Disarmed)</b>"

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"❌ Error sending nightshift alert: {e}")
            return False

    async def test_connection(self) -> dict:
        """Test bot credentials and channel connectivity."""
        if not self.is_configured:
            return {"status": "error", "message": "Bot token or Chat ID is missing."}

        url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    bot_data = res.json().get("result", {})
                    return {
                        "status": "success",
                        "bot_name": bot_data.get("first_name"),
                        "bot_username": bot_data.get("username"),
                        "chat_id": self.chat_id
                    }
                else:
                    return {"status": "error", "message": f"Invalid bot token (HTTP {res.status_code})"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

