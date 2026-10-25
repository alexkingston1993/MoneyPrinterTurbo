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
        if not os.getenv("GEMINI_MODEL_NAME") and _cfg.get("gemini_model_name"):
            os.environ["GEMINI_MODEL_NAME"] = _cfg["gemini_model_name"]
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
        timeout_sec: int = 300,  # 5-minute review window before auto-approving
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

    seo_meta = web.get("seo_meta")
    if not isinstance(seo_meta, dict) or not str(seo_meta.get("h1_title", "")).strip():
        web["seo_meta"] = {"h1_title": web.get("seo_title") or meta.get("title") or data.get("topic", "")}

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


def generate_master_json_via_ai_studio(topic: str, market_notes: str, chart_files: List[str], archetype_hint: str = "") -> Dict:
    """Calls Google AI Studio Free Tier with Structured Outputs to generate dual script + article.
    If GEMINI_API_KEY is depleted (429 ResourceExhausted) or the call errors, engages _free_llm_json_fallback.
    archetype_hint forces a specific Narrative Archetype when the Authenticity Engine demands a fresh angle."""
    api_key = os.getenv("GEMINI_API_KEY")
    prompt_file = BASE_DIR / "master_system_prompt.txt"
    schema_file = BASE_DIR / "master_schema.json"

    system_prompt = prompt_file.read_text(encoding="utf-8") if prompt_file.exists() else "Financial Educator"
    user_input = json.dumps({
        "topic": topic,
        "market_data_notes": market_notes,
        "chart_screenshots": chart_files,
        "website_domain": "flipzon.work.gd",
        "narrative_archetype_hint": archetype_hint,
    })

    if api_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            schema_dict = json.loads(schema_file.read_text(encoding="utf-8")) if schema_file.exists() else {}

            logger.info(f"🧠 Calling Google AI Studio ({os.getenv('GEMINI_MODEL_NAME', 'gemini-flash-latest')})...")
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL_NAME", "gemini-flash-latest"),
                contents=user_input,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=schema_dict,
                    temperature=0.4,
                    max_output_tokens=8192,
                ),
            )
            return _enforce_master_keys(json.loads(response.text))
        except Exception as e:
            logger.warning(f"GEMINI_API_KEY depleted or Google AI Studio call failed: {e}")
            logger.info("🔁 Engaging free LLM quota failover (OpenRouter / OpenAI / Pollinations)...")
            fallback_data = _free_llm_json_fallback(system_prompt, user_input)
            if fallback_data:
                return _enforce_master_keys(fallback_data)
            logger.warning("All free LLM providers exhausted — using local payload benchmark.")

    # Fallback to local payload benchmark
    logger.info("ℹ️ Using local payload benchmark.")
    payload_file = BASE_DIR / "payload.json"
    data = json.loads(payload_file.read_text(encoding="utf-8"))
    data["topic"] = topic
    return _enforce_master_keys(data)


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

    dataset_meta = {
        "title": "Flipzon Daily Payload",
        "id": f"{KAGGLE_USERNAME}/{DATASET_SLUG}",
        "licenses": [{"name": "CC0-1.0"}]
    }
    (KAGGLE_STAGE_DIR / "dataset-metadata.json").write_text(json.dumps(dataset_meta), encoding="utf-8")

    logger.info("☁️ Pushing payload & chart PNGs to Private Kaggle Dataset...")
    mission.update_stage("kaggle_gpu", "☁️ Pushing Dataset to Kaggle...")
    subprocess.run(
        ["kaggle", "datasets", "version", "-p", str(KAGGLE_STAGE_DIR), "-m", "Auto daily run", "--dir-mode", "zip"],
        check=True
    )
    time.sleep(12)

    # 2. Push & Trigger Kaggle Dual-T4 GPU Kernel
    kernel_dir = BASE_DIR / "kaggle_kernel"
    logger.info("🔥 Triggering Kaggle Dual-T4 GPU Kernel for Whisper + NVENC Video Render...")
    mission.update_stage("kaggle_gpu", "🔥 Waking Dual-T4 GPU Kernel...")
    subprocess.run(["kaggle", "kernels", "push", "-p", str(kernel_dir)], check=True)

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
        logger.info(f"   [Kaggle GPU Status ({elapsed_m}m {elapsed_s}s)]: {status_out}")

        if "complete" in status_out:
            mission.update_stage("kaggle_gpu", f"✅ Rendered & Uploaded ({elapsed_m}m {elapsed_s}s)")
            break
        elif "error" in status_out or "cancel" in status_out:
            mission.update_stage("kaggle_gpu", "❌ Kaggle Error — Fallback Engaged")
            raise RuntimeError(f"Kaggle GPU Kernel failed: {status_out}")
        elif "queued" in status_out:
            mission.update_stage("kaggle_gpu", f"⏳ Queued on Kaggle ({elapsed_m}m {elapsed_s}s)", "Waiting for free T4 node...")
            time.sleep(30)  # Slower poll while queued
        else:
            mission.update_stage("kaggle_gpu", f"🔥 Encoding NVENC + Whisper ({elapsed_m}m {elapsed_s}s)", "Generating 1080p MP4...")
            time.sleep(20)

    out_dir = BASE_DIR / "kaggle_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["kaggle", "kernels", "output", kernel_id, "-p", str(out_dir)], check=True)

    result_data = json.loads((out_dir / "render_result.json").read_text(encoding="utf-8"))

    # 🛡️ Surface the OpenMontage QA Gate verdict + OAuth slot + Short count on Mission Control
    qa = result_data.get("qa_audit") or {}
    oauth_slot_used = int(result_data.get("oauth_slot_used") or 0)
    shorts_count = result_data.get("shorts_count", len(result_data.get("short_video_ids") or []))
    if qa:
        if qa.get("passed"):
            qa_line = f"🛡️ QA PASSED · {qa.get('mean_volume_db')} dB · black {qa.get('black_ratio')}"
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
        {"platform": "tradingview", "symbol": "CNKADA:NIFTY", "interval": "15", "filename": "nifty_opening_range.png"},
        {"platform": "gocharting", "symbol": "NSE:NIFTY", "filename": "nifty_order_flow_absorption.png"},
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


