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


def generate_high_ctr_short_cover(headline: str, vertical: str, output_path: str) -> str:
    """Generates high-contrast 9:16 vertical cover for YouTube Shorts with massive readable typography,
    technical order flow grid lines, and glowing focal box."""
    from PIL import Image, ImageDraw, ImageFont

    width, height = 1080, 1920
    img = Image.new("RGB", (width, height), color="#090d16")
    draw = ImageDraw.Draw(img)

    vert = (vertical or "").lower()
    accent_color = "#10b981" if "stock" in vert else ("#06b6d4" if "crypto" in vert else "#f59e0b")
    glow_color = (16, 185, 129) if "stock" in vert else ((6, 182, 212) if "crypto" in vert else (245, 158, 11))

    # Radial gradient background
    center_y = 650
    for r in range(500, 0, -20):
        glow_box = [width // 2 - r, center_y - r, width // 2 + r, center_y + r]
        draw.ellipse(glow_box, fill=(glow_color[0] // 6, glow_color[1] // 6, glow_color[2] // 6))

    # Abstract order flow grid lines for technical depth
    for x in range(0, width, 120):
        draw.line([(x, 0), (x, height)], fill="#161f30", width=1)
    for y in range(0, height, 120):
        draw.line([(0, y), (width, y)], fill="#161f30", width=1)

    # Glowing focal box in upper-middle (safe from YouTube bottom overlay)
    box_rect = [70, 380, width - 70, 960]
    draw.rectangle(box_rect, fill="#0f172a", outline=accent_color, width=5)

    # Top indicator pill
    pill_label = "INSTITUTIONAL ALERT" if "stock" in vert else ("ON-CHAIN ALPHA" if "crypto" in vert else "POLICY AUDIT")
    fontfile = _find_fontfile()
    try:
        font_pill = ImageFont.truetype(fontfile, 34) if fontfile else ImageFont.load_default()
    except Exception:
        font_pill = ImageFont.load_default()
    draw.rectangle([100, 345, 460, 400], fill=accent_color)
    draw.text((115, 355), pill_label, fill="#000000", font=font_pill)

    # Render bold uppercase text (headline split into 3-4 words per line)
    try:
        font = ImageFont.truetype(fontfile, 82) if fontfile else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    clean_headline = re.sub(r"#\S+", "", headline or "").strip().upper()
    clean_headline = re.sub(r"[^\w\s\$\₹\%\-\:\?]", "", clean_headline).strip()
    words = clean_headline.split()[:8] or ["THE", "BULL", "PRINT"]

    lines = []
    current_line = ""
    for w in words:
        if len(current_line + " " + w) < 16:
            current_line += (" " + w) if current_line else w
        else:
            lines.append(current_line)
            current_line = w
    if current_line:
        lines.append(current_line)

    lines = lines[:3]  # Max 3 massive lines
    line_h = 105
    total_text_h = len(lines) * line_h
    y_text = 430 + (500 - total_text_h) // 2

    for idx, line in enumerate(lines):
        # Drop shadow for max readability
        draw.text((120 + 4, y_text + 4), line, fill="#000000", font=font)
        # Highlight last line with accent/yellow
        text_fill = "#facc15" if idx == len(lines) - 1 else "#ffffff"
        draw.text((120, y_text), line, fill=text_fill, font=font)
        y_text += line_h

    # Add bottom brand badge
    try:
        font_brand = ImageFont.truetype(fontfile, 36) if fontfile else ImageFont.load_default()
    except Exception:
        font_brand = ImageFont.load_default()
    draw.text((120, 1750), "THE BULL PRINT • INSTITUTIONAL ALPHA", fill=accent_color, font=font_brand)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, quality=95)
    logger.info(f"🎨 [High-CTR Shorts Cover] generated at {output_path}")
    return output_path


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
    candidate_voices = [
        persona.get("voice", "en-US-AndrewNeural"),
        "en-US-AndrewNeural",
        "en-US-ChristopherNeural",
        "en-US-GuyNeural",
        "en-US-BrianMultilingualNeural",
    ]
    seen = set()
    candidate_voices = [v for v in candidate_voices if not (v in seen or seen.add(v))]

    last_exc = None
    for voice in candidate_voices:
        try:
            comm = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=persona.get("rate", "+3%"),
                pitch=persona.get("pitch", "+0Hz")
            )
            await comm.save(str(mp3_path))
            if mp3_path.exists() and mp3_path.stat().st_size > 1024:
                break
        except Exception as e:
            last_exc = e
            continue
    else:
        if last_exc:
            raise last_exc

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
    cover_jpg = WORK_DIR / f"cover_{tag}.jpg"

    meta = yt.get("metadata", {})
    short_title = str(short_data.get("short_title", "") or meta.get("title", "The Bull Print Daily Brief"))
    if not short_title.endswith("#Shorts"):
        short_title = f"{short_title} #Shorts"

    # 🎨 Generate dynamic high-CTR 9:16 shelf cover
    raw_hook = (
        str(short_data.get("hook") or "")
        or str(short_data.get("short_title") or "")
        or str(short_data.get("spoken_hook_and_body", "")).split(".")[0]
        or short_title
    )
    generate_high_ctr_short_cover(raw_hook, vertical, str(cover_jpg))

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
    fontfile = _find_fontfile()
    hud_list = _hud_filters(min(dur, 58.5), vertical, fontfile, w=1080, h=1920)
    tail = list(hud_list)
    tail.append(f"subtitles='{ass.as_posix()}'")

    # 100% Fullscreen 9:16 Canvas with Ken Burns motion & subtle dark vignette (Zero bottom-half logo)
    filter_graph = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        "zoompan=z='min(zoom+0.0008,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:fps=30:s=1080x1920,"
        "drawbox=x=0:y=0:w=1080:h=1920:color=black@0.30:t=fill[bg];"
        "[1:v]scale=1080:1920[cover];"
        "[bg][cover]overlay=0:0:enable='between(t,0,0.75)'[vbase]"
    )
    if tail:
        filter_graph += ";" + "[vbase]" + ",".join(tail) + "[v]"
    else:
        filter_graph += ";[vbase]null[v]"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(chart_png or ASSETS_DIR / "charts" / "chart_1.png"),
        "-loop", "1", "-i", str(cover_jpg),
        "-i", str(mp3),
        "-filter_complex", filter_graph,
        "-map", "[v]", "-map", "2:a",
        "-af", "silenceremove=stop_periods=-1:stop_duration=0.35:stop_threshold=-42dB,loudnorm=I=-14:TP=-1.5:LRA=11",
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

    st_thumb = cover_jpg if cover_jpg.exists() else (thumb_path if (thumb_path and thumb_path.exists()) else (BASE_DIR / "assets" / "thumbnails" / "default_thumb.jpg"))
    vid_id = upload_youtube_headless(out_mp4, st_thumb, short_yt_payload)
    logger.info(f"✅ [GHA Local Engine] Short #{short_index} rendered & uploaded to YouTube! ID: {vid_id}")
    return vid_id
