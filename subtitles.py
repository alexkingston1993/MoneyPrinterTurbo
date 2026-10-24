"""
Hormozi-Style Word-Level Subtitle Generator (subtitles.py).
Generates high-retention pop-up subtitles with exact word timestamps using Whisper.
Highlights bullish words in vibrant Emerald Green (#10B981) and bearish words in Crimson Red (#EF4444).
"""

import os
import re
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger

BULLISH_KEYWORDS = {
    "BUY", "BUYING", "ACCUMULATION", "BOUNCE", "SUPPORT", "SURGE", "RALLY", "BREAKOUT",
    "MINT", "PROFIT", "EXPANSION", "GROWTH", "OPPORTUNITY", "BULL", "BULLISH", "UPSIDE", "DEMAND"
}

BEARISH_KEYWORDS = {
    "TRAP", "TRAPPED", "DUMP", "DROP", "SELLING", "ABSORPTION", "RESISTANCE", "CRASH",
    "LOSS", "LOSSES", "RISK", "WARNING", "BEAR", "BEARISH", "DOWNSIDE", "MELT", "LIQUIDITY"
}


def generate_word_timestamps(audio_path: Path, script_text: str = "") -> List[Dict[str, Any]]:
    """
    Transcribes audio with word-level timestamps using Whisper / Faster-Whisper.
    Falls back gracefully to acoustic word-duration interpolation if Whisper weights aren't cached.
    """
    logger.info(f"🎙️ Generating word-level timestamps for: {audio_path.name}")
    word_events = []
    
    # 1. Try Faster-Whisper or OpenAI Whisper
    try:
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel("base.en", device="cpu", compute_type="int8")
            segments, _ = model.transcribe(str(audio_path), word_timestamps=True)
            for seg in segments:
                for w in (seg.words or []):
                    word_events.append({
                        "word": w.word.strip().upper(),
                        "start": float(w.start),
                        "end": float(w.end)
                    })
        except ImportError:
            import whisper
            model = whisper.load_model("base")
            result = model.transcribe(str(audio_path), word_timestamps=True)
            for segment in result["segments"]:
                for w in segment.get("words", []):
                    word_events.append({
                        "word": w["word"].strip().upper(),
                        "start": float(w["start"]),
                        "end": float(w["end"])
                    })
    except Exception as e:
        logger.warning(f"Whisper model inference bypassed ({e}), using acoustic word alignment.")
        
    # 2. Fallback: Interpolated acoustic word alignment
    if not word_events and script_text:
        # Probe audio duration
        try:
            res = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
                stdout=subprocess.PIPE, text=True, check=True
            )
            total_duration = float(res.stdout.strip())
        except Exception:
            total_duration = 8.0
            
        words = re.findall(r"\b[\w']+\b", script_text)
        if words:
            total_chars = sum(max(1, len(w)) for w in words)
            curr_time = 0.0
            for w in words:
                word_dur = (len(w) / total_chars) * total_duration
                word_events.append({
                    "word": w.upper(),
                    "start": round(curr_time, 2),
                    "end": round(curr_time + word_dur, 2)
                })
                curr_time += word_dur

    return word_events


def export_hormozi_ass(word_events: List[Dict[str, Any]], output_ass_path: Path):
    """
    Exports Advanced SubStation Alpha (.ass) format with dynamic word-by-word pop-up styling:
    - Bullish keywords in Emerald Green (&H0081B910)
    - Bearish keywords in Bright Red (&H004444EF)
    - Standard words in Pure White (&H00FFFFFF) with thick obsidian outline
    """
    ass_header = """[Script Info]
Title: Hormozi Pop-Up Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: HormoziDefault,Arial,64,&H00FFFFFF,&H00000000,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,3,2,40,40,160,1
Style: HormoziBullish,Arial,72,&H0081B910,&H00000000,&H00000000,&H80000000,-1,0,0,0,105,105,0,0,1,6,4,2,40,40,160,1
Style: HormoziBearish,Arial,72,&H004444EF,&H00000000,&H00000000,&H80000000,-1,0,0,0,105,105,0,0,1,6,4,2,40,40,160,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    dialogue_lines = []
    for event in word_events:
        word = event["word"]
        # Format timestamps (H:MM:SS.cs)
        s_m, s_s = divmod(event["start"], 60)
        s_h, s_m = divmod(int(s_m), 60)
        start_str = f"{s_h}:{s_m:02d}:{s_s:05.2f}"
        
        e_m, e_s = divmod(event["end"], 60)
        e_h, e_m = divmod(int(e_m), 60)
        end_str = f"{e_h}:{e_m:02d}:{e_s:05.2f}"
        
        # Color style selection
        if any(b in word for b in BULLISH_KEYWORDS):
            style = "HormoziBullish"
        elif any(r in word for r in BEARISH_KEYWORDS):
            style = "HormoziBearish"
        else:
            style = "HormoziDefault"
            
        dialogue_lines.append(f"Dialogue: 0,{start_str},{end_str},{style},,0,0,0,,{word}")

    output_ass_path.parent.mkdir(parents=True, exist_ok=True)
    output_ass_path.write_text(ass_header + "\n".join(dialogue_lines), encoding="utf-8")
    logger.success(f"✓ Saved Hormozi subtitle track ({len(dialogue_lines)} words): {output_ass_path.name}")
    return output_ass_path


if __name__ == "__main__":
    sample_text = "Big institutional buyers absorb the order flow and prevent prices from breaking out."
    sample_events = generate_word_timestamps(Path("build/sample.mp3"), sample_text)
    export_hormozi_ass(sample_events, Path("build/sample.ass"))