async def main():
    # -- Daily slot routing: CLI args > GITHUB Action env > default stock pre-open slot
    reg = _slot_registry()
    parser = argparse.ArgumentParser(description="The Bull Print autonomous cloud pipeline")
    parser.add_argument("--slot", type=int, default=0, help="Daily slot 1-6 (vertical cadence)")
    parser.add_argument("--vertical", type=str, default="", help="Explicit vertical override (stock_market|crypto|insurance|crypto_ethereum)")
    parser.add_argument("--shorts-count", type=int, default=0, help="How many 9:16 Shorts to render from this session (1-2)")
    parser.add_argument("--topic", type=str, default="", help="Explicit topic override")
    args, _unknown = parser.parse_known_args()

    env_slot = int(os.getenv("INPUT_SLOT", "0") or 0)
    slot_index = args.slot or env_slot
    slot_cfg = reg.get(slot_index, reg[1])

    env_topic = os.getenv("INPUT_TOPIC", "")
    env_notes = os.getenv("INPUT_NOTES", "")
    env_vertical = os.getenv("INPUT_VERTICAL", "")
    env_shorts = int(os.getenv("INPUT_SHORTS_COUNT", "0") or 0)

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
    payload = generate_master_json_via_ai_studio(topic, notes, chart_files)
    payload["vertical"] = vertical                # drives kernel voice persona + HUD badge
    payload["search_cluster"] = search_cluster    # drives description + tag SEO weave

    # 🛡️ THE COMPLIANCE GATE (zero-tolerance SEBI + IRDAI + YouTube audit & 30-day freshness)
    mission.update_stage("gemini", "🛡️ Auditing Compliance Gate...", "SEBI regex + freshness + LLM auditor")
    try:
        from app.services.compliance_gate import ComplianceGate, ComplianceGateError

        payload = ComplianceGate.audit_and_enforce(payload)
    except ComplianceGateError as e:
        logger.error(str(e))
        mission.update_stage("gemini", "🚨 COMPLIANCE HALT", str(e)[:120])
        _send_telegram("🚨 *CRITICAL COMPLIANCE HALT*\n" + str(e)[:400])
        raise SystemExit(1)
    slug = payload["campaign_id"]
    mission.update_stage("gemini", f"✅ Generated + Compliance-Approved (`{slug}`)", _vertical_badge(vertical))

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
                topic, notes, chart_files, archetype_hint=report.get("archetype", "")
            )
            payload = ComplianceGate.audit_and_enforce(payload)
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

    # 4. Generate Thumbnail & Enter 5-Min Human-in-the-Loop Approval Gate
    mission.update_stage("thumbnail", "🎨 Rendering Pillow Graphics...")
    headline_words = payload["youtube_payload"]["metadata"]["thumbnail_top_text"].split()[:4]
    primary_chart = BASE_DIR / "assets" / "charts" / chart_files[0]
    avatar_1 = BASE_DIR / "assets" / "avatars" / "avatar_1.png"
    yt_thumb, discover_img = create_marketing_images(primary_chart, avatar_1, headline_words, slug)

    # Await approval or live 3-word edit from Alex via Telegram
    yt_thumb = mission.await_thumbnail_approval_or_edit(
        yt_thumb=yt_thumb,
        primary_chart=primary_chart,
        avatar_path=avatar_1,
        headline_words=headline_words,
        slug=slug,
        timeout_sec=300
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
    mission.update_stage("kaggle_gpu", "🚀 Dispatching to Kaggle Dual-T4 GPU...")
    yt_video_id, timestamps_log, short_video_ids, oauth_slot_used = run_kaggle_gpu_renderer(
        payload, chart_files, yt_thumb, mission,
        short_thumb_path=(short_thumb_paths[0] if short_thumb_paths else None),
        short_thumb_paths=short_thumb_paths,
    )
    for sid in short_video_ids:
        logger.info(f"🎬 9:16 #Shorts published: https://youtube.com/shorts/{sid}")

    # 🛡️ QA-gate halt: kernel skipped YouTube upload → don't publish an article without a video id
    if not yt_video_id:
        mission.update_stage("kaggle_gpu", "🛡️ Uploaded SKIPPED (QA gate)", "Fix render, rerun slot")
        raise SystemExit(1)

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

    print(f"\n🎉 Cloud pipeline completed successfully! Live URL: {live_url}")
    print(f"🎬 Shorts ({len(short_video_ids)}): {shorts_note} | 🐦 X Thread: {x_thread_status}")


if __name__ == "__main__":
    asyncio.run(main())
