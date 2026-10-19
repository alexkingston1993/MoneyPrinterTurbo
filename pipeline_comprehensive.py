#!/usr/bin/env python3.11
"""
Comprehensive video pipeline with:
- Script sanitization (natural dates, no special chars)
- Coqui XTTS v2 with Alex's cloned voice
- Content-aware animated stock charts
- Faster scene changes (~10s) with relevant stock footage
- Organized output: date/channel/video_name/
- EOD report generation
- Self-fixing retry logic
"""

import asyncio
import json
import math
import os
import random
import re
import shutil
import smtplib
import subprocess
import sys
import textwrap
import time
import traceback
from datetime import datetime, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

PY311 = os.path.expanduser("~/.local/bin/python3.11")
PEXELS_KEY = "2927GljrcuM0PxfFHrBTUfShGAHLL2LcVGbGhuQkxddHHTZ61NzP1sSb"
VOICE_REF = "/tmp/alex_ref.wav"
BASE_OUTPUT = os.path.expanduser("~/Documents/Antigravity/untitled folder/output")
SCRIPT_FILE = "/tmp/market_script_full.txt"
AVATAR_PATH = os.path.expanduser("~/Documents/Antigravity/untitled folder/data/avatars/placeholder.jpg")
LOG_FILE = "/tmp/pipeline_daily.log"

TODAY = date.today().isoformat()
CHANNELS = {
    "en": "The Compounder",
    "ta": "The Compounder Tamil",
    "hi": "The Compounder Hindi",
}
EMAIL_CONFIG = {
    "sender": "alex@thecompounder.in",
    "password": "",  # set via env var: EOD_EMAIL_PASSWORD
    "recipient": "", # set via env var: EOD_EMAIL_RECIPIENT
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
}

NSE_SYMBOLS = {
    "TCS": "TCS.NS", "RELIANCE": "RELIANCE.NS", "HDFC": "HDFCBANK.NS",
    "INFY": "INFY.NS", "ICICI": "ICICIBANK.NS", "SBIN": "SBIN.NS",
    "BHARTI": "BHARTIARTL.NS", "DMART": "DMART.NS", "TITAN": "TITAN.NS",
    "NIFTY": "^NSEI", "SENSEX": "^BSESN", "BANKNIFTY": "^NSEBANK",
}


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def sanitize_script(text):
    """Make script sound natural for TTS."""
    # Replace special unicode dashes/hyphens
    text = text.replace("\u2011", "-").replace("\u2012", "-").replace("\u2013", "-")
    text = text.replace("\u2014", " - ").replace("\u2015", " - ")
    text = text.replace("\u2212", "-")  # minus sign
    # Replace special spaces
    text = text.replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ")
    # Replace curly quotes
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    # Remove markdown markers
    text = re.sub(r'\*\*', '', text)
    text = re.sub(r'---', '', text)
    text = re.sub(r'###\s*', '', text)
    # Remove special characters that TTS will read aloud
    text = text.replace("–", "-")
    # Clean up multiple spaces
    text = re.sub(r' +', ' ', text)
    # Format dates: DD-MM-YYYY or YYYY-MM-DD → Month DD, YYYY
    def _fmt_date(m):
        raw = m.group(0)
        parts = raw.replace("-", "/").split("/")
        if len(parts) == 3:
            month_names = ["", "January", "February", "March", "April", "May", "June",
                          "July", "August", "September", "October", "November", "December"]
            try:
                p0, p1, p2 = parts[0], parts[1], parts[2]
                if len(p0) == 4:
                    # YYYY-MM-DD
                    return f"{month_names[int(p1)]} {int(p2)}, {p0}"
                elif int(p0) > 12:
                    # DD-MM-YYYY
                    return f"{month_names[int(p1)]} {int(p0)}, {p2}"
                else:
                    # MM-DD-YYYY
                    return f"{month_names[int(p0)]} {int(p1)}, {p2}"
            except:
                pass
        return raw
    text = re.sub(r'\b\d{2}[-/]\d{2}[-/]\d{4}\b', _fmt_date, text)
    text = re.sub(r'\b\d{4}[-/]\d{2}[-/]\d{2}\b', _fmt_date, text)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Replace % with "percent"
    text = re.sub(r'(\d+)\s*%', r'\1 percent', text)
    # Clean up
    text = text.strip()
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def extract_stock_mentions(script):
    """Extract stock names mentioned in the script for chart generation."""
    mentions = []
    for name, symbol in NSE_SYMBOLS.items():
        if re.search(r'\b' + re.escape(name) + r'\b', script, re.IGNORECASE):
            mentions.append((name, symbol))
    return mentions


