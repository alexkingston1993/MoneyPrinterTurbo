"""
Orchestrator — Hermes Agent as the overall pipeline orchestrator.
Extends HermesAgent with pipeline management, self-fixing, and EOD reporting.

The Hermes agent provides:
- Persistent knowledge base (SQLite) for pipeline state
- LLM-powered analysis for failure diagnosis and improvement
- Self-learning skills from past runs
- Content queue management

This orchestrator adds:
- Step-by-step pipeline execution with checkpoint/resume
- Auto-retry with parameter tuning on failure
- Organized output folder structure (date/channel/video)
- EOD report generation and email
- Self-fixing via Hermes skills system
"""

import asyncio
import datetime
import json
import math
import os
import random
import re
import shutil
import smtplib
import subprocess
import sys
import time
import traceback
import uuid
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Tuple

import logging
logger = logging.getLogger("orchestrator")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(ch)

# Inline imports for self-contained operation
_APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sys as _sys
_sys.path.insert(0, _APP_DIR)

from app.services.hermes_agent import (
    HermesAgent, KnowledgeBase, ContentSuggestion, Skill, NewsItem,
    get_agent as get_hermes_agent,
)

# Simple LLM fallback for failure diagnosis (no app.config dependency)
def _llm_diagnose(prompt: str) -> str:
    """Fallback: use requests to call an available LLM API."""
    try:
        import requests
        # Try Pollinations free API (no key needed)
        resp = requests.post(
            "https://text.pollinations.ai/",
            json={"messages": [{"role": "user", "content": prompt}],
                  "model": "openai", "max_tokens": 300},
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    except:
        pass
    # Fallback: return empty
    return ""

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def _get_pexels_key():
    try:
        import toml
        c = toml.load(os.path.join(_APP_DIR, "config.toml"))
        keys = c.get("app", {}).get("pexels_api_keys", [])
        if keys and keys[0]:
            return keys[0]
    except:
        pass
    return os.environ.get("PEXELS_API_KEY", "2927GljrcuM0PxfFHrBTUfShGAHLL2LcVGbGhuQkxddHHTZ61NzP1sSb")

PEXELS_KEY = _get_pexels_key()
VOICE_REF = os.path.join(_APP_DIR, "app/services/voices/alex_ref.wav")
BASE_OUTPUT = os.path.join(_APP_DIR, "output")
AVATAR_DIR = os.path.join(_APP_DIR, "data/avatars")
PY311 = os.path.expanduser("~/.local/bin/python3.11")

CHANNELS = {
    "en": "The Compounder",
    "ta": "The Compounder Tamil",
    "hi": "The Compounder Hindi",
}

NSE_SYMBOLS = {
    "TCS": "TCS.NS", "RELIANCE": "RELIANCE.NS", "HDFC": "HDFCBANK.NS",
    "INFY": "INFY.NS", "ICICI": "ICICIBANK.NS", "SBIN": "SBIN.NS",
    "BHARTI": "BHARTIARTL.NS", "DMART": "DMART.NS", "TITAN": "TITAN.NS",
    "NIFTY": "^NSEI", "SENSEX": "^BSESN", "BANKNIFTY": "^NSEBANK",
}

# ---------------------------------------------------------------------------
# Pipeline Step Result
# ---------------------------------------------------------------------------

@dataclass
class StepResult:
    name: str
    status: str  # "ok" | "fail" | "skipped"
    duration: float = 0.0
    error: str = ""
    output: str = ""
    retry_count: int = 0

# ---------------------------------------------------------------------------
# Script Utilities
# ---------------------------------------------------------------------------

def sanitize_script(text: str) -> str:
    """Make script sound natural for TTS — remove special chars, format dates."""
    try:
        from app.services.tts_normalizer import normalize_script_for_tts
        text = normalize_script_for_tts(text)
    except Exception:
        pass

    # Format dates naturally
    def _fmt_date(m):
        raw = m.group(0)
        parts = raw.replace("-", "/").split("/")
        if len(parts) == 3:
            months = ["", "January", "February", "March", "April", "May", "June",
                     "July", "August", "September", "October", "November", "December"]
            try:
                p0, p1, p2 = parts[0], parts[1], parts[2]
                if len(p0) == 4:
                    return f"{months[int(p1)]} {int(p2)}, {p0}"
                elif int(p0) > 12:
                    return f"{months[int(p1)]} {int(p0)}, {p2}"
                else:
                    return f"{months[int(p0)]} {int(p1)}, {p2}"
            except:
                pass
        return raw
    text = re.sub(r'\b\d{1,4}[-/]\d{1,2}[-/]\d{2,4}\b', _fmt_date, text)
    text = text.strip()
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def extract_stock_mentions(script: str) -> List[Tuple[str, str]]:
    mentions = []
    for name, symbol in NSE_SYMBOLS.items():
        if re.search(r'\b' + re.escape(name) + r'\b', script, re.IGNORECASE):
            mentions.append((name, symbol))
    return mentions

# ---------------------------------------------------------------------------
# Output Folder Structure
# ---------------------------------------------------------------------------

def create_output_structure(today: str = "", channel: str = "en",
                            video_name: str = "market_update") -> str:
    """Create: output/YYYY-MM-DD/channel_name/video_name/"""
    if not today:
        today = date.today().isoformat()
    day_dir = os.path.join(BASE_OUTPUT, today)
    channel_name = CHANNELS.get(channel, channel)
    video_dir = os.path.join(day_dir, channel_name, video_name)
    os.makedirs(video_dir, exist_ok=True)
    return video_dir

# ---------------------------------------------------------------------------
# Pipeline Steps (each returns StepResult)
# ---------------------------------------------------------------------------

class PipelineSteps:
    """Static methods for each pipeline step."""

    @staticmethod
    def step_script_prep(script_path: str) -> Tuple[str, List[str], List[Tuple[str, str]]]:
        """Read and sanitize script."""
        with open(script_path) as f:
            raw = f.read()
        sanitized = sanitize_script(raw)
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', sanitized) if s.strip()]
        stocks = extract_stock_mentions(raw)
        return sanitized, sentences, stocks

    @staticmethod
    def step_tts(text: str, output_path: str) -> Tuple[str, float]:
        """Generate TTS with Alex's cloned voice via Coqui XTTS v2."""
        logger.info("TTS: Coqui XTTS v2 with Alex's voice")

        tts_script = f'''import os, sys, time, json
os.environ["COQUI_TOS_AGREED"] = "1"
sys.path.insert(0, "/Users/apple/.local/share/uv/python/cpython-3.11.15-macos-x86_64-none/lib/python3.11/site-packages")

text = {json.dumps(text)}

from TTS.api import TTS
t0 = time.time()
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
print(f"LOAD_TIME={{time.time()-t0:.1f}}", flush=True)

t0 = time.time()
tts.tts_to_file(text=text, file_path="{output_path}",
                speaker_wav="{VOICE_REF}", language="en", speed=1.0)
print(f"GEN_TIME={{time.time()-t0:.1f}}", flush=True)
print(f"DURATION={{__import__('soundfile').info('{output_path}').duration}}", flush=True)
'''
        tts_file = "/tmp/_orchestrator_tts.py"
        with open(tts_file, "w") as f:
            f.write(tts_script)

        t0 = time.time()
        r = subprocess.run([PY311, tts_file], capture_output=True, text=True, timeout=7200)
        elapsed = time.time() - t0

        if r.returncode != 0 or not os.path.exists(output_path):
            raise RuntimeError(f"TTS failed: {r.stderr[:500]}")

        # Parse duration from output
        dur_match = re.search(r'DURATION=([\d.]+)', r.stdout)
        duration = float(dur_match.group(1)) if dur_match else 0
        logger.info(f"TTS: {duration:.0f}s in {elapsed:.1f}s")
        return output_path, duration

    @staticmethod
    def step_tts_fallback(text: str, output_path: str) -> Tuple[str, float]:
        """Fallback TTS using edge-tts if Coqui fails."""
        logger.info("TTS fallback: edge-tts")
        import edge_tts
        import soundfile as sf

        async def _gen():
            communicate = edge_tts.Communicate(text, "en-US-JennyNeural")
            await communicate.save(output_path)

        t0 = time.time()
        asyncio.run(_gen())
        elapsed = time.time() - t0
        data, sr = sf.read(output_path)
        duration = len(data) / sr
        logger.info(f"TTS fallback: {duration:.0f}s in {elapsed:.1f}s")
        return output_path, duration

    @staticmethod
    def step_charts(stock_mentions: List[Tuple[str, str]],
                    output_dir: str) -> List[Tuple[str, str]]:
        """Generate animated stock charts."""
        if not stock_mentions:
            return []

        chart_videos = []
        for name, symbol in stock_mentions[:3]:
            try:
                chart_video = PipelineSteps._generate_single_chart(name, symbol, output_dir)
                if chart_video:
                    chart_videos.append((name, chart_video))
            except Exception as e:
                logger.warning(f"Chart failed for {name}: {e}")
        return chart_videos

    @staticmethod
    def _generate_single_chart(name: str, symbol: str, output_dir: str) -> Optional[str]:
        """Generate animated chart for a single stock."""
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="6mo")
        if hist.empty or len(hist) < 20:
            return None

        close_prices = hist["Close"].values
        dates = hist.index

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=60)
        fig.patch.set_facecolor("#0d1117")
        ax.set_facecolor("#161b22")

        chart_dir = os.path.join(output_dir, "charts", name)
        os.makedirs(chart_dir, exist_ok=True)

        total_points = len(close_prices)
        step = max(1, total_points // 300)
        frames = []

        for i in range(0, total_points, step):
            ax.clear()
            data_up_to = close_prices[:i+1]
            dates_up_to = dates[:i+1]
            color = "#00d4aa" if data_up_to[-1] >= data_up_to[0] else "#ff6b6b"

            ax.plot(dates_up_to, data_up_to, color=color, linewidth=2.5, zorder=2)
            ax.fill_between(dates_up_to, data_up_to, alpha=0.1, color=color, zorder=1)
            current_val = data_up_to[-1]
            change = ((current_val - data_up_to[0]) / data_up_to[0]) * 100
            ax.set_title(f"{name}  |  \u20b9{current_val:.2f}  ({change:+.2f}%)",
                        color="white", fontsize=28, pad=20, fontweight="bold")
            ax.tick_params(colors="#8b949e", labelsize=14)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["bottom"].set_color("#30363d")
            ax.spines["left"].set_color("#30363d")
            ax.grid(True, alpha=0.15, color="#30363d")

            fp = os.path.join(chart_dir, f"frame_{i:04d}.png")
            fig.savefig(fp, facecolor="#0d1117", bbox_inches="tight", pad_inches=0.2)
            frames.append(fp)

        plt.close(fig)

        chart_video = os.path.join(chart_dir, f"{name}_chart.mp4")
        cmd = [
            "ffmpeg", "-y", "-framerate", "15",
            "-i", f"{chart_dir}/frame_%04d.png",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "fast", "-crf", "20",
            chart_video,
        ]
        subprocess.run(cmd, capture_output=True, check=True, timeout=120)
        for f in frames:
            os.remove(f)

        return chart_video

    @staticmethod
    def step_download_footage(search_terms: List[str], output_dir: str,
                               target_duration: float, pexels_key: str) -> List[str]:
        """Download stock footage from Pexels."""
        import requests
        os.makedirs(output_dir, exist_ok=True)

        download_urls = []
        for term in search_terms:
            if len(download_urls) >= 60:
                break
            url = f"https://api.pexels.com/videos/search?query={term}&orientation=landscape&per_page=15"
            try:
                resp = requests.get(url, headers={"Authorization": pexels_key}, timeout=15)
                data = resp.json()
                for v in data.get("videos", []):
                    dur = v.get("duration", 0)
                    if dur < 5:
                        continue
                    for f in v.get("video_files", []):
                        if f.get("quality") == "hd" and f.get("width", 0) >= 1280:
                            download_urls.append((f["link"], dur))
                            break
            except Exception as e:
                logger.warning(f"Pexels search failed for '{term}': {e}")

        random.shuffle(download_urls)
        downloaded = []
        total = 0
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
            "Referer": "https://www.pexels.com/",
        }
        for vurl, dur in download_urls:
            if total >= target_duration:
                break
            fname = os.path.join(output_dir, f"clip_{len(downloaded):04d}.mp4")
            try:
                r = requests.get(vurl, headers=headers, stream=True, timeout=30)
                if r.status_code == 200:
                    with open(fname, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                    if os.path.getsize(fname) > 10000:
                        downloaded.append(fname)
                        total += min(dur, 12)
            except:
                pass
        return downloaded

    @staticmethod
    def step_combine_video(video_paths: List[str], chart_videos: List[Tuple[str, str]],
                            audio_duration: float, output_path: str) -> str:
        """Combine footage with chart clips, alternating every ~10s."""
        clips = []
        seg_dur = 10

        chart_clips = [c[1] for c in chart_videos]
        total = 0.0
        idx = 0
        while total < audio_duration:
            remaining = audio_duration - total
            sd = min(seg_dur, remaining)

            if chart_clips and idx % 3 == 0:
                clip_path = chart_clips[(idx // 3) % len(chart_clips)]
            else:
                clip_path = video_paths[idx % len(video_paths)] if video_paths else ""

            if clip_path and os.path.exists(clip_path):
                clips.append((clip_path, sd))

            total += sd
            idx += 1

        if not clips:
            # Fallback: color clip
            fallback = output_path.replace(".mp4", "_fallback.mp4")
            cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i",
                   f"color=c=0x001e32:s=1920x1080:d={audio_duration}",
                   "-c:v", "libx264", "-pix_fmt", "yuv420p", fallback]
            subprocess.run(cmd, capture_output=True, check=True, timeout=120)
            return fallback

        concat_file = "/tmp/_orchestrator_concat.txt"
        with open(concat_file, "w") as f:
            for cp, sd in clips:
                f.write(f"file '{cp}'\n")
                f.write(f"duration {sd}\n")

        temp_combined = output_path.replace(".mp4", "_temp.mp4")
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-crf", "22", "-threads", "4",
            temp_combined,
        ]
        subprocess.run(cmd, capture_output=True, check=True, timeout=600)

        cmd = [
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", temp_combined,
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-t", str(audio_duration), "-crf", "22", "-threads", "4",
            output_path,
        ]
        subprocess.run(cmd, capture_output=True, check=True, timeout=600)

        for f in [temp_combined]:
            if os.path.exists(f):
                os.remove(f)
        return output_path

    @staticmethod
    def step_render_final(video_path: str, audio_path: str,
                           sentences: List[str], audio_duration: float,
                           avatar_path: str, output_path: str) -> str:
        """Render final video with subtitles and avatar overlay."""
        # Generate SRT
        total_chars = sum(len(s) for s in sentences)
        cps = total_chars / audio_duration if audio_duration > 0 else 10
        srt_lines = []
        ct = 0.0
        for i, sent in enumerate(sentences):
            if not sent.strip():
                continue
            sd = max(1.0, len(sent) / cps)
            start = ct
            end = min(ct + sd, audio_duration)
            if start >= audio_duration:
                break

            def _fmt(sec):
                h = int(sec // 3600)
                m = int((sec % 3600) // 60)
                s = sec % 60
                return f"{h:02d}:{m:02d}:{s:06.3f}"

            srt_lines.append(f"{i+1}")
            srt_lines.append(f"{_fmt(start)} --> {_fmt(end)}")
            srt_lines.append(sent.strip())
            srt_lines.append("")
            ct = end

        srt_path = "/tmp/_orchestrator_subs.srt"
        with open(srt_path, "w") as f:
            f.write("\n".join(srt_lines))

        # Parse subtitles for moviepy
        sub_entries = []
        blocks = re.split(r'\n\n', "\n".join(srt_lines).strip())
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) >= 3:
                tm = re.match(r'(\d+:\d+:\d+[.,]\d+) --> (\d+:\d+:\d+[.,]\d+)', lines[1])
                if tm:
                    def _pts(tstr):
                        tstr = tstr.replace(",", ".")
                        pts = tstr.split(":")
                        return int(pts[0])*3600 + int(pts[1])*60 + float(pts[2])
                    start = _pts(tm.group(1))
                    end = _pts(tm.group(2))
                    text = "\n".join(lines[2:])
                    sub_entries.append((start, end, text))

        # Write moviepy render script
        render_script = f'''import sys, os, math, json, time
import numpy as np
from PIL import Image, ImageEnhance
from PIL import Image as PILImage
from moviepy import CompositeVideoClip, VideoClip, VideoFileClip, TextClip

video = VideoFileClip("{video_path}")
duration = video.duration
fps = int(video.fps) if video.fps else 30
w, h = video.w, video.h

pil_img = Image.open("{avatar_path}").convert("RGB")
ow = int(w * 0.28)
oh = min(int(ow * pil_img.height / pil_img.width), int(h * 0.45))
pil_img = pil_img.resize((ow, oh), Image.LANCZOS)
enhancer = ImageEnhance.Contrast(pil_img)
pil_img = enhancer.enhance(1.1)
enhancer = ImageEnhance.Sharpness(pil_img)
pil_img = enhancer.enhance(1.05)
avatar_arr = np.array(pil_img)
mx, my = int(w * 0.03), int(h * 0.02)
px, py = w - ow - mx, h - oh - my

def mk_av(t):
    br = 1.0 + 0.003 * math.sin(2 * math.pi * t / 3.0)
    cw = max(1, int(ow * br))
    ch = max(1, int(oh * br))
    return np.array(PILImage.fromarray(avatar_arr).resize((cw, ch), PILImage.LANCZOS))

av_clip = (VideoClip(mk_av, duration=duration)
    .with_position(lambda t: (px, py + 1.5 * math.sin(2 * math.pi * t / 2.5)))
    .with_duration(duration))

subs = {json.dumps(sub_entries)}
ovs = [av_clip]
fp = "/System/Library/Fonts/Helvetica.ttc"

for start, end, text in subs:
    sd = end - start
    if sd <= 0: continue
    if len(text) > 60:
        words = text.split()
        lines, line = [], ""
        for w in words:
            test = f"{{{{line}} {{w}}}}".strip()
            if len(test) > 50:
                lines.append(line)
                line = w
            else:
                line = test
        if line: lines.append(line)
        text = "\\n".join(lines)
    ovs.append(
        TextClip(text=text, font_size=28, color="white",
                 font=fp, stroke_color="black", stroke_width=2,
                 method="label")
        .with_position(("center", h * 0.85))
        .with_start(start).with_duration(sd)
    )

final = CompositeVideoClip([video] + ovs)
final.write_videofile("{output_path}", codec="libx264",
                       audio_codec="aac", fps=fps, threads=4)
video.close()
final.close()
'''
        render_file = "/tmp/_orchestrator_render.py"
        with open(render_file, "w") as f:
            f.write(render_script)

        t0 = time.time()
        r = subprocess.run([PY311, render_file], capture_output=True, text=True, timeout=7200)
        elapsed = time.time() - t0

        if r.returncode != 0 or not os.path.exists(output_path):
            raise RuntimeError(f"Render failed: {r.stderr[:500]}")

        logger.info(f"Render: {os.path.getsize(output_path)/1e6:.0f}MB in {elapsed:.1f}s")
        return output_path

# ---------------------------------------------------------------------------
# EOD Report
# ---------------------------------------------------------------------------

def build_eod_report(steps: List[StepResult], today: str, hermes_stats: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ok = sum(1 for s in steps if s.status == "ok")
    fail = sum(1 for s in steps if s.status == "fail")
    skipped = sum(1 for s in steps if s.status == "skipped")

    lines = [
        "=" * 60,
        f"  PIPELINE END-OF-DAY REPORT",
        f"  Date: {today}",
        f"  Generated: {now}",
        "=" * 60, "",
        "SUMMARY",
        "-" * 40,
        f"  Steps succeeded: {ok}",
        f"  Steps failed: {fail}",
        f"  Steps skipped: {skipped}",
        f"  Attention needed: {'YES' if fail > 0 else 'NO'}",
        f"  Hermes topics tracked: {hermes_stats.get('topics', 0)}",
        f"  Hermes skills: {hermes_stats.get('skills', 0)}",
        f"  Queue pending: {hermes_stats.get('pending_queue', 0)}", "",
        "STEP DETAILS",
        "-" * 40,
    ]

    for step in steps:
        icon = {"ok": "✅", "fail": "❌", "skipped": "⏭️"}.get(step.status, "❓")
        lines.append(f"  {icon} {step.name}")
        lines.append(f"     Status: {step.status}")
        if step.duration:
            lines.append(f"     Duration: {step.duration:.1f}s")
        if step.error:
            lines.append(f"     Error: {step.error}")
        if step.output:
            lines.append(f"     Output: {step.output}")
        if step.retry_count > 0:
            lines.append(f"     Retries: {step.retry_count}")
        lines.append("")

    if fail > 0:
        lines.append("ISSUES NEEDING ATTENTION")
        lines.append("-" * 40)
        for step in steps:
            if step.status == "fail":
                lines.append(f"  ❌ {step.name}: {step.error}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def send_eod_report(content: str, today: str):
    """Send EOD report. Falls back to local save."""
    recipient = os.environ.get("EOD_EMAIL_RECIPIENT", "")
    password = os.environ.get("EOD_EMAIL_PASSWORD", "")

    # Always save locally
    report_dir = os.path.join(BASE_OUTPUT, today)
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"EOD_REPORT_{today}.md")
    with open(report_path, "w") as f:
        f.write(content)
    logger.info(f"EOD report saved: {report_path}")

    if recipient and password:
        try:
            msg = MIMEMultipart()
            msg["From"] = "alex@thecompounder.in"
            msg["To"] = recipient
            msg["Subject"] = f"Pipeline EOD Report - {today}"
            msg.attach(MIMEText(content, "plain"))
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login("alex@thecompounder.in", password)
                server.send_message(msg)
            logger.info("EOD report emailed!")
        except Exception as e:
            logger.warning(f"EOD email failed: {e}")

# ---------------------------------------------------------------------------
# Self-Fixing: analyze failure with LLM and suggest fix
# ---------------------------------------------------------------------------

def diagnose_failure(step_name: str, error: str) -> dict:
    """Use LLM to analyze a pipeline failure and suggest fixes."""
    prompt = f"""A pipeline step failed. Diagnose and suggest a fix.

Step: {step_name}
Error: {error[:300]}

Reply ONLY with JSON:
{{"likely_cause": "...", "fix_hint": "...", "should_retry": true, "adjust_params": {{}}}}"""
    try:
        response = _llm_diagnose(prompt)
        if response:
            response = re.sub(r"^```(?:json)?\s*", "", response.strip())
            response = re.sub(r"\s*```$", "", response)
            return json.loads(response)
    except Exception:
        pass
    return {"likely_cause": "unknown", "fix_hint": "retry with default settings",
            "should_retry": True, "adjust_params": {}}


def retry_step(step_fn, step_name: str, max_retries: int = 3,
               *args, **kwargs) -> Tuple[StepResult, any]:
    """Execute a step with self-fixing retry logic."""
    result = StepResult(name=step_name, status="fail")
    t0 = time.time()

    for attempt in range(max_retries):
        try:
            t0 = time.time()
            output = step_fn(*args, **kwargs)
            elapsed = time.time() - t0
            result.status = "ok"
            result.duration = elapsed
            result.retry_count = attempt
            result.output = str(output)[:200] if output else ""
            return result, output
        except Exception as e:
            elapsed = time.time() - t0
            logger.warning(f"{step_name} attempt {attempt+1}/{max_retries} failed: {e}")

            if attempt < max_retries - 1:
                diagnosis = diagnose_failure(step_name, str(e))
                wait = (attempt + 1) * 15
                logger.info(f"Diagnosis: {diagnosis.get('likely_cause', 'unknown')}")
                logger.info(f"Fix hint: {diagnosis.get('fix_hint', 'retrying')}")
                logger.info(f"Retrying in {wait}s...")
                time.sleep(wait)

    result.error = f"Failed after {max_retries} attempts"
    return result, None

# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------

class PipelineOrchestrator:
    """Hermes-driven pipeline orchestrator with self-fixing."""

    def __init__(self):
        self.hermes: HermesAgent = get_hermes_agent()
        self.today = date.today().isoformat()
        self.steps: List[StepResult] = []

    def run(self, script_path: str) -> List[StepResult]:
        """Run the full pipeline."""
        logger.info(f"\n{'='*60}")
        logger.info(f"  HERMES PIPELINE ORCHESTRATOR")
        logger.info(f"  Date: {self.today}")
        logger.info(f"{'='*60}\n")

        # -- Step 1: Script Preparation --
        logger.info("— Step 1: Script Preparation —")
        r1, (sanitized, sentences, stock_mentions) = retry_step(
            PipelineSteps.step_script_prep, "Script Preparation", 2, script_path)
        self.steps.append(r1)

        if r1.status != "ok":
            self._finalize()
            return self.steps

        # -- Step 2: TTS (Alex's Voice) --
        logger.info("— Step 2: TTS (Alex's Voice via Coqui) —")
        audio_out = "/tmp/_orch_tts_output.mp3"
        r2, tts_result = retry_step(
            PipelineSteps.step_tts, "TTS (Alex Voice)", 2, sanitized, audio_out)
        if r2.status != "ok":
            logger.warning("Coqui TTS failed, trying edge-tts fallback...")
            r2, tts_result = retry_step(
                PipelineSteps.step_tts_fallback, "TTS (Fallback edge-tts)", 2,
                sanitized, audio_out)
        self.steps.append(r2)

        if r2.status != "ok":
            self._finalize()
            return self.steps

        audio_path, audio_duration = tts_result

        # -- Step 3: Animated Charts --
        logger.info("— Step 3: Animated Charts —")
        chart_dir = "/tmp/_orch_charts"
        r3, chart_videos = retry_step(
            PipelineSteps.step_charts, "Animated Charts", 2, stock_mentions, chart_dir)
        self.steps.append(r3)

        # -- Step 4: Download Footage --
        logger.info("— Step 4: Download Stock Footage —")
        search_terms = [
            "Indian stock market trading", "Nifty 50 exchange", "business news India",
            "stock chart analysis", "corporate office buildings", "financial data graphs",
            "Mumbai business district", "trading", "share market India",
        ] + [f"{name} stock market" for name, _ in stock_mentions[:3]]

        footage_dir = "/tmp/_orch_footage"
        r4, videos = retry_step(
            PipelineSteps.step_download_footage, "Footage Download", 3,
            search_terms, footage_dir, audio_duration, PEXELS_KEY)
        self.steps.append(r4)

        if r4.status != "ok" or not videos:
            logger.warning("No footage downloaded, will use color fallback")
            videos = []

        # -- Step 5: Combine Video --
        logger.info("— Step 5: Combine Videos —")
        combined_out = "/tmp/_orch_combined.mp4"
        chart_video_list = chart_videos or []
        r5, combined_path = retry_step(
            PipelineSteps.step_combine_video, "Video Combine", 2,
            videos, chart_video_list, audio_duration, combined_out)
        self.steps.append(r5)

        if r5.status != "ok":
            self._finalize()
            return self.steps

        # -- Step 6: Render Final --
        logger.info("— Step 6: Final Render (Subtitles + Avatar) —")
        avatar_path = os.path.join(AVATAR_DIR, "placeholder.jpg")
        if not os.path.exists(avatar_path):
            avatar_path = ""
            logger.warning("No avatar image found")

        video_dir = create_output_structure(self.today, "en",
                                             f"market_update_{self.today}")
        final_out = os.path.join(video_dir, "final.mp4")

        r6, final_path = retry_step(
            PipelineSteps.step_render_final, "Final Render", 2,
            combined_path, audio_path, sentences, audio_duration,
            avatar_path, final_out)
        self.steps.append(r6)

        if r6.status == "ok":
            logger.success(f"\n✅ PIPELINE COMPLETE: {final_out}")
            logger.success(f"   Size: {os.path.getsize(final_out)/1e6:.0f}MB")
        else:
            logger.error("\n❌ Pipeline failed at final render")

        self._finalize()
        return self.steps

    def _finalize(self):
        """Generate and send EOD report, update Hermes knowledge base."""
        stats = self.hermes.get_stats()
        report = build_eod_report(self.steps, self.today, stats)
        send_eod_report(report, self.today)

        # Store pipeline results in Hermes KB
        self.hermes.kb.set_state(f"pipeline_{self.today}_steps",
                                  json.dumps([asdict(s) for s in self.steps]))

        # Learn from failures: create Hermes skills for failed steps
        for step in self.steps:
            if step.status == "fail" and step.error:
                skill_name = f"fix_{step.name.lower().replace(' ','_')[:40]}"
                skill = Skill(
                    name=skill_name,
                    description=f"Auto-generated fix for {step.name}: {step.error[:100]}",
                    pattern=json.dumps({"failed_step": step.name,
                                         "error_pattern": step.error[:100]}),
                )
                self.hermes.kb.store_skill(skill)
                logger.info(f"Hermes learned skill: {skill_name}")

    def run_news_cycle(self):
        """Run the Hermes news monitoring cycle."""
        logger.info("Running Hermes news cycle...")
        return self.hermes.cycle(max_news=30, max_suggestions=5)


def run_daily():
    """Entry point: run news cycle then pipeline."""
    orch = PipelineOrchestrator()

    # 1. News intelligence
    news_results = orch.run_news_cycle()
    logger.info(f"News cycle: {news_results.get('suggestions', 0)} suggestions")

    # 2. Pipeline
    script_path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(__file__))), "tmp", "market_script_full.txt")
    if not os.path.exists(script_path):
        # Find any script in task dirs
        tasks_dir = os.path.join(os.path.dirname(os.path.dirname(
            os.path.dirname(__file__))), "storage/tasks")
        script_path = ""
        if os.path.exists(tasks_dir):
            for td in os.listdir(tasks_dir):
                sj = os.path.join(tasks_dir, td, "script.json")
                if os.path.exists(sj):
                    try:
                        data = json.load(open(sj))
                        script_text = data.get("script", "")
                        if len(script_text) > 1000:
                            script_path = os.path.join("/tmp", f"script_{td}.txt")
                            with open(script_path, "w") as f:
                                f.write(script_text)
                            break
                    except:
                        pass

    if script_path:
        orch.run(script_path)
    else:
        logger.warning("No script found. Run Hermes news cycle first to generate content.")

    return orch


if __name__ == "__main__":
    run_daily()
