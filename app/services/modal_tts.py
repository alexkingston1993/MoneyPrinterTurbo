import base64
import os
import time

import modal

app = modal.App("mpt-tts-service")

model_vol = modal.Volume.from_name("tts-models", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "TTS==0.22.0",
        "soundfile",
        "transformers==4.44.2",
        "torch==2.5.1",
        "torchaudio==2.5.1",
    )
    .add_local_file(
        os.path.join(os.path.dirname(__file__), "voices", "alex_ref_10s.wav"),
        "/voice_ref.wav",
    )
)

_tts_model = None


@app.function(
    gpu="T4",
    image=image,
    volumes={"/root/.local/share/tts": model_vol},
    timeout=600,
    scaledown_window=300,
)
def tts(text: str, language: str = "en") -> dict:
    global _tts_model

    import torch
    import soundfile as sf

    os.environ["COQUI_TOS_AGREED"] = "1"
    from TTS.api import TTS

    device = "cuda" if torch.cuda.is_available() else "cpu"

    if _tts_model is None:
        print(f"Loading Coqui XTTS v2 on {device}...")
        t0 = time.time()
        _tts_model = TTS(
            "tts_models/multilingual/multi-dataset/xtts_v2"
        ).to(device)
        print(f"Model loaded in {time.time()-t0:.1f}s")

    out_path = "/tmp/output.wav"
    t0 = time.time()
    _tts_model.tts_to_file(
        text=text,
        file_path=out_path,
        speaker_wav="/voice_ref.wav",
        language=language,
        speed=1.0,
    )
    elapsed = time.time() - t0

    data, sr = sf.read(out_path)
    duration = len(data) / sr

    with open(out_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode()

    return {
        "audio_b64": audio_b64,
        "duration": duration,
        "sample_rate": sr,
        "elapsed": elapsed,
        "device": device,
        "chars": len(text),
    }


@app.local_entrypoint()
def main():
    text = (
        "Hello from Modal GPU. This is a test of the Coqui TTS pipeline "
        "using Modal cloud compute with persistent model caching."
    )
    result = tts.remote(text=text, language="en")
    print(
        f"\nTTS: {result['duration']:.0f}s audio in {result['elapsed']:.1f}s "
        f"({result['chars']} chars, {result['device']})"
    )
    print(f"Audio size: {len(result['audio_b64']) // 1024}KB base64")
