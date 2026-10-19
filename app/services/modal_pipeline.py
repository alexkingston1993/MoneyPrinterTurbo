import base64
import json
import os
import re
import subprocess
import time
from datetime import date
from typing import List, Tuple

import modal

app = modal.App("mpt-pipeline")

output_vol = modal.Volume.from_name("pipeline-outputs", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "fonts-dejavu-core", "fonts-noto-cjk")
    .pip_install(
        "moviepy",
        "yfinance",
        "matplotlib",
        "requests",
        "numpy",
        "edge-tts",
        "soundfile",
    )
)

_tts_fn = None


def _get_tts_fn():
    global _tts_fn
    if _tts_fn is None:
        _tts_fn = modal.Function.from_name("mpt-tts-service", "tts")
    return _tts_fn


def _log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _sanitize_script(text: str) -> str:
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
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _sentences_from_script(script: str) -> List[str]:
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', script) if s.strip()]


def _compute_subtitle_entries(sentences: List[str], audio_duration: float) -> list:
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


# ── Script Generation ──

SEBI_PROMPT = """# Role: Script for Alex (Retail Investor from Chennai)

You are writing a script for Alex, a retail investor from Chennai, Tamil Nadu.
Alex shares his personal views on the Indian stock market for educational purposes.

## Content Rules (HARD CONSTRAINTS - Never Violate)
1. FRAME EVERYTHING as personal opinion: "I would...", "In my view...", "The data shows..."
2. NEVER say "you should", "you must", "you need to" (buy/sell/invest)
3. NEVER give price targets or stock predictions
4. NEVER promise returns or use words like "guaranteed", "sure-shot", "double your money"
5. Every "I would buy/sell/hold" MUST be followed by "But please do your own research"
6. Use only historical data (90+ days old). No live prices.
7. Start the script with: "Hey, I'm Alex from Chennai. Before we dive in — this is for educational purposes only. I'm not a SEBI-registered advisor."
8. End with: "This is Alex from Chennai, signing off."
9. Keep language simple enough for a common person to understand
10. Include BOTH positives and risks when discussing any stock
11. NEVER mention future price movements or predictions
12. NEVER use the phrase "this is not financial advice" — instead say "this is for educational purposes"

## Tone
- Conversational, like one friend explaining to another
- Use "I", "my", "me" — Alex's personal perspective
- Confident but humble — data speaks, not ego
- Speak in short, punchy sentences

## Format
Return ONLY the raw script text. No markdown, no formatting, no titles, no labels.

## Subject
{subject}
- Language: {language}"""


