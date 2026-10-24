"""
Thumbnail & Discover Image Generator.
Composites high-CTR YouTube thumbnails (1280x720) and Google Discover marketing images (1200x675).
Uses PIL with institutional dark theme, vibrant typography, and studio avatar compositing.
"""

import os
from pathlib import Path
from typing import List, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from loguru import logger

BASE_DIR = Path(__file__).parent
THUMBS_DIR = BASE_DIR / "output" / "thumbnails"
THUMBS_DIR.mkdir(parents=True, exist_ok=True)


def _get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Attempts to find system sans-serif bold fonts, falling back to default."""
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/SFNSMono.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                continue
    return ImageFont.load_default()


def create_marketing_images(
    chart_bg_path: Path,
    avatar_path: Path,
    headline_words: List[str],
    output_slug: str
) -> Tuple[Path, Path]:
    """
    Creates high-CTR marketing graphics:
    1. YouTube Long-form / Shorts Thumbnail (1280x720)
    2. Google Discover / OpenGraph Image (1200x675)
    Returns: (yt_thumb_path, discover_img_path)
    """
    logger.info(f"🎨 Generating high-CTR marketing graphics for: {output_slug}")

    yt_thumb_path = THUMBS_DIR / f"{output_slug}_yt_thumb.jpg"
    discover_img_path = THUMBS_DIR / f"{output_slug}_discover.jpg"

    def _render_canvas(width: int, height: int, is_discover: bool = False) -> Image.Image:
        # Base canvas
        img = Image.new("RGB", (width, height), color=(11, 14, 20)) # #0B0E14

        # 1. Background Chart Layer
        if chart_bg_path and Path(chart_bg_path).exists():
            try:
                bg = Image.open(chart_bg_path).convert("RGB")
                bg = bg.resize((width, height), Image.Resampling.LANCZOS)
                # Darken chart for high text contrast
                enhancer = ImageEnhance.Brightness(bg)
                bg = enhancer.enhance(0.42)
                img.paste(bg, (0, 0))
            except Exception as e:
                logger.warning(f"Could not load chart background: {e}")

        draw = ImageDraw.Draw(img)

        # 2. Gradient overlay for text legibility
        for x in range(int(width * 0.7)):
            alpha = int(220 * (1 - (x / (width * 0.7))))
            draw.line([(x, 0), (x, height)], fill=(11, 14, 20), width=1)

        # 3. Avatar Layer (Right Side)
        if avatar_path and Path(avatar_path).exists():
            try:
                avatar = Image.open(avatar_path).convert("RGBA")
                # Scale avatar to fit nicely on the right
                target_h = int(height * 0.88)
                ratio = target_h / avatar.height
                target_w = int(avatar.width * ratio)
                avatar = avatar.resize((target_w, target_h), Image.Resampling.LANCZOS)
                
                # Position on bottom right
                paste_x = width - target_w + 30
                paste_y = height - target_h
                
                # Soft glow behind avatar
                glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                glow_draw = ImageDraw.Draw(glow)
                glow_draw.ellipse([paste_x - 40, paste_y - 20, width + 40, height + 40], fill=(16, 185, 129, 65))
                glow = glow.filter(ImageFilter.GaussianBlur(35))
                img.paste(glow, (0, 0), glow)
                
                # Paste avatar
                img.paste(avatar, (paste_x, paste_y), avatar)
            except Exception as e:
                logger.warning(f"Could not composite avatar: {e}")

        # 4. Regulatory / Educational Badge at Top Left
        font_badge = _get_font(18, bold=True)
        badge_text = "🛡️ SEBI COMPLIANT • 30-DAY HISTORICAL STUDY"
        draw.rounded_rectangle([40, 36, 480, 72], radius=8, fill=(22, 27, 34, 230), outline=(16, 185, 129), width=2)
        draw.text((54, 44), badge_text, font=font_badge, fill=(255, 255, 255))

        # 5. Bold High-Contrast Stacked Headline
        font_headline = _get_font(62 if width >= 1280 else 56, bold=True)
        start_y = 110
        colors = [(255, 255, 255), (250, 204, 21), (16, 185, 129)] # White, Gold, Mint

        clean_words = [w.strip().upper() for w in headline_words if w.strip()]
        if not clean_words:
            clean_words = ["INSTITUTIONAL", "DELTA", "TRAP"]

        for i, word in enumerate(clean_words[:3]):
            c = colors[i % len(colors)]
            text_y = start_y + (i * 84)
            # Contrast drop shadow
            draw.text((44, text_y + 4), word, font=font_headline, fill=(0, 0, 0))
            draw.text((40, text_y), word, font=font_headline, fill=c)

        # 6. Bottom Micro-Bar: The Bull Print / Flipzon Brand
        font_brand = _get_font(20, bold=True)
        brand_text = "THE BULL PRINT • EDUCATIONAL RESEARCH DOSSIER"
        draw.text((42, height - 52), brand_text, font=font_brand, fill=(148, 163, 184))

        return img

    # Render YouTube Thumbnail (1280x720)
    yt_img = _render_canvas(1280, 720, is_discover=False)
    yt_img.save(yt_thumb_path, format="JPEG", quality=95)

    # Render Discover Image (1200x675)
    disc_img = _render_canvas(1200, 675, is_discover=True)
    disc_img.save(discover_img_path, format="JPEG", quality=95)

    logger.success(f"✓ Created thumbnails: {yt_thumb_path.name}, {discover_img_path.name}")
    return yt_thumb_path, discover_img_path
