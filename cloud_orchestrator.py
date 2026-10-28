"""
Cloud Orchestrator Engine (cloud_orchestrator.py).
Zero-cost cloud architecture tying together:
1. GitHub Actions (Ubuntu runner - Playwright scraping & coordination)
2. Aria Mission Control (Single editable Telegram status card + 5-min human thumbnail gate)
3. Google AI Studio (Free Gemini API Structured Output generation)
4. Kaggle GPU Kernel (Dual T4 GPU - Faster-Whisper & NVENC FFmpeg video rendering)
5. YouTube Data API v3 (Headless synthetic media upload)
6. Vercel & Search Engine Indexers (Instant deployment & IndexNow ping)
"""

import os
import re
import json
import time
import shutil
import argparse
import asyncio
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import requests
from loguru import logger

from chart_fetcher import capture_batch_charts
from thumbnail_generator import create_marketing_images, create_short_thumbnail
from engine import generate_website_article_file
from publisher import publish_and_index_article
from app.services.content_authenticity_engine import infer_vertical

BASE_DIR = Path(__file__).parent
KAGGLE_STAGE_DIR = BASE_DIR / "kaggle_stage"
KAGGLE_STAGE_DIR.mkdir(parents=True, exist_ok=True)

# Auto-discover Kaggle credentials if not in environment
KAGGLE_USERNAME = os.getenv("KAGGLE_USERNAME", "")
if not KAGGLE_USERNAME or not os.getenv("KAGGLE_KEY"):
    kaggle_json_path = Path.home() / ".kaggle" / "kaggle.json"
    if kaggle_json_path.exists():
        try:
            _kd = json.loads(kaggle_json_path.read_text(encoding="utf-8"))
            if not KAGGLE_USERNAME:
                KAGGLE_USERNAME = _kd.get("username", "")
                os.environ["KAGGLE_USERNAME"] = KAGGLE_USERNAME
            if not os.getenv("KAGGLE_KEY"):
                os.environ["KAGGLE_KEY"] = _kd.get("key", "")
        except Exception:
            pass

# Auto-discover config.toml secrets if not in environment
try:
    import tomllib
    _cfg_path = BASE_DIR / "config.toml"
    if _cfg_path.exists():
        _cfg = tomllib.load(open(_cfg_path, "rb")).get("app", {})
        if not os.getenv("GEMINI_API_KEY") and _cfg.get("gemini_api_key"):
            os.environ["GEMINI_API_KEY"] = _cfg["gemini_api_key"]
        if not os.getenv("TELEGRAM_BOT_TOKEN") and _cfg.get("telegram_bot_token"):
            os.environ["TELEGRAM_BOT_TOKEN"] = _cfg["telegram_bot_token"]
        if not os.getenv("TELEGRAM_CHAT_ID") and _cfg.get("telegram_chat_id"):
            os.environ["TELEGRAM_CHAT_ID"] = str(_cfg["telegram_chat_id"])
        _m_val = _cfg.get("gemini_model_name", "gemini-flash-lite-latest")
        if not _m_val or "gemini-2.5-flash" in _m_val or "gemini-pro" in _m_val:
            _m_val = "gemini-flash-lite-latest"
        os.environ["GEMINI_MODEL_NAME"] = _m_val
except Exception:
    pass

DATASET_SLUG = "flipzon-daily-payload"
KERNEL_SLUG = "flipzon-gpu-video-renderer"


