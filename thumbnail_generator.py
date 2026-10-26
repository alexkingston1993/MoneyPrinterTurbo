"""
Thumbnail & Discover Image Generator — High-CTR Overhaul.
Deconstruction-based psychological formula from top-tier financial/tech channels:

 1. 3-4 massive punchy words (#1Most critical word color-coded: Neon Green #10B981
    upside / Bright Red #EF4444 trap-warning).
 2. Emotion+Object focal point: expressive studio avatar (right third) paired with
    a stark chart anchor, blurred + vignetted so text & face dominate.
 3. Dark vignette & edge isolation (#0B0E14, alpha 180 → edges pitch black).
 4. Mobile "thumb test": 96pt+ heavy sans-serif, thick black stroke + deep drop
    shadow.

Outputs (JPEG quality=95) → output/images/, with legacy mirror copies in
output/thumbnails/ so existing website/OG consumers keep working.
"""

import os
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from loguru import logger

BASE_DIR = Path(__file__).parent
IMAGES_DIR = BASE_DIR / "output" / "images"
THUMBS_DIR = BASE_DIR / "output" / "thumbnails"
for _d in (IMAGES_DIR, THUMBS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

VIGNETTE_RGB = (11, 14, 20)          # #0B0E14 dark charcoal
NEON_GREEN = (16, 185, 129)          # #10B981 upside
BRIGHT_RED = (239, 68, 68)           # #EF4444 warning/trap
GOLD = (245, 158, 11)                # #F59E0B urgency
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

BEARISH_MARKERS = {
    "trap", "crash", "selling", "dump", "dumping", "lie", "fraud", "warning",
    "loss", "lose", "losing", "danger", "risk", "death", "dead", "over",
    "banned", "broken", "bleeding", "panic", "exposed", "trapped", "falling",
    "sinking", "collapse", "bubble", "fraud", "scam", "fail", "fails", "failed",
}
BULLISH_MARKERS = {
    "winning", "wins", "wins", "profit", "profits", "gains", "rally", "safe",
    "smart", "edge", "secret", "coiled", "spring", "loaded", "gem",
    "breakout", "soaring", "green", "richest",
}


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    """Heavy bold display font: Inter if shipped in assets, else system sans-serif."""
    candidates = [
        BASE_DIR / "assets" / "fonts" / "Inter-Bold.ttf",
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        Path("/System/Library/Fonts/SFNSMono.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
    ]
    for c in candidates:
        if c.exists():
            try:
                return ImageFont.truetype(str(c), size)
            except Exception:
                continue
    return ImageFont.load_default()


def detect_sentiment(headline_words: List[str]) -> str:
    """bull / bear classification of the punchline keyword."""
    joined = " ".join(w.lower() for w in headline_words)
    for w in BEARISH_MARKERS:
        if w in joined:
            return "bear"
    for w in BULLISH_MARKERS:
        if w in joined:
            return "bull"
    return "bull"


def _sentiment_color(headline_words: List[str], override: Optional[str]) -> Tuple[int, int, int]:
    if override == "green":
        return NEON_GREEN
    if override == "red":
        return BRIGHT_RED
    if override == "gold":
        return GOLD
    return BRIGHT_RED if detect_sentiment(headline_words) == "bear" else NEON_GREEN


def _fit_headline(draw: ImageDraw.ImageDraw, words: List[str], max_width: int, max_height: int, start: int = 170, floor: int = 92):
    """Binary-search the largest font size where the wrapped 3-4 word block fits."""
    lo, hi, best = floor, start, floor
    best_lines = [" ".join(words)]
    best_font = _get_font(floor)
    while lo <= hi:
        mid = (lo + hi) // 2
        font = _get_font(mid)
        lines = _wrap_words(draw, words, font, max_width)
        total_h = sum(_line_h(draw, line, font) for line in lines)
        widest = max((draw.textlength(line, font=font) for line in lines), default=0)
        if total_h <= max_height and widest <= max_width:
            best, best_lines, best_font = mid, lines, font
            lo = mid + 1
        else:
            hi = mid - 1
    return best_font, best_lines


def _wrap_words(draw: ImageDraw.ImageDraw, words: List[str], font: ImageFont.FreeTypeFont, max_width: int, max_per_line: int = 2) -> List[str]:
    lines, cur = [], ""
    for w in words[:4]:
        trial = f"{cur} {w}".strip()
        if cur and (draw.textlength(trial, font=font) > max_width or len(cur.split()) >= max_per_line):
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines[:3]


def _line_h(draw: ImageDraw.ImageDraw, line: str, font: ImageFont.FreeTypeFont) -> int:
    bbox = draw.textbbox((0, 0), line, font=font)
    return bbox[3] - bbox[1]


def _punchy_shadow_text(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    lines: List[str],
    font: ImageFont.FreeTypeFont,
    x: int,
    y: int,
    punch_color: Tuple[int, int, int],
    punch_index: int,
    line_gap: int = 16,
) -> int:
    """Word-row renderer: soft blurred drop shadow + 5px black stroke + fill."""
    # 1. soft drop shadow layer (blurred black behind everything)
    shadow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow_layer)
    # 2. crisp main layer
    main_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    mdraw = ImageDraw.Draw(main_layer)

    cursor = y
    for i, line in enumerate(lines):
        color = punch_color if i == punch_index else WHITE
        # shadow pass
        sdraw.text((x + 10, cursor + 12), line, font=font, fill=(0, 0, 0, 200))
        # main pass with thick outline
        mdraw.text(
            (x, cursor), line, font=font, fill=color + (255,),
            stroke_width=5, stroke_fill=(0, 0, 0, 255),
        )
        bbox = mdraw.textbbox((0, 0), line, font=font)
        cursor += (bbox[3] - bbox[1]) + line_gap + font.size // 6

    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(9))
    img.alpha_composite(shadow_layer)
    img.alpha_composite(main_layer)
    return cursor