def _generate_script(subject: str, language: str = "en") -> Tuple[str, List[str]]:
    import requests as req

    prompt = SEBI_PROMPT.format(subject=subject, language=language)
    _log(f"Generating script via Pollinations.ai: {subject}")

    for attempt in range(5):
        try:
            resp = req.post(
                "https://text.pollinations.ai/openai",
                json={
                    "model": "openai-fast",
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60,
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
            sanitized = _sanitize_script(raw)
            sentences = _sentences_from_script(sanitized)
            _log(f"Script generated: {len(sanitized)} chars, {len(sentences)} sentences")
            return sanitized, sentences
        except Exception as e:
            _log(f"Script gen attempt {attempt+1} failed: {e}")
            time.sleep(3)

    raise RuntimeError("Failed to generate script after 5 attempts")


# ── Compliance (SEBI) ──

BANNED_PHRASES = [
    r"you should (buy|sell|invest|purchase|enter|trade)",
    r"you must (buy|sell|invest|purchase|enter|trade)",
    r"you need to (buy|sell|invest|purchase|enter|trade)",
    r"buy (this|the) stock",
    r"sell (this|the) stock",
    r"don't miss (this|the) opportunity",
    r"best stock to (buy|invest)",
    r"sure.?shot (winner|stock)",
    r"guaranteed (return|profit|income)",
    r"double your money",
    r"maximum profit",
    r"secret (strategy|formula|tip|technique)",
    r"(stock|trading) (tip|signal|call)",
    r"target (price|of) ₹?\s*\d+",
    r"(will|going to) (reach|hit|touch) ₹?\d+",
    r"price (target|prediction)",
    r"this is not financial advice",
]

REQUIRED_DISCLAIMER_PATTERNS = [
    r"educational (purpose|only)",
    r"not (a |an |)SEBI[\s-]?(registered|regist)",
    r"(do your own|your own) research",
]


def _validate_script(script: str) -> Tuple[bool, List[str]]:
    violations = []
    for pattern in BANNED_PHRASES:
        matches = re.findall(pattern, script, re.IGNORECASE)
        for m in matches:
            fm = m[0] if isinstance(m, tuple) else m
            violations.append(f"Banned: \"{fm}\"")

    for pattern in REQUIRED_DISCLAIMER_PATTERNS:
        if not re.search(pattern, script, re.IGNORECASE):
            violations.append(f"Missing disclaimer: {pattern}")

    return len(violations) == 0, violations


# ── Charts ──

def _generate_charts(output_dir: str, audio_duration: float) -> List[str]:
    import yfinance as yf
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tickers = [
        ("NIFTY 50", "^NSEI"),
        ("SENSEX", "^BSESN"),
        ("BANK NIFTY", "^NSEBANK"),
    ]

    chart_dir = os.path.join(output_dir, "charts")
    os.makedirs(chart_dir, exist_ok=True)

    chart_videos = []
    for name, symbol in tickers:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="6mo")
            if hist.empty or len(hist) < 20:
                continue
            close_prices = hist["Close"].values
            dates = hist.index

            fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=60)
            fig.patch.set_facecolor("#0d1117")
            ax.set_facecolor("#161b22")

            step = max(1, len(close_prices) // 150)
            frames = []
            for i in range(0, len(close_prices), step):
                ax.clear()
                data_up = close_prices[: i + 1]
                dates_up = dates[: i + 1]
                color = "#00d4aa" if data_up[-1] >= data_up[0] else "#ff6b6b"
                ax.plot(dates_up, data_up, color=color, linewidth=2.5, zorder=2)
                ax.fill_between(dates_up, data_up, alpha=0.1, color=color, zorder=1)
                cv = data_up[-1]
                ch = ((cv - data_up[0]) / data_up[0]) * 100
                ax.set_title(
                    f"{name}  |  ₹{cv:.2f}  ({ch:+.2f}%)",
                    color="white", fontsize=28, pad=20, fontweight="bold",
                )
                ax.tick_params(colors="#8b949e", labelsize=14)
                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)
                ax.grid(True, alpha=0.15, color="#30363d")
                fp = os.path.join(chart_dir, f"frame_{i:04d}.png")
                fig.savefig(fp, facecolor="#0d1117", bbox_inches="tight", pad_inches=0.2)
                frames.append(fp)
            plt.close(fig)

            chart_video = os.path.join(chart_dir, f"{name.replace(' ','_')}_chart.mp4")
            concat_file = os.path.join(chart_dir, "files.txt")
            with open(concat_file, "w") as cf:
                for fr in frames:
                    cf.write(f"file '{os.path.basename(fr)}'\n")

            subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", concat_file,
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-preset", "fast", "-crf", "20", chart_video,
                ],
                capture_output=True, check=True, timeout=120,
            )
            os.remove(concat_file)
            for f in frames:
                os.remove(f)
            chart_videos.append(chart_video)
            _log(f"Chart: {name}")
        except Exception as e:
            _log(f"Chart failed for {name}: {str(e)[:80]}")
    return chart_videos


# ── Background ──

def _generate_background(chart_videos: List[str], audio_duration: float, output_dir: str) -> str:
    out_path = os.path.join(output_dir, "background.mp4")
    if chart_videos:
        clip_path = chart_videos[0]
        _log(f"Looping chart video for {audio_duration:.0f}s background")
        subprocess.run(
            [
                "ffmpeg", "-y", "-stream_loop", "-1", "-i", clip_path,
                "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-t", str(audio_duration), "-crf", "28", "-threads", "4", out_path,
            ],
            capture_output=True, check=True, timeout=600,
        )
    else:
        _log(f"Dark background ({audio_duration:.0f}s)")
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi", "-i",
                f"color=c=0x001e32:s=1920x1080:d={audio_duration}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path,
            ],
            capture_output=True, check=True, timeout=120,
        )
    return out_path


# ── Final Render ──

