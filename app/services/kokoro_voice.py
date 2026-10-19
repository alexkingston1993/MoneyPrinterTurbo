"""
Kokoro-82M High-Fidelity Open-Source TTS Engine.

Integrates the SOTA open-weights Kokoro model (GitHub: hexgrad/Kokoro-82M):
- 82 Million parameters, studio-grade prosody and natural human cadence
- 100% Free, runs locally on CPU/GPU without cloud costs or rate limits
- Generates 24,000 Hz studio audio with synchronized subtitle integration

Supported Studio Voices:
- kokoro:am_adam (American Male, authoritative & crisp financial anchor)
- kokoro:am_michael (American Male, deep documentary presenter)
- kokoro:af_heart (American Female, voted #1 naturalness score in open TTS)
- kokoro:af_bella (American Female, expressive & dynamic)
- kokoro:af_nicole (American Female, formal broadcast anchor)
- kokoro:bm_george (British Male, BBC style analyst)
- kokoro:bm_lewis (British Male, refined documentary narrator)
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
try:
    import torch
    torch.set_num_threads(1)
except Exception:
    pass

from typing import Optional, Union
from loguru import logger
import numpy as np
import soundfile as sf

from app.services.voice import (
    SubMaker,
    ensure_file_path_exists,
    ensure_legacy_submaker_fields,
    populate_legacy_submaker_with_full_text,
)

# Global lazy pipeline singleton
_kokoro_pipeline = None


def get_kokoro_pipeline(lang_code: str = "a"):
    global _kokoro_pipeline
    if _kokoro_pipeline is None:
        try:
            import torch
            torch.set_num_threads(1)
            try:
                torch.set_num_interop_threads(1)
            except Exception:
                pass
            from kokoro import KPipeline
            logger.info(f"[KokoroTTS] Initializing KPipeline with lang_code='{lang_code}'...")
            _kokoro_pipeline = KPipeline(lang_code=lang_code)
            logger.info("[KokoroTTS] KPipeline initialized successfully")
        except Exception as e:
            logger.error(f"[KokoroTTS] Failed to initialize KPipeline: {e}")
            return None
    return _kokoro_pipeline


def is_kokoro_voice(voice_name: str) -> bool:
    if not voice_name:
        return False
    return voice_name.lower().startswith("kokoro:")


def parse_kokoro_voice(voice_name: str) -> tuple[str, str]:
    """
    Parses voice string into (voice_id, lang_code).
    e.g. 'kokoro:am_adam' -> ('am_adam', 'a')
         'kokoro:bm_george' -> ('bm_george', 'b')
    """
    parts = voice_name.split(":")
    raw_voice = parts[1] if len(parts) > 1 and parts[1] else "af_heart"
    voice_id = raw_voice.split("-")[0].strip()

    # Determine language code: 'b' for British, 'a' for American
    lang_code = "b" if voice_id.startswith("b") else "a"
    return voice_id, lang_code


def kokoro_tts(
    text: str,
    voice_name: str,
    voice_rate: float,
    voice_file: str,
    voice_volume: float = 1.0,
) -> Union[SubMaker, None]:
    """
    Synthesizes speech using Kokoro-82M neural model.
    """
    try:
        ensure_file_path_exists(voice_file)
        voice_id, lang_code = parse_kokoro_voice(voice_name)
        pipeline = get_kokoro_pipeline(lang_code=lang_code)

        if not pipeline:
            logger.error("[KokoroTTS] Kokoro pipeline is unavailable")
            return None

        # Speed mapping: voice_rate (1.0 default)
        speed = max(0.6, min(1.8, voice_rate))
        logger.info(f"[KokoroTTS] Synthesizing text with voice='{voice_id}', speed={speed}...")

        clean_text = text.strip()
        generator = pipeline(clean_text, voice=voice_id, speed=speed)

        audio_chunks = []
        for i, (gs, ps, audio) in enumerate(generator):
            if audio is not None and len(audio) > 0:
                audio_chunks.append(audio)

        if not audio_chunks:
            logger.error("[KokoroTTS] Generator yielded no audio chunks")
            return None

        full_audio = np.concatenate(audio_chunks)

        # Apply volume scaling if requested
        if voice_volume != 1.0:
            full_audio = full_audio * voice_volume
            full_audio = np.clip(full_audio, -1.0, 1.0)

        sample_rate = 24000
        duration_seconds = len(full_audio) / float(sample_rate)

        # Save audio file
        sf.write(voice_file, full_audio, sample_rate)
        logger.info(f"[KokoroTTS] Audio saved to {voice_file} ({duration_seconds:.2f}s)")

        # Create synchronized SubMaker object
        sub_maker = ensure_legacy_submaker_fields(SubMaker())
        sub_maker = populate_legacy_submaker_with_full_text(
            sub_maker=sub_maker,
            text=clean_text,
            audio_duration_seconds=duration_seconds,
        )

        return sub_maker

    except Exception as e:
        logger.error(f"[KokoroTTS] Error during synthesis: {e}")
        return None
