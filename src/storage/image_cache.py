import os
import re
import logging
from pathlib import Path
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cache" / "logos"
TEAMS_DIR = CACHE_DIR / "teams"
TOURNAMENTS_DIR = CACHE_DIR / "tournaments"

TEAMS_DIR.mkdir(parents=True, exist_ok=True)
TOURNAMENTS_DIR.mkdir(parents=True, exist_ok=True)


class ImageCacheService:
    """
    Local On-Disk Image Cache Service for Football Crests & Competition Logos.
    Downloads images once and serves them locally to prevent redundant external API calls.
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
    }

    @staticmethod
    def _sanitize_id(identifier: str) -> str:
        return re.sub(r'[^a-zA-Z0-9_-]', '_', str(identifier))

    @classmethod
    async def get_or_download_team_logo(cls, team_id: Optional[str] = None, logo_url: Optional[str] = None) -> Optional[bytes]:
        """Fetch team logo from local disk cache, or download and store if missing."""
        key = cls._sanitize_id(team_id or logo_url or "team_default")
        local_file = TEAMS_DIR / f"{key}.png"
        
        if local_file.exists() and local_file.stat().st_size > 0:
            return local_file.read_bytes()

        url = logo_url
        if not url and team_id:
            # Extract numeric id if present
            digits = re.findall(r'\d+', str(team_id))
            tid = digits[0] if digits else team_id
            url = f"https://api.sofascore.app/api/v1/team/{tid}/image"

        if not url:
            return None

        try:
            async with httpx.AsyncClient(headers=cls.HEADERS, timeout=10.0) as client:
                resp = await client.get(url, follow_redirects=True)
                if resp.status_code == 200 and resp.content:
                    local_file.write_bytes(resp.content)
                    return resp.content
        except Exception as e:
            logger.debug(f"Could not download team logo {url}: {e}")

        return None

    @classmethod
    async def get_or_download_tournament_logo(cls, tournament_id: Optional[str] = None, logo_url: Optional[str] = None) -> Optional[bytes]:
        """Fetch tournament logo from local disk cache, or download and store if missing."""
        key = cls._sanitize_id(tournament_id or logo_url or "tourn_default")
        local_file = TOURNAMENTS_DIR / f"{key}.png"
        
        if local_file.exists() and local_file.stat().st_size > 0:
            return local_file.read_bytes()

        url = logo_url
        if not url and tournament_id:
            digits = re.findall(r'\d+', str(tournament_id))
            tid = digits[0] if digits else tournament_id
            url = f"https://api.sofascore.app/api/v1/unique-tournament/{tid}/image"

        if not url:
            return None

        try:
            async with httpx.AsyncClient(headers=cls.HEADERS, timeout=10.0) as client:
                resp = await client.get(url, follow_redirects=True)
                if resp.status_code == 200 and resp.content:
                    local_file.write_bytes(resp.content)
                    return resp.content
        except Exception as e:
            logger.debug(f"Could not download tournament logo {url}: {e}")

        return None
