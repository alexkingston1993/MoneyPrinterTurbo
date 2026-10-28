"""
YouTube upload automation for the Investing, Not Trading channel.

Supports 3 channels (English, Tamil, Hindi) via YouTube Data API v3.
OAuth 2.0 authentication with token persistence and auto-refresh.
Also supports service account authentication for server-side uploads.
"""

import base64
import datetime
import json
import os
import pickle
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as SACredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from loguru import logger

from app.config import config

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
TOKEN_DIR = os.path.join(DATA_DIR, "youtube_tokens")
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


CHANNEL_LANGUAGES = {
    "en": {"name": "The Compounder", "desc": "English"},
    "ta": {"name": "The Compounder Tamil", "desc": "Tamil"},
    "hi": {"name": "The Compounder Hindi", "desc": "Hindi"},
}

DEFAULT_CATEGORY = "22"  # "People & Blogs"
DEFAULT_PRIVACY = "public"  # public, unlisted, private

SHORTS_TAGS_MAP = {
    "insurance": ["#HealthInsurance", "#TermInsurance", "#IRDAI", "#PersonalFinanceIndia", "#TheBullPrint", "#shorts"],
    "crypto": ["#Bitcoin", "#CryptoIndia", "#OnChainAnalysis", "#CryptoTaxIndia", "#TheBullPrint", "#shorts"],
    "stock_market": ["#Nifty50", "#BankNifty", "#InstitutionalOrderFlow", "#StockMarketIndia", "#TheBullPrint", "#shorts"],
}
LONGFORM_TAGS_MAP = {
    "insurance": ["#HealthInsurance", "#TermInsurance", "#IRDAI", "#PersonalFinanceIndia", "#TheBullPrint", "#InsuranceClaims", "#ConsumerProtection"],
    "crypto": ["#Bitcoin", "#CryptoIndia", "#OnChainAnalysis", "#CryptoTaxIndia", "#Section115BBH", "#PerpetualFutures", "#TheBullPrint"],
    "stock_market": ["#Nifty50", "#BankNifty", "#InstitutionalOrderFlow", "#StockMarketIndia", "#OptionsTrading", "#FIIFlows", "#TheBullPrint"],
}
SHORTS_TAGS = ["#shorts", "#investing", "#stockmarketindia", "#nifty", "#sensex"]
LONGFORM_TAGS = [
    "#investing", "#stockmarketindia", "#nifty", "#sensex",
    "#longterminvesting", "#financialeducation", "#personalfinance",
]


