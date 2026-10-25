"""
Local Fast Short Renderer & Uploader (app/services/short_renderer.py).
Renders 9:16 companion YouTube Shorts directly on GitHub Actions (CPU ffmpeg)
with Edge-TTS, Hormozi subtitles, HUD graphics, OpenMontage QA, and Headless YouTube Upload.
"""

import os
import re
import json
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
        "voice": "en-US-AndrewMultilingualNeural",
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
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return ""


def _hud_filters(duration: float, vertical: str, fontfile: str = "", w: int = 1080, h: int = 1920) -> list:
    dur = max(1.0, float(duration))
    bar_y = h - 26
    prog = (
        f"drawbox=x=0:y={bar_y}:w={w}:h=6:color=0x10B981@0.25:t=fill,"
        f"drawbox=x=0:y={bar_y}:w='min({w}\\,(t/{dur:.2f})*{w})':h=6:color=0x34D399@0.95:t=fill"
    )
    chain = [prog]
    if fontfile:
        badge = HUD_BADGES.get(vertical or "", "THE BULL PRINT")
        ff_esc = fontfile.replace(":", "\\:").replace("'", "\\'")
        chain.append(
            f"drawbox=x=32:y=36:w=440:h=48:color=0x064E3B@0.85:t=fill,"
            f"drawtext=fontfile='{ff_esc}':text='{badge}':fontcolor=0x34D399:fontsize=22:x=48:y=50"
        )
    return chain


async def make_short_tts_and_subtitles(text: str, mp3_path: Path, ass_path: Path, persona: dict) -> float:
    import edge_tts
    comm = edge_tts.Communicate(
        text=text,
        voice=persona.get("voice", "en-US-AndrewNeural"),
        rate=persona.get("rate", "+3%"),
        pitch=persona.get("pitch", "+0Hz")
    )
    await comm.save(str(mp3_path))

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


async def render_and_upload_short_local(
    payload: dict,
    short_index: int = 1,
    thumb_path: Optional[Path] = None,
    vertical: str = "stock_market",
    existing_long_id: str = "",
) -> str:
    """
    Renders Short #1 locally on GitHub Actions Ubuntu Runner using CPU FFmpeg
    and uploads directly to YouTube with synthetic media status.
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

    dur = await make_short_tts_and_subtitles(narration, mp3, ass, persona)

    chart_png = None
    chart_ref = str(short_data.get("chart_image_ref", "") or "")
    if chart_ref and (CHARTS_DIR / chart_ref).exists():
        chart_png = CHARTS_DIR / chart_ref
    if chart_png is None:
        pngs = sorted(CHARTS_DIR.glob("*.png"))
        if pngs:
            chart_png = pngs[0]

    avatar_img = AVATARS_DIR / "avatar_1.png"
    if not avatar_img.exists():
        avatar_img = BASE_DIR / "avatar_1.png"

    fontfile = _find_fontfile()
    hud_list = _hud_filters(min(dur, 58.5), vertical, fontfile, w=1080, h=1920)
    tail = list(hud_list)
    tail.append(f"subtitles='{ass.as_posix()}'")

    filter_graph = (
        "[0:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960[chartm];"
        "[1:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960[ava];"
        "[chartm][ava]vstack=inputs=2,"
        "drawbox=x=0:y=956:w=1080:h=8:color=0x10B981@1.0:t=fill"
    )
    if tail:
        filter_graph += "," + ",".join(tail)
    filter_graph += "[v]"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(chart_png or avatar_img),
        "-loop", "1", "-i", str(avatar_img),
        "-i", str(mp3),
        "-filter_complex", filter_graph,
        "-map", "[v]", "-map", "2:a",
        "-c:v", "libx264", "-preset", "ultrafast",
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

    meta = yt.get("metadata", {})
    short_title = str(short_data.get("short_title", "") or meta.get("title", "The Bull Print Daily Brief"))
    if not short_title.endswith("#Shorts"):
        short_title = f"{short_title} #Shorts"

    description_body = (
        f"{str(short_data.get('spoken_hook_and_body', ''))[:180]}\n\n"
        f"🛠️ Get every free trading tool: https://the-bull-print.vercel.app/tools\n\n"
        f"🎓 SEBI: Educational content only — not investment advice."
    )
    short_yt_payload = {
        "metadata": {
            "title": short_title,
            "description_body": description_body,
            "tags": (meta.get("tags", []) or [])[:15] + ["shorts"],
        }
    }

    st_thumb = thumb_path if (thumb_path and thumb_path.exists()) else (BASE_DIR / "assets" / "thumbnails" / "default_thumb.jpg")
    vid_id = upload_youtube_headless(out_mp4, st_thumb, short_yt_payload)
    logger.info(f"✅ [GHA Local Engine] Short #{short_index} rendered & uploaded to YouTube! ID: {vid_id}")
    return vid_id
