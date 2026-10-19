"""
Colab GPU Worker client — offloads GPU-intensive tasks to Google Colab.

Usage:
    from app.services.colab_worker import ColabWorker

    worker = ColabWorker()
    # Send TTS job
    audio_path = worker.tts(text="Hello world", voice_ref="/path/to/ref.wav", language="en")

Architecture:
    Colab runs a FastAPI server behind an ngrok tunnel.
    This module discovers the tunnel URL (via env var, file, or stdin)
    and sends HTTP requests to the Colab worker.
"""

import json
import os
import time
import requests
from loguru import logger

COLAB_URL_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "colab_url.txt"
)


class ColabWorker:
    """Client for the Colab GPU worker server."""

    def __init__(self, base_url: str = None, timeout: int = 600):
        self.base_url = base_url or self._discover_url()
        self.timeout = timeout
        self.session = requests.Session()

    def _discover_url(self) -> str:
        """Discover Colab worker URL from env var or file."""
        url = os.environ.get("COLAB_WORKER_URL", "")
        if url:
            return url.rstrip("/")
        if os.path.exists(COLAB_URL_FILE):
            with open(COLAB_URL_FILE) as f:
                url = f.read().strip()
            if url:
                return url.rstrip("/")
        return ""

    def is_available(self) -> bool:
        """Check if Colab worker is reachable."""
        if not self.base_url:
            return False
        try:
            r = self.session.get(f"{self.base_url}/health", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def tts(self, text: str, voice_ref: str, language: str = "en",
            output_path: str = None) -> str:
        """
        Generate TTS audio on Colab GPU using Coqui XTTS v2.

        Args:
            text: Text to synthesize.
            voice_ref: Path to speaker reference WAV file.
            language: Language code (en, hi, ta).
            output_path: Local path to save the audio file.

        Returns:
            Path to the downloaded audio file.
        """
        if not output_path:
            output_path = "/tmp/_colab_tts_output.wav"

        logger.info(f"Colab TTS: {len(text)} chars, lang={language}")

        with open(voice_ref, "rb") as f:
            files = {"voice_ref": f}
            data = {"text": text, "language": language}
            r = self.session.post(
                f"{self.base_url}/tts",
                files=files, data=data, timeout=self.timeout
            )

        if r.status_code != 200:
            raise RuntimeError(f"Colab TTS failed: {r.status_code} {r.text[:200]}")

        with open(output_path, "wb") as f:
            f.write(r.content)

        logger.success(f"Colab TTS saved: {output_path} ({len(r.content)} bytes)")
        return output_path

    def render(self, video_path: str, audio_path: str, avatar_path: str,
               subtitle_entries: list, output_path: str) -> str:
        """
        Render final video on Colab GPU using moviepy.

        Args:
            video_path: Path to background video.
            audio_path: Path to TTS audio.
            avatar_path: Path to avatar image.
            subtitle_entries: List of (start_sec, end_sec, text) tuples.
            output_path: Local path for the final video.

        Returns:
            Path to the rendered video.
        """
        logger.info(f"Colab render: video={video_path}, audio={audio_path}")

        files = {}
        data = {"subtitle_entries": json.dumps(subtitle_entries)}

        for label, path in [("video", video_path), ("audio", audio_path),
                             ("avatar", avatar_path)]:
            if path and os.path.exists(path):
                with open(path, "rb") as f:
                    files[label] = (os.path.basename(path), f.read())

        r = self.session.post(
            f"{self.base_url}/render",
            files=files, data=data, timeout=self.timeout * 2
        )

        if r.status_code != 200:
            raise RuntimeError(f"Colab render failed: {r.status_code} {r.text[:200]}")

        with open(output_path, "wb") as f:
            f.write(r.content)

        logger.success(f"Colab render saved: {output_path} ({len(r.content)} bytes)")
        return output_path

    @staticmethod
    def save_url(url: str):
        """Save a discovered Colab worker URL for reuse."""
        os.makedirs(os.path.dirname(COLAB_URL_FILE), exist_ok=True)
        with open(COLAB_URL_FILE, "w") as f:
            f.write(url.strip())
        logger.info(f"Colab URL saved to {COLAB_URL_FILE}")