def _vignette(img: Image.Image, intensity: int = 180) -> Image.Image:
    """Radial vignette: edges pitch black, center preserved."""
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    cx, cy = w // 2, h // 2
    max_r = (max(w, h) ** 2 / 4) ** 0.5
    steps = 90
    for i in range(steps, 0, -1):
        r = max_r * i / steps
        t = i / steps
        alpha = int(intensity * (t ** 1.8))
        md.ellipse([cx - r * 1.25, cy - r, cx + r * 1.25, cy + r], fill=alpha)
    overlay = Image.new("RGB", (w, h), VIGNETTE_RGB)
    img.paste(overlay, (0, 0), mask)
    return img


def _chart_background(
    canvas_size: Tuple[int, int],
    chart_bg_path: Optional[Path],
    blur_radius: float = 1.5,
    zoom: float = 1.0,
    brightness: float = 0.75,
) -> Image.Image:
    """Chart layer: cover-crop, optional gaussian blur, blended toward dark charcoal."""
    w, h = canvas_size
    base = Image.new("RGB", (w, h), VIGNETTE_RGB)
    if chart_bg_path and Path(chart_bg_path).exists():
        try:
            bg = Image.open(chart_bg_path).convert("RGB")
            scale = max(w / bg.width, h / bg.height) * zoom
            bg = bg.resize((int(bg.width * scale), int(bg.height * scale)), Image.Resampling.LANCZOS)
            left = (bg.width - w) // 2
            top = (bg.height - h) // 2
            bg = bg.crop((left, top, left + w, top + h))
            base.paste(bg, (0, 0))
            if blur_radius > 0:
                base = base.filter(ImageFilter.GaussianBlur(blur_radius))
            dark = Image.new("RGB", (w, h), VIGNETTE_RGB)
            base = Image.blend(dark, base, max(0.05, min(1.0, brightness)))
        except Exception as e:
            logger.warning(f"[Thumbs] chart background failed: {e}")
    return base


def _avatar_layer(
    img: Image.Image,
    avatar_path: Optional[Path],
    target_h: int,
    right_x: int,
    bottom_y: int,
) -> Image.Image:
    """Avatar with soft edge-blend shadow so it pops off the dark background."""
    img = img.convert("RGBA")
    if not (avatar_path and Path(avatar_path).exists()):
        return img
    try:
        ava = Image.open(avatar_path).convert("RGBA")
        ratio = target_h / ava.height
        ava = ava.resize((int(ava.width * ratio), target_h), Image.Resampling.LANCZOS)

        # Opaque-corner avatars (flat rectangle assets) get rounded, feathered
        # edges so they blend into the dark studio background instead of showing
        # a hard rectangular block.
        try:
            alphas = ava.split()[3]
            opaque_corners = all(alphas.getpixel(pt) > 200 for pt in
                                 ((0, 0), (ava.width - 1, 0), (0, ava.height - 1), (ava.width - 1, ava.height - 1)))
            if opaque_corners:
                mask = Image.new("L", ava.size, 0)
                mdraw = ImageDraw.Draw(mask)
                mdraw.rounded_rectangle([(6, 6), (ava.width - 6, ava.height - 6)], radius=int(ava.width * 0.075), fill=255)
                mask = mask.filter(ImageFilter.GaussianBlur(4))
                ava.putalpha(Image.composite(alphas, mask, mask.point(lambda a: min(a, 255))))
        except Exception:
            pass

        paste_x = right_x - ava.width
        paste_y = bottom_y - ava.height

        # drop shadow: black silhouette of the avatar, blurred, offset
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        smask = ava.split()[3].point(lambda a: min(a, 140))
        black_ava = Image.new("RGBA", ava.size, (0, 0, 0, 255))
        black_ava.putalpha(smask)
        shadow.paste(black_ava, (paste_x + 14, paste_y + 18), black_ava)
        shadow = shadow.filter(ImageFilter.GaussianBlur(14))
        img.alpha_composite(shadow)

        # subtle emerald rim glow to separate from the vignette
        glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        gmask = ava.split()[3].point(lambda a: int(a * 0.35))
        rim = Image.new("RGBA", ava.size, (16, 185, 129, 255))
        rim.putalpha(gmask)
        rim = rim.filter(ImageFilter.GaussianBlur(6))
        glow.paste(rim, (paste_x, paste_y), rim)
        img.alpha_composite(glow)

        img.alpha_composite(ava, (paste_x, paste_y))
    except Exception as e:
        logger.warning(f"[Thumbs] avatar compositing failed: {e}")
    return img


