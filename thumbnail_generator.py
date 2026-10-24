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


def create_short_thumbnail(
    chart_bg_path: Path,
    avatar_path: Path,
    headline_words: List[str],
    output_slug: str,
    punch_color: Optional[str] = None,
) -> Path:
    """
    Vertical 9:16 (1080x1920) YouTube Shorts shelf thumbnail:
      - Top half (1080x960): zoomed macro/footprint chart with a sentiment-coded
        indicator box (bright red/green border + translucent fill).
      - Bottom half (1080x960): rich dark studio backdrop with the avatar centered.
      - Massive centered 3-word text on a solid black badge with yellow/green border.
    Returns: short thumbnail path (output/images/{slug}_short.jpg)
    """
    logger.info(f"🎨 [High-CTR Shorts] generating 9:16 shelf thumb for: {output_slug}")
    punch = _sentiment_color(headline_words, punch_color)
    out_path = IMAGES_DIR / f"{output_slug}_short.jpg"

    W, H = 1080, 1920
    HALF = H // 2

    img = Image.new("RGB", (W, H), VIGNETTE_RGB).convert("RGBA")

    # ---- Top half: zoomed chart + sentiment-coded indicator box ----
    top = _chart_background((W, HALF), chart_bg_path, blur_radius=0.8, zoom=1.45, brightness=0.9)
    img.paste(top, (0, 0))
    overlay = Image.new("RGBA", (W, HALF), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.rounded_rectangle([(70, 210), (W - 70, 800)], radius=24,
                            outline=punch + (255,), width=8,
                            fill=punch + (56,))  # translucent sentiment fill
    odraw.rounded_rectangle([(84, 224), (W - 84, 786)], radius=18,
                            outline=(255, 255, 255, 90), width=3,
                            fill=(0, 0, 0, 0))
    img.alpha_composite(overlay)
    tdraw = ImageDraw.Draw(img)
    label = "LIVE MARKET STRUCTURE"
    f_lbl = _get_font(38)
    lw = tdraw.textlength(label, font=f_lbl)
    tdraw.text(((W - lw) // 2, 240), label, font=f_lbl, fill=WHITE, stroke_width=3, stroke_fill=BLACK)

    # ---- Bottom half: rich dark studio backdrop + centered avatar ----
    studio = Image.new("RGB", (W, HALF), VIGNETTE_RGB)
    s_draw = ImageDraw.Draw(studio)
    for y in range(HALF):
        t = y / HALF
        s_draw.line([(0, y), (W, y)], fill=(int(14 + 16 * (1 - t)), int(18 + 22 * (1 - t)), int(28 + 30 * (1 - t))))
    img.paste(studio, (0, HALF))
    img = _avatar_layer(img, avatar_path, target_h=880, right_x=W // 2 + 440, bottom_y=H - 40)

    # ---- Emerald seam divider ----
    ddraw = ImageDraw.Draw(img)
    ddraw.rectangle([(0, HALF - 4), (W, HALF + 4)], fill=NEON_GREEN)

    # ---- Massive banner text badge (solid black, yellow/green border) ----
    words = [w.strip().upper() for w in headline_words if w.strip()][:4] or ["MARKET", "STRUCTURE", "TRUTH"]
    badge_h = 430
    badge_y = HALF - badge_h // 2
    ddraw.rounded_rectangle([(48, badge_y), (W - 48, badge_y + badge_h)],
                            radius=28, fill=(5, 6, 10), outline=GOLD, width=8)
    inner = ImageDraw.Draw(img)
    f_big, lines = _fit_headline(inner, words, W - 190, badge_h - 110, start=150, floor=96)
    # vertically center the wrapped block inside the badge (mirrors renderer spacing)
    heights = [inner.textbbox((0, 0), ln, font=f_big)[3] - inner.textbbox((0, 0), ln, font=f_big)[1] for ln in lines]
    gap = 10 + f_big.size // 6
    total_h = sum(heights) + (len(lines) - 1) * gap
    start_y = badge_y + max(30, (badge_h - total_h) // 2)
    _punchy_shadow_text(img, inner, lines, f_big, 110 + 30, start_y, punch, punch_index=len(lines) - 1, line_gap=10)

    img.convert("RGB").save(out_path, "JPEG", quality=95)
    logger.success(f"✓ [High-CTR Shorts] saved: {out_path.name}")
    return out_path
