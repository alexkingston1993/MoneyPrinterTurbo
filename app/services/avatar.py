import datetime
import math
import os
from typing import Callable, List, Optional

import numpy as np
from loguru import logger
from moviepy import AudioFileClip, CompositeVideoClip, VideoClip, VideoFileClip
from PIL import Image, ImageEnhance
from scipy.ndimage import gaussian_filter1d

AVATAR_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "avatars",
)
CACHE_DIR = os.path.join(AVATAR_DIR, ".cache")

OVERLAY_WIDTH_RATIO = 0.28
OVERLAY_MARGIN_RATIO = 0.03
OVERLAY_BOTTOM_RATIO = 0.02

BREATHING_AMPLITUDE = 0.003
BREATHING_PERIOD = 3.0
BOB_AMPLITUDE = 1.5
BOB_PERIOD = 2.5


def ensure_directories():
    os.makedirs(AVATAR_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)


def get_available_avatars() -> List[str]:
    ensure_directories()
    if not os.path.exists(AVATAR_DIR):
        return []
    valid_exts = (".jpg", ".jpeg", ".png", ".webp")
    files = sorted([
        os.path.join(AVATAR_DIR, f)
        for f in os.listdir(AVATAR_DIR)
        if f.lower().endswith(valid_exts) and not f.startswith(".")
    ])
    return files


def get_today_avatar() -> Optional[str]:
    avatars = get_available_avatars()
    if not avatars:
        logger.warning("No avatar images found in data/avatars/")
        return None
    day_of_year = datetime.datetime.now().timetuple().tm_yday
    index = day_of_year % len(avatars)
    selected = avatars[index]
    logger.info(f"[Avatar] Day {day_of_year} -> index {index}: {os.path.basename(selected)}")
    return selected


def _get_audio_amplitude_envelope(
    audio_path: str,
    fps: int = 30,
    window_ms: int = 100,
) -> np.ndarray:
    try:
        audio = AudioFileClip(audio_path)
        sr = 22050
        duration = audio.duration
        samples = audio.to_soundarray(fps=sr, nbytes=2, quantize=True)
        if samples.ndim > 1:
            samples = samples.mean(axis=1)
        window_size = int(sr * window_ms / 1000)
        num_frames = int(duration * fps)
        envelope = np.zeros(num_frames)
        for i in range(num_frames):
            center = int(i / fps * sr)
            half = window_size // 2
            start = max(0, center - half)
            end = min(len(samples), center + half)
            if end > start:
                rms = np.sqrt(np.mean(samples[start:end] ** 2))
                envelope[i] = rms
        max_val = envelope.max()
        if max_val > 0:
            envelope = envelope / max_val
        envelope = gaussian_filter1d(envelope, sigma=1.5)
        audio.close()
        return envelope
    except Exception as e:
        logger.warning(f"[Avatar] Audio envelope failed: {e}")
        return np.ones(1) * 0.3


def _process_avatar_image(
    image_path: str,
    target_width: int,
    target_height: int,
):
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    overlay_w = int(target_width * OVERLAY_WIDTH_RATIO)
    aspect = h / w
    overlay_h = int(overlay_w * aspect)
    max_h = int(target_height * 0.45)
    if overlay_h > max_h:
        overlay_h = max_h
        overlay_w = int(overlay_h / aspect)
    img = img.resize((overlay_w, overlay_h), Image.LANCZOS)

    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.1)
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(1.05)

    overlay_w, overlay_h = img.size
    vignette = Image.new("RGB", (overlay_w, overlay_h), (0, 0, 0))
    cx, cy = overlay_w // 2, overlay_h // 2
    for x in range(overlay_w):
        dx = (x - cx) / cx
        for y in range(overlay_h):
            dy = (y - cy) / cy
            dist = math.sqrt(dx * dx + dy * dy)
            darken = max(0, 1 - dist * 0.15)
            r, g, b = img.getpixel((x, y))
            vignette.putpixel((x, y), (
                int(r * darken), int(g * darken), int(b * darken),
            ))
    return vignette