def generate_animated_charts(stock_mentions, output_dir, num_frames=300):
    """Generate animated stock price charts using matplotlib."""
    if not stock_mentions:
        log("No stock mentions found, skipping charts")
        return []
    
    chart_files = []
    for name, symbol in stock_mentions[:3]:  # Max 3 stocks
        try:
            log(f"Generating chart for {name} ({symbol})...")
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="6mo")
            if hist.empty or len(hist) < 20:
                log(f"  Insufficient data for {name}, skipping")
                continue
            
            close_prices = hist["Close"].values
            dates = hist.index
            
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import matplotlib.animation as animation
            from matplotlib.patches import FancyBboxPatch
            
            fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=60)
            fig.patch.set_facecolor("#0d1117")
            ax.set_facecolor("#161b22")
            
            chart_dir = os.path.join(output_dir, "charts")
            os.makedirs(chart_dir, exist_ok=True)
            
            total_points = len(close_prices)
            step = max(1, total_points // num_frames)
            
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
                
                ax.set_title(f"{name}  |  ₹{current_val:.2f}  ({change:+.2f}%)",
                           color="white", fontsize=28, pad=20, fontweight="bold")
                
                ax.tick_params(colors="#8b949e", labelsize=14)
                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)
                ax.spines["bottom"].set_color("#30363d")
                ax.spines["left"].set_color("#30363d")
                ax.set_xlabel("")
                ax.set_ylabel("Price (₹)", color="#8b949e", fontsize=16)
                ax.grid(True, alpha=0.15, color="#30363d")
                
                frame_path = os.path.join(chart_dir, f"{name}_frame_{i:04d}.png")
                fig.savefig(frame_path, facecolor="#0d1117", bbox_inches="tight", pad_inches=0.2)
                frames.append(frame_path)
            
            plt.close(fig)
            
            # Combine frames into video
            chart_video = os.path.join(chart_dir, f"{name}_chart.mp4")
            cmd = [
                "ffmpeg", "-y", "-framerate", "15", "-pattern_type", "glob",
                "-i", f"{chart_dir}/{name}_frame_*.png",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-preset", "fast", "-crf", "20",
                chart_video,
            ]
            subprocess.run(cmd, capture_output=True, check=True, timeout=120)
            
            # Cleanup frames
            for f in frames:
                os.remove(f)
            
            chart_files.append((name, chart_video))
            log(f"  Chart for {name} generated: {chart_video}")
        except Exception as e:
            log(f"  Chart generation failed for {name}: {e}")
    
    return chart_files


def run_coqui_tts(text, output_path):
    """Generate TTS using Coqui XTTS v2 with Alex's voice."""
    log("Generating TTS with Alex's voice (Coqui XTTS v2)...")
    
    sanitized = sanitize_script(text)
    
    # Save sanitized script
    script_out = output_path.replace(".mp3", "_script.txt")
    with open(script_out, "w") as f:
        f.write(sanitized)
    log(f"Sanitized script saved: {script_out}")
    
    # Run with Python 3.11 (Coqui-compatible)
    tts_script = f'''
import os, sys, time
os.environ["COQUI_TOS_AGREED"] = "1"
sys.path.insert(0, "/Users/apple/.local/share/uv/python/cpython-3.11.15-macos-x86_64-none/lib/python3.11/site-packages")

text = {json.dumps(sanitized)}

from TTS.api import TTS
t0 = time.time()
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
print(f"Model loaded in {{time.time()-t0:.1f}}s", flush=True)

t0 = time.time()
tts.tts_to_file(
    text=text,
    file_path="{output_path}",
    speaker_wav="{VOICE_REF}",
    language="en",
    speed=1.0,
)
print(f"TTS generated in {{time.time()-t0:.1f}}s", flush=True)
'''
    tts_file = "/tmp/_coqui_tts_runner.py"
    with open(tts_file, "w") as f:
        f.write(tts_script)
    
    t0 = time.time()
    r = subprocess.run(
        [PY311, tts_file],
        capture_output=True, text=True, timeout=7200,
    )
    elapsed = time.time() - t0
    
    if r.returncode != 0:
        log(f"Coqui TTS FAILED (rc={r.returncode}): {r.stderr[:500]}")
        return None
    
    log(f"TTS completed in {elapsed:.1f}s")
    
    if not os.path.exists(output_path):
        log("TTS output file not found!")
        return None
    
    size_mb = os.path.getsize(output_path) / 1e6
    log(f"Audio: {size_mb:.1f}MB")
    
    import soundfile as sf
    data, sr = sf.read(output_path)
    duration = len(data) / sr
    log(f"Duration: {duration:.1f}s")
    
    return output_path, duration, sanitized