def _badge(draw: ImageDraw.ImageDraw, text: str, xy: Tuple[int, int], outline: Tuple[int, int, int] = NEON_GREEN, pad: int = 14):
    font = _get_font(26)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x0, y0 = xy
    draw.rounded_rectangle(
        [(x0, y0), (x0 + tw + pad * 2 + 10, y0 + th + pad * 2)],
        radius=10, fill=(10, 12, 18, 235), outline=outline, width=3,
    )
    draw.text((x0 + pad + 5, y0 + pad - 2), text, font=font, fill=WHITE)


def create_marketing_images(
    chart_bg_path: Path,
    avatar_path: Path,
    headline_words: List[str],
    output_slug: str,
    punch_color: Optional[str] = None,
) -> Tuple[Path, Path]:
    """
    High-CTR marketing graphics overhaul:
      1. YouTube Long-Form thumbnail (1280x720) — blurred chart, radial vignette,
         avatar right third (620px), 3-4 word 96pt+ left-side stack with
         sentiment-coded punchline, 5px stroke + blurred shadow.
      2. Google Discover / OpenGraph image (1200x675) — same formula, scaled.
    Returns: (yt_thumb_path, discover_img_path)
    """
    logger.info(f"🎨 [High-CTR] generating marketing graphics for: {output_slug}")
    punch_color = _sentiment_color(headline_words, punch_color)

    yt_thumb_path = IMAGES_DIR / f"{output_slug}_yt_thumb.jpg"
    discover_img_path = IMAGES_DIR / f"{output_slug}_discover.jpg"
    legacy_yt = THUMBS_DIR / f"{output_slug}_yt_thumb.jpg"
    legacy_disc = THUMBS_DIR / f"{output_slug}_discover.jpg"

    def _render(width: int, height: int) -> Image.Image:
        # 1. Background: chart blurred + heavy radial vignette (#0B0E14, 180)
        base = _chart_background((width, height), chart_bg_path, blur_radius=1.5, brightness=0.66)
        # 2. Avatar on the right-hand third (~620px on 720p)
        img = _avatar_layer(base, avatar_path, target_h=int(height * 0.86), right_x=int(width * 1.02), bottom_y=int(height * 1.04))
        img = _vignette(img.convert("RGB"), intensity=180).convert("RGBA")
        draw = ImageDraw.Draw(img)

        # 3. Top-left compliance badge
        _badge(draw, "SEBI COMPLIANT • EDUCATIONAL ONLY", (36, 30), outline=NEON_GREEN)

        # 4. High-impact typography (left half), punchline = last word
        words = [w.strip().upper() for w in headline_words if w.strip()][:4] or ["MARKET", "STRUCTURE", "TRUTH"]
        usable_w = int(width * (0.60 if width >= 1280 else 0.58))
        usable_h = int(height * 0.66)
        font, lines = _fit_headline(draw, words, usable_w, usable_h, start=int(width * 0.132), floor=int(width * 0.072))
        text_x = int(width * 0.035)
        text_y = int(height * (0.16 if width >= 1280 else 0.20))
        _punchy_shadow_text(img, draw, lines, font, text_x, text_y, punch_color, punch_index=len(lines) - 1)

        # 5. Brand micro-bar bottom-left
        brand_font = _get_font(24)
        draw.text((text_x, height - int(height * 0.065)), "THE BULL PRINT", font=brand_font, fill=(200, 206, 215), stroke_width=2, stroke_fill=BLACK)

        return img

    yt_img = _render(1280, 720)
    yt_img.convert("RGB").save(yt_thumb_path, "JPEG", quality=95)
    yt_img.resize((1200, 675), Image.Resampling.LANCZOS).convert("RGB").save(discover_img_path, "JPEG", quality=95)

    # legacy mirror copies for existing OG/website consumers
    shutil.copy2(yt_thumb_path, legacy_yt)
    shutil.copy2(discover_img_path, legacy_disc)

    logger.success(f"✓ [High-CTR] thumbnails saved: {yt_thumb_path.name}, {discover_img_path.name}")
    return yt_thumb_path, discover_img_path