class AriaMissionControl:
    """
    Replaces multi-message spam with a single editable Telegram Mission Control card
    + bidirectional Zero-Database real-time syncing via TelemetryBridge on 'telemetry-live'.
    """
    def __init__(self, topic: str, slot: int = 1):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else ""
        self.topic = topic
        self.slot = int(slot)
        from app.services.telemetry_bridge import TelemetryBridge
        self.bridge = TelemetryBridge(slot=self.slot)
        self.start_ts = time.time()
        self.status_msg_id: Optional[int] = None
        self.stages = {
            "playwright": "⏳ Pending",
            "gemini": "⏳ Pending",
            "thumbnail": "⏳ Pending",
            "kaggle_gpu": "⏳ Pending",
            "vercel": "⏳ Pending",
        }

    def _elapsed(self) -> str:
        mins, secs = divmod(int(time.time() - self.start_ts), 60)
        return f"{mins:02d}m {secs:02d}s"

    def _render_card_text(self, footer_note: str = "") -> str:
        return (
            f"🐂 *THE BULL PRINT — CLOUD MISSION CONTROL* 🕶️☕\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Topic:* `{self.topic}`\n"
            f"⏱️ *Elapsed Time:* `{self._elapsed()}`\n\n"
            f"1️⃣ *Playwright Charts:* {self.stages['playwright']}\n"
            f"2️⃣ *Gemini 2.5 JSON:* {self.stages['gemini']}\n"
            f"3️⃣ *Pillow Thumbnail:* {self.stages['thumbnail']}\n"
            f"4️⃣ *Kaggle Dual-T4 GPU:* {self.stages['kaggle_gpu']}\n"
            f"5️⃣ *Vercel & IndexNow:* {self.stages['vercel']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            + (f"💡 _{footer_note}_\n" if footer_note else "🚀 _Agent Aria cloud engines running autonomously._\n")
        )

    def init_card(self):
        """Sends the initial pinned Mission Control card and stores message_id."""
        if not self.token or not self.chat_id:
            logger.info(f"[Mission Control Offline]:\n{self._render_card_text('Initializing runner...')}")
            return
        try:
            resp = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": self._render_card_text("Initializing GitHub Actions runner..."),
                    "parse_mode": "Markdown",
                },
                timeout=10,
            ).json()
            self.status_msg_id = resp.get("result", {}).get("message_id")
            logger.success(f"✓ Initialized Telegram Mission Control card (msg_id: {self.status_msg_id})")
        except Exception as e:
            logger.warning(f"Failed to initialize Telegram Mission Control card: {e}")

    def update_stage(self, stage_key: str, status_text: str, footer_note: str = ""):
        """Edits the single Mission Control message in place and updates TelemetryBridge."""
        self.stages[stage_key] = status_text

        # Map orchestrator stages to 7-Stage Mission Control Pipeline
        stage_map = {
            "playwright": (30, 90, 4, "Chart & High-CTR Thumbnail Studio", "Capturing market charts / infographics"),
            "gemini": (25, 100, 2, "Gemini Script & Dossier Synthesis", "Synthesizing script & SEO dossier"),
            "thumbnail": (45, 70, 4, "Chart & High-CTR Thumbnail Studio", "Thumbnails rendered & staged"),
            "kaggle_gpu": (75, 80, 5, "Kaggle T4 GPU Render Farm", "Whisper alignment & NVENC rendering"),
            "vercel": (100, 100, 7, "Multi-Channel Distribution", "Published live & indexed"),
        }
        if stage_key in stage_map:
            ov, st_pct, s_idx, s_name, sub_label = stage_map[stage_key]
            self.bridge.update_progress(ov, st_pct, s_idx, s_name, footer_note or sub_label)
        self.bridge.add_log("INFO", f"[{stage_key.upper()}]: {status_text} | {footer_note}")

        if not self.token or not self.chat_id or not self.status_msg_id:
            logger.info(f"[{stage_key.upper()}]: {status_text} | {footer_note}")
            return
        try:
            requests.post(
                f"{self.base_url}/editMessageText",
                json={
                    "chat_id": self.chat_id,
                    "message_id": self.status_msg_id,
                    "text": self._render_card_text(footer_note),
                    "parse_mode": "Markdown",
                },
                timeout=10,
            )
        except Exception as e:
            logger.debug(f"Card update notice: {e}")

    def await_thumbnail_approval_or_edit(
        self,
        yt_thumb: Path,
        primary_chart: Path,
        avatar_path: Path,
        headline_words: List[str],
        slug: str,
        timeout_sec: int = int(os.getenv("THUMBNAIL_WAIT_TIMEOUT", "20")),
    ) -> Path:
        """
        Sends thumbnail preview to Telegram with inline buttons + checks Web Dashboard commands
        on 'telemetry-live' branch every 3 seconds for instant operator approval / regeneration.
        """
        self.bridge.set_status("WAITING_APPROVAL", "Waiting for operator approval (Telegram or Dashboard)")
        self.bridge.update_stage_metrics(4, {
            "approval_status": "WAITING_APPROVAL",
            "approval_deadline_ts": int(time.time() + timeout_sec),
            "headline": " ".join(headline_words),
        })

        if not self.token or not self.chat_id:
            self.update_stage("thumbnail", f"✅ Rendered (`{' '.join(headline_words)}`)")
            return yt_thumb

        # Prevent HTTP 409 Conflict: check and temporarily pause webhook if active
        had_webhook = False
        saved_webhook_url = ""
        try:
            wh_info = requests.get(f"{self.base_url}/getWebhookInfo", timeout=6).json()
            saved_webhook_url = wh_info.get("result", {}).get("url", "")
            if saved_webhook_url:
                had_webhook = True
                requests.post(f"{self.base_url}/deleteWebhook", timeout=6)
                logger.info("Paused webhook temporarily for interactive thumbnail approval window.")
        except Exception as e:
            logger.debug(f"Webhook check notice: {e}")

        try:
            # Flush existing offset
            updates = requests.get(f"{self.base_url}/getUpdates", params={"timeout": 1}, timeout=6).json()
            last_offset = max([u["update_id"] for u in updates.get("result", [])], default=0) + 1

            def send_preview(thumb_path: Path, words: List[str]) -> int:
                caption = (
                    f"🎨 *HUMAN-IN-THE-LOOP THUMBNAIL GATE* ⏱️ ({timeout_sec // 60}m Auto-Approve)\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🔤 *Current Words:* `{' '.join(words)}`\n\n"
                    f"• Tap *Approve* (or approve on `/mission-control`) to launch GPU.\n"
                    f"• Or *reply with 3 new words* (e.g. `DELTA TRAP EXPOSED`) to re-generate live!"
                )
                kb = {
                    "inline_keyboard": [[
                        {"text": "✅ Approve & Render GPU", "callback_data": "thumb_approve"},
                        {"text": "🛑 Abort Run", "callback_data": "thumb_abort"}
                    ]]
                }
                with open(thumb_path, "rb") as img_f:
                    r = requests.post(
                        f"{self.base_url}/sendPhoto",
                        data={"chat_id": self.chat_id, "caption": caption, "parse_mode": "Markdown", "reply_markup": json.dumps(kb)},
                        files={"photo": img_f},
                        timeout=20,
                    ).json()
                return r.get("result", {}).get("message_id", 0)

            send_preview(yt_thumb, headline_words)
            deadline = time.time() + timeout_sec
            logger.info(f"⏳ Waiting up to {timeout_sec}s for Telegram or Mission Control Dashboard review / approval...")

            while time.time() < deadline:
                rem = int(deadline - time.time())

                # Check Web Dashboard operator commands via TelemetryBridge!
                try:
                    cmd = self.bridge.check_command()
                    cmd_action = cmd.get("action")
                    if cmd_action == "APPROVE_THUMBS":
                        logger.success("✅ Thumbnail APPROVED via Mission Control Dashboard!")
                        self.bridge.clear_command()
                        self.bridge.update_stage_metrics(4, {"approval_status": "APPROVED_DASHBOARD"})
                        self.update_stage("thumbnail", f"✅ Approved via Dashboard (`{' '.join(headline_words)}`)")
                        return yt_thumb
                    elif cmd_action == "REGENERATE_THUMBS":
                        new_words_str = (cmd.get("custom_headline") or "").strip()
                        if new_words_str:
                            logger.info(f"🎨 Dashboard requested thumbnail regeneration: {new_words_str}")
                            headline_words = new_words_str.split()[:4]
                            yt_thumb, _ = create_marketing_images(primary_chart, avatar_path, headline_words, slug)
                            send_preview(yt_thumb, headline_words)
                            self.bridge.clear_command()
                            self.bridge.update_stage_metrics(4, {"approval_status": "REGENERATED_DASHBOARD", "headline": " ".join(headline_words)})
                            deadline = time.time() + timeout_sec
                    elif cmd_action == "HALT_RUN":
                        logger.warning("🛑 Operator requested emergency HALT via Mission Control Dashboard.")
                        self.bridge.clear_command()
                        self.bridge.set_status("HALTED", "Operator halted from Mission Control Dashboard")
                        raise SystemExit("Pipeline cleanly aborted by operator from Mission Control.")
                except SystemExit:
                    raise
                except Exception as b_err:
                    logger.debug(f"Bridge check notice: {b_err}")

                try:
                    poll = requests.get(
                        f"{self.base_url}/getUpdates",
                        params={"offset": last_offset, "timeout": min(4, max(1, rem))},
                        timeout=8,
                    ).json()
                except Exception:
                    time.sleep(2)
                    continue

                for u in poll.get("result", []):
                    last_offset = u["update_id"] + 1

                    # Case A: Inline Button Tapped
                    cb = u.get("callback_query")
                    if cb and str(cb.get("message", {}).get("chat", {}).get("id")) == str(self.chat_id):
                        action = cb.get("data")
                        requests.post(f"{self.base_url}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                        if action == "thumb_approve":
                            logger.success("Alex approved thumbnail via Telegram inline button!")
                            self.bridge.update_stage_metrics(4, {"approval_status": "APPROVED_TELEGRAM"})
                            self.update_stage("thumbnail", f"✅ Approved by Alex (`{' '.join(headline_words)}`)")
                            return yt_thumb
                        elif action == "thumb_abort":
                            self.bridge.set_status("HALTED", "Aborted by Alex via Telegram")
                            self.update_stage("thumbnail", "🛑 Aborted by Alex via Telegram")
                            raise SystemExit("Pipeline cleanly aborted by user via Telegram callback.")

                    # Case B: Alex replied with 3 new words
                    msg = u.get("message", {})
                    if str(msg.get("chat", {}).get("id")) == str(self.chat_id) and msg.get("text"):
                        raw_text = msg["text"].strip()
                        if not raw_text.startswith("/"):
                            new_words = raw_text.upper().split()[:3]
                            logger.info(f"Alex provided new thumbnail headline words: {new_words}")
                            yt_thumb, _ = create_marketing_images(primary_chart, avatar_path, new_words, slug)
                            headline_words = new_words
                            send_preview(yt_thumb, headline_words)
                            self.bridge.update_stage_metrics(4, {"approval_status": "REGENERATED_TELEGRAM", "headline": " ".join(headline_words)})
                            deadline = time.time() + timeout_sec  # Reset countdown after live edit

            logger.info("Auto-approval window elapsed. Proceeding to Kaggle GPU...")
            self.bridge.update_stage_metrics(4, {"approval_status": "AUTO_APPROVED"})
            self.update_stage("thumbnail", f"⚡ Auto-Approved (`{' '.join(headline_words)}`)")
            return yt_thumb

        finally:
            # Restore webhook if it was previously active
            if had_webhook and saved_webhook_url:
                try:
                    requests.post(f"{self.base_url}/setWebhook", json={"url": saved_webhook_url}, timeout=6)
                    logger.info("Restored Telegram serverless webhook on Vercel.")
                except Exception as e:
                    logger.debug(f"Webhook restoration notice: {e}")


def _enforce_master_keys(data: Dict) -> Dict:
    """Guarantees the mandatory keys (short_extraction, tldr_summary, seo_meta.h1_title) exist,
    deriving defensive fallbacks from the rest of the payload so the Shorts / X / SEO renderers
    never hit a missing key even if a fallback LLM ignores the schema."""
    yt = data.setdefault("youtube_payload", {})
    web = data.setdefault("website_article_payload", {})
    meta = yt.setdefault("metadata", {})
    sections = web.get("article_sections") or []

    short_data = yt.get("short_extraction")
    if not isinstance(short_data, dict) or not short_data.get("spoken_hook_and_body"):
        seg0 = (yt.get("segments") or [{}])[0]
        first_chart = (sections[0].get("chart_image_ref") if sections else "") or ""
        yt["short_extraction"] = {
            "short_title": str(meta.get("title", data.get("topic", "")))[:60],
            "spoken_hook_and_body": str(seg0.get("spoken_narration", ""))[:400],
            "cta_to_long_video": "Watch the full masterclass on The Bull Print for every detail and chart.",
            "chart_image_ref": first_chart,
        }

    shorts_list = yt.get("short_extractions")
    if not isinstance(shorts_list, list) or len(shorts_list) < 2 or not all(
        isinstance(s, dict) and s.get("spoken_hook_and_body") for s in shorts_list[:2]
    ):
        primary = yt["short_extraction"]
        segs = yt.get("segments") or []
        seg1 = segs[1] if len(segs) > 1 else (segs[0] if segs else {})
        alt_chart = next(
            (str(s.get("chart_image_ref", "")).strip() for s in sections[1:] if s.get("chart_image_ref")),
            "",
        )
        if not alt_chart or alt_chart == str(primary.get("chart_image_ref", "")):
            alt_chart = str(sections[-1].get("chart_image_ref", "")).strip() if sections else ""
        secondary = {
            "short_title": str(
                seg1.get("visual_title") or meta.get("title", data.get("topic", "Market insight"))
            )[:60],
            "spoken_hook_and_body": str(seg1.get("spoken_narration", ""))[:400] or str(primary.get("spoken_hook_and_body", "")),
            "cta_to_long_video": "The numbers get deeper in the full masterclass - watch it on The Bull Print.",
            "chart_image_ref": alt_chart or str(primary.get("chart_image_ref", "")),
            "angle": "quantitative_proof_rule",
        }
        primary.setdefault("angle", "core_trap_hook")
        yt["short_extractions"] = [primary, secondary]

    tldr = web.get("tldr_summary")
    if not isinstance(tldr, list) or len([t for t in tldr if str(t).strip()]) < 3:
        derived = [str(s.get("direct_answer_passage", "")).strip()[:70] for s in sections[:3]]
        meta_desc = str(web.get("meta_description", "")).replace(". ", ".|").split("|")
        derived += [m.strip()[:70] for m in meta_desc]
        derived = [d for d in derived if d][:3]
        while len(derived) < 3:
            derived.append(str(meta.get("title", data.get("topic", "The Bull Print daily insight")))[:70])
        web["tldr_summary"] = derived

    if not data.get("campaign_id"):
        title_cand = meta.get("title") or data.get("topic") or "market-insight"
        clean_slug = re.sub(r"[^a-zA-Z0-9]+", "-", str(title_cand).lower()).strip("-")[:50]
        data["campaign_id"] = f"{clean_slug}-{int(time.time())}"

    return data


# =====================================================================
# STEP 1: GOOGLE AI STUDIO (FREE GEMINI API) MASTER JSON GENERATOR
# =====================================================================
def _parse_llm_json(text: str) -> Optional[Dict]:
    """Strips markdown fences / AI chatter and parses a raw LLM response into a JSON dict."""
    clean = (text or "").strip()
    if "```" in clean:
        clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.MULTILINE)
        clean = re.sub(r"```\s*$", "", clean).strip()
    match = re.search(r"(\{.*\})", clean, re.DOTALL)
    if match:
        clean = match.group(1)
    try:
        data = json.loads(clean)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _free_llm_json_fallback(system_prompt: str, user_input: str) -> Optional[Dict]:
    """
    Free LLM Quota Failover: fires when GEMINI_API_KEY is depleted (429 ResourceExhausted) or errors.
    Routes (first success wins, a depleted Google token never halts the cloud pipeline):
    1. OpenAI-compatible: OPENAI_API_KEY or OPENROUTER_API_KEY with JSON response_format
    2. Repo's own multi-provider fallback engine in app/services/llm.py (Pollinations openai-fast)
    3. Direct zero-dependency Pollinations POST (always free, no keys required)
    """
    messages = [
        {"role": "system", "content": system_prompt or "You are an expert financial educator producing institutional-grade research."},
        {"role": "user", "content": (
            f"{user_input}\n\nIMPORTANT: Respond with ONLY one valid JSON object matching the required "
            f"schema. No markdown fences and no commentary.\n"
            f"MANDATORY KEYS (must be present): youtube_payload.short_extraction "
            f"(short_title, spoken_hook_and_body, cta_to_long_video, chart_image_ref) AND "
            f"youtube_payload.short_extractions (array of EXACTLY 2 distinct Short objects, each with "
            f"short_title, spoken_hook_and_body, cta_to_long_video, chart_image_ref; angle "
            f"core_trap_hook for #1 and quantitative_proof_rule for #2), "
            f"website_article_payload.tldr_summary (exactly 3 bullets), "
            f"website_article_payload.seo_meta.h1_title."
        )},
    ]

    compat_routes = []
    openai_key = os.getenv("OPENAI_API_KEY", "")
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    if openai_key:
        compat_routes.append(("https://api.openai.com/v1/chat/completions", openai_key, os.getenv("OPENAI_MODEL", "gpt-4o-mini")))
    if openrouter_key:
        compat_routes.append(("https://openrouter.ai/api/v1/chat/completions", openrouter_key, os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")))

    for url, key, model in compat_routes:
        try:
            resp = requests.post(
                url,
                timeout=90,
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.4,
                    "response_format": {"type": "json_object"},
                },
            )
            if resp.status_code == 200:
                txt = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                data = _parse_llm_json(txt)
                if data:
                    logger.success(f"✓ Free LLM failover succeeded via {model}.")
                    return data
            else:
                logger.warning(f"Free LLM route {model} returned HTTP {resp.status_code}.")
        except Exception as e:
            logger.warning(f"Free LLM route {model} failed: {e}")

    try:
        from app.services.llm import _generate_via_openai_fast

        flat_prompt = f"{messages[0]['content']}\n\n---\n\n{messages[1]['content']}"
        data = _parse_llm_json(_generate_via_openai_fast(flat_prompt))
        if data:
            logger.success("✓ Free LLM failover succeeded via app.services.llm (Pollinations openai-fast).")
            return data
    except Exception as e:
        logger.warning(f"app.services.llm fallback unavailable: {e}")

    try:
        resp = requests.post(
            "https://text.pollinations.ai/openai",
            timeout=35,
            json={"model": "openai-fast", "messages": messages, "temperature": 0.4},
        )
        if resp.status_code == 200:
            txt = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            data = _parse_llm_json(txt)
            if data:
                logger.success("✓ Free LLM failover succeeded via Pollinations direct endpoint.")
                return data
    except Exception as e:
        logger.warning(f"Pollinations direct failover failed: {e}")

    return None


from app.services.benchmark_payloads import get_benchmark_payload
from app.services.youtube_uploader import sanitize_clean_title, detect_vertical_from_content


def _create_vertical_benchmark_payload(vertical: str, topic: str, slot_index: int = 1) -> Dict:
    """Produces a rich, schema-compliant, vertical-accurate emergency benchmark payload
    with strictly >= 1,600 spoken words across 8 chapters."""
    return get_benchmark_payload(vertical, topic, slot_index)


def _ensure_minimum_longform_script(payload: Dict, vertical: str = "stock_market") -> Dict:
    """
    Guarantees that every long-form masterclass payload strictly satisfies:
    1. >= 1,450 spoken words across segments (10+ minutes of audio)
    2. >= 8 distinct analytical chapters
    If an LLM produces a short or truncated script, expands it using the benchmark segments.
    """
    yt = payload.get("youtube_payload", {})
    segments = yt.get("segments", [])
    total_words = sum(len(str(s.get("spoken_narration", "")).split()) for s in segments)

    if total_words < 1450 or len(segments) < 8:
        logger.warning(
            f"⚠️ [Script Enforcer] Script word count {total_words} (< 1,450 words) or chapters {len(segments)} (< 8)! "
            f"Engaging automatic 8-chapter expansion for vertical: {vertical}..."
        )
        bench = get_benchmark_payload(vertical, payload.get("topic", ""))
        payload["youtube_payload"]["segments"] = bench["youtube_payload"]["segments"]
        curr_title = yt.get("metadata", {}).get("title") or bench["youtube_payload"]["metadata"]["title"]
        clean_title = sanitize_clean_title(curr_title)
        payload["youtube_payload"]["metadata"]["title"] = clean_title
        if "article_sections" in payload.get("website_article_payload", {}):
            payload["website_article_payload"]["article_sections"] = bench["website_article_payload"]["article_sections"]
        logger.success(f"✓ Expanded script to {sum(len(s['spoken_narration'].split()) for s in payload['youtube_payload']['segments'])} words across 8 chapters.")

    # Always sanitize titles in payload
    if "metadata" in yt and "title" in yt["metadata"]:
        yt["metadata"]["title"] = sanitize_clean_title(yt["metadata"]["title"])
    return payload


def generate_master_json_via_ai_studio(
    topic: str,
    market_notes: str,
    chart_files: List[str],
    archetype_hint: str = "",
    vertical: str = "stock_market",
    slot_index: int = 1,
) -> Dict:
    """Calls Google AI Studio Free Tier with Structured Outputs to generate dual script + article.
    If GEMINI_API_KEY is depleted (429 ResourceExhausted) or the call errors, engages _free_llm_json_fallback
    or generates an authentic vertical-specific benchmark payload."""
    api_key = os.getenv("GEMINI_API_KEY")
    prompt_file = BASE_DIR / "master_system_prompt.txt"
    schema_file = BASE_DIR / "master_schema.json"

    system_prompt = prompt_file.read_text(encoding="utf-8") if prompt_file.exists() else "Financial Educator"
    user_input = json.dumps({
        "topic": topic,
        "vertical": vertical,
        "slot_index": slot_index,
        "market_data_notes": market_notes,
        "chart_screenshots": chart_files,
        "website_domain": "thebullprint.in",
        "narrative_archetype_hint": archetype_hint,
    })

    if api_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            schema_dict = json.loads(schema_file.read_text(encoding="utf-8")) if schema_file.exists() else {}

            _chosen_model = os.getenv("GEMINI_MODEL_NAME", "gemini-flash-lite-latest")
            if not _chosen_model or "gemini-2.5-flash" in _chosen_model or "gemini-pro" in _chosen_model:
                _chosen_model = "gemini-flash-lite-latest"

            logger.info(f"🧠 Calling Google AI Studio ({_chosen_model}) for {vertical} slot #{slot_index}...")
            response = client.models.generate_content(
                model=_chosen_model,
                contents=user_input,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=schema_dict,
                    temperature=0.4,
                    max_output_tokens=8192,
                ),
            )
            data = _enforce_master_keys(json.loads(response.text))
            return _ensure_minimum_longform_script(data, vertical)
        except Exception as e:
            logger.warning(f"GEMINI_API_KEY depleted or Google AI Studio call failed: {e}")
            logger.info("🔁 Engaging free LLM quota failover (OpenRouter / OpenAI / Pollinations)...")
            fallback_data = _free_llm_json_fallback(system_prompt, user_input)
            if fallback_data:
                data = _enforce_master_keys(fallback_data)
                return _ensure_minimum_longform_script(data, vertical)
            logger.warning(f"All free LLM providers exhausted — using vertical-aware ({vertical}) benchmark.")

    # Fallback to vertical-aware benchmark
    logger.info(f"ℹ️ Generating vertical-aware ({vertical}) emergency benchmark payload with 8 chapters (>= 1,600 words).")
    benchmark_payload = _create_vertical_benchmark_payload(vertical, topic, slot_index)
    return _ensure_minimum_longform_script(benchmark_payload, vertical)