def _render_final(bg_video: str, audio_path: str, sentences: List[str],
                  audio_duration: float, output_path: str):
    from moviepy import (
        CompositeVideoClip, VideoFileClip, AudioFileClip, TextClip,
    )

    video = VideoFileClip(bg_video)
    audio = AudioFileClip(audio_path)
    w, h = video.w, video.h
    fps = video.fps or 30

    fp = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if not os.path.exists(fp):
        fp = ""

    subtitle_entries = _compute_subtitle_entries(sentences, audio_duration)
    overlays = []
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
            TextClip(
                text=text, font_size=28, color="white", font=fp,
                stroke_color="black", stroke_width=2, method="label",
            )
            .with_position(("center", h * 0.85))
            .with_start(start).with_duration(sd)
        )

    final = CompositeVideoClip([video] + overlays)
    final = final.with_audio(audio)
    _log("MoviePy rendering...")
    final.write_videofile(
        output_path, codec="libx264",
        audio_codec="aac", fps=fps, threads=4,
        logger=None,
    )
    video.close()
    audio.close()
    final.close()
    _log(f"Render: {output_path} ({os.path.getsize(output_path)/1e6:.0f}MB)")


# ── Pipeline Function ──

@app.function(
    image=image,
    volumes={"/output": output_vol},
    timeout=3600,
    scaledown_window=300,
)
def daily_pipeline(subject: str, language: str = "en") -> dict:
    import soundfile as sf

    today = date.today().isoformat()
    out_dir = f"/output/{today}/The Compounder/market_update_{today}"
    os.makedirs(out_dir, exist_ok=True)

    t0 = time.time()

    # Step 1: Script
    _log("— Step 1: Script —")
    sanitized, sentences = _generate_script(subject, language)
    is_clean, violations = _validate_script(sanitized)
    if is_clean:
        _log("SEBI compliance: PASSED")
    else:
        _log(f"SEBI compliance violations:\n" + "\n".join(violations))
    with open(os.path.join(out_dir, "script.txt"), "w") as f:
        f.write(sanitized)

    # Step 2: TTS via Modal GPU function
    _log("— Step 2: TTS (Modal GPU) —")
    tts_fn = _get_tts_fn()
    tts_result = tts_fn.remote(text=sanitized, language=language)
    audio_path = os.path.join(out_dir, "audio.wav")
    with open(audio_path, "wb") as f:
        f.write(base64.b64decode(tts_result["audio_b64"]))
    audio_duration = tts_result["duration"]
    _log(f"TTS: {audio_duration:.0f}s ({tts_result['elapsed']:.1f}s gen, {tts_result['device']})")

    # Step 3: Charts
    _log("— Step 3: Charts —")
    chart_videos = _generate_charts(out_dir, audio_duration)

    # Step 4: Background
    _log("— Step 4: Background —")
    bg_video = _generate_background(chart_videos, audio_duration, out_dir)

    # Step 5: Render
    _log("— Step 5: Render —")
    final_out = os.path.join(out_dir, "final.mp4")
    _render_final(bg_video, audio_path, sentences, audio_duration, final_out)

    elapsed = time.time() - t0
    output_vol.commit()

    _log(f"\nPipeline complete in {elapsed/60:.1f}m")
    _log(f"Output: {final_out} ({os.path.getsize(final_out)/1e6:.0f}MB)")

    return {
        "output_path": final_out,
        "audio_duration": audio_duration,
        "total_chars": len(sanitized),
        "total_sentences": len(sentences),
        "elapsed_minutes": round(elapsed / 60, 1),
        "tts_gen_sec": tts_result["elapsed"],
        "tts_device": tts_result["device"],
    }


@app.function(
    image=image,
    volumes={"/output": output_vol},
    timeout=7200,
    schedule=modal.Cron("0 6 * * *"),
)
def scheduled_daily():
    subjects = [
        "SIP vs lump sum investing: which is better for Indian investors?",
        "NIFTY 50 weekly market analysis and trends",
        "Why most retail traders lose money in options trading",
        "ELSS tax saving funds compared to traditional options",
        "Dividend investing strategy for long-term wealth building",
    ]
    results = []
    for subject in subjects:
        try:
            r = daily_pipeline.remote(subject=subject, language="en")
            results.append(r)
            _log(f"Done: {subject[:40]}... -> {r['output_path']}")
        except Exception as e:
            _log(f"Failed: {subject[:40]}... -> {e}")
    output_vol.commit()
    return results


@app.local_entrypoint()
def main(subject: str = "SIP vs lump sum investing", language: str = "en"):
    result = daily_pipeline.remote(subject=subject, language=language)
    print(json.dumps(result, indent=2))
