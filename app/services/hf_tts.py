"""
Hugging Face Inference API — Free cloud TTS with Coqui XTTS v2 voice cloning.

100% cloud, 100% automated, 100% free (30K chars/month).

Requirements:
  1. pip install huggingface_hub
  2. HF_TOKEN env var or ~/.cache/huggingface/token
     Get one at: https://huggingface.co/settings/tokens

Usage:
    from app.services.hf_tts import hf_tts
    audio_path = hf_tts("Hello world", "/path/to/voice_ref.wav", "en")
"""

import io
import os
import tempfile
import time

REQUIRES = ["huggingface_hub"]


def _get_client():
    """Get Hugging Face InferenceClient with token."""
    from huggingface_hub import InferenceClient

    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN") or ""
    token_file = os.path.expanduser("~/.cache/huggingface/token")
    if not token and os.path.exists(token_file):
        with open(token_file) as f:
            token = f.read().strip()

    if not token:
        raise RuntimeError(
            "Hugging Face token not found.\n"
            "1. Go to https://huggingface.co/settings/tokens\n"
            "2. Create a token (read-only is fine)\n"
            "3. Set env var: export HF_TOKEN='your_token_here'"
        )

    return InferenceClient(token=token)


def is_available() -> bool:
    """Check if HF token is configured."""
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN") or ""
    token_file = os.path.expanduser("~/.cache/huggingface/token")
    if not token and os.path.exists(token_file):
        with open(token_file) as f:
            token = f.read().strip()
    return bool(token)


def hf_tts(text: str, voice_ref_path: str, language: str = "en") -> str:
    """
    Run Coqui XTTS v2 on Hugging Face Inference API with voice cloning.

    Args:
        text: Text to synthesize.
        voice_ref_path: Path to reference WAV for voice cloning.
        language: Language code (en, ta, hi).

    Returns:
        Path to generated WAV file.

    Raises:
        RuntimeError: if the API call fails.
    """
    client = _get_client()

    # Read voice reference
    with open(voice_ref_path, "rb") as f:
        voice_data = f.read()

    print(f"[hf-tts] Calling Coqui XTTS v2 API ({len(text)} chars, lang={language})…")
    t0 = time.time()

    try:
        audio_bytes = client.text_to_speech(
            text=text,
            model="coqui/XTTS-v2",
            speaker_audio=io.BytesIO(voice_data),
            language=language,
        )
    except Exception as e:
        raise RuntimeError(f"HF TTS API call failed: {e}")

    elapsed = time.time() - t0

    # Save to temp file
    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    if isinstance(audio_bytes, bytes):
        out.write(audio_bytes)
    else:
        out.write(audio_bytes.read())

    out_path = out.name
    out.close()

    # Get duration
    try:
        import soundfile as sf
        data, sr = sf.read(out_path)
        duration = len(data) / sr
        print(f"[hf-tts] ✅ {duration:.0f}s audio in {elapsed:.1f}s")
    except Exception:
        print(f"[hf-tts] ✅ Audio saved to {out_path} in {elapsed:.1f}s")

    return out_path
