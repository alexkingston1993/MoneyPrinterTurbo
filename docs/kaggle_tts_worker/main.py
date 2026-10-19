"""
MPT TTS Worker — runs Coqui XTTS v2 on Kaggle GPU.
Triggered via Kaggle API. Reads input from payload dict.
"""
import json, base64, os, time, subprocess, sys, shutil

# Wait for network to initialize, then install deps
import urllib.request
for _ in range(6):
    try:
        urllib.request.urlopen("https://pypi.org", timeout=5)
        break
    except Exception:
        time.sleep(5)

subprocess.run("pip install -q TTS soundfile 2>&1 | tail -3", shell=True, check=True)

# ── Payload injected by local script before push ──
PAYLOAD_PLACEHOLDER

import torch
from TTS.api import TTS
import soundfile as sf

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Device: {device}")
if device == "cuda":
    print(f"GPU: {torch.cuda.get_device_name(0)}")

# Decode voice reference
voice_ref_path = "/tmp/ref.wav"
with open(voice_ref_path, "wb") as f:
    f.write(base64.b64decode(payload["voice_ref_b64"]))
print(f"Voice ref: {os.path.getsize(voice_ref_path)} bytes")

# Load TTS model
print("Loading Coqui XTTS v2...")
os.environ["COQUI_TOS_AGREED"] = "1"
t0 = time.time()
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
print(f"Model loaded in {time.time()-t0:.1f}s")

# Run TTS
text = payload["text"]
language = payload.get("language", "en")
print(f"TTS: {len(text)} chars, lang={language}")
t0 = time.time()
out_path = "/tmp/output.wav"
tts.tts_to_file(
    text=text, file_path=out_path,
    speaker_wav=voice_ref_path, language=language, speed=1.0
)
elapsed = time.time() - t0

# Duration
data, sr = sf.read(out_path)
duration = len(data) / sr
print(f"Generated {duration:.0f}s audio in {elapsed:.1f}s")

# Copy to output dir
os.makedirs("/kaggle/working/output", exist_ok=True)
shutil.copy(out_path, "/kaggle/working/output/tts_output.wav")
with open("/kaggle/working/output/result.json", "w") as f:
    json.dump({"duration": duration}, f)
print("Done. Output in /kaggle/working/output/")
