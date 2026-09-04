import os
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
    def get_team_logo_path(team_id: str) -> Path:
        return TEAMS_DIR / f"{team_id}.png"

    @staticmethod
    def get_tournament_logo_path(tournament_id: str) -> Path:
        return TOURNAMENTS_DIR / f"{tournament_id}.png"

    @classmethod
    async def get_or_download_team_logo(cls, team_id: str) -> Optional[bytes]:
        """Fetch team logo from local disk cache, or download and store if missing."""
        if not team_id:
            return None

        local_file = cls.get_team_logo_path(team_id)
        if local_file.exists() and local_file.stat().st_size > 0:
            return local_file.read_bytes()

        url = f"https://api.sofascore.app/api/v1/team/{team_id}/image"
        try:
            async with httpx.AsyncClient(headers=cls.HEADERS, timeout=10.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200 and resp.content:
                    local_file.write_bytes(resp.content)
                    logger.info(f"💾 Cached team logo locally: team {team_id} ({len(resp.content)} bytes)")
                    return resp.content
        except Exception as e:
            logger.debug(f"Could not download team logo {team_id}: {e}")

        return None

    @classmethod
    async def get_or_download_tournament_logo(cls, tournament_id: str) -> Optional[bytes]:
        """Fetch tournament logo from local disk cache, or download and store if missing."""
        if not tournament_id:
            return None

        local_file = cls.get_tournament_logo_path(tournament_id)
        if local_file.exists() and local_file.stat().st_size > 0:
            return local_file.read_bytes()

        url = f"https://api.sofascore.app/api/v1/unique-tournament/{tournament_id}/image"
        try:
            async with httpx.AsyncClient(headers=cls.HEADERS, timeout=10.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200 and resp.content:
                    local_file.write_bytes(resp.content)
                    logger.info(f"💾 Cached tournament logo locally: tournament {tournament_id} ({len(resp.content)} bytes)")
                    return resp.content
        except Exception as e:
            logger.debug(f"Could not download tournament logo {tournament_id}: {e}")

        return None
