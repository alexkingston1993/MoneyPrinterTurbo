#!/usr/bin/env python3.11
"""
Unified pipeline runner — generates videos using Colab GPU worker when available.

Zero-touch operation:
  python run_pipeline.py --auto-colab --subject "Your topic here"

  This automatically:
  1. Checks if a Colab worker is already running (env var or saved URL)
  2. If not, launches Chrome via Playwright, opens colab.research.google.com,
     uploads the GPU worker notebook, runs all cells, and captures the URL
  3. Uses Colab GPU for TTS (Alex's cloned voice via Coqui XTTS v2) and rendering
  4. If Colab fails or is unavailable, falls back to local CPU (edge-tts + FFmpeg)

Requirements for --auto-colab:
  - Google Chrome installed and logged into your Google account
  - NGROK_AUTH_TOKEN env var set (recommended, or free 1-hr tunnels)
  - pip install playwright + playwright install chromium (done once)

Usage:
    python run_pipeline.py --auto-colab --subject "Why long-term investing beats trading"
    python run_pipeline.py --auto-colab --subject "NIFTY 50 analysis" --language ta
    python run_pipeline.py --local --subject "SIP vs lumpsum"
    python run_pipeline.py --script /tmp/script.txt
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import date
from typing import List, Tuple

sys.path.insert(0, os.path.dirname(__file__))

from app.services.llm import _generate_response as call_llm, generate_script as llm_generate_script
from app.services.colab_worker import ColabWorker, COLAB_URL_FILE
from app.services.colab_launcher import launch_colab
from app.services.kaggle_worker import KaggleWorker
from app.services.compliance import validate_script, generate_compliance_report

# Lazy import for Modal (may not be installed)
_modal_fn = None
def _get_modal_tts():
    global _modal_fn
    if _modal_fn is None:
        try:
            import modal
            _modal_fn = modal.Function.from_name("mpt-tts-service", "tts")
        except Exception:
            _modal_fn = False
    return _modal_fn if _modal_fn is not False else None


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
AVATAR_DIR = os.path.join(PROJECT_DIR, "data", "avatars")
VOICE_REF = os.path.join(PROJECT_DIR, "app/services/voices/alex_ref_10s.wav")
BASE_OUTPUT = os.path.join(PROJECT_DIR, "output")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sanitize_script(text: str) -> str:
    text = text.replace("\u2011", "-").replace("\u2012", "-").replace("\u2013", "-")
    text = text.replace("\u2014", " - ").replace("\u2015", " - ").replace("\u2212", "-")
    text = text.replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ")
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = re.sub(r'\*\*', '', text)
    text = re.sub(r'---', '', text)
    text = re.sub(r'###\s*', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'(\d+)\s*%', r'\1 percent', text)
    text = re.sub(r' +', ' ', text)
    text = text.strip()
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def sentences_from_script(script: str) -> List[str]:
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', script) if s.strip()]


def compute_subtitle_entries(sentences: List[str], audio_duration: float) -> list:
    total_chars = sum(len(s) for s in sentences)
    cps = total_chars / audio_duration if audio_duration > 0 else 10
    entries = []
    ct = 0.0
    for sent in sentences:
        if not sent.strip():
            continue
        sd = max(1.0, len(sent) / cps)
        start = ct
        end = min(ct + sd, audio_duration)
        if start >= audio_duration:
            break
        entries.append((start, end, sent.strip()))
        ct = end
    return entries


def auto_discover_colab(timeout: int = 600) -> str:
    """
    Discover or auto-launch a Colab worker.

    1. Check COLAB_WORKER_URL env var → if reachable, use it
    2. Check data/colab_url.txt → if reachable, use it
    3. Launch Colab via Playwright → wait for ngrok URL

    Returns the worker URL, or empty string if unavailable.
    """
    # Check env var
    env_url = os.environ.get("COLAB_WORKER_URL", "").strip()
    if env_url:
        w = ColabWorker(base_url=env_url)
        if w.is_available():
            log(f"Colab found via COLAB_WORKER_URL: {env_url}")
            return env_url
        log(f"COLAB_WORKER_URL set but not reachable: {env_url}")

    # Check saved URL file
    if os.path.exists(COLAB_URL_FILE):
        with open(COLAB_URL_FILE) as f:
            file_url = f.read().strip()
        if file_url:
            w = ColabWorker(base_url=file_url)
            if w.is_available():
                log(f"Colab found via {COLAB_URL_FILE}: {file_url}")
                return file_url
            log(f"Saved URL not reachable: {file_url}")

    # Auto-launch Colab
    log("No existing Colab worker found. Auto-launching Colab via Playwright…")
    log("(A Chrome window will open — this is normal)")
    try:
        url = launch_colab(timeout=timeout)
        log(f"Colab auto-launched: {url}")
        return url
    except Exception as e:
        log(f"Colab auto-launch failed: {e}")
        return ""


def wait_for_colab(timeout: int = 300) -> bool:
    """Wait for Colab worker to become available. Returns True if found."""
    log("Waiting for Colab worker...")
    t0 = time.time()
    while time.time() - t0 < timeout:
        worker = ColabWorker()
        if worker.is_available():
            log(f"Colab worker ready at {worker.base_url}")
            return True
        # Also check if URL file was created
        if not worker.base_url and os.path.exists(COLAB_URL_FILE):
            log(f"Found Colab URL file: {open(COLAB_URL_FILE).read().strip()}")
            continue
        time.sleep(5)
    log("Colab worker not found within timeout")
    return False


# ── Step 0: Script Generation ──

def step_generate_script(subject: str, language: str = "en") -> Tuple[str, List[str]]:
    """Generate a SEBI-compliant script using the LLM."""
    log(f"Generating script for: {subject}")
    raw = llm_generate_script(
        video_subject=subject,
        language=language,
        paragraph_number=8,
        compliance_mode=True,
    )
    sanitized = sanitize_script(raw)
    sentences = sentences_from_script(sanitized)
    log(f"Generated: {len(sanitized)} chars, {len(sentences)} sentences")

    is_clean, violations = validate_script(sanitized)
    if is_clean:
        log("✅ SEBI compliance check passed")
    else:
        log(f"⚠️  Compliance violations:\n{generate_compliance_report(sanitized)}")

    return sanitized, sentences


# ── Step 1: Script ──

def step_script(script_path: str) -> Tuple[str, List[str]]:
    with open(script_path) as f:
        raw = f.read()
    sanitized = sanitize_script(raw)
    sentences = sentences_from_script(sanitized)
    log(f"Script: {len(sanitized)} chars, {len(sentences)} sentences")

    is_clean, violations = validate_script(sanitized)
    if is_clean:
        log("✅ SEBI compliance check passed")
    else:
        log(f"⚠️  Compliance violations:\n{generate_compliance_report(sanitized)}")

    return sanitized, sentences


# ── Step 2: TTS Audio ──

def step_tts(text: str, use_colab: bool = True, use_kaggle: bool = False,
             use_modal: bool = True) -> Tuple[str, float]:
    """Generate TTS audio. Tries Modal GPU first, then Colab/Kaggle, falls back to edge-tts."""
    audio_out = "/tmp/_pipeline_tts.mp3"

    if use_modal:
        modal_fn = _get_modal_tts()
        if modal_fn:
            log("Using Modal GPU for TTS (Coqui XTTS v2 — Alex's cloned voice)")
            try:
                import base64
                result = modal_fn.remote(text=text, language="en")
                wav_out = audio_out.replace(".mp3", ".wav")
                with open(wav_out, "wb") as f:
                    f.write(base64.b64decode(result["audio_b64"]))
                duration = result["duration"]
                log(f"Modal TTS: {duration:.0f}s audio ({result['elapsed']:.1f}s gen, {result['device']})")
                return wav_out, duration
            except Exception as e:
                log(f"Modal TTS failed: {e}, trying next method")
        else:
            log("Modal not available (not deployed or modal not installed)")

    if use_kaggle:
        log("Using Kaggle GPU for TTS (Coqui XTTS v2 — Alex's cloned voice)")
        try:
            worker = KaggleWorker()
            wav_out = "/tmp/_pipeline_tts_kaggle.wav"
            result = worker.run_tts(text=text, voice_ref_path=VOICE_REF, language="en")
            shutil.copy2(result["audio_path"], wav_out)
            duration = result.get("duration", 0)
            if not duration:
                import soundfile as sf
                data, sr = sf.read(wav_out)
                duration = len(data) / sr
            log(f"Kaggle TTS: {duration:.0f}s audio with Alex's cloned voice")
            return wav_out, duration
        except Exception as e:
            log(f"Kaggle TTS failed: {e}, falling back to edge-tts")

    if use_colab:
        worker = ColabWorker()
        if worker.is_available():
            log("Using Colab GPU for TTS (Coqui XTTS v2 — Alex's voice)")
            try:
                wav_out = audio_out.replace(".mp3", ".wav")
                worker.tts(text=text, voice_ref=VOICE_REF,
                           language="en", output_path=wav_out)
                import soundfile as sf
                data, sr = sf.read(wav_out)
                duration = len(data) / sr
                log(f"Colab TTS: {duration:.0f}s audio with Alex's cloned voice")
                return wav_out, duration
            except Exception as e:
                log(f"Colab TTS failed: {e}, falling back to edge-tts")
        else:
            log("Colab not available, using edge-tts")

    import edge_tts

    async def _gen():
        communicate = edge_tts.Communicate(text, "en-US-JennyNeural")
        await communicate.save(audio_out)

    import asyncio
    t0 = time.time()
    asyncio.run(_gen())
    elapsed = time.time() - t0

    from moviepy import AudioFileClip
    clip = AudioFileClip(audio_out)
    duration = clip.duration
    clip.close()

    log(f"Edge TTS: {duration:.0f}s in {elapsed:.1f}s (synthetic voice)")
    return audio_out, duration


# ── Step 3: Charts ──

def step_charts(output_dir: str) -> List[str]:
    """Generate animated chart videos for NIFTY, SENSEX, BANK NIFTY."""
    chart_dir = os.path.join(output_dir, "charts")
    os.makedirs(chart_dir, exist_ok=True)

    tickers = [
        ("NIFTY 50", "^NSEI"),
        ("SENSEX", "^BSESN"),
        ("BANK NIFTY", "^NSEBANK"),
    ]

    chart_videos = []
    for name, symbol in tickers:
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="6mo")
            if hist.empty or len(hist) < 20:
                continue
            close_prices = hist["Close"].values
            dates = hist.index

            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=60)
            fig.patch.set_facecolor("#0d1117")
            ax.set_facecolor("#161b22")

            step = max(1, len(close_prices) // 150)
            frames = []
            for i in range(0, len(close_prices), step):
                ax.clear()
                data_up = close_prices[:i+1]
                dates_up = dates[:i+1]
                color = "#00d4aa" if data_up[-1] >= data_up[0] else "#ff6b6b"
                ax.plot(dates_up, data_up, color=color, linewidth=2.5, zorder=2)
                ax.fill_between(dates_up, data_up, alpha=0.1, color=color, zorder=1)
                cv = data_up[-1]
                ch = ((cv - data_up[0]) / data_up[0]) * 100
                prefix = "\u20b9"
                ax.set_title(f"{name}  |  {prefix}{cv:.2f}  ({ch:+.2f}%)",
                            color="white", fontsize=28, pad=20, fontweight="bold")
                ax.tick_params(colors="#8b949e", labelsize=14)
                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)
                ax.grid(True, alpha=0.15, color="#30363d")
                fp = os.path.join(chart_dir, f"frame_{i:04d}.png")
                fig.savefig(fp, facecolor="#0d1117", bbox_inches="tight", pad_inches=0.2)
                frames.append(fp)
            plt.close(fig)

            chart_video = os.path.join(chart_dir, f"{name.replace(' ','_')}_chart.mp4")

            # Write a concat file for ffmpeg (avoids glob/space issues)
            concat_file = os.path.join(chart_dir, "files.txt")
            with open(concat_file, "w") as cf:
                for fr in frames:
                    cf.write(f"file '{os.path.basename(fr)}'\n")

            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                 "-i", concat_file,
                 "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-preset", "fast", "-crf", "20", chart_video],
                capture_output=True, check=True, timeout=120,
            )

            os.remove(concat_file)

            for f in frames:
                os.remove(f)
            chart_videos.append(chart_video)
            log(f"Chart: {name}")
        except Exception as e:
            log(f"Chart failed for {name}: {str(e)[:80]}")
    return chart_videos


# ── Step 4: Background Video ──

def step_background(chart_videos: List[str], audio_duration: float,
                    output_dir: str) -> str:
    """Create background video by looping first chart or generating a dark screen."""
    out_path = os.path.join(output_dir, "background.mp4")

    if chart_videos:
        clip_path = chart_videos[0]
        log(f"Looping chart video for {audio_duration:.0f}s background")
        subprocess.run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", clip_path,
            "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-t", str(audio_duration), "-crf", "28", "-threads", "4", out_path],
            capture_output=True, check=True, timeout=600)
    else:
        log(f"Generating dark background ({audio_duration:.0f}s)")
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
            f"color=c=0x001e32:s=1920x1080:d={audio_duration}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path],
            capture_output=True, check=True, timeout=120)
    return out_path


# ── Step 5: Final Render ──

def step_render(bg_video: str, audio_path: str, subtitle_entries: list,
                avatar_path: str, output_path: str,
                use_colab: bool = True) -> str:
    """Render final video with subtitles and avatar overlay.
    Uses Colab GPU if available, otherwise falls back to local moviepy."""

    if use_colab:
        worker = ColabWorker()
        if worker.is_available():
            log("Using Colab GPU for final render")
            try:
                return worker.render(
                    video_path=bg_video, audio_path=audio_path,
                    avatar_path=avatar_path if os.path.exists(avatar_path) else None,
                    subtitle_entries=subtitle_entries,
                    output_path=output_path,
                )
            except Exception as e:
                log(f"Colab render failed: {e}, rendering locally")

    log("Rendering locally (moviepy on CPU — this will be slow)")
    from moviepy import CompositeVideoClip, VideoFileClip, AudioFileClip, TextClip

    video = VideoFileClip(bg_video)
    audio = AudioFileClip(audio_path)
    duration = audio.duration
    w, h = video.w, video.h
    fps = video.fps or 30

    overlays = []
    fp = "/System/Library/Fonts/Helvetica.ttc"
    if not os.path.exists(fp):
        fp = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if not os.path.exists(fp):
        fp = ""

    for start, end, text in subtitle_entries:
        sd = end - start
        if sd <= 0:
            continue
        if len(text) > 60:
            words = text.split()
            lines, line = [], ""
            for w in words:
                test = f"{line} {w}".strip()
                if len(test) > 50:
                    lines.append(line)
                    line = w
                else:
                    line = test
            if line:
                lines.append(line)
            text = "\n".join(lines)
        overlays.append(
            TextClip(text=text, font_size=28, color="white", font=fp,
                     stroke_color="black", stroke_width=2, method="label")
            .with_position(("center", h * 0.85))
            .with_start(start).with_duration(sd)
        )

    final = CompositeVideoClip([video] + overlays)
    final = final.with_audio(audio)
    log("MoviePy rendering started (this takes longest)")
    final.write_videofile(output_path, codec="libx264",
                          audio_codec="aac", fps=fps, threads=4)
    video.close()
    audio.close()
    final.close()

    log(f"Render saved: {output_path} ({os.path.getsize(output_path)/1e6:.0f}MB)")
    return output_path


# ── Main Pipeline ──

def run_pipeline(script_path: str = None, subject: str = None,
                 language: str = "en", local_only: bool = False,
                 use_kaggle: bool = False, use_modal: bool = True):
    log(f"\n{'='*60}")
    log(f"  PIPELINE - {date.today().isoformat()}")
    log(f"{'='*60}\n")

    use_colab = not local_only and not use_kaggle

    if use_kaggle:
        log("GPU mode: Kaggle (Coqui XTTS v2 via notebook push)")
    elif use_modal:
        log("GPU TTS: Modal (Coqui XTTS v2 on T4)")

    # Check Modal availability
    if use_modal:
        fn = _get_modal_tts()
        if fn:
            log(f"Modal GPU TTS: AVAILABLE")
        else:
            log("Modal GPU TTS: not deployed — will fall back")
            use_modal = False

    # Check Colab availability
    if use_colab:
        worker = ColabWorker()
        if worker.is_available():
            log(f"Colab GPU worker: AVAILABLE at {worker.base_url}")
        else:
            log("Colab GPU worker: not available — running locally")
            use_colab = False

    today = date.today().isoformat()
    output_dir = os.path.join(BASE_OUTPUT, today, "The Compounder",
                              f"market_update_{today}")
    os.makedirs(output_dir, exist_ok=True)

    avatar_path = ""
    avatars = sorted([f for f in os.listdir(AVATAR_DIR)
                      if f.endswith(('.jpg', '.png'))])
    if avatars:
        avatar_path = os.path.join(AVATAR_DIR, avatars[0])
    log(f"Avatar: {avatar_path or 'none'}")

    # Step 1: Script
    log("\n— Step 1: Script Prep —")
    if subject:
        sanitized, sentences = step_generate_script(subject, language)
    elif script_path and os.path.exists(script_path):
        sanitized, sentences = step_script(script_path)
    else:
        log("No script provided. Use --script <path> or --subject <topic>")
        return
    with open(os.path.join(output_dir, "script.txt"), "w") as f:
        f.write(sanitized)

    # Step 2: TTS
    log("\n— Step 2: TTS —")
    audio_path, audio_duration = step_tts(sanitized, use_colab=use_colab, use_kaggle=use_kaggle, use_modal=use_modal)
    audio_out = os.path.join(output_dir, "audio.mp3")
    shutil.copy2(audio_path, audio_out)

    # Step 3: Charts
    log("\n— Step 3: Charts —")
    chart_videos = step_charts(output_dir)

    # Step 4: Background video
    log("\n— Step 4: Background Video —")
    bg_video = step_background(chart_videos, audio_duration, output_dir)

    # Step 5: Render final
    log("\n— Step 5: Final Render —")
    subs = compute_subtitle_entries(sentences, audio_duration)
    log(f"  {len(subs)} subtitle entries")

    final_out = os.path.join(output_dir, "final.mp4")
    step_render(bg_video, audio_out, subs, avatar_path, final_out,
                use_colab=use_colab)

    log(f"\n{'='*60}")
    log(f"  PIPELINE COMPLETE")
    log(f"  Output: {final_out}")
    log(f"  Size: {os.path.getsize(final_out)/1e6:.0f}MB")
    log(f"{'='*60}")
    return final_out


def main():
    parser = argparse.ArgumentParser(description="Unified pipeline runner")
    parser.add_argument("--script", default="",
                        help="Path to script file")
    parser.add_argument("--subject", default="",
                        help="Video subject (generates script via LLM)")
    parser.add_argument("--language", default="en",
                        help="Script language (en, ta, hi)")
    parser.add_argument("--local", action="store_true",
                        help="Run locally without Colab")
    parser.add_argument("--wait-for-colab", action="store_true",
                        help="Wait for Colab worker to become available")
    parser.add_argument("--auto-colab", action="store_true",
                        help="Auto-launch Colab via browser automation if not already running")
    parser.add_argument("--kaggle", action="store_true",
                        help="Use Kaggle GPU for TTS (push notebook via API)")
    parser.add_argument("--no-modal", action="store_true",
                        help="Skip Modal cloud GPU TTS (use Colab or edge-tts fallback)")
    args = parser.parse_args()

    if args.auto_colab and args.kaggle:
        print("Cannot use both --auto-colab and --kaggle. Pick one.")
        return 1

    if args.auto_colab:
        url = auto_discover_colab()
        if url:
            os.environ["COLAB_WORKER_URL"] = url

    if args.wait_for_colab:
        if not wait_for_colab():
            log("Colab didn't become available, proceeding locally")

    if not args.subject and not args.script:
        print("Provide --subject <topic> to generate a script, or --script <path> for a file.")
        return 1

    if args.script and not os.path.exists(args.script):
        print(f"Script not found: {args.script}")
        return 1

    t0 = time.time()
    run_pipeline(script_path=args.script or None,
                 subject=args.subject or None,
                 language=args.language,
                 local_only=args.local,
                 use_kaggle=args.kaggle,
                 use_modal=not args.no_modal)
    elapsed = time.time() - t0
    print(f"\nTotal time: {elapsed/60:.1f} minutes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
