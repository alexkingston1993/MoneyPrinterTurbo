"""
Local Fast Short Renderer & Uploader (app/services/short_renderer.py).
Renders 9:16 companion YouTube Shorts directly on GitHub Actions (CPU ffmpeg)
with Edge-TTS, Hormozi subtitles, HUD graphics, OpenMontage QA, and Headless YouTube Upload.
"""

import os
import sys
import re
import json
import shutil
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Optional
from loguru import logger

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = BASE_DIR / "assets"
AVATARS_DIR = ASSETS_DIR / "avatars"
CHARTS_DIR = ASSETS_DIR / "charts"
WORK_DIR = BASE_DIR / "build"
WORK_DIR.mkdir(parents=True, exist_ok=True)

VOICE_PERSONAS = {
    "stock_market": {
        "voice": "en-US-AndrewNeural",
        "rate": "+4%",
        "pitch": "-2Hz",
        "desc": "Quantitative Institutional Desk Anchor",
    },
    "crypto": {
        "voice": "en-US-BrianMultilingualNeural",
        "rate": "+6%",
        "pitch": "-1Hz",
        "desc": "Derivatives & On-Chain Strategist",
    },
    "insurance": {
        "voice": "en-IN-PrabhatNeural",
        "rate": "+3%",
        "pitch": "-2Hz",
        "desc": "Forensic Policy & Risk Auditor",
    },
}

HUD_BADGES = {
    "stock_market": "LIVE INSTITUTIONAL FLOW",
    "crypto": "LIVE ON-CHAIN DATA",
    "insurance": "POLICY WORDING AUDIT",
}


def _find_fontfile() -> str:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        str(BASE_DIR / "assets" / "fonts" / "Inter-Bold.ttf"),
        "/Library/Fonts/Arial.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return ""


from thumbnail_generator import (
    generate_high_ctr_short_cover,
    generate_persistent_short_header,
)


def _probe_ffmpeg_caps() -> dict:
    caps = {"subtitles": False, "drawtext": False, "drawbox": False}
    try:
        chk = subprocess.run(["ffmpeg", "-filters"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        caps["subtitles"] = " subtitles " in chk.stdout
        caps["drawtext"] = " drawtext " in chk.stdout
        caps["drawbox"] = " drawbox " in chk.stdout
    except Exception:
        pass
    return caps

FFCAPS = _probe_ffmpeg_caps()


def _hud_filters(duration: float, vertical: str, fontfile: str = "", w: int = 1080, h: int = 1920) -> list:
    dur = max(1.0, float(duration))
    bar_y = h - 26
    chain = []
    if FFCAPS.get("drawbox"):
        prog = (
            f"drawbox=x=0:y={bar_y}:w={w}:h=6:color=0x10B981@0.25:t=fill:enable='gte(t,5.0)',"
            f"drawbox=x=0:y={bar_y}:w='min({w}\\,(t/{dur:.2f})*{w})':h=6:color=0x34D399@0.95:t=fill:enable='gte(t,5.0)'"
        )
        chain.append(prog)
    if fontfile and FFCAPS.get("drawtext"):
        badge = HUD_BADGES.get(vertical or "", "THE BULL PRINT")
        ff_esc = fontfile.replace(":", "\\:").replace("'", "\\'")
        chain.append(
            f"drawbox=x=32:y=36:w=440:h=48:color=0x064E3B@0.85:t=fill:enable='gte(t,5.0)',"
            f"drawtext=fontfile='{ff_esc}':text='{badge}':fontcolor=0x34D399:fontsize=22:x=48:y=50:enable='gte(t,5.0)'"
        )
    return chain


async def make_short_tts_and_subtitles(text: str, mp3_path: Path, ass_path: Path, persona: dict = None) -> float:
    from app.services.cloned_prabhat_tts import synthesize_arjun_voice
    synthesize_arjun_voice(text, mp3_path)

    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(mp3_path)],
        stdout=subprocess.PIPE, text=True, check=True
    )
    duration = float(res.stdout.strip())

    ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, BackColour, Bold, Outline, Shadow, Alignment, MarginV
Style: Hormozi,Arial,64,&H0081B910,&H80000000,-1,4,2,2,220

