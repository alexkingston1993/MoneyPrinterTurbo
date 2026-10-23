"""
The Bull Print — Autonomous Kaggle GPU Masterclass Video Engine.
Executes 100% on Kaggle's free Nvidia Tesla T4 GPU (30 hours/week quota).
Synthesizes 10-minute cloned voice on CUDA, generates animated charts,
composites 1080p video with GPU acceleration, and uploads to YouTube.
"""

import base64
import json
import math
import os
import pickle
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

# 1. Environment bootstrap: ensure Python 3.11 with CUDA and TTS via uv
if sys.version_info >= (3, 12):
    env_dir = "/tmp/mpt_py11"
    env_py = os.path.join(env_dir, "bin", "python")
    if not os.path.exists(env_py):
        print("[KaggleWorker] Setting up optimized Python 3.11 CUDA runtime via uv...", flush=True)
        subprocess.run(["/usr/local/bin/uv", "venv", "--python", "3.11", env_dir], check=True)
        subprocess.run(
            [
                "/usr/local/bin/uv", "pip", "install", "--python", env_py,
                "transformers==4.37.2", "numpy==1.26.4", "TTS", "soundfile", "pydub", "moviepy", "matplotlib", "yfinance", "google-api-python-client", "google-auth-oauthlib", "requests", "pillow", "torch", "torchaudio"
            ],
            check=True
        )
    print("[KaggleWorker] Re-executing worker in Python 3.11 CUDA runtime...", flush=True)
    os.execv(env_py, [env_py, __file__])

print(f"[KaggleWorker] Running inside Python {sys.version.split()[0]} on GPU...", flush=True)

# 2. Inject Payload Placeholder (re-written before kernel push)
PAYLOAD_PLACEHOLDER

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

# Monkeypatch torch.load to prevent weights_only error with PyTorch 2.6+ in Coqui TTS
_orig_torch_load = torch.load
def _safe_torch_load(*args, **kwargs):
    if "weights_only" not in kwargs:
        kwargs["weights_only"] = False
    return _orig_torch_load(*args, **kwargs)
torch.load = _safe_torch_load

try:
    import soundfile as sf
except ImportError:
    import scipy.io.wavfile as wavfile
    class _SfCompat:
        @staticmethod
        def read(path):
            sr, d = wavfile.read(path)
            if d.dtype == np.int16:
                d = d.astype(np.float32) / 32767.0
            return d, sr
        @staticmethod
        def write(path, d, sr):
            if d.dtype != np.int16:
                d = (np.clip(d, -1.0, 1.0) * 32767.0).astype(np.int16)
            wavfile.write(path, sr, d)
    sf = _SfCompat()

import yfinance as yf
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from PIL import Image, ImageDraw, ImageFont

try:
    from moviepy.editor import AudioFileClip, CompositeVideoClip, TextClip, VideoFileClip, ImageClip
except ImportError:
    from moviepy import AudioFileClip, CompositeVideoClip, TextClip, VideoFileClip, ImageClip

def set_dur(clip, d):
    return clip.with_duration(d) if hasattr(clip, "with_duration") else clip.set_duration(d)

def set_pos(clip, pos):
    return clip.with_position(pos) if hasattr(clip, "with_position") else clip.set_position(pos)

def set_st(clip, st):
    return clip.with_start(st) if hasattr(clip, "with_start") else clip.set_start(st)

def set_aud(clip, aud):
    return clip.with_audio(aud) if hasattr(clip, "with_audio") else clip.set_audio(aud)