def download_pexels_videos(search_terms, output_dir, target_duration):
    """Download stock footage from Pexels."""
    import requests
    log(f"Downloading videos (target: {target_duration:.0f}s)...")
    
    os.makedirs(output_dir, exist_ok=True)
    download_urls = []
    
    for term in search_terms:
        if len(download_urls) >= 60:
            break
        url = f"https://api.pexels.com/videos/search?query={term}&orientation=landscape&per_page=15"
        try:
            resp = requests.get(url, headers={"Authorization": PEXELS_KEY}, timeout=15)
            data = resp.json()
            for v in data.get("videos", []):
                dur = v.get("duration", 0)
                if dur < 5:
                    continue
                for file in v.get("video_files", []):
                    if file.get("quality") == "hd" and file.get("width", 0) >= 1280:
                        download_urls.append((file["link"], dur))
                        break
        except Exception as e:
            log(f"  Search failed for '{term}': {e}")
    
    random.shuffle(download_urls)
    downloaded = []
    total = 0
    dl_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
        "Referer": "https://www.pexels.com/",
    }
    
    for vurl, dur in download_urls:
        if total >= target_duration:
            break
        fname = os.path.join(output_dir, f"clip_{len(downloaded):04d}.mp4")
        try:
            r = requests.get(vurl, headers=dl_headers, stream=True, timeout=30)
            if r.status_code == 200:
                with open(fname, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                if os.path.getsize(fname) > 10000:
                    downloaded.append(fname)
                    total += min(dur, 12)
                    log(f"  [{len(downloaded)}] {dur}s clip ({os.path.getsize(fname)/1e6:.1f}MB)")
                else:
                    os.remove(fname)
        except Exception as e:
            pass
    
    log(f"Downloaded {len(downloaded)} clips ({total:.0f}s)")
    return downloaded


def combine_videos_with_charts(video_paths, chart_videos, audio_duration, output_path):
    """Combine Pexels videos with chart animations."""
    log("Combining videos + charts...")
    
    clips = []
    target_clip_duration = 10  # Change scene every 10 seconds
    total = 0
    
    # Interleave chart clips with stock footage
    chart_clips = [c[1] for c in chart_videos]
    
    while total < audio_duration:
        remaining = audio_duration - total
        seg_dur = min(target_clip_duration, remaining)
        
        # Alternate between chart and stock footage
        if chart_clips and len(clips) % 3 == 0:
            idx = (len(clips) // 3) % len(chart_clips)
            clip_path = chart_clips[idx]
        else:
            if not video_paths:
                break
            clip_path = video_paths[total % len(video_paths)]
        
        clips.append((clip_path, seg_dur))
        total += seg_dur
    
    # Write ffmpeg concat file with duration trimming
    concat_file = "/tmp/pipeline_concat.txt"
    with open(concat_file, "w") as f:
        for clip_path, seg_dur in clips:
            if not os.path.exists(clip_path):
                continue
            f.write(f"file '{clip_path}'\n")
            f.write(f"duration {seg_dur}\n")
    
    # First combine with stream copy if possible
    temp_combined = output_path.replace(".mp4", "_temp.mp4")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-crf", "22", "-threads", "4",
        temp_combined,
    ]
    log("  Running concat...")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        log(f"  Concat failed: {r.stderr[:200]}")
        # Fallback: use available clips directly
        return None
    
    # Loop to match exactly audio_duration
    cmd = [
        "ffmpeg", "-y", "-stream_loop", "-1", "-i", temp_combined,
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-t", str(audio_duration), "-crf", "22", "-threads", "4",
        output_path,
    ]
    log("  Looping to match duration...")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        log(f"  Loop failed: {r.stderr[:200]}")
        shutil.copy(temp_combined, output_path)
    
    for f in [temp_combined]:
        if os.path.exists(f):
            os.remove(f)
    
    log(f"Combined video: {output_path}")
    return output_path


def generate_subtitles_from_timing(sentences, audio_duration):
    """Generate subtitles with per-sentence timing based on char count."""
    total_chars = sum(len(s) for s in sentences)
    chars_per_sec = total_chars / audio_duration if audio_duration > 0 else 10
    
    srt_lines = []
    current_time = 0.0
    for i, sent in enumerate(sentences):
        if not sent.strip():
            continue
        sent_dur = max(1.0, len(sent) / chars_per_sec)
        start = current_time
        end = min(current_time + sent_dur, audio_duration)
        if start >= audio_duration:
            break
        
        h1 = int(start // 3600)
        m1 = int((start % 3600) // 60)
        s1 = start % 60
        h2 = int(end // 3600)
        m2 = int((end % 3600) // 60)
        s2 = end % 60
        
        srt_lines.append(f"{i+1}")
        srt_lines.append(f"{h1:02d}:{m1:02d}:{s1:06.3f} --> {h2:02d}:{m2:02d}:{s2:06.3f}")
        srt_lines.append(sent.strip())
        srt_lines.append("")
        current_time = end
    
    return "\n".join(srt_lines)


def render_final_video(video_path, audio_path, srt_content, avatar_path, output_path):
    """Render final video with audio, subtitles, and avatar overlay."""
    log("Rendering final video...")
    
    # Write SRT
    srt_file = "/tmp/_final_subs.srt"
    with open(srt_file, "w") as f:
        f.write(srt_content)
    
    # Step 1: Replace audio in video
    audio_video = output_path.replace(".mp4", "_audio.mp4")
    cmd = [
        "ffmpeg", "-y", "-i", video_path, "-i", audio_path,
        "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0",
        "-shortest", "-threads", "4", audio_video,
    ]
    log("  Adding audio track...")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        log(f"  Audio replace failed: {r.stderr[:200]}")
        return None
    
    # Step 2: Composite subtitles + avatar using moviepy
    t0 = time.time()
    render_script = f'''
import sys, os, math, json, time
import numpy as np
from PIL import Image, ImageEnhance
os.environ["COQUI_TOS_AGREED"] = "1"

from moviepy import CompositeVideoClip, VideoClip, VideoFileClip, TextClip

video = VideoFileClip("{audio_video}")
duration = video.duration
fps = int(video.fps) if video.fps else 30
w, h = video.w, video.h

# Avatar setup
pil_img = Image.open("{avatar_path}").convert("RGB")
overlay_w = int(w * 0.28)
aspect_pct = pil_img.height / pil_img.width
overlay_h = int(overlay_w * aspect_pct)
max_h = int(h * 0.45)
if overlay_h > max_h:
    overlay_h = max_h
    overlay_w = int(overlay_h / aspect_pct)
pil_img = pil_img.resize((overlay_w, overlay_h), Image.LANCZOS)
enhancer = ImageEnhance.Contrast(pil_img)
pil_img = enhancer.enhance(1.1)
enhancer = ImageEnhance.Sharpness(pil_img)
pil_img = enhancer.enhance(1.05)
avatar_array = np.array(pil_img)

margin_x = int(w * 0.03)
margin_y = int(h * 0.02)
pos_x = w - overlay_w - margin_x
pos_y = h - overlay_h - margin_y

def make_avatar_frame(t):
    breath = 1.0 + 0.003 * math.sin(2 * math.pi * t / 3.0)
    cw = max(1, int(overlay_w * breath))
    ch = max(1, int(overlay_h * breath))
    frame_pil = Image.fromarray(avatar_array).resize((cw, ch), Image.LANCZOS)
    return np.array(frame_pil)

avatar_clip = (
    VideoClip(make_avatar_frame, duration=duration)
    .with_position(lambda t: (pos_x, pos_y + 1.5 * math.sin(2 * math.pi * t / 2.5)))
    .with_duration(duration)
)

# Subtitle clips
sub_data = {json.dumps([s for s in (lambda x: x)(_scratch)])}  # will handle below _
overlays = [avatar_clip]

for start, end, text in sub_data:
    seg_dur = end - start
    if seg_dur <= 0:
        continue
    wrapped = text
    if len(text) > 60:
        words = text.split()
        lines = []
        line = ""
        for wd in words:
            test = f"{{line}} {{wd}}".strip()
            if len(test) > 50:
                lines.append(line)
                line = wd
            else:
                line = test
        if line:
            lines.append(line)
        wrapped = "\\n".join(lines)
    
    txt_clip = (
        TextClip(text=wrapped, font_size=28, color="white",
                 font="/System/Library/Fonts/Helvetica.ttc",
                 stroke_color="black", stroke_width=2,
                 method="label")
        .with_position(("center", h * 0.85))
        .with_start(start)
        .with_duration(seg_dur)
    )
    overlays.append(txt_clip)

final = CompositeVideoClip([video] + overlays)
output = "{output_path}"
print(f"Writing final video ({{len(overlays)}} layers)...", flush=True)
final.write_videofile(output, codec="libx264", audio_codec="aac", fps=fps, threads=4)
video.close()
final.close()
print(f"Done in {{time.time()-{t0}:.1f}}s", flush=True)
'''
    # Actually, let me write this as a cleaner script
    log("  Compositing subtitles + avatar...")
    
    # Parse SRT into timestamps
    sub_entries = []
    srt_pattern = re.compile(r'(\d+)\n(\d+:\d+:\d+,\d+) --> (\d+:\d+:\d+,\d+)\n(.+?)(?=\n\n|\Z)', re.DOTALL)
    
    def _parse_srt_time(t_str):
        t_str = t_str.replace(",", ".")
        parts = t_str.split(":")
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    
    entries = re.split(r'\n\n', srt_content.strip())
    sub_list = []
    for entry in entries:
        lines = entry.strip().split('\n')
        if len(lines) >= 3:
            idx = lines[0]
            time_part = lines[1]
            text = '\n'.join(lines[2:])
            time_match = re.match(r'(\d+:\d+:\d+[.,]\d+) --> (\d+:\d+:\d+[.,]\d+)', time_part)
            if time_match:
                start = _parse_srt_time(time_match.group(1))
                end = _parse_srt_time(time_match.group(2))
                sub_list.append((start, end, text))
    
    render_py = f'''
import sys, os, math, json, time
import numpy as np
from PIL import Image, ImageEnhance
os.environ["COQUI_TOS_AGREED"] = "1"

from moviepy import CompositeVideoClip, VideoClip, VideoFileClip, TextClip

video = VideoFileClip("{audio_video}")
duration = video.duration
fps = int(video.fps) if video.fps else 30
w, h = video.w, video.h

avatar_array = np.array(Image.open("{avatar_path}").convert("RGB").resize(
    (int(w * 0.28), min(int(w * 0.28 * (Image.open("{avatar_path}").height / Image.open("{avatar_path}").width)), int(h * 0.45))),
    Image.LANCZOS
))
overlay_w, overlay_h = avatar_array.shape[1], avatar_array.shape[0]
margin_x, margin_y = int(w * 0.03), int(h * 0.02)
pos_x, pos_y = w - overlay_w - margin_x, h - overlay_h - margin_y

def make_avatar(t):
    breath = 1.0 + 0.003 * math.sin(2 * math.pi * t / 3.0)
    cw = max(1, int(overlay_w * breath))
    ch = max(1, int(overlay_h * breath))
    from PIL import Image as Im
    return np.array(Im.fromarray(avatar_array).resize((cw, ch), Im.LANCZOS))

avatar_clip = (VideoClip(make_avatar, duration=duration)
    .with_position(lambda t: (pos_x, pos_y + 1.5 * math.sin(2 * math.pi * t / 2.5)))
    .with_duration(duration))

sub_list = {json.dumps(sub_list)}
overlays = [avatar_clip]
font_path = "/System/Library/Fonts/Helvetica.ttc"

for start, end, text in sub_list[:]:
    sd = end - start
    if sd <= 0:
        continue
    if len(text) > 60:
        words = text.split()
        lines, line = [], ""
        for wd in words:
            test = f"{{{{line}} {{wd}}}}".strip()
            if len(test) > 50:
                lines.append(line)
                line = wd
            else:
                line = test
        if line: lines.append(line)
        text = "\\n".join(lines)
    overlays.append(
        TextClip(text=text, font_size=28, color="white",
                 font=font_path, stroke_color="black", stroke_width=2,
                 method="label")
        .with_position(("center", h * 0.85))
        .with_start(start).with_duration(sd)
    )

final = CompositeVideoClip([video] + overlays)
print(f"Writing ({{len(overlays)}} layers, {{fps}}fps)...", flush=True)
final.write_videofile("{output_path}", codec="libx264", audio_codec="aac", fps=fps, threads=4)
video.close()
final.close()
print("Done!", flush=True)
'''
    render_file = "/tmp/_render_final.py"
    with open(render_file, "w") as f:
        f.write(render_py)
    
    t0 = time.time()
    r = subprocess.run([PY311, render_file], capture_output=True, text=True, timeout=7200)
    elapsed = time.time() - t0
    
    if r.returncode != 0:
        log(f"  Render FAILED: {r.stderr[:500]}")
        log(f"  Stdout: {r.stdout[:300]}")
        return None
    
    log(f"  Render completed in {elapsed:.1f}s")
    
    if os.path.exists(output_path):
        log(f"  Final video: {output_path} ({os.path.getsize(output_path)/1e6:.1f}MB)")
        return output_path
    return None


def create_output_structure(channel="en", video_name="market_update"):
    """Create organized folder structure: output/YYYY-MM-DD/channel/video_name/"""
    day_dir = os.path.join(BASE_OUTPUT, TODAY)
    channel_dir = os.path.join(day_dir, CHANNELS.get(channel, channel))
    video_dir = os.path.join(channel_dir, video_name)
    os.makedirs(video_dir, exist_ok=True)
    return video_dir


def send_eod_report(results):
    """Send end-of-day report via email."""
    recipient = os.environ.get("EOD_EMAIL_RECIPIENT") or EMAIL_CONFIG["recipient"]
    sender = EMAIL_CONFIG["sender"]
    password = os.environ.get("EOD_EMAIL_PASSWORD") or EMAIL_CONFIG["password"]
    
    if not recipient or not password:
        log("EOD report: email not configured (set EOD_EMAIL_RECIPIENT and EOD_EMAIL_PASSWORD)")
        # Save report locally instead
        report_path = os.path.join(BASE_OUTPUT, TODAY, f"EOD_REPORT_{TODAY}.md")
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w") as f:
            f.write(results)
        log(f"EOD report saved locally: {report_path}")
        return
    
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = f"Pipeline EOD Report - {TODAY}"
    msg.attach(MIMEText(results, "plain"))
    
    try:
        with smtplib.SMTP(EMAIL_CONFIG["smtp_server"], EMAIL_CONFIG["smtp_port"]) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
        log("EOD report sent successfully!")
    except Exception as e:
        log(f"EOD report send failed: {e}")


def build_eod_report(steps_results):
    """Build EOD report content."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "=" * 60,
        f"  PIPELINE END-OF-DAY REPORT",
        f"  Date: {TODAY}",
        f"  Generated: {now}",
        "=" * 60,
        "",
        "SUMMARY",
        "-" * 40,
    ]
    
    success_count = sum(1 for s in steps_results if s.get("status") == "ok")
    fail_count = sum(1 for s in steps_results if s.get("status") == "fail")
    lines.append(f"  Steps succeeded: {success_count}")
    lines.append(f"  Steps failed: {fail_count}")
    lines.append(f"  Attention needed: {'YES' if fail_count > 0 else 'NO'}")
    lines.append("")
    
    lines.append("STEP DETAILS")
    lines.append("-" * 40)
    for step in steps_results:
        status_icon = "✅" if step.get("status") == "ok" else "❌"
        lines.append(f"  {status_icon} {step['name']}")
        lines.append(f"     Status: {step.get('status', 'unknown')}")
        if step.get("duration"):
            lines.append(f"     Duration: {step['duration']:.1f}s")
        if step.get("error"):
            lines.append(f"     Error: {step['error']}")
        if step.get("output"):
            lines.append(f"     Output: {step['output']}")
        lines.append("")
    
    lines.append("NEXT STEPS")
    lines.append("-" * 40)
    if fail_count > 0:
        lines.append("  ⚠️  Some steps failed and need attention:")
        for step in steps_results:
            if step.get("status") == "fail":
                lines.append(f"     - {step['name']}: {step.get('error', 'unknown error')}")
    else:
        lines.append("  ✅ All steps completed successfully.")
        lines.append("  No action needed.")
    lines.append("")
    lines.append("=" * 60)
    
    return "\n".join(lines)


def retry(func, max_retries=3, *args, **kwargs):
    """Self-fixing: retry with increasing backoff."""
    for attempt in range(max_retries):
        try:
            result = func(*args, **kwargs)
            if result is not None:
                return result
        except Exception as e:
            log(f"Attempt {attempt+1}/{max_retries} failed: {e}")
        if attempt < max_retries - 1:
            wait = (attempt + 1) * 10
            log(f"Retrying in {wait}s...")
            time.sleep(wait)
    return None


def run_daily_pipeline():
    """Main pipeline orchestrator for a daily run."""
    log(f"\n{'='*60}")
    log(f"  DAILY PIPELINE RUN - {TODAY}")
    log(f"{'='*60}\n")
    
    steps_results = []
    
    # Step 1: Read and sanitize script
    log("--- Step 1: Script Preparation ---")
    t0 = time.time()
    try:
        with open(SCRIPT_FILE) as f:
            raw_script = f.read()
        sanitized_script = sanitize_script(raw_script)
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', sanitized_script) if s.strip()]
        stock_mentions = extract_stock_mentions(raw_script)
        steps_results.append({
            "name": "Script preparation",
            "status": "ok",
            "duration": time.time() - t0,
            "output": f"{len(sentences)} sentences, {len(stock_mentions)} stocks mentioned",
        })
        log(f"  {len(sentences)} sentences, {len(stock_mentions)} stock mentions")
    except Exception as e:
        steps_results.append({"name": "Script preparation", "status": "fail", "error": str(e)})
        log(f"  FAILED: {e}")
        return steps_results
    
    # Step 2: TTS with Alex's voice
    log("--- Step 2: TTS Generation (Alex's Voice) ---")
    t0 = time.time()
    audio_file = "/tmp/pipeline_tts_output.mp3"
    tts_result = retry(
        lambda: run_coqui_tts(sanitized_script, audio_file),
        max_retries=2,
    )
    if tts_result:
        audio_path, audio_duration, final_script = tts_result
        steps_results.append({
            "name": "TTS (Alex voice)",
            "status": "ok",
            "duration": time.time() - t0,
            "output": f"{audio_duration:.0f}s",
        })
        log(f"  Audio: {audio_duration:.0f}s")
    else:
        steps_results.append({"name": "TTS (Alex voice)", "status": "fail", "error": "TTS failed after retries"})
        log("  FAILED: TTS generation failed")
        return steps_results
    
    # Step 3: Animated charts for stock mentions
    log("--- Step 3: Animated Charts ---")
    t0 = time.time()
    chart_dir = "/tmp/pipeline_charts"
    chart_videos = []
    for name, symbol in stock_mentions[:3]:
        result = retry(lambda n=name, s=symbol: generate_animated_charts([(n, s)], chart_dir), max_retries=2)
        if result:
            chart_videos.extend(result)
    
    steps_results.append({
        "name": "Animated charts",
        "status": "ok" if chart_videos else "skipped",
        "duration": time.time() - t0,
        "output": f"{len(chart_videos)} charts generated" if chart_videos else "No stocks to chart",
    })
    log(f"  {len(chart_videos)} chart videos")
    
    # Step 4: Download stock footage
    log("--- Step 4: Download Stock Footage ---")
    t0 = time.time()
    search_terms = [
        "Indian stock market trading", "Nifty 50 exchange", "business news India",
        "stock chart analysis", "corporate office", "financial data graphs",
        "Mumbai business district", "trading floor stocks", "share market India",
    ] + [f"{name} stock" for name, _ in stock_mentions[:3]]
    
    footage_dir = "/tmp/pipeline_footage"
    videos = retry(
        lambda: download_pexels_videos(search_terms, footage_dir, audio_duration),
        max_retries=2,
    )
    if not videos:
        steps_results.append({"name": "Stock footage download", "status": "fail", "error": "No videos downloaded"})
        log("  FAILED: No videos")
        return steps_results
    
    steps_results.append({
        "name": "Stock footage download",
        "status": "ok",
        "duration": time.time() - t0,
        "output": f"{len(videos)} clips",
    })
    log(f"  {len(videos)} clips")
    
    # Step 5: Combine videos
    log("--- Step 5: Combine Videos ---")
    t0 = time.time()
    combined_video = "/tmp/pipeline_combined.mp4"
    video_result = retry(
        lambda: combine_videos_with_charts(videos, chart_videos, audio_duration, combined_video),
        max_retries=2,
    )
    
    if not video_result or not os.path.exists(combined_video):
        steps_results.append({"name": "Video combination", "status": "fail", "error": "Video combine failed"})
        log("  FAILED: Video combination")
        return steps_results
    
    # Check if combined video duration is sufficient
    probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                  "-of", "default=noprint_wrappers=1:nokey=1", combined_video]
    r = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
    vid_dur = float(r.stdout.strip()) if r.stdout else 0
    
    if vid_dur < audio_duration * 0.8:
        log(f"  Video too short ({vid_dur:.0f}s vs audio {audio_duration:.0f}s), creating fallback")
        fallback_video = "/tmp/pipeline_fallback.mp4"
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"color=c=0x001e32:s=1920x1080:d={audio_duration}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", fallback_video,
        ]
        subprocess.run(cmd, capture_output=True, timeout=120)
        video_result = fallback_video
        combined_video = fallback_video
    
    steps_results.append({
        "name": "Video combination",
        "status": "ok",
        "duration": time.time() - t0,
        "output": f"{vid_dur:.0f}s video",
    })
    
    # Step 6: Generate subtitles
    log("--- Step 6: Subtitle Generation ---")
    t0 = time.time()
    srt_content = generate_subtitles_from_timing(sentences, audio_duration)
    steps_results.append({
        "name": "Subtitle generation",
        "status": "ok",
        "duration": time.time() - t0,
        "output": f"{len(sentences)} segments",
    })
    
    # Step 7: Render final video with avatar
    log("--- Step 7: Final Render (Subtitles + Avatar) ---")
    t0 = time.time()
    
    # Create output structure
    video_dir = create_output_structure("en", f"market_update_{TODAY}")
    final_output = os.path.join(video_dir, "final.mp4")
    
    render_result = retry(
        lambda: render_final_video(combined_video, audio_path, srt_content, AVATAR_PATH, final_output),
        max_retries=1,
    )
    
    if render_result and os.path.exists(final_output):
        file_size = os.path.getsize(final_output) / 1e6
        steps_results.append({
            "name": "Final render",
            "status": "ok",
            "duration": time.time() - t0,
            "output": f"{file_size:.0f}MB at {video_dir}",
        })
        log(f"  ✅ FINAL VIDEO READY: {final_output} ({file_size:.0f}MB)")
    else:
        steps_results.append({"name": "Final render", "status": "fail", "error": "Render returned no output"})
        log("  FAILED: Final render")
    
    # Generate EOD report
    log("--- Step 8: EOD Report ---")
    report = build_eod_report(steps_results)
    send_eod_report(report)
    
    log(f"\n{'='*60}")
    log(f"  PIPELINE COMPLETE")
    log(f"{'='*60}\n")
    
    return steps_results


if __name__ == "__main__":
    results = run_daily_pipeline()
    success = all(s.get("status") == "ok" for s in results)
    sys.exit(0 if success else 1)