def generate_high_ctr_short_cover(headline: str, vertical: str, output_path: str) -> str:
    """Generates high-contrast 9:16 vertical cover for YouTube Shorts with massive readable typography,
    technical order flow grid lines, and glowing focal box."""
    from PIL import Image, ImageDraw, ImageFont
    import re

    width, height = 1080, 1920
    img = Image.new("RGB", (width, height), color="#090d16")
    draw = ImageDraw.Draw(img)

    vert = (vertical or "").lower()
    accent_color = "#10b981" if "stock" in vert else ("#06b6d4" if "crypto" in vert else "#f59e0b")
    glow_color = (16, 185, 129) if "stock" in vert else ((6, 182, 212) if "crypto" in vert else (245, 158, 11))

    # Radial gradient background
    center_y = 650
    for r in range(500, 0, -20):
        glow_box = [width // 2 - r, center_y - r, width // 2 + r, center_y + r]
        draw.ellipse(glow_box, fill=(glow_color[0] // 6, glow_color[1] // 6, glow_color[2] // 6))

    # Abstract order flow grid lines for technical depth
    for x in range(0, width, 120):
        draw.line([(x, 0), (x, height)], fill="#161f30", width=1)
    for y in range(0, height, 120):
        draw.line([(0, y), (width, y)], fill="#161f30", width=1)

    # Glowing focal box in upper-middle (safe from YouTube bottom overlay)
    box_rect = [70, 380, width - 70, 960]
    draw.rectangle(box_rect, fill="#0f172a", outline=accent_color, width=5)

    # Top indicator pill
    pill_label = "INSTITUTIONAL ALERT" if "stock" in vert else ("ON-CHAIN ALPHA" if "crypto" in vert else "POLICY AUDIT")
    font_pill = _get_font(34)
    draw.rectangle([100, 345, 460, 400], fill=accent_color)
    draw.text((115, 355), pill_label, fill="#000000", font=font_pill)

    # Render bold uppercase text (headline split into 3-4 words per line)
    font = _get_font(84)

    clean_headline = re.sub(r"#\S+", "", headline or "").strip().upper()
    clean_headline = re.sub(r"[^\w\s\$\₹\%\-\:\?]", "", clean_headline).strip()
    words = clean_headline.split()[:8] or ["THE", "BULL", "PRINT"]

    lines = []
    current_line = ""
    for w in words:
        if len(current_line + " " + w) < 16:
            current_line += (" " + w) if current_line else w
        else:
            lines.append(current_line)
            current_line = w
    if current_line:
        lines.append(current_line)

    lines = lines[:3]  # Max 3 massive lines
    line_h = 105
    total_text_h = len(lines) * line_h
    y_text = 430 + (500 - total_text_h) // 2

    for idx, line in enumerate(lines):
        # Drop shadow for max readability
        draw.text((120 + 4, y_text + 4), line, fill="#000000", font=font)
        # Highlight last line with accent/yellow
        text_fill = "#facc15" if idx == len(lines) - 1 else "#ffffff"
        draw.text((120, y_text), line, fill=text_fill, font=font)
        y_text += line_h

    # Add bottom brand badge
    font_brand = _get_font(36)
    draw.text((120, 1750), "THE BULL PRINT • INSTITUTIONAL ALPHA", fill=accent_color, font=font_brand)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, quality=95)
    logger.info(f"🎨 [High-CTR Shorts Cover] generated at {output_path}")
    return output_path


def create_short_thumbnail(
    chart_bg_path: Path,
    avatar_path: Path,
    headline_words: List[str],
    output_slug: str,
    punch_color: Optional[str] = None,
) -> Path:
    """
    Vertical 9:16 (1080x1920) YouTube Shorts high-CTR shelf cover.
    """
    logger.info(f"🎨 [High-CTR Shorts] generating 9:16 shelf thumb for: {output_slug}")
    out_path = IMAGES_DIR / f"{output_slug}_short.jpg"
    headline = " ".join(headline_words)
    generate_high_ctr_short_cover(headline, punch_color or "stock", str(out_path))

    # Also mirror to legacy THUMBS_DIR so existing consumers keep working
    legacy_path = THUMBS_DIR / f"{output_slug}_short.jpg"
    shutil.copy2(out_path, legacy_path)
    return out_path
