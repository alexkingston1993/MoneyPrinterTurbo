"""
Kaggle GPU worker for TTS.

Pushes a notebook to Kaggle, runs Coqui XTTS v2 on GPU, downloads the result.
100% cloud, 100% automated — no local GPU or browser needed.

Requirements (one-time):
  1. pip install kaggle
  2. Download API token from https://www.kaggle.com/settings → Create New Token
  3. Place at ~/.kaggle/kaggle.json
  4. Accept Coqui TOS: export COQUI_TOS_AGREED=1

Usage:
    from app.services.kaggle_worker import KaggleWorker
    worker = KaggleWorker()
    result = worker.run_tts("Hello world", "/path/to/voice_ref.wav", "en")
    print(result["audio_path"], result["duration"])
"""

import base64
import json
import os
import shutil
import tempfile
import time
import uuid

KAGGLE_NOTEBOOK_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "docs", "kaggle_tts_worker",
)


def _get_api():
    """Authenticate and return a KaggleApi instance."""
    u = os.getenv("KAGGLE_USERNAME")
    k = os.getenv("KAGGLE_KEY")
    if u and k:
        cfg_dir = os.path.expanduser("~/.kaggle")
        os.makedirs(cfg_dir, exist_ok=True)
        cfg_file = os.path.join(cfg_dir, "kaggle.json")
        if not os.path.exists(cfg_file):
            with open(cfg_file, "w") as f:
                json.dump({"username": u, "key": k}, f)
            os.chmod(cfg_file, 0o600)

    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    return api


def _prepare_voice_ref_b64(voice_ref_path: str, max_duration_sec: float = 8.0) -> str:
    """
    Prepares a compact, gzipped base64-encoded voice reference for Kaggle.
    Kaggle limits kernel source code to 1MB. Trimming reference audio to <=8s
    and gzipping keeps payload around 350-400KB while preserving full XTTS cloning fidelity.
    """
    if not voice_ref_path or not os.path.exists(voice_ref_path):
        return ""

    import gzip
    import io
    import wave

    try:
        with wave.open(voice_ref_path, "rb") as w:
            params = w.getparams()
            max_frames = min(w.getnframes(), int(params.framerate * max_duration_sec))
            frames = w.readframes(max_frames)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as w_out:
            w_out.setparams(params)
            w_out.writeframes(frames)
        audio_bytes = buf.getvalue()
    except Exception:
        # Fallback to reading file directly
        with open(voice_ref_path, "rb") as f:
            audio_bytes = f.read()

    compressed = gzip.compress(audio_bytes)
    return base64.b64encode(compressed).decode("ascii")


def _replace_payload(template_path: str, payload: dict) -> str:
    """Read notebook template, inject payload dict, return modified source."""
    with open(template_path) as f:
        source = f.read()

    payload_json = json.dumps(payload, indent=2)
    payload_code = f"payload = {payload_json}"
    if "PAYLOAD_PLACEHOLDER" not in source:
        raise RuntimeError("Template missing PAYLOAD_PLACEHOLDER marker")
    source = source.replace("PAYLOAD_PLACEHOLDER", payload_code)
    return source