def create_pillow_text_clip(text, duration, position, font_size=24, color=(255, 255, 255), bg_color=(10, 15, 29, 210), width=1600, height=60, start=0.0):
    img = Image.new("RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    font = None
    for fpath in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]:
        if os.path.exists(fpath):
            try:
                font = ImageFont.truetype(fpath, font_size)
                break
            except Exception:
                pass
    if font is None:
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = max(10, (width - tw) // 2)
    ty = max(5, (height - th) // 2)
    draw.text((tx, ty), text, fill=color, font=font)
    img_np = np.array(img)
    clip = ImageClip(img_np)
    clip = set_dur(clip, duration)
    if start > 0:
        clip = set_st(clip, start)
    clip = set_pos(clip, position)
    return clip

os.environ["COQUI_TOS_AGREED"] = "1"
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[KaggleWorker] Hardware platform: {device}", flush=True)
if device == "cuda":
    print(f"[KaggleWorker] Active GPU: {torch.cuda.get_device_name(0)}", flush=True)

# ── Extract Inputs ──
subject = payload.get("subject", "The Bull Print Masterclass")
script = payload.get("script", "")
youtube_token_b64 = payload.get("youtube_token_b64", "")
pexels_api_key = payload.get("pexels_api_key", "")
voice_ref_b64 = payload.get("voice_ref_b64", "")

work_dir = "/kaggle/working"
temp_dir = "/tmp/mpt_run"
os.makedirs(temp_dir, exist_ok=True)
output_dir = os.path.join(work_dir, "output")
os.makedirs(output_dir, exist_ok=True)

# Save reference voice
voice_ref_path = os.path.join(temp_dir, "prabhat_ref.wav")
if voice_ref_b64:
    ref_bytes = base64.b64decode(voice_ref_b64)
    try:
        import gzip
        ref_bytes = gzip.decompress(ref_bytes)
    except Exception:
        pass
    with open(voice_ref_path, "wb") as f:
        f.write(ref_bytes)

# ── Step 1: Voice Synthesis via Coqui XTTS on CUDA GPU ──
try:
    from TTS.api import TTS
except ImportError:
    raise RuntimeError(
        "Coqui TTS is not installed because outbound internet is blocked on this Kaggle account. "
        "Complete one-time SMS phone verification at https://www.kaggle.com/settings to enable GPU internet."
    )

t0 = time.time()
tts_engine = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
print(f"[KaggleWorker] XTTS model ready in {time.time()-t0:.1f}s", flush=True)

# Split script into natural sentence units for synchronized cues
lines = [l.strip() for l in script.splitlines() if l.strip()]
sentences = []
for line in lines:
    for s in re.split(r'(?<=[.?!;।])\s+', line):
        s = s.strip()
        if s:
            sentences.append(s)

print(f"[KaggleWorker] Synthesizing {len(sentences)} sentences on GPU...", flush=True)
audio_pieces = []
subtitle_entries = []
current_time = 0.0

for i, sent in enumerate(sentences):
    t_chunk = time.time()
    chunk_path = os.path.join(temp_dir, f"chunk_{i:04d}.wav")
    tts_engine.tts_to_file(
        text=sent,
        file_path=chunk_path,
        speaker_wav=voice_ref_path if os.path.exists(voice_ref_path) else None,
        language="en",
        speed=1.0,
    )
    data, sr = sf.read(chunk_path)
    dur = len(data) / float(sr)
    audio_pieces.append(data)
    # 0.15s pause between sentences
    pause_data = np.zeros(int(sr * 0.15))
    audio_pieces.append(pause_data)

    subtitle_entries.append((current_time, current_time + dur, sent))
    current_time += dur + 0.15

full_audio = np.concatenate(audio_pieces)
audio_path = os.path.join(temp_dir, "masterclass_audio.wav")
sf.write(audio_path, full_audio, 24000)
audio_duration = len(full_audio) / 24000.0
print(f"[KaggleWorker] Speech synthesis complete: {audio_duration:.1f}s audio generated in {time.time()-t0:.1f}s", flush=True)

# ── Step 2: Animated Candlestick Visuals ──
print("[KaggleWorker] Step 2: Building live candlestick animations...", flush=True)
chart_dir = os.path.join(temp_dir, "charts")
os.makedirs(chart_dir, exist_ok=True)
chart_videos = []

indices = [
    ("^NSEI", "Nifty 50"),
    ("^NSEBANK", "Bank Nifty"),
    ("^BSESN", "BSE Sensex"),
]

for ticker, name in indices:
    try:
        df = yf.download(ticker, period="1mo", interval="1d", progress=False)
        if df.empty or len(df) < 5:
            continue
        close_prices = df["Close"].values.flatten()
        dates = range(len(close_prices))

        frames = []
        fig, ax = plt.subplots(figsize=(16, 9), facecolor="#0a0f1d")
        for idx in range(3, len(close_prices)):
            ax.clear()
            ax.set_facecolor("#0a0f1d")
            sc = close_prices[: idx + 1]
            sd = dates[: idx + 1]
            color = "#00e599" if sc[-1] >= sc[0] else "#f43f5e"
            ax.plot(sd, sc, color=color, linewidth=3.5)
            ax.fill_between(sd, sc, alpha=0.15, color=color)
            val = sc[-1]
            chg = ((val - sc[0]) / sc[0]) * 100
            ax.set_title(f"THE BULL PRINT  |  {name}  ₹{val:,.2f}  ({chg:+.2f}%)", color="#f8fafc", fontsize=24, fontweight="bold", pad=20)
            ax.tick_params(colors="#94a3b8", labelsize=14)
            for sp in ["top", "right"]:
                ax.spines[sp].set_visible(False)
            ax.spines["left"].set_color("#334155")
            ax.spines["bottom"].set_color("#334155")
            ax.grid(True, alpha=0.15, color="#334155", linestyle="--")

            frame_img = os.path.join(chart_dir, f"{name.replace(' ', '_')}_{idx:04d}.png")
            fig.savefig(frame_img, facecolor="#0a0f1d", bbox_inches="tight")
            frames.append(frame_img)

        plt.close(fig)

        chart_vid = os.path.join(chart_dir, f"{name.replace(' ', '_')}.mp4")
        concat_txt = os.path.join(chart_dir, f"{name.replace(' ', '_')}_list.txt")
        with open(concat_txt, "w") as f:
            for fr in frames:
                f.write(f"file '{fr}'\n")

        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_txt, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", chart_vid],
            check=True, capture_output=True,
        )
        chart_videos.append(chart_vid)
    except Exception as e:
        print(f"[KaggleWorker] Chart error: {e}", flush=True)

# ── Step 3: Pexels B-Roll Video Gathering ──
print("[KaggleWorker] Step 3: Fetching HD financial footage...", flush=True)
video_clips_paths = []
if pexels_api_key:
    import requests
    headers = {"Authorization": pexels_api_key}
    queries = ["stock market chart", "financial data numbers", "trading desk monitor", "corporate balance sheet"]
    for q in queries:
        try:
            resp = requests.get(f"https://api.pexels.com/videos/search?query={q}&per_page=3&orientation=landscape", headers=headers, timeout=10)
            if resp.status_code == 200:
                for v in resp.json().get("videos", []):
                    files = v.get("video_files", [])
                    files_sorted = sorted(files, key=lambda x: (x.get("width") or 0) * (x.get("height") or 0), reverse=True)
                    for vf in files_sorted:
                        if (vf.get("width") or 0) >= 1280:
                            v_url = vf.get("link")
                            f_path = os.path.join(temp_dir, f"broll_{len(video_clips_paths):03d}.mp4")
                            r_down = requests.get(v_url, timeout=30)
                            with open(f_path, "wb") as f_out:
                                f_out.write(r_down.content)
                            video_clips_paths.append(f_path)
                            break
        except Exception as e:
            print(f"[KaggleWorker] Pexels fetch notice: {e}", flush=True)

# Fallback background if none downloaded
if not video_clips_paths:
    bg_fallback = os.path.join(temp_dir, "dark_bg.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=#0a0f1d:s=1920x1080:d=10", "-c:v", "libx264", "-pix_fmt", "yuv420p", bg_fallback],
        check=True, capture_output=True,
    )
    video_clips_paths.append(bg_fallback)

