"""
Shorts Repurposing Studio — Multiplier Engine (1 Masterclass -> 3 Shorts).
Inspired by darkzOGx YouTube Automation Agent Shorts Repurposing Studio.

Takes an approved 10-minute long-form masterclass and automatically slices out
three 45-60 second high-impact vertical (9:16) Shorts:
- Short 1: The Liquidity Sweep & Stop-Loss Trap
- Short 2: The SEBI Derivatives Negative Expectancy Truth
- Short 3: Volume Profile & Institutional Point of Control (POC)

Reuses 100% of the rendered video and audio generated in cloud GPU:
- Zero extra stock video credits used
- Zero extra TTS generation compute
- Transcoded to 1080x1920 portrait using compiled ffmpeg hardware-accelerated center-crop
- Generates psychological CTR titles via TitleLab
"""

import os
import subprocess
from typing import Dict, List, Optional
from loguru import logger

from app.services.title_lab import title_lab


class ShortsRepurposer:
    """Extracts and formats 9:16 vertical Shorts from 16:9 masterclasses."""

    CHAPTER_INTERVALS = [
        {
            "part": 1,
            "title_hook": "How Institutions Trap 91% of Retail Breakout Buyers",
            "tag": "LIQUIDITY TRAP",
            "start_sec": 35.0,
            "duration_sec": 50.0,
        },
        {
            "part": 2,
            "title_hook": "Why 93 Percent of Everyday People Lose Money in Quick Bets",
            "tag": "AVOID THIS TRAP",
            "start_sec": 170.0,
            "duration_sec": 52.0,
        },
        {
            "part": 3,
            "title_hook": "How Big Banks Buy Cheap When Everyday Investors Panic",
            "tag": "BIG BANKS DUMP",
            "start_sec": 315.0,
            "duration_sec": 55.0,
        },
    ]

    @classmethod
    def repurpose_masterclass_to_shorts(
        cls,
        source_video_path: str,
        output_dir: Optional[str] = None,
        base_subject: str = "The Bull Print Masterclass",
    ) -> List[Dict]:
        """
        Slices 3 vertical Shorts from a 16:9 masterclass video using ffmpeg.

        Args:
            source_video_path: Path to the 16:9 rendered masterclass MP4
            output_dir: Destination directory for short MP4s
            base_subject: Topic of the masterclass for title generation

        Returns:
            List of generated Short dictionaries with metadata and file paths
        """
        if not os.path.exists(source_video_path):
            raise FileNotFoundError(f"Source masterclass video not found: {source_video_path}")

        if not output_dir:
            output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "output", "repurposed_shorts")
        os.makedirs(output_dir, exist_ok=True)

        generated_shorts: List[Dict] = []
        logger.info(f"[Repurposer] 🎬 Slicing 3 vertical Shorts from masterclass: {source_video_path}...")

        for ch in cls.CHAPTER_INTERVALS:
            part_num = ch["part"]
            start = ch["start_sec"]
            dur = ch["duration_sec"]
            short_filename = f"short_part_{part_num}_{int(start)}s.mp4"
            short_path = os.path.join(output_dir, short_filename)

            # Generate high-CTR title via TitleLab
            title_candidate = f"{ch['title_hook']} | The Bull Print"
            best_title = title_lab.get_best_title(title_candidate, slot_name="breakout_radar")

            # Center crop 16:9 (1920x1080) into 9:16 (1080x1920) with vertical scaling & audio pass-through
            # Filter: crop to center 9:16 aspect ratio then scale to 1080x1920
            vf_filter = "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920"

            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start),
                "-i", source_video_path,
                "-t", str(dur),
                "-vf", vf_filter,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "22",
                "-c:a", "aac",
                "-b:a", "192k",
                short_path
            ]

            try:
                subprocess.run(cmd, capture_output=True, check=True, timeout=120)
                if os.path.exists(short_path) and os.path.getsize(short_path) > 10000:
                    logger.success(f"[Repurposer] ✅ Short Part {part_num} ready: {short_path} ({os.path.getsize(short_path)/1024/1024:.1f}MB)")
                    generated_shorts.append({
                        "part": part_num,
                        "title": best_title,
                        "tag": ch["tag"],
                        "video_path": short_path,
                        "start_sec": start,
                        "duration_sec": dur,
                        "tags": ["#shorts", "#stockmarketindia", "#nifty", "#thebullprint", "#tradingpsychology"],
                    })
            except Exception as e:
                logger.error(f"[Repurposer] Failed to extract Short Part {part_num}: {e}")

        logger.info(f"[Repurposer] Complete! Successfully extracted {len(generated_shorts)} Shorts from Masterclass.")
        return generated_shorts


# Global instance
shorts_repurposer = ShortsRepurposer()