def create_position_fn(
    pos_x: int, pos_y: int, overlay_w: int, overlay_h: int,
) -> Callable[[float], tuple]:
    def pos_fn(t):
        bob_y = BOB_AMPLITUDE * math.sin(2 * math.pi * t / BOB_PERIOD)
        return (pos_x, pos_y + bob_y)
    return pos_fn


def create_avatar_overlay(
    avatar_image_path: str,
    audio_path: str,
    video_width: int,
    video_height: int,
    duration: float,
    fps: int = 30,
) -> Optional[VideoClip]:
    try:
        pil_img = _process_avatar_image(avatar_image_path, video_width, video_height)
    except Exception as e:
        logger.error(f"[Avatar] Failed to process image: {e}")
        return None

    overlay_w, overlay_h = pil_img.size
    img_array = np.array(pil_img)

    margin_x = int(video_width * OVERLAY_MARGIN_RATIO)
    margin_y = int(video_height * OVERLAY_BOTTOM_RATIO)
    pos_x = video_width - overlay_w - margin_x
    pos_y = video_height - overlay_h - margin_y

    envelope = _get_audio_amplitude_envelope(audio_path, fps)
    num_frames = len(envelope)

    def make_frame(t):
        frame_idx = min(int(t * fps), num_frames - 1)
        breath = 1.0 + BREATHING_AMPLITUDE * math.sin(2 * math.pi * t / BREATHING_PERIOD)
        cw = max(1, int(overlay_w * breath))
        ch = max(1, int(overlay_h * breath))
        from PIL import Image as PILImage
        frame_pil = PILImage.fromarray(img_array).resize((cw, ch), PILImage.LANCZOS)
        frame = np.array(frame_pil)
        # Ensure correct shape (H, W, 3)
        if frame.ndim == 2:
            frame = np.stack([frame] * 3, axis=-1)
        return frame

    clip = VideoClip(make_frame, duration=duration)
    clip = clip.with_position(create_position_fn(pos_x, pos_y, overlay_w, overlay_h))
    clip = clip.with_duration(duration)

    logger.info(
        f"[Avatar] Created overlay: {overlay_w}x{overlay_h} at ({pos_x}, {pos_y}), "
        f"duration={duration:.1f}s"
    )
    return clip


def composite_avatar_on_video(
    video_path: str,
    audio_path: str,
    output_path: str,
    avatar_image_path: Optional[str] = None,
) -> str:
    if avatar_image_path is None:
        avatar_image_path = get_today_avatar()
    if avatar_image_path is None:
        logger.warning("[Avatar] No avatar available, returning original video")
        return video_path

    video = VideoFileClip(video_path)
    duration = video.duration

    overlay = create_avatar_overlay(
        avatar_image_path=avatar_image_path,
        audio_path=audio_path,
        video_width=video.w,
        video_height=video.h,
        duration=duration,
    )

    if overlay is None:
        logger.warning("[Avatar] Overlay creation failed, returning original")
        video.close()
        return video_path

    final = CompositeVideoClip([video, overlay])
    final.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        fps=video.fps or 30,
        threads=2,
    )

    video.close()
    final.close()

    logger.success(f"[Avatar] Composited video saved: {output_path}")
    return output_path


def setup_avatars_guide():
    ensure_directories()
    print(f"""
Avatar Setup Guide
==================
1. Take 10+ photos of yourself sitting at a desk with upper body visible.
2. Use different outfits in each photo for daily rotation.
3. Good lighting is CRITICAL: face a window or use a ring light.
4. Keep background clean: plain wall, bookshelf, or your actual desk.
5. Save all photos to: {AVATAR_DIR}/
   (Supported: .jpg, .jpeg, .png, .webp)
6. The app auto-rotates through them daily.
""")


ensure_directories()