[Events]
Format: Layer, Start, End, Style, Text
"""
    words = text.strip().split()
    events = []
    if words and duration > 0:
        word_dur = duration / len(words)
        for i, w in enumerate(words):
            w_start = i * word_dur
            w_end = min(duration, (i + 1) * word_dur)
            # Keep 0.0s to 5.0s 100% pristine Flow AI artwork (no text collision)
            if w_end <= 5.0:
                continue
            w_start = max(5.0, w_start)
            s_m, s_s = divmod(w_start, 60)
            e_m, e_s = divmod(w_end, 60)
            events.append(f"Dialogue: 0,0:{int(s_m):02d}:{s_s:05.2f},0:{int(e_m):02d}:{e_s:05.2f},Hormozi,{w.upper()}")

    ass_path.write_text(ass_header + "\n".join(events), encoding="utf-8")
    return duration



def verify_short_qa(mp4_path: Path, expected_min_dur: float = 0.0) -> dict:
    audit = {"passed": False, "reasons": []}
    try:
        res = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(mp4_path)],
            stdout=subprocess.PIPE, text=True, check=True
        )
        dur = float(res.stdout.strip())
        if dur < 10.0:
            audit["reasons"].append(f"Duration too short ({dur:.1f}s)")
        else:
            audit["passed"] = True
    except Exception as e:
        audit["reasons"].append(str(e))
    return audit


def format_vertical_description(short_data: dict, vertical: str, long_video_id: str = "") -> str:
    """Formats sentence-safe YouTube Shorts description with vertical-specific disclaimer and real domain."""
    spoken = str(short_data.get("spoken_hook_and_body") or short_data.get("hook") or "").strip()
    sentences = [s.strip() for s in re.split(r'(?<=[.?!])\s+', spoken) if s.strip()]
    hook_summary = ""
    for s in sentences:
        if len(hook_summary) + len(s) + 1 <= 240:
            hook_summary = f"{hook_summary} {s}".strip()
        else:
            if not hook_summary:
                hook_summary = s[:240].rsplit(' ', 1)[0] + "..."
            break
    if not hook_summary:
        hook_summary = spoken[:200].rsplit(' ', 1)[0] + "..." if len(spoken) > 200 else spoken

    vert = (vertical or "").lower()
    if vert == "insurance":
        disclaimer = "🛡️ IRDAI Educational Forensics: Policy terms, room-rent math & claim forensics only — check your policy schedule."
        dossier_text = "🔍 Read the full Policy Forensic Dossier & Claim Audit: https://thebullprint.in"
    elif "crypto" in vert:
        disclaimer = "⚡ VDA & On-Chain Educational Research: Market structure & liquidity risk analysis only — not financial advice."
        dossier_text = "📊 Full On-Chain CVD & Tax Dossier: https://thebullprint.in"
    else:
        disclaimer = "📌 SEBI Educational Research: Market structure, order-flow & derivative dynamics only — not investment advice."
        dossier_text = "📈 Full Institutional Order-Flow Dossier: https://thebullprint.in"

    parts = [hook_summary, ""]
    if long_video_id:
        parts.extend([f"▶️ Watch the FULL MASTERCLASS: https://youtu.be/{long_video_id}", ""])
    parts.extend([dossier_text, "🛠️ Free Financial Tools & Calculators: https://thebullprint.in", "", disclaimer])
    return "\n".join(parts)



async def render_and_upload_short_local(
    payload: dict,
    short_index: int = 1,
    thumb_path: Optional[Path] = None,
    header_path: Optional[Path] = None,
    vertical: str = "stock_market",
    existing_long_id: str = "",
) -> str:
    """
    Renders Short locally on GitHub Actions Ubuntu Runner using CPU FFmpeg
    with persistent top hook header (t=0 to end) and uploads directly to YouTube.
    """
    from kaggle_kernel.kaggle_worker import upload_youtube_headless

    logger.info(f"⚡ [GHA Local Engine] Starting parallel rendering of Short #{short_index} ({vertical})...")
    yt = payload.get("youtube_payload", {})
    shorts_list = yt.get("short_extractions") or []
    if not shorts_list and yt.get("short_extraction"):
        shorts_list = [yt["short_extraction"]]

    if short_index <= len(shorts_list):
        short_data = shorts_list[short_index - 1]
    elif shorts_list:
        short_data = shorts_list[0]
    else:
        logger.warning(f"No short extraction data found for Short #{short_index}")
        return ""

    persona = VOICE_PERSONAS.get(vertical, VOICE_PERSONAS["stock_market"])
    narration = " ".join(filter(None, [
        str(short_data.get("spoken_hook_and_body", "")).strip(),
        str(short_data.get("cta_to_long_video", "")).strip(),
    ]))
    if not narration:
        narration = "Watch the institutional breakdown on The Bull Print. Follow for daily edge."

    tag = f"local_{short_index:02d}_{os.getpid()}"
    mp3 = WORK_DIR / f"short_{tag}.mp3"
    ass = WORK_DIR / f"short_{tag}.ass"
    out_mp4 = WORK_DIR / f"final_short_{tag}.mp4"
    cover_jpg = thumb_path if (thumb_path and Path(thumb_path).exists()) else (WORK_DIR / f"cover_{tag}.jpg")
    header_png = header_path if (header_path and Path(header_path).exists()) else (WORK_DIR / f"header_{tag}.png")

    meta = yt.get("metadata", {})
    short_title = str(short_data.get("short_title", "") or meta.get("title", "The Bull Print Daily Brief"))
    if not short_title.endswith("#Shorts"):
        short_title = f"{short_title} #Shorts"

    raw_hook = (
        str(short_data.get("hook") or "")
        or str(short_data.get("short_title") or "")
        or str(short_data.get("spoken_hook_and_body", "")).split(".")[0]
        or short_title
    )
    s_hook = short_data.get("thumbnail_hook")

    chart_png = None
    chart_ref = str(short_data.get("chart_image_ref", "") or "")
    if chart_ref and (CHARTS_DIR / chart_ref).exists():
        chart_png = CHARTS_DIR / chart_ref
    if chart_png is None:
        pngs = sorted(CHARTS_DIR.glob("*.png"))
        if pngs:
            chart_png = pngs[0]

    from thumbnail_generator import get_flow_ai_master
    # 🎨 Direct Master-Asset Injection Pipeline: Lock Flow AI master
    chosen_master = get_flow_ai_master(raw_hook, vertical, index=short_index - 1)
    shutil.copy2(chosen_master, cover_jpg)

    dur = await make_short_tts_and_subtitles(narration, mp3, ass, persona)

    fontfile = _find_fontfile()
    hud_list = _hud_filters(min(dur, 58.5), vertical, fontfile, w=1080, h=1920)
    tail = list(hud_list)
    if FFCAPS.get("subtitles"):
        tail.append(f"subtitles='{ass.as_posix()}'")

    # 0.0s to 5.0s Full-Bleed Flow AI Master Lock (Beating YouTube's Sampler between 2.0s and 4.0s)
    # t > 5.0s: Forensic Chart breakdown with clean HUD progress bar & subtitles (No Pillow stamps)
    base_chain = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5,"
        "drawbox=x=0:y=0:w=1080:h=1920:color=black@0.60:t=fill[bg];"
        "[0:v]scale=1040:-1[fg_chart];"
        "[bg][fg_chart]overlay=20:540[with_chart];"
        "[with_chart]drawbox=x=18:y=538:w=1044:h=590:color=0x10B981@0.8:t=3[chart_view]"
    )
    if tail:
        base_chain += ";" + "[chart_view]" + ",".join(tail) + "[chart_analyzed]"
        final_bg = "[chart_analyzed]"
    else:
        final_bg = "[chart_view]"

    filter_graph = (
        f"{base_chain};"
        f"[1:v]scale=1080:1920[flow_master];"
        f"{final_bg}[flow_master]overlay=0:0:enable='between(t,0,5.0)'[v]"
    )

    vcodec = ["-c:v", "h264_videotoolbox", "-b:v", "6000k"] if sys.platform == "darwin" else ["-c:v", "libx264", "-preset", "ultrafast"]

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(chart_png or ASSETS_DIR / "charts" / "chart_1.png"),
        "-loop", "1", "-i", str(cover_jpg),
        "-i", str(mp3),
        "-filter_complex", filter_graph,
        "-map", "[v]", "-map", "2:a",
        "-af", "silenceremove=stop_periods=-1:stop_duration=0.35:stop_threshold=-42dB,loudnorm=I=-14:TP=-1.5:LRA=11",
        *vcodec,
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-t", f"{min(dur, 58.5):.2f}",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True)

    qa = verify_short_qa(out_mp4)
    if not qa["passed"]:
        logger.error(f"❌ Local Short #{short_index} failed QA: {qa['reasons']}")
        return ""

    description_body = format_vertical_description(short_data, vertical)
    custom_status = short_data.get("status") or yt.get("status") or {}
    short_yt_payload = {
        "metadata": {
            "title": short_title,
            "description_body": description_body,
            "tags": (meta.get("tags", []) or [])[:15] + ["shorts"],
        },
        "status": custom_status,
        "force_upload": yt.get("force_upload", False) or payload.get("force_upload", False) or True,
    }

    st_thumb = cover_jpg if cover_jpg.exists() else (thumb_path if (thumb_path and thumb_path.exists()) else (BASE_DIR / "assets" / "thumbnails" / "default_thumb.jpg"))
    vid_id = upload_youtube_headless(out_mp4, st_thumb, short_yt_payload)
    logger.info(f"✅ [GHA Local Engine] Short #{short_index} rendered & uploaded to YouTube! ID: {vid_id}")
    return vid_id