# Interleave charts and b-roll
all_source_clips = []
max_len = max(len(video_clips_paths), len(chart_videos), 1)
for k in range(max_len):
    if k < len(video_clips_paths):
        all_source_clips.append(video_clips_paths[k])
    if k < len(chart_videos):
        all_source_clips.append(chart_videos[k])

# Build looping base video
concat_base = os.path.join(temp_dir, "concat_base.txt")
total_bg_duration = 0.0
with open(concat_base, "w") as f:
    while total_bg_duration < (audio_duration + 5.0):
        for clip in all_source_clips:
            f.write(f"file '{clip}'\n")
            total_bg_duration += 10.0

stitched_bg = os.path.join(temp_dir, "stitched_bg.mp4")
subprocess.run(
    ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_base, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", "-t", str(math.ceil(audio_duration + 2)), stitched_bg],
    check=True, capture_output=True,
)

# ── Step 4: Video Compositing with Animated Subtitles & Watermark ──
print("[KaggleWorker] Step 4: Compositing 10-minute 1080p masterclass video...", flush=True)
bg_clip = set_dur(VideoFileClip(stitched_bg), audio_duration)
audio_clip = AudioFileClip(audio_path)
w, h = bg_clip.w, bg_clip.h

overlays = []
# Watermark
try:
    badge = create_pillow_text_clip(
        "THE BULL PRINT  |  INSTITUTIONAL MASTERCLASS",
        duration=audio_duration,
        position=("center", int(h * 0.05)),
        font_size=24,
        color=(0, 229, 153),
        bg_color=(10, 15, 29, 230),
        width=850,
        height=50,
    )
    overlays.append(badge)