def sanitize_clean_title(title: str) -> str:
    """Strips debug slot tags, dates, and part numbers to enforce clean, human-written viral titles."""
    if not title:
        return ""
    cleaned = re.sub(r"\s*\(\s*\d{1,2}\s+[A-Za-z]+\s+\d{4}\s+Slot\s*#\d+\s*\)", "", title, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*\(?\s*Slot\s*#\d+\s*\)?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*\(\s*\d{1,2}\s+[A-Za-z]+\s+\d{4}\s*\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*-\s*Slot\s*#\d+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*#\s*Slot\s*#\d+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def detect_vertical_from_content(title: str, description: str = "") -> str:
    """Classifies the true vertical based on title and description keywords."""
    combined = f"{title} {description}".lower()
    if any(k in combined for k in ["insurance", "claim", "icr", "csr", "policy", "irdai", "hospital", "term plan", "sub-limit", "proportional deduction"]):
        return "insurance"
    if any(k in combined for k in ["crypto", "bitcoin", "btc", "on-chain", "115bbh", "194s", "swap", "liquidation", "token", "usdt", "eth", "funding rate"]):
        return "crypto"
    return "stock_market"


def get_video_duration_seconds(video_path: str) -> float:
    """Inspects video container duration via ffprobe with robust fallback."""
    import subprocess
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", video_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except Exception as e:
        logger.warning(f"ffprobe duration check failed for {video_path}: {e}")
        return 0.0



def _token_path(language: str) -> str:
    os.makedirs(TOKEN_DIR, exist_ok=True)
    return os.path.join(TOKEN_DIR, f"youtube_token_{language}.pickle")


def _client_secrets_path(language: str) -> str:
    return os.path.join(TOKEN_DIR, f"client_secrets_{language}.json")


def _service_account_path(language: str) -> str:
    return os.path.join(TOKEN_DIR, f"service_account_{language}.json")


class YouTubeUploader:
    """Upload videos to YouTube channels via Data API v3."""

    def __init__(self):
        self.services: Dict[str, any] = {}

    def _get_service_account_credentials(self, language: str):
        """Try to authenticate via service account JSON key."""
        sa_path = _service_account_path(language)
        if not os.path.exists(sa_path):
            return None
        try:
            with open(sa_path) as f:
                sa_info = json.load(f)
            creds = SACredentials.from_service_account_info(sa_info, scopes=SCOPES)
            return creds
        except Exception as e:
            logger.warning(f"failed to load service account for {language}: {e}")
            return None

    def _get_service(self, language: str):
        """Get or create an authenticated YouTube API service for a channel.
        Tries raw env credentials (YT_CLIENT_ID/SECRET/REFRESH_TOKEN) first,
        then base64 pickle env, then local pickle file, then service account key."""
        if language in self.services:
            return self.services[language]

        creds = None

        # 1. Direct Cloud Secrets: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
        client_id = os.getenv(f"YT_CLIENT_ID_{language.upper()}") or os.getenv("YT_CLIENT_ID")
        client_secret = os.getenv(f"YT_CLIENT_SECRET_{language.upper()}") or os.getenv("YT_CLIENT_SECRET")
        refresh_token = os.getenv(f"YT_REFRESH_TOKEN_{language.upper()}") or os.getenv("YT_REFRESH_TOKEN")

        if client_id and client_secret and refresh_token:
            try:
                creds = Credentials(
                    token=None,
                    refresh_token=refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=client_id,
                    client_secret=client_secret,
                    scopes=SCOPES
                )
                creds.refresh(Request())
                logger.info(f"✓ Authenticated YouTube API via direct OAuth refresh token for {language}")
            except Exception as e:
                logger.warning(f"Failed to refresh YouTube direct OAuth credentials for {language}: {e}")
                creds = None

        # 2. Base64 Cloud Secret: YOUTUBE_TOKEN_<LANG> (e.g. YOUTUBE_TOKEN_EN)
        if not creds:
            b64_env = os.getenv(f"YOUTUBE_TOKEN_{language.upper()}")
            if b64_env:
                try:
                    raw_bytes = base64.b64decode(b64_env)
                    creds = pickle.loads(raw_bytes)
                    logger.info(f"Loaded YouTube credentials from base64 env for {language}")
                except Exception as e:
                    logger.warning(f"Failed to parse base64 YOUTUBE_TOKEN_{language.upper()}: {e}")

        # 3. Local token pickle file
        token_file = _token_path(language)
        if not creds and os.path.exists(token_file):
            try:
                with open(token_file, "rb") as f:
                    creds = pickle.load(f)
            except Exception as e:
                logger.warning(f"failed to load token for {language}: {e}")

        # 4. Auto-refresh if token is expired
        if creds and (creds.expired or not creds.valid or not creds.token) and creds.refresh_token:
            try:
                creds.refresh(Request())
                if os.path.exists(token_file):
                    try:
                        with open(token_file, "wb") as f:
                            pickle.dump(creds, f)
                    except Exception:
                        pass
                logger.info(f"refreshed token for {language}")
            except Exception as e:
                logger.warning(f"failed to refresh token for {language} (invalid_grant or network): {e}")
                creds = None

        # 5. Fallback to service account
        if not creds or not creds.valid:
            creds = self._get_service_account_credentials(language)

        if not creds or not creds.valid:
            logger.warning(
                f"no valid token for {language}. "
                f"Set YT_REFRESH_TOKEN / YOUTUBE_TOKEN_{language.upper()} in env, "
                f"or place token at {token_file}"
            )
            return None

        try:
            service = build("youtube", "v3", credentials=creds)
            self.services[language] = service
            return service
        except Exception as e:
            logger.error(f"failed to build YouTube service for {language}: {e}")
            return None

    def auth_setup(self, language: str):
        """Run OAuth 2.0 authorization flow for a channel.

        Requires a client_secrets_{language}.json file in the tokens directory.
        Get this from Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client IDs.
        """
        secrets_file = _client_secrets_path(language)
        if not os.path.exists(secrets_file):
            logger.error(
                f"client secrets not found: {secrets_file}. "
                f"Create an OAuth 2.0 client ID in Google Cloud Console "
                f"(Desktop app type) and save it here."
            )
            return False

        flow = InstalledAppFlow.from_client_secrets_file(secrets_file, SCOPES)
        creds = flow.run_console()

        token_file = _token_path(language)
        with open(token_file, "wb") as f:
            pickle.dump(creds, f)

        logger.success(f"OAuth setup complete for {language}. Token saved to {token_file}")
        return True

    def is_authenticated(self, language: str) -> bool:
        """Check if a channel has a valid token."""
        service = self._get_service(language)
        return service is not None

    def verify(self, language: str) -> bool:
        """Verify the token works by calling the channels.list API."""
        service = self._get_service(language)
        if not service:
            return False

        try:
            response = service.channels().list(part="snippet", mine=True).execute()
            items = response.get("items", [])
            if items:
                channel = items[0]
                logger.info(
                    f"[{language}] Authenticated as: {channel['snippet']['title']} "
                    f"({channel['snippet']['customUrl']})"
                )
                return True
            else:
                logger.warning(f"[{language}] No channel found for this account")
                return False
        except HttpError as e:
            logger.error(f"[{language}] Verification failed: {e}")
            return False

    @staticmethod
    def _normalize_title(text: str) -> str:
        """Case-insensitive, punctuation-insensitive title fingerprint."""
        return " ".join(re.sub(r"[^\w\s]+", " ", str(text or "").lower()).split())

    def _load_credential_pool(self) -> List[Dict]:
        """
        Multi-Project Quota Rotator: every distinct OAuth slot the channel can use.
        Sources (deduplicated case-insensitively by client_id):
          1) YT_OAUTH_POOL_JSON     -> JSON list of {client_id, client_secret, refresh_token}
          2) YT_CLIENT_ID[_N]/YT_CLIENT_SECRET[_N]/YT_REFRESH_TOKEN[_N] (1..6 + raw)
          3) YOUTUBE_TOKEN_<LANG>[_N] base64 pickles
          4) local data/youtube_tokens/youtube_token_*.pickle files
        Slots matching the primary (cached-service) credential are dropped so the
        rotation loop only spends time on genuinely different Google Cloud projects.
        """
        slots: List[Dict] = []

        pool_json = os.getenv("YT_OAUTH_POOL_JSON")
        if pool_json:
            try:
                parsed = json.loads(pool_json)
                if isinstance(parsed, dict):
                    parsed = [parsed]
                for s in parsed:
                    if s.get("client_id") and s.get("client_secret") and s.get("refresh_token"):
                        slots.append({"client_id": s["client_id"], "client_secret": s["client_secret"],
                                      "refresh_token": s["refresh_token"], "source": "YT_OAUTH_POOL_JSON"})
            except Exception as e:
                logger.warning(f"YT_OAUTH_POOL_JSON unparsable: {e}")

        for suffix in ("", "1", "2", "3", "4", "5", "6"):
            variants = ((f"YT_CLIENT_ID{suffix}", f"YT_CLIENT_SECRET{suffix}", f"YT_REFRESH_TOKEN{suffix}"),) if not suffix else (
                (f"YT_CLIENT_ID{suffix}", f"YT_CLIENT_SECRET{suffix}", f"YT_REFRESH_TOKEN{suffix}"),
                (f"YT_CLIENT_ID_{suffix}", f"YT_CLIENT_SECRET_{suffix}", f"YT_REFRESH_TOKEN_{suffix}"),
            )
            for cid_v, cse_v, rt_v in variants:
                cid, cse, rt = os.getenv(cid_v), os.getenv(cse_v), os.getenv(rt_v)
                if cid and cse and rt:
                    slots.append({"client_id": cid, "client_secret": cse, "refresh_token": rt, "source": cid_v})
                    break

        for i in range(1, 6):
            lang_key = (os.getenv("PIPELINE_LANGUAGE", "en") or "en").upper()
            env_name = f"YOUTUBE_TOKEN_{lang_key}" if i == 1 else f"YOUTUBE_TOKEN_{lang_key}_{i}"
            b64_env = os.getenv(env_name)
            if b64_env:
                try:
                    obj = pickle.loads(base64.b64decode(b64_env))
                    if isinstance(obj, dict) and "credentials" in obj:
                        obj = obj["credentials"]
                    slot = {"client_id": obj.get("client_id"), "client_secret": obj.get("client_secret"),
                            "refresh_token": obj.get("refresh_token"), "source": env_name}
                    if all(slot.values()) and slot not in slots:
                        slots.append(slot)
                except Exception as e:
                    logger.warning(f"{env_name} decode failed: {e}")

        for p in sorted(Path(TOKEN_DIR).glob("youtube_token_*.pickle")):
            try:
                obj = pickle.loads(p.read_bytes())
                if isinstance(obj, dict) and "credentials" in obj:
                    obj = obj["credentials"]
                slot = {"client_id": obj.get("client_id"), "client_secret": obj.get("client_secret"),
                        "refresh_token": obj.get("refresh_token"), "source": f"pickle:{p.name}"}
                if all(slot.values()) and slot not in slots:
                    slots.append(slot)
            except Exception:
                continue

        seen, unique = set(), []
        for s in slots:
            key = (s["client_id"] or "").lower()
            if key and key not in seen:
                seen.add(key)
                unique.append(s)
        return unique

    @staticmethod
    def _is_quota_error(exc: Exception) -> bool:
        """True when the error is retryable-offline by rotating to another project slot."""
        text = str(exc)
        return any(
            marker in text
            for marker in ("quotaExceeded", "dailyLimitExceeded", "uploadLimitExceeded", "rateLimitExceeded", "invalid_grant", "invalidCredentials")
        )

    def _find_recent_duplicate(self, language: str, title: str, window_hours: int = 24) -> Optional[str]:
        """
        Idempotency guard against overlapping schedulers / workflow retries.
        Pass A: channel uploads playlist scan (freshest & cheapest).
        Pass B: search.list(forMine=True) fallback (covers delayed playlist indexing
        after fast overlapping runs). A same-title upload inside the 24h window
        returns the EXISTING video_id instead of uploading a duplicate copy.
        """
        service = self._get_service(language)
        if not service:
            return None

        normalized = self._normalize_title(title)
        if not normalized:
            return None
        prefix_match = normalized[:60]
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=window_hours)

        candidates: List[Tuple[str, str, str]] = []

        # Pass A: uploads playlist (up to 25 most recent)
        try:
            channel_res = service.channels().list(mine=True, part="contentDetails").execute()
            uploads_pl = channel_res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
            recent_items = service.playlistItems().list(
                playlistId=uploads_pl, part="snippet", maxResults=25
            ).execute().get("items", [])
            for item in recent_items:
                snippet = item.get("snippet", {})
                candidates.append((
                    snippet.get("resourceId", {}).get("videoId", ""),
                    snippet.get("title", ""),
                    snippet.get("publishedAt", ""),
                ))
        except Exception as e:
            logger.debug(f"[{language}] Duplicate playlist scan notice: {e}")

        # Pass B: search.list forMine (up to 15 most recent by date)
        try:
            found = service.search().list(
                part="snippet", forMine=True, type="video", maxResults=15, order="date"
            ).execute().get("items", [])
            for item in found:
                snippet = item.get("snippet", {})
                candidates.append((
                    item.get("id", {}).get("videoId", ""),
                    snippet.get("title", ""),
                    snippet.get("publishTime", ""),
                ))
        except Exception as e:
            logger.debug(f"[{language}] Duplicate search.scan notice: {e}")

        seen: set = set()
        for video_id, video_title, published_at in candidates:
            if not video_id or video_id in seen:
                continue
            seen.add(video_id)
            norm = self._normalize_title(video_title)
            if not published_at or not (norm == normalized or norm[:60] == prefix_match):
                continue
            try:
                when = datetime.datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
                if when >= cutoff:
                    return video_id
            except Exception:
                continue
        return None

    def upload_video(
        self,
        language: str,
        video_path: str,
        title: str,
        description: str = "",
        tags: Optional[List[str]] = None,
        category_id: str = DEFAULT_CATEGORY,
        privacy_status: str = DEFAULT_PRIVACY,
        is_short: bool = False,
        thumbnail_path: Optional[str] = None,
        publish_at: Optional[str] = None,
    ) -> Dict:
        """Upload a video to YouTube.

        Args:
            language: Channel language code (en, ta, hi)
            video_path: Path to the video file
            title: Video title (max 100 chars)
            description: Video description
            tags: List of tags
            category_id: YouTube category ID
            privacy_status: public, unlisted, or private
            is_short: If True, adds #shorts tag
            thumbnail_path: Optional path to custom thumbnail image
            publish_at: Optional RFC 3339 datetime string (e.g. 2026-10-24T14:00:00Z) to schedule publishing

        Returns:
            dict: Upload result with video_id, status, url
        """
        service = self._get_service(language)
        if not service and not self._load_credential_pool():
            return {"success": False, "error": f"Not authenticated for {language}"}

        if not os.path.exists(video_path):
            return {"success": False, "error": f"Video not found: {video_path}"}

        # 1. Clean title: strip debug slot/date tags
        title = sanitize_clean_title(title)

        # 2. Hard Pre-Upload Quarantine Gate:
        # Long-form videos MUST be >= 480 seconds (8 minutes)
        if not is_short:
            dur = get_video_duration_seconds(video_path)
            if dur > 0 and dur < 480.0:
                logger.error(
                    f"🚨 [HARD QUARANTINE GATE TRIGGERED] Long-form video '{title}' duration is {dur:.1f}s (< 480s / 8 min)! "
                    f"ABORTING UPLOAD to protect channel from YouTube repetitive/low-effort penalties."
                )
                return {
                    "success": False,
                    "error": f"QUARANTINE_GATE_TRIGGERED: duration {dur:.1f}s < 480s (8 min)",
                    "quarantined": True,
                    "duration": dur,
                }

        # 3. Detect vertical & tailor tags / description
        vertical = detect_vertical_from_content(title, description)
        video_tags = list(tags or [])
        target_tags_map = SHORTS_TAGS_MAP if is_short else LONGFORM_TAGS_MAP
        default_vert_tags = target_tags_map.get(vertical, target_tags_map["stock_market"])
        for t in default_vert_tags:
            if t not in video_tags:
                video_tags.append(t)

        channel_name = CHANNEL_LANGUAGES.get(language, {}).get("name", "The Bull Print")

        # Vertical-accurate hashtag footer
        if vertical == "insurance":
            footer_hashtags = "#TheBullPrint #HealthInsurance #TermInsurance #IRDAI #PersonalFinanceIndia #InsuranceClaims #ConsumerProtection"
        elif vertical == "crypto":
            footer_hashtags = "#TheBullPrint #Bitcoin #CryptoIndia #CryptoTaxIndia #Section115BBH #OnChainData #PerpetualFutures"
        else:
            footer_hashtags = "#TheBullPrint #Nifty50 #BankNifty #StockMarketIndia #OptionsTrading #FIIFlows #InstitutionalTrading"

        full_description = (
            f"{description}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 Official Portal & Research Dossiers:\n"
            f"https://thebullprint.in\n"
            f"(Data models, Actuarial/On-Chain/Order-flow matrices & Calculators)\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚖️ MANDATORY SEBI / IRDAI REGULATORY DISCLAIMER & RISK WARNING\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"1. NOT A SEBI REGISTERED FINANCIAL ADVISER / RESEARCH ANALYST:\n"
            f"The creator of The Bull Print is NOT registered with the Securities and Exchange Board of India (SEBI) "
            f"as an Investment Adviser (under SEBI IA Regulations, 2013) or as a Research Analyst (under SEBI RA Regulations, 2014).\n\n"
            f"2. STRICTLY FOR EDUCATIONAL & RESEARCH PURPOSES:\n"
            f"This video and market breakdown are produced strictly for educational, informational, and financial literacy purposes. "
            f"Nothing stated in this video constitutes financial, investment, legal, or tax advice.\n\n"
            f"3. ZERO BUY / SELL / HOLD CALLS OR RECOMMENDATIONS:\n"
            f"We NEVER provide stock tips, buy/sell recommendations, price targets, or guaranteed return claims. "
            f"All commentary represents historical price action, mathematical observations, and personal perspectives "
            f"('What I personally observe / what data shows' — NEVER 'What you should trade or buy').\n\n"
            f"4. HIGH CAPITAL RISK IN DERIVATIVES (F&O TRADING):\n"
            f"Trading in Equity Derivatives (Futures and Options) involves substantial leverage and severe capital risk. "
            f"According to SEBI's official research study, 9 out of 10 individual retail traders in equity derivatives incur net financial losses. "
            f"Past performance does not guarantee future results. Consult a qualified, SEBI-registered financial professional.\n\n"
            f"5. AFFILIATE & COMMERCIAL DISCLOSURE:\n"
            f"Links to platforms may be partner/affiliate links that provide commissions at zero extra cost to you. "
            f"These affiliations do not influence our independent educational analysis.\n\n"
            f"{footer_hashtags}"
        )

        effective_privacy = "private" if publish_at else privacy_status
        body = {
            "snippet": {
                "title": title[:100],
                "description": full_description[:5000],
                "tags": video_tags[:500],
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": effective_privacy,
                "selfDeclaredMadeForKids": False,
            },
        }
        if publish_at:
            body["status"]["publishAt"] = publish_at


        # Prevent duplicate uploads: same normalized title on the channel within 24h
        try:
            existing_video_id = self._find_recent_duplicate(language, title, window_hours=24)
        except Exception as dup_err:
            logger.debug(f"[{language}] Duplicate upload check notice: {dup_err}")
            existing_video_id = None

        if existing_video_id:
            existing_url = f"https://youtu.be/{existing_video_id}"
            logger.warning(
                f"[{language}] Duplicate title detected on channel within 24h — SKIPPING upload, returning existing video: {existing_url}"
            )
            return {
                "success": True,
                "video_id": existing_video_id,
                "url": existing_url,
                "title": title[:100],
                "language": language,
                "already_existed": True,
            }

        # Multi-Project Quota Rotator: attempt the upload on each OAuth slot in turn.
        # Slot 1 re-uses the already-authenticated primary service; every further slot is a
        # distinct Google Cloud project rounded-robin on quotaExceeded/invalid_grant.
        pool = self._load_credential_pool()
        logger.info(f"[{language}] Credential pool: {len(pool)} alternate OAuth slot(s) loaded")

        attempts: List[Tuple[int, Optional[Dict]]] = [(1, None)]
        attempts.extend((i + 2, slot) for i, slot in enumerate(pool))

        last_error = "unknown"
        for slot_index, slot in attempts:
            try:
                if slot is None:
                    service = self._get_service(language)
                    if not service:
                        if attempts[1:] and slot_index == 1:
                            last_error = f"No primary credentials for {language} — skipping to pool slots"
                            logger.warning(f"[{language}] no primary credentials — attempting {len(pool)} pool slot(s)")
                            continue
                        raise RuntimeError(last_error)
                else:
                    logger.info(f"🔑 [Slot #{slot_index}] rotating upload to fresh Google Cloud project ({slot['source']})")
                    creds = Credentials(
                        token=None,
                        refresh_token=slot["refresh_token"],
                        token_uri="https://oauth2.googleapis.com/token",
                        client_id=slot["client_id"],
                        client_secret=slot["client_secret"],
                        scopes=SCOPES,
                    )
                    creds.refresh(Request())
                    service = build("youtube", "v3", credentials=creds)

                logger.info(f"[{language}] Uploading: {title[:60]}... ({os.path.getsize(video_path)/1024/1024:.1f}MB)")

                media = MediaFileUpload(video_path, chunksize=1024 * 1024, resumable=True)
                request = service.videos().insert(
                    part="snippet,status",
                    body=body,
                    media_body=media,
                )

                response = None
                last_progress = 0
                while response is None:
                    status, response = request.next_chunk()
                    if status:
                        progress = int(status.progress() * 100)
                        if progress - last_progress >= 10:
                            logger.info(f"[{language}] Upload progress: {progress}%")
                            last_progress = progress

                video_id = response.get("id")
                video_url = f"https://youtu.be/{video_id}"

                logger.success(f"[{language}] Uploaded (Slot #{slot_index}): {video_url}")

                # Upload thumbnail if provided
                if thumbnail_path and os.path.exists(thumbnail_path):
                    try:
                        service.thumbnails().set(
                            videoId=video_id,
                            media_body=MediaFileUpload(thumbnail_path),
                        ).execute()
                        logger.info(f"[{language}] Thumbnail set for {video_id}")
                    except HttpError as e:
                        logger.warning(f"[{language}] Thumbnail upload failed: {e}")

                return {
                    "success": True,
                    "video_id": video_id,
                    "url": video_url,
                    "title": title[:100],
                    "language": language,
                    "publish_at": publish_at,
                    "scheduled": bool(publish_at),
                    "oauth_slot_used": slot_index,
                }

            except Exception as e:
                last_error = str(e)
                if self._is_quota_error(e) and slot_index < attempts[-1][0]:
                    logger.warning(
                        f"⚠️ YouTube API Slot #{slot_index} exhausted — rotating to Slot #{slot_index + 1} ({type(e).__name__})"
                    )
                    continue
                logger.error(f"[{language}] Upload failed: {last_error}")
                return {"success": False, "error": last_error}

        logger.error(f"[{language}] All {len(attempts)} OAuth slot(s) exhausted: {last_error}")
        quota_note = "YouTube API quota exceeded on every available slot. Try again tomorrow (or add more pool slots)."
        return {"success": False, "error": quota_note, "detail": last_error}

    def upload_multilanguage(
        self,
        videos: Dict[str, Dict],
        is_short: bool = False,
        privacy_status: str = DEFAULT_PRIVACY,
    ) -> Dict[str, Dict]:
        """Upload videos for all available languages.

        Args:
            videos: Dict mapping language -> {video_path, title, description, tags, thumbnail_path}
            is_short: Whether these are Shorts
            privacy_status: public, unlisted, private

        Returns:
            dict: language -> upload result
        """
        results = {}
        for lang, info in videos.items():
            logger.info(f"\n--- Uploading [{lang}] video ---")
            result = self.upload_video(
                language=lang,
                video_path=info.get("video_path", ""),
                title=info.get("title", "Investing, Not Trading"),
                description=info.get("description", ""),
                tags=info.get("tags"),
                is_short=is_short,
                privacy_status=privacy_status,
                thumbnail_path=info.get("thumbnail_path"),
            )
            results[lang] = result
            if result.get("success"):
                logger.success(f"[{lang}] → {result['url']}")
            else:
                logger.warning(f"[{lang}] → FAILED: {result.get('error')}")

            # Small delay between uploads to avoid quota issues
            if len(videos) > 1:
                time.sleep(2)

        return results

    def append_article_link_to_description(self, language: str, video_id: str, article_url: str, article_title: str) -> bool:
        """Append the published website article link to the YouTube video description for backlinks."""
        # Ironclad privacy failsafe: never expose GitHub repository or blob URLs to public viewers
        if not article_url or "github.com" in article_url:
            article_url = "https://the-bull-print.vercel.app"

        service = self._get_service(language)
        if not service:
            return False
        try:
            # 1. Fetch current video snippet
            response = service.videos().list(part="snippet", id=video_id).execute()
            items = response.get("items", [])
            if not items:
                return False
            
            snippet = items[0]["snippet"]
            current_desc = snippet.get("description", "")
            
            # Clean any existing leaked github urls in description
            if "github.com" in current_desc:
                current_desc = re.sub(r"https?://github\.com/\S+", "https://the-bull-print.vercel.app", current_desc)

            # 2. Append link if not already present
            if article_url not in current_desc:
                cta_block = (
                    f"\n\n📊 IN-DEPTH FINANCIAL REPORT & DATA TABLES:\n"
                    f"Read full breakdown for '{article_title}':\n"
                    f"👉 {article_url}\n"
                )
                snippet["description"] = (cta_block + current_desc)[:5000]
                
                # 3. Update video
                service.videos().update(
                    part="snippet",
                    body={"id": video_id, "snippet": snippet}
                ).execute()
                logger.info(f"[{language}] Successfully updated YouTube description with article link: {article_url}")
                return True
            return True
        except Exception as e:
            logger.warning(f"[{language}] Failed to append article link to YouTube description: {e}")
            return False

    def post_pinned_comment(self, language: str, video_id: str, comment_text: str) -> bool:
        """Post a single top comment on the video with strict idempotency and deduplication."""
        # Ironclad privacy failsafe: never expose GitHub URLs in public comments
        if "github.com" in comment_text:
            comment_text = re.sub(r"https?://github\.com/\S+", "https://thebullprint.in", comment_text)

        service = self._get_service(language)
        if not service:
            return False
        try:
            # 1. Fetch our own channel ID
            channel_id = None
            try:
                ch_resp = service.channels().list(mine=True, part="id").execute()
                channel_id = ch_resp.get("items", [{}])[0].get("id")
            except Exception:
                pass

            # 2. Check existing top-level comments
            existing_threads = []
            try:
                threads_resp = service.commentThreads().list(
                    part="snippet", videoId=video_id, maxResults=50
                ).execute()
                existing_threads = threads_resp.get("items", [])
            except Exception as list_err:
                logger.debug(f"[{language}] commentThreads.list notice for {video_id}: {list_err}")

            # Filter for comments authored by our channel
            own_comments = []
            for t in existing_threads:
                top = t.get("snippet", {}).get("topLevelComment", {})
                author_ch = top.get("snippet", {}).get("authorChannelId", {}).get("value")
                if author_ch and author_ch == channel_id:
                    own_comments.append(top)

            # If our channel already has comments:
            if own_comments:
                first_comment = own_comments[0]
                first_id = first_comment.get("id")
                # Delete any extra duplicate comments
                for dup in own_comments[1:]:
                    dup_id = dup.get("id")
                    if dup_id:
                        try:
                            service.comments().delete(id=dup_id).execute()
                            logger.info(f"[{language}] Deleted duplicate creator comment {dup_id} on {video_id}")
                        except Exception as del_err:
                            logger.warning(f"Failed to delete duplicate comment {dup_id}: {del_err}")

                # Update the first comment in-place if text changed
                existing_text = first_comment.get("snippet", {}).get("textOriginal", "")
                if existing_text != comment_text and first_id:
                    try:
                        service.comments().update(
                            part="snippet",
                            body={"id": first_id, "snippet": {"textOriginal": comment_text}}
                        ).execute()
                        logger.info(f"[{language}] Updated existing creator comment in-place on {video_id}")
                    except Exception as upd_err:
                        logger.warning(f"Failed to update comment in-place: {upd_err}")
                return True

            # If 0 comments by our channel, insert new one
            service.commentThreads().insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId": video_id,
                        "topLevelComment": {
                            "snippet": {
                                "textOriginal": comment_text
                            }
                        }
                    }
                }
            ).execute()
            logger.info(f"[{language}] Pinned creator comment posted on video {video_id}")
            return True
        except Exception as e:
            logger.warning(f"[{language}] Failed to post comment on video {video_id}: {e}")
            return False



# Singleton
_uploader: Optional[YouTubeUploader] = None


def get_uploader() -> YouTubeUploader:
    global _uploader
    if _uploader is None:
        _uploader = YouTubeUploader()
    return _uploader
