import os
import math
import shutil
from os import path
from typing import Dict, List, Optional, Tuple

from loguru import logger

from app.models import const
from app.models.schema import VideoParams, VideoConcatMode
from app.services import llm, voice, subtitle, video
from app.services import state as sm
from app.utils import utils


LANGUAGE_NAMES = {
    "en": "English",
    "ta": "Tamil",
    "hi": "Hindi",
    "te": "Telugu",
    "kn": "Kannada",
    "ml": "Malayalam",
    "bn": "Bengali",
    "gu": "Gujarati",
    "mr": "Marathi",
}


def generate_multilanguage_content(
    task_id: str,
    params: VideoParams,
    primary_script: str,
    downloaded_videos: List[str],
    audio_duration: float,
) -> Dict[str, dict]:
    target_langs = params.target_languages or []
    if not target_langs:
        return {}

    logger.info(f"\n\n## generating multi-language content for: {target_langs}")

    results = {}
    primary_lang = params.video_language or "en"

    for i, lang in enumerate(target_langs):
        lang_name = LANGUAGE_NAMES.get(lang, lang)
        logger.info(f"\n--- [{i+1}/{len(target_langs)}] {lang_name} ({lang}) ---")

        # 1. Translate script
        translated = llm.translate_script(
            script=primary_script,
            target_language=lang_name,
            source_language=LANGUAGE_NAMES.get(primary_lang, "English"),
        )
        if not translated:
            logger.error(f"translation to {lang} failed, skipping")
            continue

        script_file = path.join(utils.task_dir(task_id), f"script_{lang}.json")
        script_data = {
            "script": translated,
            "source_script": primary_script,
            "language": lang,
        }
        with open(script_file, "w", encoding="utf-8") as f:
            f.write(utils.to_json(script_data))

        sm.state.update_task(
            task_id, progress=55 + i * 15, status=f"translating to {lang_name}"
        )

        # 2. Select voice for this language
        selected_voice = voice.select_voice_for_language(
            language=lang,
            default_voice=params.voice_name,
        )
        logger.info(f"{lang} -> voice: {selected_voice}")

        # 3. Generate audio
        audio_file = path.join(utils.task_dir(task_id), f"audio_{lang}.mp3")
        sub_maker = voice.tts(
            text=translated,
            voice_name=voice.parse_voice_name(selected_voice),
            voice_rate=params.voice_rate,
            voice_file=audio_file,
        )
        if sub_maker is None:
            logger.error(f"audio generation failed for {lang}, skipping")
            continue

        lang_audio_duration = math.ceil(voice.get_audio_duration(sub_maker))
        if lang_audio_duration == 0:
            logger.error(f"audio duration is 0 for {lang}, skipping")
            continue

        logger.info(f"{lang} audio generated: {lang_audio_duration}s")

        # 4. Generate subtitle
        subtitle_path = ""
        if params.subtitle_enabled:
            subtitle_path = path.join(utils.task_dir(task_id), f"subtitle_{lang}.srt")
            subtitle_provider = "edge"
            try:
                from app.config import config as cfg
                subtitle_provider = cfg.app.get("subtitle_provider", "edge").strip().lower()
            except Exception:
                pass

            subtitle_fallback = False
            if subtitle_provider == "edge":
                voice.create_subtitle(
                    text=translated, sub_maker=sub_maker, subtitle_file=subtitle_path
                )
                if not os.path.exists(subtitle_path):
                    subtitle_fallback = True
                    logger.warning(f"subtitle file not found for {lang}, fallback to whisper")

            if subtitle_provider == "whisper" or subtitle_fallback:
                subtitle.create(audio_file=audio_file, subtitle_file=subtitle_path)
                subtitle.correct(subtitle_file=subtitle_path, video_script=translated)

            if not os.path.exists(subtitle_path):
                logger.warning(f"subtitle not generated for {lang}")
                subtitle_path = ""

        # 5. Generate video
        combined_video_path = path.join(
            utils.task_dir(task_id), f"combined_{lang}.mp4"
        )
        video.combine_videos(
            combined_video_path=combined_video_path,
            video_paths=downloaded_videos,
            audio_file=audio_file,
            video_aspect=params.video_aspect,
            video_concat_mode=(
                params.video_concat_mode
                if params.video_count == 1
                else VideoConcatMode.random
            ),
            video_transition_mode=params.video_transition_mode,
            max_clip_duration=params.video_clip_duration,
            threads=params.n_threads,
            video_resolution=params.video_resolution or "standard",
        )

        final_video_path = path.join(
            utils.task_dir(task_id), f"final_{lang}.mp4"
        )
        video.generate_video(
            video_path=combined_video_path,
            audio_path=audio_file,
            subtitle_path=subtitle_path,
            output_file=final_video_path,
            params=params,
        )

        results[lang] = {
            "script": translated,
            "audio_file": audio_file,
            "audio_duration": lang_audio_duration,
            "subtitle_path": subtitle_path,
            "combined_video": combined_video_path,
            "final_video": final_video_path,
        }

        logger.success(f"[{lang}] video generated: {final_video_path}")

    return results