class KaggleWorker:
    """
    Pushes TTS tasks to Kaggle GPU notebooks and retrieves results.

    Each call:
      1. Creates a temp kernel directory with the notebook + metadata
      2. Calls the Kaggle API to push + run the GPU notebook
      3. Polls the Kaggle API until the kernel completes
      4. Downloads the output WAV file
      5. Cleans up temporary files

    Args:
        timeout: Max seconds to wait for a Kaggle kernel to complete.
    """

    def __init__(self, timeout: int = 2400):
        self.api = _get_api()
        self.username = self.api.get_config_value("username")
        if not self.username:
            raise RuntimeError("Could not read 'username' from Kaggle config")
        self.timeout = timeout
        self._last_run_output_dir: str | None = None

    def is_available(self) -> bool:
        """Check if Kaggle API is configured (not a live check)."""
        try:
            _get_api()
            return True
        except Exception:
            return False

    def run_tts(self, text: str, voice_ref_path: str, language: str = "en") -> dict:
        """
        Run TTS on Kaggle GPU.

        Args:
            text: Text to synthesize.
            voice_ref_path: Path to voice reference WAV file.
            language: Language code (en, ta, hi).

        Returns:
            dict with:
                'audio_path'  - path to downloaded WAV file
                'duration'    - float seconds of audio

        Raises:
            RuntimeError: if TTS fails or times out.
        """
        # Encode voice reference (trimmed <= 8s & gzipped to stay under Kaggle 1MB limit)
        voice_ref_b64 = _prepare_voice_ref_b64(voice_ref_path, max_duration_sec=8.0)

        payload = {
            "text": text,
            "language": language,
            "voice_ref_b64": voice_ref_b64,
        }

        # Create temp kernel directory
        kernel_slug = f"mpt-tts-{uuid.uuid4().hex[:8]}"
        tmp_dir = tempfile.mkdtemp(prefix="kaggle_tts_")
        output_dir = tempfile.mkdtemp(prefix="kaggle_out_")
        self._last_run_output_dir = output_dir

        full_id = f"{self.username}/{kernel_slug}"

        try:
            # ── Prepare kernel files ──
            notebook_src = os.path.join(KAGGLE_NOTEBOOK_DIR, "main.py")
            modified_notebook = _replace_payload(notebook_src, payload)

            kernel_main = os.path.join(tmp_dir, "main.py")
            with open(kernel_main, "w") as f:
                f.write(modified_notebook)

            metadata = {
                "id": f"{self.username}/{kernel_slug}",
                "title": kernel_slug,
                "code_file": "main.py",
                "language": "python",
                "kernel_type": "script",
                "is_private": True,
                "enable_gpu": True,
                "enable_internet": True,
                "enable_tpu": False,
            }
            with open(os.path.join(tmp_dir, "kernel-metadata.json"), "w") as f:
                json.dump(metadata, f, indent=2)

            # ── Push to Kaggle ──
            print(f"[kaggle] Pushing kernel '{kernel_slug}' to Kaggle GPU…")
            push_resp = self.api.kernels_push(tmp_dir)
            kernel_url = getattr(push_resp, "url", f"https://www.kaggle.com/{full_id}")
            print(f"[kaggle] Pushed: {kernel_url}")
            print("[kaggle] Waiting for GPU to start…")

            # ── Wait for completion ──
            status = self._wait_for_kernel(full_id)

            if status == "error":
                err_msg = self._fetch_error(full_id, output_dir)
                raise RuntimeError(
                    f"Kaggle kernel failed. {err_msg}"
                    f"\nSee: https://www.kaggle.com/{full_id}"
                )
            elif status == "timeout":
                raise RuntimeError(
                    f"Kaggle kernel did not complete within {self.timeout}s. "
                    f"See: https://www.kaggle.com/{full_id}"
                )

            # ── Download output ──
            print("[kaggle] Downloading TTS output…")
            self._download_output(full_id, output_dir)

            tts_output = os.path.join(output_dir, "tts_output.wav")
            result_json = os.path.join(output_dir, "result.json")

            if not os.path.exists(tts_output):
                raise RuntimeError(
                    f"TTS output not found in kernel results. "
                    f"Check: https://www.kaggle.com/{full_id}"
                )

            result = {"audio_path": tts_output}
            if os.path.exists(result_json):
                with open(result_json) as f:
                    result.update(json.load(f))

            print(f"[kaggle] ✅ TTS complete: {os.path.getsize(tts_output)/1e3:.0f}KB @ {result.get('duration', '?')}s")
            return result

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _wait_for_kernel(self, full_id: str) -> str:
        """Poll kernel status. Returns 'complete', 'error', or 'timeout'."""
        t0 = time.time()
        while time.time() - t0 < self.timeout:
            try:
                status_resp = self.api.kernels_status(full_id)
                status_str = str(getattr(status_resp, "status", "")).lower()

                if "complete" in status_str:
                    return "complete"
                if "error" in status_str or "failed" in status_str:
                    return "error"

                elapsed = time.time() - t0
                if "running" in status_str:
                    if int(elapsed) % 60 < 10:
                        print(f"[kaggle]   Status: running ({elapsed:.0f}s)")
                else:
                    if int(elapsed) % 30 < 10:
                        print(f"[kaggle]   Status: {status_str} ({elapsed:.0f}s)")
            except Exception as e:
                elapsed = time.time() - t0
                if int(elapsed) % 30 < 10:
                    print(f"[kaggle]   Status check error: {e}")
            time.sleep(15)
        return "timeout"

    def _download_output(self, full_id: str, output_dir: str):
        """Download kernel output files."""
        try:
            files, _ = self.api.kernels_output(full_id, path=output_dir, force=True, quiet=True)
            if files:
                print(f"[kaggle]   Downloaded {len(files)} files")
        except Exception as e:
            print(f"[kaggle]   Download error: {e}")

    def _fetch_error(self, full_id: str, output_dir: str) -> str:
        """Try to get error details from kernel output."""
        try:
            self._download_output(full_id, output_dir)
            log_path = os.path.join(output_dir, "main.py.log")
            if os.path.exists(log_path):
                with open(log_path) as f:
                    return f"Errors:\n{f.read()[:500]}"
            # Check for other log files
            for fname in os.listdir(output_dir):
                if fname.endswith(".log") or fname.endswith(".txt"):
                    with open(os.path.join(output_dir, fname)) as f:
                        return f.read()[:500]
        except Exception:
            pass
        return "Check the kernel page for details."

    def cleanup_last_run(self):
        """Delete the temp output directory from the last run."""
        if self._last_run_output_dir and os.path.exists(self._last_run_output_dir):
            shutil.rmtree(self._last_run_output_dir, ignore_errors=True)
            self._last_run_output_dir = None

    def run_masterclass_gpu(
        self,
        subject: str,
        script: str,
        pexels_api_key: str = "",
        youtube_token_b64: str = "",
        voice_ref_path: str = None,
    ) -> str:
        """
        Executes the 10-minute masterclass generation and YouTube publication on Kaggle's free Nvidia T4 GPU.
        Returns the published YouTube URL, or None if failed.
        """
        if not voice_ref_path or not os.path.exists(voice_ref_path):
            candidates = [
                os.path.join(os.path.dirname(__file__), "voices", "prabhat_ref_8s.wav"),
                os.path.join(os.path.dirname(__file__), "voices", "prabhat_ref_master.wav"),
                os.path.join(os.path.dirname(__file__), "voices", "alex_ref_10s.wav"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    voice_ref_path = c
                    break

        # Trim <= 8s & gzip-encode so kernel source remains ~400KB (well below Kaggle's 1MB limit)
        voice_ref_b64 = _prepare_voice_ref_b64(voice_ref_path, max_duration_sec=8.0)

        payload = {
            "subject": subject,
            "script": script,
            "pexels_api_key": pexels_api_key,
            "youtube_token_b64": youtube_token_b64,
            "voice_ref_b64": voice_ref_b64,
            "playlist_id": "PLO2FWTao-JNA",
        }

        kernel_slug = f"mpt-masterclass-{uuid.uuid4().hex[:8]}"
        tmp_dir = tempfile.mkdtemp(prefix="kaggle_mc_")
        output_dir = tempfile.mkdtemp(prefix="kaggle_mc_out_")
        self._last_run_output_dir = output_dir

        full_id = f"{self.username}/{kernel_slug}"

        try:
            worker_src = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "docs", "kaggle_masterclass_worker", "main.py",
            )
            modified_script = _replace_payload(worker_src, payload)

            kernel_main = os.path.join(tmp_dir, "main.py")
            with open(kernel_main, "w") as f:
                f.write(modified_script)

            metadata = {
                "id": full_id,
                "title": kernel_slug,
                "code_file": "main.py",
                "language": "python",
                "kernel_type": "script",
                "is_private": True,
                "enable_gpu": True,
                "enable_internet": True,
                "enable_tpu": False,
            }
            with open(os.path.join(tmp_dir, "kernel-metadata.json"), "w") as f:
                json.dump(metadata, f, indent=2)

            print(f"[kaggle] 🚀 Offloading 10-minute masterclass to Kaggle Nvidia T4 GPU: {full_id}...")
            push_resp = self.api.kernels_push(tmp_dir)
            kernel_url = getattr(push_resp, "url", f"https://www.kaggle.com/{full_id}")
            print(f"[kaggle] Kernel dispatched: {kernel_url}")

            status = self._wait_for_kernel(full_id)
            if status != "complete":
                err_msg = self._fetch_error(full_id, output_dir)
                print(f"[kaggle] Kernel failed or timed out: {err_msg}")
                return None

            print("[kaggle] Downloading masterclass output result...")
            self._download_output(full_id, output_dir)

            result_json = os.path.join(output_dir, "result.json")
            if os.path.exists(result_json):
                with open(result_json) as f:
                    data = json.load(f)
                    yt_url = data.get("youtube_url")
                    if yt_url:
                        print(f"[kaggle] ✅ Autonomous Masterclass published via Kaggle GPU: {yt_url}")
                        return yt_url
            return None
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