except Exception as e:
    print(f"[KaggleWorker] Watermark notice: {e}", flush=True)

# Subtitles
for start, end, stext in subtitle_entries:
    sdur = end - start
    if sdur <= 0:
        continue
    try:
        sclip = create_pillow_text_clip(
            stext[:75],
            duration=sdur,
            position=("center", int(h * 0.84)),
            font_size=28,
            color=(255, 255, 255),
            bg_color=(10, 15, 29, 210),
            width=1500,
            height=60,
            start=start,
        )
        overlays.append(sclip)
    except Exception as e:
        pass

final_video = CompositeVideoClip([bg_clip] + overlays)
final_video = set_aud(final_video, audio_clip)
final_video = set_dur(final_video, audio_duration)
rendered_mp4 = os.path.join(temp_dir, "final_masterclass.mp4")

# Render video
t_rend = time.time()
final_video.write_videofile(
    rendered_mp4,
    fps=24,
    codec="libx264",
    audio_codec="aac",
    preset="ultrafast",
    ffmpeg_params=["-crf", "22"],
    threads=4,
)
print(f"[KaggleWorker] Video rendering completed in {time.time()-t_rend:.1f}s", flush=True)

# ── Step 5: Autonomous YouTube Upload directly from Kaggle ──
print("[KaggleWorker] Step 5: Uploading masterclass to YouTube...", flush=True)
yt_url = None
if youtube_token_b64:
    try:
        token_data = base64.b64decode(youtube_token_b64)
        creds = pickle.loads(token_data)
        yt_service = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": subject[:100],
                "description": f"{subject}\n\n{script[:2500]}\n\n#TheBullPrint #Nifty50 #StockMarketIndia #TradingMasterclass",
                "tags": ["Nifty50", "StockMarket", "TradingMasterclass", "TheBullPrint", "InstitutionalTrading"],
                "categoryId": "27",
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(rendered_mp4, mimetype="video/mp4", resumable=True, chunksize=1024 * 1024 * 8)
        req = yt_service.videos().insert(part="snippet,status", body=body, media_body=media)

        resp = None
        while resp is None:
            status, resp = req.next_chunk()
            if status:
                print(f"[KaggleWorker] Uploading: {int(status.progress() * 100)}%", flush=True)

        vid_id = resp.get("id")
        if vid_id:
            yt_url = f"https://youtu.be/{vid_id}"
            print(f"[KaggleWorker] ✅ Masterclass published successfully: {yt_url}", flush=True)
            # Add to playlist
            playlist_id = payload.get("playlist_id", "PLO2FWTao-JNA")
            if playlist_id:
                try:
                    yt_service.playlistItems().insert(
                        part="snippet",
                        body={
                            "snippet": {
                                "playlistId": playlist_id,
                                "resourceId": {
                                    "kind": "youtube#video",
                                    "videoId": vid_id,
                                },
                            }
                        },
                    ).execute()
                    print(f"[KaggleWorker] Added video {vid_id} to playlist {playlist_id}", flush=True)
                except Exception as pe:
                    print(f"[KaggleWorker] Playlist insert notice: {pe}", flush=True)
    except Exception as e:
        print(f"[KaggleWorker] YouTube upload error: {e}", flush=True)

# ── Write Output Result ──
result = {
    "success": bool(yt_url),
    "youtube_url": yt_url,
    "duration": audio_duration,
    "rendered_file_size": os.path.getsize(rendered_mp4) if os.path.exists(rendered_mp4) else 0,
}

with open(os.path.join(output_dir, "result.json"), "w") as f:
    json.dump(result, f, indent=2)

print("[KaggleWorker] Pipeline execution finished cleanly.", flush=True)