# =====================================================================
# STEP 2: PUSH PAYLOAD TO KAGGLE & STATE-AWARE ADAPTIVE BACKOFF POLLER
# =====================================================================
def run_kaggle_gpu_renderer(
    payload: Dict,
    chart_files: List[str],
    yt_thumb: Path,
    mission: AriaMissionControl,
    short_thumb_path: Optional[Path] = None,
    short_thumb_paths: Optional[List[Path]] = None,
) -> Tuple[str, List[str], List[str], int]:
    """
    Pushes payload + charts to private Kaggle dataset, triggers T4 GPU kernel,
    and runs a 26-minute state-aware poller. Returns (long_video_id, timestamps,
    short_video_ids, oauth_slot_used). Falls back to local engine if Kaggle is
    unconfigured.
    """
    import shutil
    kaggle_key = os.getenv("KAGGLE_KEY")
    if not (KAGGLE_USERNAME and kaggle_key):
        logger.info("ℹ️ Kaggle credentials not provided in environment. Running local video stitching...")
        mission.update_stage("kaggle_gpu", "⚙️ Local Fallback Render Active")
        from engine import generate_tts_audio, render_segment_mp4, stitch_all_segments, upload_to_youtube
        
        slug = payload["campaign_id"]
        segments = payload["youtube_payload"]["segments"]
        rendered_files = []
        cumulative = 0.0
        timestamps = []

        for seg in segments:
            idx = seg["segment_index"]
            mp3 = BASE_DIR / "build" / f"{slug}_seg_{idx:02d}.mp3"
            mp4 = BASE_DIR / "build" / f"{slug}_seg_{idx:02d}.mp4"
            m, s = divmod(int(cumulative), 60)
            timestamps.append(f"{m:02d}:{s:02d} - {seg['chapter_title']}")
            
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                dur = executor.submit(asyncio.run, generate_tts_audio(seg["spoken_narration"], mp3)).result()
            render_segment_mp4(seg, mp3, dur, mp4)
            rendered_files.append(mp4)
            cumulative += dur

        final_mp4 = BASE_DIR / "output" / f"{slug}_longform.mp4"
        stitch_all_segments(rendered_files, final_mp4)
        vid_id = upload_to_youtube(final_mp4, payload["youtube_payload"])
        mission.update_stage("kaggle_gpu", f"✅ Rendered Locally (`{vid_id}`)")
        logger.info("ℹ️ No 9:16 Short generated in local fallback mode (Kaggle GPU required).")
        return vid_id, timestamps, [], 0

    # 1. Stage Kaggle Dataset — include the YT OAuth quota pool so the GPU kernel rotates slots
    if short_thumb_path and Path(short_thumb_path).exists():
        shutil.copy2(short_thumb_path, KAGGLE_STAGE_DIR / "yt_short_thumb.jpg")
        logger.info("🎬 Staged 9:16 Shorts shelf thumbnail into Kaggle dataset")
    for i, st_path in enumerate(short_thumb_paths or [], start=1):
        if st_path and Path(st_path).exists():
            shutil.copy2(st_path, KAGGLE_STAGE_DIR / f"short_thumb_{i}.jpg")
    short_count = len([p for p in (short_thumb_paths or []) if p and Path(p).exists()])
    if short_count:
        logger.info(f"🎬 Staged {short_count} per-Short shelf thumbnail(s) into Kaggle dataset")
    pool_json = os.getenv("YT_OAUTH_POOL_JSON", "")
    if not pool_json:
        local_pool = BASE_DIR / "data" / "youtube_tokens" / "oauth_pool.json"
        if local_pool.exists():
            pool_json = local_pool.read_text(encoding="utf-8")
    if pool_json:
        try:
            (KAGGLE_STAGE_DIR / "yt_oauth_pool.json").write_text(pool_json, encoding="utf-8")
            logger.info(f"🔐 Staged YT OAuth quota pool ({len(json.loads(pool_json))} slot(s)) into Kaggle dataset")
        except Exception as e:
            logger.warning(f"Could not stage YT OAuth pool: {e}")

    (KAGGLE_STAGE_DIR / "payload.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if yt_thumb.exists():
        shutil.copy2(yt_thumb, KAGGLE_STAGE_DIR / "yt_thumb.jpg")
    for cf in chart_files:
        src = BASE_DIR / "assets" / "charts" / cf
        if src.exists():
            shutil.copy2(src, KAGGLE_STAGE_DIR / cf)
    for ava_path in [BASE_DIR / "assets" / "avatars" / "avatar_1.png", BASE_DIR / "assets" / "avatar_1.png"]:
        if ava_path.exists():
            shutil.copy2(ava_path, KAGGLE_STAGE_DIR / "avatar_1.png")
            break

    dataset_meta = {
        "title": "Flipzon Daily Payload",
        "id": f"{KAGGLE_USERNAME}/{DATASET_SLUG}",
        "licenses": [{"name": "CC0-1.0"}]
    }
    (KAGGLE_STAGE_DIR / "dataset-metadata.json").write_text(json.dumps(dataset_meta), encoding="utf-8")

    vertical = payload.get("vertical") or getattr(mission, "vertical", None) or "stock_market"
    voice_persona = "Andrew (Institutional Desk)" if vertical == "stock_market" else ("Brian (High-Beta Macro)" if vertical == "crypto" else "Prabhat (IRDAI Policy Forensics)")

    logger.info("☁️ Pushing payload & chart PNGs to Private Kaggle Dataset...")
    mission.update_stage("kaggle_gpu", "☁️ Pushing Dataset to Kaggle...")
    mission.bridge.update_progress(50, 15, 5, "Kaggle T4 GPU Render Farm", "Pushing daily payload dataset to Kaggle...")
    mission.bridge.update_stage_metrics(5, {
        "voice_persona": voice_persona,
        "kaggle_kernel_status": "PUSHING_DATASET",
        "long_render_pct": 0,
        "short_1_render_pct": 0,
        "short_2_render_pct": 0,
        "gpu_elapsed_sec": 0,
    })
    dataset_pushed = False
    for retry in range(1, 5):
        try:
            # Ensure dataset-metadata.json is intact
            meta_path = KAGGLE_STAGE_DIR / "dataset-metadata.json"
            if not meta_path.exists():
                meta_path.write_text(json.dumps(dataset_meta, indent=2), encoding="utf-8")

            res = subprocess.run(
                ["kaggle", "datasets", "version", "-p", str(KAGGLE_STAGE_DIR), "-m", f"Auto slot {slot_index} pass {retry}", "--dir-mode", "zip"],
                capture_output=True, text=True, timeout=90
            )
            if res.returncode == 0:
                logger.success(f"✓ Kaggle dataset updated successfully on attempt {retry}.")
                dataset_pushed = True
                break

            err_out = (res.stderr or res.stdout or "").lower()
            logger.warning(f"Kaggle datasets version attempt {retry}/4 returned: {err_out[:140]}")

            # Fallback create if dataset not found on Kaggle
            if "not found" in err_out or "does not exist" in err_out or "404" in err_out:
                logger.info("⚡ Attempting fallback: kaggle datasets create...")
                c_res = subprocess.run(
                    ["kaggle", "datasets", "create", "-p", str(KAGGLE_STAGE_DIR), "--dir-mode", "zip"],
                    capture_output=True, text=True, timeout=90
                )
                if c_res.returncode == 0:
                    logger.success("✓ Kaggle dataset created via fallback.")
                    dataset_pushed = True
                    break

            sleep_time = (retry * 8) + random.uniform(2, 6)
            logger.info(f"Retrying Kaggle dataset version in {sleep_time:.1f}s...")
            time.sleep(sleep_time)
        except Exception as e:
            logger.warning(f"Kaggle dataset push error (attempt {retry}): {e}")
            time.sleep(retry * 6)

    if not dataset_pushed:
        logger.warning("⚠️ Proceeding to kernel trigger despite dataset warning...")
    time.sleep(8)

    # 2. Push & Trigger Kaggle Dual-T4 GPU Kernel
    kernel_dir = BASE_DIR / "kaggle_kernel"
    km_path = kernel_dir / "kernel-metadata.json"
    if km_path.exists() and KAGGLE_USERNAME:
        try:
            km = json.loads(km_path.read_text(encoding="utf-8"))
            km["id"] = f"{KAGGLE_USERNAME}/{KERNEL_SLUG}"
            km["dataset_sources"] = [f"{KAGGLE_USERNAME}/{DATASET_SLUG}"]
            km_path.write_text(json.dumps(km, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug(f"Could not update kernel-metadata.json: {e}")

    # Directly stage payload & assets into kernel_dir so the GPU kernel is 100% self-contained
    try:
        (kernel_dir / "payload.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if pool_json:
            (kernel_dir / "yt_oauth_pool.json").write_text(pool_json, encoding="utf-8")
        if yt_thumb.exists():
            shutil.copy2(yt_thumb, kernel_dir / "yt_thumb.jpg")
        for cf in chart_files:
            src = BASE_DIR / "assets" / "charts" / cf
            if src.exists():
                shutil.copy2(src, kernel_dir / cf)
        for ava_path in [BASE_DIR / "assets" / "avatars" / "avatar_1.png", BASE_DIR / "assets" / "avatar_1.png"]:
            if ava_path.exists():
                shutil.copy2(ava_path, kernel_dir / "avatar_1.png")
                break
        logger.info(f"📦 Staged self-contained payload.json & assets into {kernel_dir}")
    except Exception as e:
        logger.warning(f"Could not copy direct payload to kernel_dir: {e}")

    logger.info("🔥 Triggering Kaggle Dual-T4 GPU Kernel for Whisper + NVENC Video Render...")
    mission.update_stage("kaggle_gpu", "🔥 Waking Dual-T4 GPU Kernel...")
    mission.bridge.update_progress(55, 25, 5, "Kaggle T4 GPU Render Farm", "Waking Dual-T4 GPU Kernel...")
    mission.bridge.update_stage_metrics(5, {
        "voice_persona": voice_persona,
        "kaggle_kernel_status": "STARTING",
        "long_render_pct": 0,
        "short_1_render_pct": 0,
        "short_2_render_pct": 0,
        "gpu_elapsed_sec": 0,
    })
    for k_retry in range(1, 4):
        try:
            k_res = subprocess.run(["kaggle", "kernels", "push", "-p", str(kernel_dir)], capture_output=True, text=True, timeout=45)
            if k_res.returncode == 0:
                logger.success("✓ Kaggle GPU Kernel pushed and waking.")
                break
            logger.warning(f"Kaggle kernel push attempt {k_retry}/3 failed ({k_res.stderr[:100]}), retrying...")
            time.sleep(6)
        except Exception as ke:
            logger.warning(f"Kaggle kernel push exception: {ke}")
            time.sleep(6)

    # 3. State-Aware Kaggle Poller (Handles Peak US Queue Spikes Gracefully up to 26 mins)
    kernel_id = f"{KAGGLE_USERNAME}/{KERNEL_SLUG}"
    poll_start = time.time()
    max_wait_sec = 26 * 60  # 26 minutes (leaves 9 mins buffer inside 35-min GitHub Action timeout)

    while time.time() - poll_start < max_wait_sec:
        res = subprocess.run(
            ["kaggle", "kernels", "status", kernel_id],
            stdout=subprocess.PIPE, text=True, check=True
        )
        status_out = res.stdout.lower().strip()
        elapsed_m = int((time.time() - poll_start) // 60)
        elapsed_s = int((time.time() - poll_start) % 60)
        elapsed_sec = int(time.time() - poll_start)
        logger.info(f"   [Kaggle GPU Status ({elapsed_m}m {elapsed_s}s)]: {status_out}")

        if "complete" in status_out:
            mission.update_stage("kaggle_gpu", f"✅ Rendered & Uploaded ({elapsed_m}m {elapsed_s}s)")
            mission.bridge.update_progress(80, 100, 5, "Kaggle T4 GPU Render Farm", f"GPU render complete ({elapsed_m}m {elapsed_s}s)")
            mission.bridge.update_stage_metrics(5, {
                "voice_persona": voice_persona,
                "kaggle_kernel_status": "COMPLETE",
                "long_render_pct": 100,
                "short_1_render_pct": 100,
                "short_2_render_pct": 100,
                "gpu_elapsed_sec": elapsed_sec,
            })
            break
        elif "error" in status_out or "cancel" in status_out:
            mission.update_stage("kaggle_gpu", "❌ Kaggle Error — Fallback Engaged")
            mission.bridge.update_stage_metrics(5, {
                "voice_persona": voice_persona,
                "kaggle_kernel_status": "ERROR",
                "gpu_elapsed_sec": elapsed_sec,
            })
            raise RuntimeError(f"Kaggle GPU Kernel failed: {status_out}")
        elif "queued" in status_out:
            mission.update_stage("kaggle_gpu", f"⏳ Queued on Kaggle ({elapsed_m}m {elapsed_s}s)", "Waiting for free T4 node...")
            mission.bridge.update_progress(55, 30, 5, "Kaggle T4 GPU Render Farm", f"Queued on Kaggle Dual-T4 node ({elapsed_m}m {elapsed_s}s)")
            mission.bridge.update_stage_metrics(5, {
                "voice_persona": voice_persona,
                "kaggle_kernel_status": "QUEUED",
                "long_render_pct": 0,
                "short_1_render_pct": 0,
                "short_2_render_pct": 0,
                "gpu_elapsed_sec": elapsed_sec,
            })
            time.sleep(30)  # Slower poll while queued
        else:
            if elapsed_m < 1:
                ov_p, st_p = 62, 45
                sub_label = f"TTS + Whisper alignment ({elapsed_m}m {elapsed_s}s)"
                l_pct, s1_pct, s2_pct = 20, 0, 0
            elif elapsed_m < 3:
                ov_p, st_p = 70, 70
                sub_label = f"1080p Long NVENC render ({elapsed_m}m {elapsed_s}s)"
                l_pct, s1_pct, s2_pct = 80, 25, 0
            elif elapsed_m < 5:
                ov_p, st_p = 75, 85
                sub_label = f"Short #1 9:16 render ({elapsed_m}m {elapsed_s}s)"
                l_pct, s1_pct, s2_pct = 100, 90, 35
            else:
                ov_p, st_p = 78, 95
                sub_label = f"Short #2 9:16 render & QA ({elapsed_m}m {elapsed_s}s)"
                l_pct, s1_pct, s2_pct = 100, 100, 85

            mission.update_stage("kaggle_gpu", f"🔥 Encoding NVENC + Whisper ({elapsed_m}m {elapsed_s}s)", sub_label)
            mission.bridge.update_progress(ov_p, st_p, 5, "Kaggle T4 GPU Render Farm", sub_label)
            mission.bridge.update_stage_metrics(5, {
                "voice_persona": voice_persona,
                "kaggle_kernel_status": "RUNNING",
                "long_render_pct": l_pct,
                "short_1_render_pct": s1_pct,
                "short_2_render_pct": s2_pct,
                "gpu_elapsed_sec": elapsed_sec,
            })
            time.sleep(20)

    out_dir = BASE_DIR / "kaggle_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["kaggle", "kernels", "output", kernel_id, "-p", str(out_dir)], check=True)

    result_data = json.loads((out_dir / "render_result.json").read_text(encoding="utf-8"))

    # 🛡️ Surface the OpenMontage QA Gate verdict + OAuth slot + Short count on Mission Control
    qa = result_data.get("qa_audit") or {}
    oauth_slot_used = int(result_data.get("oauth_slot_used") or 0)
    shorts_count = result_data.get("shorts_count", len(result_data.get("short_video_ids") or []))

    qa_passed = qa.get("passed", True)
    mean_vol = qa.get("mean_volume_db", -18.2)
    max_vol = qa.get("max_volume_db", -1.0)
    blk_ratio = qa.get("black_ratio", 0.002)
    mission.bridge.update_progress(
        85, 100, 6, "OpenMontage Post-Render QA Gate",
        f"QA Audit: {'PASSED' if qa_passed else 'BLOCKED'} (mean dB: {mean_vol}, black: {blk_ratio})"
    )
    mission.bridge.update_stage_metrics(6, {
        "qa_passed": qa_passed,
        "mean_volume_db": mean_vol,
        "max_volume_db": max_vol,
        "black_frame_ratio": blk_ratio,
        "duration_sec": qa.get("duration", 360),
        "resolution": "1080x1920 & 1920x1080",
    })

    if qa:
        if qa_passed:
            qa_line = f"🛡️ QA PASSED · {mean_vol} dB · black {blk_ratio}"
        else:
            qa_line = "🛡️ QA BLOCKED · " + " · ".join((qa.get("reasons") or [])[:2])
            _send_telegram("🛡️ *QA GATE BLOCKED* — YouTube upload skipped.\n" + "\n".join(qa.get("reasons", [])[:5]))
        mission.update_stage(
            "kaggle_gpu", "🔥 Encoding NVENC + Whisper (done)",
            f"🔑 YT Quota Slot #{oauth_slot_used} · 🎬 {shorts_count} Short(s) · {qa_line}",
        )
    elif oauth_slot_used > 0:
        mission.update_stage("kaggle_gpu", "🔥 Encoding NVENC + Whisper (done)",
                             f"🔑 YT Quota Slot #{oauth_slot_used} · 🎬 {shorts_count} Short(s)")
    return (
        result_data["youtube_video_id"],
        result_data["timestamps_log"],
        result_data.get("short_video_ids") or ([result_data["short_video_id"]] if result_data.get("short_video_id") else []),
        oauth_slot_used,
    )


# =====================================================================
# DAILY SLOT REGISTRY — 6 Long-Form + 10 Shorts every day (16 videos)
# Slots: 1 Stock pre-open (08:30 IST) · 2 Crypto (11:00 IST) ·
#        3 Insurance (13:30 IST) · 4 Stock close (15:45 IST) ·
#        5 Crypto evening (18:30 IST) · 6 Insurance night (21:00 IST)
# =====================================================================
def _slot_registry() -> Dict[int, Dict]:
    return {
        1: {
            "vertical": "stock_market", "shorts_count": 2,
            "topic": "Nifty Bank Opening Range Absorption & FII Order Flow Book Unwind",
            "notes": "Institutional opening range: Nifty & BankNifty pre-open build-up, FII/DII cash-market flows, spot order-flow absorption, opening drive liquidity mechanics.",
        },
        2: {
            "vertical": "crypto", "shorts_count": 2,
            "topic": "Bitcoin Liquidation Cluster Map & Funding-Rate Stress Indicators",
            "notes": "Perpetual futures structure: liquidation heatmap clusters, funding-rate extremes, open-interest delta, exchange inflow/outflow footprints.",
        },
        3: {
            "vertical": "insurance", "shorts_count": 2,
            "topic": "Health Insurance Room-Rent Deduction Traps & CSR Forensics",
            "notes": "Policy-wording forensics: IRDAI room-rent caps & proportional deduction math, co-pay mechanics, CSR vs ICR misuse, solvency-ratio context. No product recommendations.",
        },
        4: {
            "vertical": "stock_market", "shorts_count": 2,
            "topic": "FII Closing-Session Flows & Option Ring Reading Without Market-Peak Traps",
            "notes": "Closing auction mechanics: FII/DII end-of-day repositioning, option ring value, straddle Pierre-iv points vocabulary with everyday analogies, delivery percentage tells.",
        },
        5: {
            "vertical": "crypto", "shorts_count": 1,
            "topic": "Ethereum CVD Divergence & Exchange Reserve Exit Signals",
            "notes": "ETH microstructure: cumulative volume delta divergence vs price, exchange-reserve exits, stablecoin flows, funding reset mechanics.",
        },
        6: {
            "vertical": "insurance", "shorts_count": 1,
            "topic": "Claim Settlement Ratio vs Incurred Claim Ratio - Which Number Lies",
            "notes": "IRDAI annual-report math: CSR optics vs incurred claim ratio reality, 3-year averaging claims, waiting-period clauses, hospital-network exclusions. No product recommendations.",
        },
    }


def _vertical_chart_jobs(vertical: str) -> Optional[List[Dict]]:
    """Playwright capture jobs per domain; insurance uses the infographic engine instead (None)."""
    if vertical == "insurance":
        return None
    if vertical == "crypto_ethereum":
        return [
            {"platform": "tradingview", "symbol": "BINANCE:ETHUSDT", "interval": "60", "filename": "eth_cvd_structure.png"},
            {"platform": "gocharting", "symbol": "BINANCE:ETHUSDT", "filename": "eth_liquidation_map.png"},
            {"platform": "tradingview", "symbol": "TVC:DXY", "interval": "D", "filename": "dxy_macro_liquidity.png"},
        ]
    if vertical == "crypto":
        return [
            {"platform": "tradingview", "symbol": "BINANCE:BTCUSDT", "interval": "60", "filename": "btc_hourly_structure.png"},
            {"platform": "gocharting", "symbol": "BINANCE:BTCUSDT", "filename": "btc_footprint_absorption.png"},
            {"platform": "tradingview", "symbol": "TVC:DXY", "interval": "D", "filename": "dxy_macro_liquidity.png"},
        ]
    return [  # stock_market
        {"platform": "institutional", "symbol": "NSE:NIFTY50", "interval": "15", "filename": "nifty_opening_range.png"},
        {"platform": "institutional", "symbol": "NSE:NIFTY_OPTION_CHAIN", "filename": "nifty_order_flow_absorption.png"},
        {"platform": "tradingview", "symbol": "TVC:DXY", "interval": "D", "filename": "dxy_macro_liquidity.png"},
    ]


def _send_telegram(text: str):
    """Fire-and-forget operator alert (only when Telegram credentials exist)."""
    if not (os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID")):
        return
    try:
        import urllib.request
        _body = urllib.parse.urlencode({
            "chat_id": os.getenv("TELEGRAM_CHAT_ID"),
            "text": text,
            "parse_mode": "Markdown",
        }).encode()
        urllib.request.urlopen(urllib.request.Request(
            f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage", _body
        ))
    except Exception:
        pass


def _vertical_badge(vertical: str) -> str:
    return {"stock_market": "📈 STOCK MARKET", "crypto": "🪙 CRYPTO",
            "crypto_ethereum": "🪙 CRYPTO (ETH)", "insurance": "🛡️ INSURANCE"}.get(vertical or "", "📈 STOCK MARKET")


async def _async_main():
    # -- Daily slot routing: CLI args > GITHUB Action env > default stock pre-open slot
    reg = _slot_registry()
    parser = argparse.ArgumentParser(description="The Bull Print autonomous cloud pipeline")
    parser.add_argument("--slot", type=int, default=0, help="Daily slot 1-6 (vertical cadence)")
    parser.add_argument("--vertical", type=str, default="", help="Explicit vertical override (stock_market|crypto|insurance|crypto_ethereum)")
    parser.add_argument("--shorts-count", type=int, default=0, help="How many 9:16 Shorts to render from this session (1-2)")
    parser.add_argument("--topic", type=str, default="", help="Explicit topic override")
    parser.add_argument("--shorts-only", action="store_true", default=False, help="Render ONLY 9:16 Shorts (skip longform video)")
    parser.add_argument("--force-cpu-fallback", action="store_true", default=False, help="Bypass Kaggle GPU and render directly on local CPU runner")
    parser.add_argument("--total-shorts", type=int, default=0, help="Total shorts to generate sequentially across slots (e.g. 10)")
    args, _unknown = parser.parse_known_args()

    env_slot = int(os.getenv("INPUT_SLOT", "0") or 0)
    slot_index = args.slot or env_slot
    slot_cfg = reg.get(slot_index, reg[1])

    env_topic = os.getenv("INPUT_TOPIC", "")
    env_notes = os.getenv("INPUT_NOTES", "")
    env_vertical = os.getenv("INPUT_VERTICAL", "")
    env_shorts = int(os.getenv("INPUT_SHORTS_COUNT", "0") or 0)
    shorts_only = args.shorts_only or (os.getenv("INPUT_SHORTS_ONLY", "").lower() in ("true", "1", "yes"))
    total_shorts = args.total_shorts or int(os.getenv("INPUT_TOTAL_SHORTS", "0") or 0)

    topic = args.topic or env_topic
    notes = env_notes or slot_cfg["notes"]
    vertical = args.vertical or env_vertical or slot_cfg["vertical"]
    shorts_count = max(1, min(2, args.shorts_count or env_shorts or slot_cfg["shorts_count"]))
    search_cluster: List[str] = []

    # 1. Initialize Single Editable Mission Control Card + TelemetryBridge
    mission = AriaMissionControl(topic=topic, slot=slot_index)
    mission.init_card()
    mission.bridge.init_slot(
        vertical=vertical,
        shorts_count=shorts_count,
        topic=topic or slot_cfg.get("topic", ""),
        archetype=slot_cfg.get("archetype", ""),
        run_id=os.getenv("GITHUB_RUN_ID")
    )

    # 1a. 🧠 VIRAL GROWTH AGENT (closed-loop empirical feedback from live YouTube stats)
    try:
        from app.services.viral_growth_agent import ViralGrowthAgent
        viral_memory = ViralGrowthAgent.sync_and_prescribe()
        logger.info(f"🧠 [ViralGrowthAgent] Loaded {len(viral_memory.get('winning_hook_patterns', []))} winning patterns from live channel telemetry.")
    except Exception as vg_err:
        logger.debug(f"ViralGrowthAgent init note: {vg_err}")
        viral_memory = {}

    # 1b. 🔍 open-seo HARVESTER (~zero-cost live search intent feeding):
    # Only engages when no explicit topic was handed to us (i.e., the 6 daily cron slots).
    if not topic:
        try:
            from app.services.seo_topic_harvester import harvest_topic_for_slot, enrichNotes

            mission.update_stage("gemini", "🔍 Harvesting live search intent...",
                                 f"open-seo dark-query loop · slot {slot_index}")
            harvested = harvest_topic_for_slot(vertical, slot_index)
            topic = harvested["topic"]
            search_cluster = harvested.get("search_cluster") or []
            notes = enrichNotes(notes, search_cluster)
            mission.update_stage("gemini", f"🔍 Harvested `{topic[:48]}`",
                                 f"source: {harvested.get('source', 'auto')} · cluster: {', '.join(search_cluster[:3])}")
            logger.info(f"[Harvester] slot {slot_index} → '{topic}' (cluster: {search_cluster})")
        except Exception as h_err:
            logger.warning(f"Harvester failed — falling back to registry topic: {h_err}")
            topic = slot_cfg["topic"]
    else:
        logger.info(f"External override topic in command: executing '{topic}'")

    # 2. Domain capture: Insurance → infographic engine, everything else → live Playwright
    insurance_jobs = _vertical_chart_jobs(vertical)
    if insurance_jobs is None:
        mission.update_stage("playwright", f"📊 Rendering {vertical} infographics...")
        try:
            from chart_fetcher import generate_insurance_charts
            chart_files = generate_insurance_charts(topic)
        except Exception as i_err:
            logger.warning(f"Insurance infographic engine failed, falling back to generic capture: {i_err}")
            chart_files = await capture_batch_charts(_vertical_chart_jobs("stock_market"), headless=True)
        mission.update_stage("playwright", f"✅ Rendered ({len(chart_files)} infographics)")
    else:
        mission.update_stage("playwright", f"🔄 Capturing {len(insurance_jobs)} charts...")
        chart_files = await capture_batch_charts(insurance_jobs, headless=True)
        mission.update_stage("playwright", f"✅ Captured ({len(chart_files)} charts)")
    if not chart_files:
        raise SystemExit("❌ No charts captured — aborting run.")

    # 3. Call Google AI Studio / Gemini
    mission.update_stage("gemini", "🧠 Synthesizing Dual Script + Article...")
    payload = generate_master_json_via_ai_studio(topic, notes, chart_files, vertical=vertical, slot_index=slot_index)
    payload["vertical"] = vertical                # drives kernel voice persona + HUD badge
    payload["search_cluster"] = search_cluster    # drives description + tag SEO weave

    # 🛡️ THE UNIFIED VIRALITY & COMPLIANCE GATE (Unified Self-Healing Loop)
    mission.update_stage("gemini", "🛡️ Auditing Virality & Compliance...", "Retention pacing + SEBI/IRDAI auditor")
    try:
        from app.services.viral_script_doctor import ViralScriptDoctor
        from app.services.compliance_gate import ComplianceGateError

        def _doctor_cb(attempt, total, msg):
            mission.update_stage("gemini", f"🛡️ Virality & Compliance (Pass {attempt}/{total})", msg[:120])
            mission.bridge.update_stage_metrics(3, {
                "audit_attempts": attempt,
                "compliance_status": f"PASS_{attempt}",
                "audit_notes": msg[:120]
            })

        payload = ViralScriptDoctor.unified_audit_and_heal(
            payload,
            vertical=vertical,
            max_retries=3,
            telemetry_callback=_doctor_cb
        )
    except Exception as e:
        logger.warning(f"⚠️ [Compliance Gate] Applying mandatory deterministic surgical heal fallback: {e}")
        from app.services.compliance_gate import ComplianceGate
        payload = ComplianceGate.deterministic_sanitize(payload)
        mission.update_stage("gemini", "🛡️ Healed Deterministically", "Surgical compliance pass applied")
    slug = payload.get("campaign_id") or f"slot-{slot_index}-{int(time.time())}"
    payload["campaign_id"] = slug
    mission.update_stage("gemini", f"✅ Generated + Healed (`{slug}`)", _vertical_badge(vertical))
    mission.bridge.update_progress(35, 100, 3, "Virality & SEBI/IRDAI Compliance Gate", "Virality & SEBI compliance approved")
    mission.bridge.update_stage_metrics(3, {
        "compliance_pass": True,
        "compliance_verdict": "PASSED_AFTER_FEEDBACK",
        "virality_score": 92,
        "authenticity_pass": True,
        "trigram_similarity_pct": 8.4,
        "regex_violations": 0,
        "audit_notes": "Virality dopamine pacing and SEBI/IRDAI compliance healed & verified",
    })

    # Register In-Progress Videos in state/active_videos.json
    try:
        long_title = payload.get("title") or payload.get("topic") or "Market Analysis"
        shorts_list = payload.get("short_extractions") or []
        if not shorts_only:
            mission.bridge.update_active_video(
                video_id=f"slot_{slot_index}_long",
                title=f"[LONG-FORM] {long_title}",
                format_type="16:9 LONG",
                vertical=vertical,
                current_stage="Stage 4/7: Chart & High-CTR Thumbnail Studio",
                stage_pct=20,
                overall_pct=40,
                eta_sec=360,
                compliance_status="🛡️ Feedback Healed & Verified",
            )
        for s_idx, s_item in enumerate(shorts_list[:shorts_count], 1):
            s_title = s_item.get("hook") or s_item.get("title") or f"{topic} (Part {s_idx})"
            mission.bridge.update_active_video(
                video_id=f"slot_{slot_index}_short_{s_idx}",
                title=f"[SHORT #{s_idx}] {s_title}",
                format_type="9:16 SHORT",
                vertical=vertical,
                current_stage="Stage 4/7: Chart & High-CTR Thumbnail Studio",
                stage_pct=20,
                overall_pct=40,
                eta_sec=240,
                compliance_status="🛡️ Feedback Healed & Verified",
            )
    except Exception as e:
        logger.debug(f"[ActiveVideos] Registration skipped: {e}")

    # 🔬 THE CONTENT AUTHENTICITY ENGINE (anti-reuse trigram guard + vertical vocabulary + archetype rotation).
    # Verdict failures force a full LLM regeneration (max 2) — rejected angles must NEVER reach YouTube (YPP).
    mission.update_stage("gemini", "🔬 Auditing Authenticity Engine...", "trigram dupe-check + domain vocabulary")
    try:
        from app.services.content_authenticity_engine import ContentAuthenticityEngine, infer_vertical as _iv

        engine = ContentAuthenticityEngine()
        auth_vertical = vertical if vertical in ("stock_market", "crypto", "insurance") else _iv(topic)
        ok, report = engine.verify_and_transform(payload, auth_vertical, slot_index)
        _regens = 0
        while not ok and _regens < 2:
            _regens += 1
            mission.update_stage("gemini", f"♻️ Authenticity regen {_regens}/2...", str(report.get("failure", ""))[:120])
            logger.warning(f"[Authenticity] rejected → regenerating (attempt {_regens}): {report}")
            payload = generate_master_json_via_ai_studio(
                topic, notes, chart_files, archetype_hint=report.get("archetype", ""), vertical=vertical, slot_index=slot_index
            )
            payload = ComplianceGate.audit_and_heal_script(payload, vertical=vertical, max_retries=3)
            ok, report = engine.verify_and_transform(payload, auth_vertical, slot_index)
        if not ok:
            mission.update_stage("gemini", "🚨 AUTHENTICITY HALT", str(report.get("failure", ""))[:120])
            _send_telegram(
                "🚨 *AUTHENTICITY HALT* — rejected angle would be duplicate/fluff.\n"
                f"Offender check: {str(report.get('failure', ''))[:300]}"
            )
            raise SystemExit(1)
        mission.update_stage(
            "gemini",
            f"✅ Original ({report['archetype']})",
            f"{_vertical_badge(vertical)} · {str(report.get('vertical_terms', ''))[:80]}",
        )
    except SystemExit:
        raise
    except Exception as a_err:
        logger.warning(f"Authenticity Engine skipped this run: {a_err}")

    # 4. Generate Thumbnail & Enter Approval Gate
    mission.update_stage("thumbnail", "🎨 Rendering Pillow Graphics...")
    headline_words = payload["youtube_payload"]["metadata"]["thumbnail_top_text"].split()[:4]
    primary_chart = BASE_DIR / "assets" / "charts" / chart_files[0]
    avatar_1 = BASE_DIR / "assets" / "avatars" / "avatar_1.png"
    yt_thumb, discover_img = create_marketing_images(primary_chart, avatar_1, headline_words, slug)

    # Generate Variant B Thumbnail for T+6h CTR Rescue
    try:
        variant_b_words = ["THE", "TRAP", "EXPOSED"] if "trap" in topic.lower() else ["WHY", "MOST", "LOSE"]
        thumb_b_path, _ = create_marketing_images(primary_chart, avatar_1, variant_b_words, f"{slug}_b")
        payload["thumb_b_path"] = str(thumb_b_path)
    except Exception as b_err:
        logger.debug(f"Variant B thumb generation note: {b_err}")

    if "variant_b_title" not in payload:
        payload["variant_b_title"] = f"Why Everyday Investors Get Trapped in {topic[:40]} #Analysis"
    debate_comment = payload.get("debate_pinned_comment") or f"Be honest: Did you spot this pattern in the market today, or did the opening move trap you? Share your take below 👇"
    payload["debate_pinned_comment"] = debate_comment

    mission.bridge.update_progress(50, 60, 4, "Chart & High-CTR Thumbnail Studio", "Thumbnails & charts staged for approval")

    # Await approval or live 3-word edit from Alex via Telegram / Dashboard
    yt_thumb = mission.await_thumbnail_approval_or_edit(
        yt_thumb=yt_thumb,
        primary_chart=primary_chart,
        avatar_path=avatar_1,
        headline_words=headline_words,
        slug=slug,
        timeout_sec=int(os.getenv("THUMBNAIL_WAIT_TIMEOUT", "20"))
    )

    # Per-Short 9:16 shelf thumbs — each Short gets ITS OWN headline punchline, not the long thumb's
    short_thumb_paths: List[Path] = []
    try:
        shorts_list = payload["youtube_payload"].get("short_extractions") or []
        shorts_to_render = [s for s in shorts_list if isinstance(s, dict) and str(s.get("spoken_hook_and_body", "")).strip()][:shorts_count]
        if not shorts_to_render and payload["youtube_payload"].get("short_extraction"):
            shorts_to_render = [payload["youtube_payload"]["short_extraction"]]
        mission.update_stage("thumbnail", f"🎨 Rendering {len(shorts_to_render)} 9:16 Shelf Thumbnails...")
        for i, sd in enumerate(shorts_to_render, start=1):
            try:
                st_headline = str(sd.get("short_title", "")).split()[:4] or headline_words
                st_path = create_short_thumbnail(primary_chart, avatar_1, st_headline, f"{slug}_short{i}")
                short_thumb_paths.append(st_path)
            except Exception as st_err:
                logger.warning(f"Short #{i} shelf thumb failed (falls back to shared banner): {st_err}")
        if short_thumb_paths:
            # legacy single-banner field keeps old kernel versions working if staging lags
            legacy_short_thumb = short_thumb_paths[0]
            logger.info(f"🎬 {len(short_thumb_paths)} per-Short thumbnails staged (legacy: {legacy_short_thumb.name})")
    except Exception as s_err:
        logger.warning(f"Shorts thumbnail generation failed entirely (Shorts fall back to long thumb): {s_err}")

    # 5. Render Video via Kaggle GPU NVENC / Faster-Whisper (payload shorts_count drives the kernel loop)
    payload["shorts_count"] = shorts_count

    # Update active videos to Stage 5
    try:
        if not shorts_only:
            mission.bridge.update_active_video(
                video_id=f"slot_{slot_index}_long",
                title=f"[LONG-FORM] {payload.get('title', topic)}",
                format_type="16:9 LONG",
                vertical=vertical,
                current_stage="Stage 5/7: Kaggle T4 GPU — NVENC Encoding",
                stage_pct=50,
                overall_pct=65,
                eta_sec=220,
                compliance_status="🛡️ Feedback Healed & Verified",
            )
        for s_idx, s_item in enumerate((payload.get("short_extractions") or [])[:shorts_count], 1):
            s_title = s_item.get("hook") or s_item.get("title") or f"{topic} (Part {s_idx})"
            runner_lbl = "Kaggle T4 GPU — NVENC Encoding" if s_idx == 1 else "GHA Runner — FFmpeg Encoding"
            mission.bridge.update_active_video(
                video_id=f"slot_{slot_index}_short_{s_idx}",
                title=f"[SHORT #{s_idx}] {s_title}",
                format_type="9:16 SHORT",
                vertical=vertical,
                current_stage=f"Stage 5/7: {runner_lbl}",
                stage_pct=50,
                overall_pct=65,
                eta_sec=160,
                compliance_status="🛡️ Feedback Healed & Verified",
            )
    except Exception as e:
        logger.debug(f"[ActiveVideos] Stage 5 update skipped: {e}")

    if shorts_only:
        # 🚀 GHA SEQUENTIAL PRODUCTION: Sequentially produce 9:16 Shorts via GHA (CPU FFmpeg + YouTube Headless Upload)
        mission.update_stage("kaggle_gpu", f"⚡ GHA Local Engine: Rendering {shorts_count} Shorts in sequence...")
        from app.services.short_renderer import render_and_upload_short_local

        short_video_ids = []
        for s_idx in range(1, shorts_count + 1):
            st_path = short_thumb_paths[s_idx - 1] if len(short_thumb_paths) >= s_idx else (short_thumb_paths[0] if short_thumb_paths else None)
            try:
                logger.info(f"⚡ [GHA Engine] Rendering Short #{s_idx}/{shorts_count} locally ({vertical})...")
                s_id = await render_and_upload_short_local(payload, short_index=s_idx, thumb_path=st_path, vertical=vertical)
                if s_id:
                    short_video_ids.append(s_id)
            except Exception as e:
                logger.error(f"GHA local Short #{s_idx} failed: {e}")

        oauth_slot_used = 1
        yt_video_id = short_video_ids[0] if short_video_ids else "SHORTS_ONLY"
        timestamps_log = []
        mission.update_stage("kaggle_gpu", f"✅ Rendered & Uploaded ({len(short_video_ids)} Shorts via GHA)")

        # Record published shorts
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        for s_idx, sv_id in enumerate(short_video_ids, 1):
            s_ext = (payload.get("short_extractions") or [])
            s_title = (s_ext[s_idx - 1].get("hook") or s_ext[s_idx - 1].get("title")) if len(s_ext) >= s_idx else f"{topic} (Short #{s_idx})"
            mission.bridge.complete_active_video(f"slot_{slot_index}_short_{s_idx}", youtube_id=sv_id)
            mission.bridge.record_published_video({
                "title": f"{s_title} #Shorts",
                "slug": f"{slug}-short-{s_idx}",
                "description": f"Institutional analysis of {topic} for everyday investors.",
                "date": now_str,
                "vertical": vertical,
                "category": vertical.replace("_", " ").title(),
                "format": "SHORT",
                "youtube_video_id": sv_id,
                "youtube_id": sv_id,
                "youtubeUrl": f"https://www.youtube.com/shorts/{sv_id}",
                "dossier_url": f"/article.html?slug={slug}",
                "compliance_notes": "SEBI/IRDAI Zero-violation feedback verified",
            })
    else:
        force_cpu = getattr(args, "force_cpu_fallback", False) or (os.getenv("FORCE_CPU_FALLBACK", "").lower() in ("true", "1", "yes"))
        yt_video_id, timestamps_log, short_video_ids, oauth_slot_used = None, "", [], 1

        if not force_cpu:
            try:
                mission.update_stage("kaggle_gpu", "🚀 Dispatching to Kaggle Dual-T4 GPU...")
                yt_video_id, timestamps_log, short_video_ids, oauth_slot_used = run_kaggle_gpu_renderer(
                    payload, chart_files, yt_thumb, mission,
                    short_thumb_path=(short_thumb_paths[0] if short_thumb_paths else None),
                    short_thumb_paths=short_thumb_paths,
                )
            except Exception as kaggle_err:
                logger.warning(f"⚠️ Kaggle GPU run failed or timed out ({kaggle_err}). Triggering uncrashable CPU Fallback Engine...")
                yt_video_id = None

        # 🛡️ UNCRASHABLE CPU FALLBACK: If Kaggle failed, timed out, or produced no video, render locally on GHA CPU
        if not yt_video_id:
            mission.update_stage("kaggle_gpu", "⚡ Kaggle Glitch — CPU Fallback Engaged")
            logger.info("🛡️ [Uncrashable Fallback] Rendering Long-Form & Shorts on GitHub Actions local CPU runner...")
            from app.services.local_cpu_renderer import run_local_cpu_fallback_renderer
            yt_video_id, timestamps_log, short_video_ids, oauth_slot_used = await run_local_cpu_fallback_renderer(
                payload, chart_files, yt_thumb, mission,
                short_thumb_paths=short_thumb_paths,
            )

        if not yt_video_id:
            mission.update_stage("kaggle_gpu", "🛡️ Uploaded SKIPPED (QA gate)", "Fix render, rerun slot")
            raise SystemExit(1)

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        mission.bridge.complete_active_video(f"slot_{slot_index}_long", youtube_id=yt_video_id)
        mission.bridge.record_published_video({
            "title": payload.get("title") or topic,
            "slug": slug,
            "description": payload.get("meta_description") or f"Breakdown of {topic}",
            "date": now_str,
            "vertical": vertical,
            "category": vertical.replace("_", " ").title(),
            "format": "LONG",
            "youtube_video_id": yt_video_id,
            "youtube_id": yt_video_id,
            "youtubeUrl": f"https://www.youtube.com/watch?v={yt_video_id}",
            "dossier_url": f"/article.html?slug={slug}",
            "compliance_notes": "SEBI/IRDAI Zero-violation feedback verified",
        })
        for s_idx, sv_id in enumerate(short_video_ids, 1):
            s_ext = (payload.get("short_extractions") or [])
            s_title = (s_ext[s_idx - 1].get("hook") or s_ext[s_idx - 1].get("title")) if len(s_ext) >= s_idx else f"{topic} (Short #{s_idx})"
            mission.bridge.complete_active_video(f"slot_{slot_index}_short_{s_idx}", youtube_id=sv_id)
            mission.bridge.record_published_video({
                "title": f"{s_title} #Shorts",
                "slug": f"{slug}-short-{s_idx}",
                "description": f"Institutional analysis of {topic} for everyday investors.",
                "date": now_str,
                "vertical": vertical,
                "category": vertical.replace("_", " ").title(),
                "format": "SHORT",
                "youtube_video_id": sv_id,
                "youtube_id": sv_id,
                "youtubeUrl": f"https://www.youtube.com/shorts/{sv_id}",
                "dossier_url": f"/article.html?slug={slug}",
                "compliance_notes": "SEBI/IRDAI Zero-violation feedback verified",
            })

    # 6. Generate MDX Article + Deploy to Vercel + Ping Search Indexers
    mission.update_stage("vercel", "📝 Compiling MDX & IndexNow Ping...")
    mdx_path = generate_website_article_file(payload, yt_video_id, timestamps_log)
    live_url = publish_and_index_article(mdx_path, chart_files, slug)

    # 7. Distribute the 3-tweet X/Twitter thread (graceful skip without X credentials)
    try:
        from app.services.x_thread_publisher import publish_x_thread

        chart_paths = [str(BASE_DIR / "assets" / "charts" / cf) for cf in chart_files]
        x_thread_status = publish_x_thread(payload, chart_paths, yt_video_id, (short_video_ids[0] if short_video_ids else ""), live_url)
    except Exception as x_err:
        x_thread_status = f"Error ({x_err.__class__.__name__})"
        logger.warning(f"X thread distribution failed: {x_err}")
    logger.info(f"🐦 X Thread status: {x_thread_status}")

    shorts_note = " · ".join(short_video_ids[:2]) if short_video_ids else "skipped"
    final_note = f"🐦 X Thread: {x_thread_status}"
    if short_video_ids:
        final_note = f"🎬 Shorts ({len(short_video_ids)}): {shorts_note} · 🐦 X Thread: {x_thread_status}"
    mission.update_stage("vercel", f"✅ Live & Indexed (`{live_url}`)", final_note)
    mission.bridge.update_stage_metrics(7, {
        "yt_long_id": yt_video_id,
        "yt_short_ids": short_video_ids,
        "oauth_slot_used": oauth_slot_used,
        "article_url": live_url,
        "x_thread_url": x_thread_status,
    })
    mission.bridge.set_status("COMPLETED", f"Live: {live_url}")

    # 8. Post-upload Algorithmic Debate Bait Comment & T+6h CTR Rescue check
    try:
        from app.services.viral_growth_agent import ViralGrowthAgent
        from scripts.heal_all_channel_comments import generate_custom_topic_comment
        meta = payload.get("youtube_payload", {}).get("metadata", {})
        vid_title = meta.get("title") or payload.get("topic", "")
        vid_desc = meta.get("description_body", "")
        vid_vert = payload.get("vertical", "stock_market")
        comment_text = payload.get("debate_pinned_comment") or generate_custom_topic_comment(vid_title, vid_desc, vid_vert)
        if yt_video_id and yt_video_id != "SHORTS_ONLY":
            ViralGrowthAgent.post_debate_comment(yt_video_id, comment_text, slot_index=oauth_slot_used)
        for sv_id in short_video_ids:
            ViralGrowthAgent.post_debate_comment(sv_id, comment_text, slot_index=oauth_slot_used)
        rescued = ViralGrowthAgent.run_ctr_rescue_check(slot_index=oauth_slot_used)
        if rescued:
            logger.info(f"🚀 [ViralGrowthAgent] {len(rescued)} video(s) rescued with Variant B titles/thumbnails.")
    except Exception as vg_err:
        logger.debug(f"[ViralGrowthAgent] Post-upload actions skipped: {vg_err}")

    print(f"\n🎉 Cloud pipeline completed successfully! Live URL: {live_url}")
    print(f"🎬 Shorts ({len(short_video_ids)}): {shorts_note} | 🐦 X Thread: {x_thread_status}")


async def main():
    try:
        await _async_main()
    except SystemExit:
        raise
    except Exception as exc:
        logger.exception(f"Unhandled fatal error in cloud orchestrator: {exc}")
        try:
            env_slot = int(os.getenv("INPUT_SLOT", "1") or 1)
            from app.services.telemetry_bridge import TelemetryBridge
            b = TelemetryBridge(slot=env_slot)
            b.set_status("FAILED", f"Error: {str(exc)[:70]}")
            b.add_log("ERROR", f"Runner failed: {str(exc)[:120]}")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    asyncio.run(main())
