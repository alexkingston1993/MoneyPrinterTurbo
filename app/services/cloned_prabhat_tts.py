"""
Coqui XTTS-v2 Offline Cloned Voice Engine — Prabhat (en-IN).

Runs 100% locally with ZERO network connection, zero Microsoft dependency,
and zero cloud API calls. Uses pre-extracted multi-phonetic speaker conditioning
latents from authentic Prabhat training audio.
"""

import os
import re
import time
from typing import Optional, Union

import numpy as np
import soundfile as sf
import torch
from loguru import logger

from app.services.voice import (
    SubMaker,
    ensure_file_path_exists,
    ensure_legacy_submaker_fields,
    populate_legacy_submaker_with_full_text,
)

# Set Coqui license agreement non-interactively
os.environ["COQUI_TOS_AGREED"] = "1"

VOICES_DIR = os.path.join(os.path.dirname(__file__), "voices")
LATENTS_PATH = os.path.join(VOICES_DIR, "prabhat_latents.pt")
REF_WAV_PATH = os.path.join(VOICES_DIR, "prabhat_ref_master.wav")

_xtts_model = None
_cached_latents = None


def get_xtts_model():
    """Lazy-load the local XTTS-v2 model singleton."""
    global _xtts_model
    if _xtts_model is None:
        try:
            from TTS.api import TTS
            logger.info("[XTTS-Prabhat] Loading local XTTS-v2 model into memory...")
            t0 = time.time()
            tts_instance = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
            device = "cuda" if torch.cuda.is_available() else "cpu"
            tts_instance.to(device)
            _xtts_model = tts_instance.synthesizer.tts_model
            logger.info(f"[XTTS-Prabhat] XTTS-v2 model loaded successfully on {device} in {time.time()-t0:.2f}s")
        except Exception as e:
            logger.error(f"[XTTS-Prabhat] Failed to load local XTTS model: {e}")
            return None
    return _xtts_model


def get_prabhat_latents(model):
    """Retrieves or calculates the pre-computed speaker conditioning latents."""
    global _cached_latents
    if _cached_latents is not None:
        return _cached_latents

    if os.path.exists(LATENTS_PATH):
        try:
            _cached_latents = torch.load(LATENTS_PATH, map_location=model.device)
            logger.info(f"[XTTS-Prabhat] Loaded cached speaker latents from {LATENTS_PATH}")
            return _cached_latents
        except Exception as e:
            logger.warning(f"[XTTS-Prabhat] Could not load cached latents: {e}. Recomputing...")

    if os.path.exists(REF_WAV_PATH):
        logger.info(f"[XTTS-Prabhat] Computing speaker latents from master audio: {REF_WAV_PATH}...")
        gpt_cond_latent, speaker_embedding = model.get_conditioning_latents(audio_path=[REF_WAV_PATH])
        _cached_latents = {
            "gpt_cond_latent": gpt_cond_latent,
            "speaker_embedding": speaker_embedding,
        }
        os.makedirs(os.path.dirname(LATENTS_PATH), exist_ok=True)
        torch.save(_cached_latents, LATENTS_PATH)
        logger.info(f"[XTTS-Prabhat] Saved new speaker latents to {LATENTS_PATH}")
        return _cached_latents

    raise FileNotFoundError(f"Neither {LATENTS_PATH} nor {REF_WAV_PATH} exists.")


def cloned_prabhat_tts(
    text: str,
    voice_file: str,
    voice_rate: float = 1.0,
    voice_volume: float = 1.0,
    temperature: float = 0.7,
) -> Union[SubMaker, None]:
    """
    Synthesize speech 100% locally and offline using the cloned Prabhat voice model.

    Returns:
        SubMaker: Synchronized subtitle maker object with time offsets.
    """
    try:
        ensure_file_path_exists(voice_file)
        model = get_xtts_model()
        if not model:
            logger.error("[XTTS-Prabhat] Model is unavailable")
            return None

        latents = get_prabhat_latents(model)
        clean_text = text.strip()

        # Split into natural sentence clauses for natural prosody
        sentences = [s.strip() for s in re.split(r'(?<=[.?!;।])\s+', clean_text) if s.strip()]
        if not sentences:
            sentences = [clean_text]

        logger.info(f"[XTTS-Prabhat] Synthesizing {len(clean_text)} chars ({len(sentences)} sentences) offline with cloned Prabhat voice...")
        t0 = time.time()

        audio_pieces = []
        for i, s in enumerate(sentences):
            if not s:
                continue
            out = model.inference(
                text=s,
                language="en",
                gpt_cond_latent=latents["gpt_cond_latent"],
                speaker_embedding=latents["speaker_embedding"],
                temperature=temperature,
                speed=max(0.7, min(1.4, voice_rate)),
            )
            wav_chunk = out["wav"]
            if isinstance(wav_chunk, torch.Tensor):
                wav_chunk = wav_chunk.cpu().numpy()
            audio_pieces.append(wav_chunk)
            # Add subtle natural pause between sentences (0.15s of silence)
            audio_pieces.append(np.zeros(int(24000 * 0.15)))

        if not audio_pieces:
            logger.error("[XTTS-Prabhat] Inference generated no audio")
            return None

        full_audio = np.concatenate(audio_pieces)

        if voice_volume != 1.0:
            full_audio = np.clip(full_audio * voice_volume, -1.0, 1.0)

        sample_rate = 24000
        duration_seconds = len(full_audio) / float(sample_rate)

        sf.write(voice_file, full_audio, sample_rate)
        logger.success(f"[XTTS-Prabhat] Cloned speech generated offline: {voice_file} ({duration_seconds:.2f}s in {time.time()-t0:.2f}s)")

        # Generate synchronized SubMaker
        sub_maker = ensure_legacy_submaker_fields(SubMaker())
        sub_maker = populate_legacy_submaker_with_full_text(
            sub_maker=sub_maker,
            text=clean_text,
            audio_duration_seconds=duration_seconds,
        )
        return sub_maker

    except Exception as e:
        logger.error(f"[XTTS-Prabhat] Local synthesis error: {e}")
        return None
