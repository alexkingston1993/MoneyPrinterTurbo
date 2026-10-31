#!/usr/bin/env python3
"""
scripts/build_tether_master_audio.py

Synthesizes the complete 12-minute 8-chapter narration for the Tether Masterclass
using edge-tts and measures the exact duration.
"""

import asyncio
import json
import subprocess
from pathlib import Path
import edge_tts

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
AUDIO_DIR = OUTPUT_DIR / "tether_audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

PAYLOAD_PATH = OUTPUT_DIR / "tether_12min_master_payload.json"
VOICE = "en-US-ChristopherNeural"  # Authoritative documentary narrator voice

async def synthesize_all_chapters():
    with open(PAYLOAD_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    chapters = payload["chapters"]
    audio_files = []

    print(f"🎙️ Synthesizing {len(chapters)} chapters with voice: {VOICE}...")

    for c in chapters:
        idx = c["chapter_index"]
        title = c["title"]
        text = c["narration"]
        out_file = AUDIO_DIR / f"chapter_{idx:02d}.mp3"
        print(f"  -> Synthesizing Chapter {idx}: {title} ({len(text.split())} words)...")

        communicate = edge_tts.Communicate(text, VOICE, rate="-2%", pitch="-2Hz")
        await communicate.save(str(out_file))
        audio_files.append(out_file)

    # Concat all chapters with ffmpeg
    concat_list = AUDIO_DIR / "concat_list.txt"
    with open(concat_list, "w") as f:
        for af in audio_files:
            f.write(f"file '{af.name}'\n")

    master_audio = OUTPUT_DIR / "tether_12min_master_audio.mp3"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(master_audio)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Probe duration
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(master_audio)
    ], stdout=subprocess.PIPE, text=True, check=True)

    duration_sec = float(probe.stdout.strip())
    mins = int(duration_sec // 60)
    secs = int(duration_sec % 60)

    print(f"\n🎉 Successfully synthesized Master Audio Track!")
    print(f"📁 Output: {master_audio}")
    print(f"⏱️ Exact Duration: {duration_sec:.2f}s ({mins} minutes {secs} seconds)")

if __name__ == "__main__":
    asyncio.run(synthesize_all_chapters())
