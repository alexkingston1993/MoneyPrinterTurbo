"""
Thumbnail & Discover Image Generator — High-CTR Multi-Layer Visual Compositor.
Engineered strictly according to ImageEditPro guidelines:
https://imageeditpro.in/blog/how-to-make-a-youtube-thumbnail-that-gets-more-clicks

Core Rules Implemented:
 1. The Title Test: NEVER repeat the 7-9 word video title. Strictly 2-4 punchy words + concrete number claim.
 2. 3-Layer Depth Composite:
    - Layer 1 (Calm Zone): Blurred (radius=14), darkened (brightness=0.35) background with directional gradient on left 58%.
    - Layer 2 (Foreground Focal Subject): Sharp right-third focal card (Split Comparison / Zoomed Chart Spike) + Studio Avatar with soft drop-shadow.
    - Layer 3 (Dynamic Hierarchy): Line 1 Setup in 76pt Bold White; Line 2 Power Word in 118pt Extra-Bold Accent (1.4x larger); Stat Badge below.
 3. Safe Zones: Bottom-right corner (x > 1050, y > 600) kept 100% free of text (YouTube duration badge safe).
 4. Persistent Shorts Hook Header: 1080x420 transparent overlay pinned across t=0 to end of 9:16 Shorts,
    guaranteeing that YouTube's mid-video frame samplers (15%, 50%, 85%) always capture a deliberate viral cover!
 5. Unsharp Mask: UnsharpMask(radius=1.5, percent=130, threshold=3) on final export. All outputs < 2MB.
"""

import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from loguru import logger

BASE_DIR = Path(__file__).parent
IMAGES_DIR = BASE_DIR / "output" / "images"
THUMBS_DIR = BASE_DIR / "output" / "thumbnails"
for _d in (IMAGES_DIR, THUMBS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# 3-Color Palette Standard (ImageEditPro)
BG_DARK = (7, 11, 20)             # Dominant dark tone #070B14
CARD_DARK = (15, 23, 42)          # Surface slate #0F172A
WHITE = (255, 255, 255)           # Primary setup text
ACCENT_YELLOW = (250, 204, 21)    # Electric Gold #FACC15
ACCENT_RED = (255, 59, 48)        # Alert Red #FF3B30
ACCENT_GREEN = (16, 185, 129)     # Emerald #10B981
MUTED_SLATE = (148, 163, 184)     # #94A3B8
BLACK = (0, 0, 0)

BEARISH_MARKERS = {
    "trap", "crash", "selling", "dump", "dumping", "lie", "fraud", "warning",
    "loss", "lose", "losing", "danger", "risk", "death", "dead", "over",
    "banned", "broken", "bleeding", "panic", "exposed", "trapped", "falling",
    "sinking", "collapse", "bubble", "fraud", "scam", "fail", "fails", "failed",
    "slashed", "vanished", "denied", "recked",
}


def _get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Finds the heaviest available sans-serif font for maximum mobile readability."""
    candidates = [
        BASE_DIR / "assets" / "fonts" / "Montserrat-Black.ttf",
        BASE_DIR / "assets" / "fonts" / "Inter-Bold.ttf",
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        Path("/System/Library/Fonts/Supplemental/Impact.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"),
        Path("/System/Library/Fonts/Helvetica.ttc"),
        Path("/Library/Fonts/Arial.ttf"),
    ]
    for c in candidates:
        if c.exists():
            try:
                return ImageFont.truetype(str(c), size)
            except Exception:
                continue
    return ImageFont.load_default()


def detect_sentiment(words: List[str]) -> str:
    """Classifies punchline keyword into warning/trap vs upside/alpha."""
    joined = " ".join(str(w).lower() for w in words)
    for w in BEARISH_MARKERS:
        if w in joined:
            return "bear"
    return "bull"


def _extract_hook_elements(
    headline_words: List[str],
    hook_data: Optional[Dict] = None,
    vertical: str = "stock_market",
) -> Dict:
    """Guarantees Line 1 Setup (1-2 words), Line 2 Power (1-2 words), and Stat Badge."""
    vert = (vertical or "stock_market").lower()
    if hook_data and isinstance(hook_data, dict):
        line1 = str(hook_data.get("line1_setup") or "").strip().upper()
        line2 = str(hook_data.get("line2_power") or "").strip().upper()
        badge = str(hook_data.get("badge") or hook_data.get("comparison_badge") or "")
        pair = hook_data.get("comparison_pair") or {}
        cat = str(hook_data.get("category_pill") or "")
        col = hook_data.get("accent_color")
        if line1 and line2:
            return {
                "line1": line1,
                "line2": line2,
                "badge": badge or (pair.get("badge") if isinstance(pair, dict) else ""),
                "pair": pair,
                "category": cat or ("🛡️ POLICY FORENSICS" if "insurance" in vert else ("⚡ ON-CHAIN ALPHA" if "crypto" in vert else "📈 ORDER FLOW")),
                "accent_rgb": ACCENT_RED if (col == "#FF3B30" or "insurance" in vert or detect_sentiment([line2]) == "bear") else ACCENT_YELLOW,
            }

    # Intelligent fallback from raw words / vertical
    raw = [re.sub(r"[^\w\$\₹\%\-\:\?]", "", str(w)).strip().upper() for w in headline_words if str(w).strip()]
    if "insurance" in vert:
        line1 = "HOSPITAL BILL"
        line2 = "50% SLASHED!"
        badge = "₹6L CLAIM ➔ ₹3L PAID"
        pair = {"left": "CLAIM: ₹6,00,000", "right": "PAID: ₹2,80,000 ❌", "badge": badge}
        cat = "🛡️ POLICY FORENSICS"
        accent_rgb = ACCENT_RED
    elif "crypto" in vert:
        line1 = "CRYPTO TAX"
        line2 = "30% TAX SHOCK"
        badge = "30% Flat + 1% TDS"
        pair = {"left": "PROFIT: ₹5L", "right": "LOSS: ₹0 OFFSET ❌", "badge": badge}
        cat = "⚡ ON-CHAIN FORENSICS"
        accent_rgb = ACCENT_YELLOW
    else:
        line1 = "NIFTY EXPIRY"
        line2 = "90% GET TRAPPED"
        badge = "93% Retail Trapped"
        pair = {"left": "RETAIL BUY", "right": "FII DUMP ❌", "badge": badge}
        cat = "📈 ORDER FLOW RADAR"
        accent_rgb = ACCENT_YELLOW

    if len(raw) >= 2:
        line1 = " ".join(raw[:2])
        line2 = " ".join(raw[2:4]) if len(raw) > 2 else raw[1]
        accent_rgb = ACCENT_RED if detect_sentiment([line2]) == "bear" else ACCENT_YELLOW

    return {
        "line1": line1,
        "line2": line2,
        "badge": badge,
        "pair": pair,
        "category": cat,
        "accent_rgb": accent_rgb,
    }


def _create_calm_zone_background(
    canvas_size: Tuple[int, int],
    chart_bg_path: Optional[Path],
    blur_radius: float = 14.0,
    brightness: float = 0.35,
) -> Image.Image:
    """
    Layer 1 (Calm Zone Depth Composite):
    Scales chart background, applies Gaussian blur (r=14) + darkening (0.35),
    then overlays a directional dark horizontal gradient across the left 58%
    so typography sits on a tranquil, high-contrast dark foundation.
    """
    w, h = canvas_size
    base = Image.new("RGBA", (w, h), BG_DARK + (255,))

    if chart_bg_path and Path(chart_bg_path).exists():
        try:
            bg = Image.open(chart_bg_path).convert("RGBA")
            scale = max(w / bg.width, h / bg.height) * 1.12
            bg = bg.resize((int(bg.width * scale), int(bg.height * scale)), Image.Resampling.LANCZOS)
            left = (bg.width - w) // 2
            top = (bg.height - h) // 2
            bg = bg.crop((left, top, left + w, top + h))

            if blur_radius > 0:
                bg = bg.filter(ImageFilter.GaussianBlur(blur_radius))

            # Darken to calm level
            dark = Image.new("RGBA", (w, h), BG_DARK + (255,))
            bg = Image.blend(dark, bg, max(0.10, min(0.60, brightness)))
            base.paste(bg, (0, 0))
        except Exception as e:
            logger.warning(f"[Thumbs] chart background blend note: {e}")

    # Directional dark gradient over left 58% (calm zone for text)
    calm_surf = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(calm_surf)
    calm_w = int(w * 0.62)
    for x in range(calm_w):
        # alpha from 245 at x=0 fading smoothly to 0 at calm_w
        ratio = x / float(calm_w)
        alpha = int(245 * ((1.0 - ratio) ** 1.6))
        cdraw.line([(x, 0), (x, h)], fill=(BG_DARK[0], BG_DARK[1], BG_DARK[2], alpha))

    # Radial vignette on extreme edges
    vig_mask = Image.new("L", (w, h), 0)
    vdraw = ImageDraw.Draw(vig_mask)
    cx, cy = w // 2, h // 2
    max_r = int(((w ** 2 + h ** 2) ** 0.5) / 2)
    for r in range(max_r, 0, -20):
        t = r / float(max_r)
        a = int(190 * (t ** 2.2))
        vdraw.ellipse([cx - int(r * 1.2), cy - r, cx + int(r * 1.2), cy + r], fill=a)

    base = Image.alpha_composite(base, calm_surf)
    vig_layer = Image.new("RGBA", (w, h), BG_DARK + (255,))
    base.paste(vig_layer, (0, 0), vig_mask)
    return base


def _render_split_comparison_card(
    draw: ImageDraw.ImageDraw,
    rect: Tuple[int, int, int, int],
    pair: Dict[str, str],
    accent_rgb: Tuple[int, int, int],
):
    """
    Renders a crisp Before/After or Split Comparison Card (e.g. CLAIM vs PAID ❌)
    with a thin crisp center divider and colored metric blocks.
    """
    x0, y0, x1, y1 = rect
    card_w = x1 - x0
    card_h = y1 - y0

    # Base container with rounded corners and subtle border
    draw.rounded_rectangle([x0, y0, x1, y1], radius=18, fill=(15, 23, 42, 240), outline=(51, 65, 85, 255), width=2)

    # Top header pill
    font_h = _get_font(22)
    header_title = "FORENSIC DISCREPANCY AUDIT"
    draw.text((x0 + 24, y0 + 16), header_title, font=font_h, fill=(148, 163, 184))

    # Split into Left and Right
    split_x = x0 + card_w // 2
    draw.line([(split_x, y0 + 52), (split_x, y1 - 20)], fill=(51, 65, 85, 220), width=2)

    left_label = str(pair.get("left") or "EXPECTED")
    right_label = str(pair.get("right") or "REALITY ❌")

    # Left Side: Slate/Green
    font_sub = _get_font(20)
    font_val = _get_font(26)
    draw.text((x0 + 24, y0 + 64), "ORIGINAL / CLAIM", font=font_sub, fill=(100, 116, 139))
    draw.text((x0 + 24, y0 + 98), left_label, font=font_val, fill=ACCENT_GREEN)

    # Right Side: Alert Red
    draw.text((split_x + 24, y0 + 64), "ACTUARIAL REALITY", font=font_sub, fill=(100, 116, 139))
    draw.text((split_x + 24, y0 + 98), right_label, font=font_val, fill=accent_rgb)

    # Bottom discrepancy callout
    badge_text = str(pair.get("badge") or "50% REDUCTION ENFORCED")
    font_badge = _get_font(22)
    draw.rounded_rectangle(
        [x0 + 20, y1 - 58, x1 - 20, y1 - 16],
        radius=10, fill=(30, 41, 59, 230), outline=accent_rgb, width=1,
    )
    draw.text((x0 + 36, y1 - 48), f"⚠️ {badge_text}", font=font_badge, fill=WHITE)


def _render_chart_spike_card(
    draw: ImageDraw.ImageDraw,
    rect: Tuple[int, int, int, int],
    accent_rgb: Tuple[int, int, int],
):
    """Fallback focal card showing simplified vector trend crash with bright alert circle."""
    x0, y0, x1, y1 = rect
    draw.rounded_rectangle([x0, y0, x1, y1], radius=18, fill=(15, 23, 42, 240), outline=(51, 65, 85, 255), width=2)

    font_h = _get_font(22)
    draw.text((x0 + 24, y0 + 16), "ORDER FLOW ABSORPTION POINT", font=font_h, fill=(148, 163, 184))

    # Simplified candlestick / vector curve
    mid_y = y0 + (y1 - y0) // 2
    points = [
        (x0 + 30, mid_y + 40),
        (x0 + 80, mid_y + 10),
        (x0 + 140, mid_y - 20),
        (x0 + 200, mid_y - 60),  # peak / trap
        (x0 + 260, mid_y + 20),
        (x0 + 320, mid_y + 80),  # crash
    ]
    for i in range(len(points) - 1):
        color = ACCENT_GREEN if i < 3 else accent_rgb
        draw.line([points[i], points[i + 1]], fill=color, width=4)

    # Focal Circle on the exact breakdown / trap point
    trap_pt = points[3]
    draw.ellipse([trap_pt[0] - 12, trap_pt[1] - 12, trap_pt[0] + 12, trap_pt[1] + 12], fill=accent_rgb, outline=WHITE, width=2)
    font_trap = _get_font(20)
    draw.text((trap_pt[0] - 40, trap_pt[1] - 38), "TRAP ZONE", font=font_trap, fill=accent_rgb)


def _composite_studio_avatar(
    img: Image.Image,
    avatar_path: Optional[Path],
    target_h: int,
    right_x: int,
    bottom_y: int,
) -> Image.Image:
    """Seamlessly composites studio presenter avatar with soft drop-shadow (no thick neon outlines)."""
    if not (avatar_path and Path(avatar_path).exists()):
        return img
    try:
        ava = Image.open(avatar_path).convert("RGBA")
        ratio = target_h / float(ava.height)
        new_w = int(ava.width * ratio)
        ava = ava.resize((new_w, target_h), Image.Resampling.LANCZOS)

        # Feather corners if rectangular
        try:
            alphas = ava.split()[3]
            corners = [(0, 0), (new_w - 1, 0), (0, target_h - 1), (new_w - 1, target_h - 1)]
            if all(alphas.getpixel(pt) > 180 for pt in corners):
                mask = Image.new("L", (new_w, target_h), 0)
                mdraw = ImageDraw.Draw(mask)
                mdraw.rounded_rectangle([(6, 6), (new_w - 6, target_h - 6)], radius=int(new_w * 0.08), fill=255)
                mask = mask.filter(ImageFilter.GaussianBlur(6))
                ava.putalpha(Image.composite(alphas, mask, mask.point(lambda a: min(a, 255))))
        except Exception:
            pass

        paste_x = right_x - new_w
        paste_y = bottom_y - target_h

        # Soft black drop shadow
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        smask = ava.split()[3].point(lambda a: int(a * 0.55))
        black_sil = Image.new("RGBA", ava.size, (0, 0, 0, 255))
        black_sil.putalpha(smask)
        shadow.paste(black_sil, (paste_x + 12, paste_y + 14), black_sil)
        shadow = shadow.filter(ImageFilter.GaussianBlur(12))

        img.alpha_composite(shadow)
        img.alpha_composite(ava, (paste_x, paste_y))
    except Exception as e:
        logger.warning(f"[Thumbs] avatar compositing note: {e}")
    return img


def create_marketing_images(
    chart_bg_path: Path,
    avatar_path: Path,
    headline_words: List[str],
    output_slug: str,
    punch_color: Optional[str] = None,
    hook_data: Optional[Dict] = None,
    vertical: str = "stock_market",
) -> Tuple[Path, Path]:
    """
    State-of-the-art 16:9 Long-Form YouTube Thumbnail (1280x720) & Google Discover (1200x675).
    ImageEditPro Benchmark:
      - Left 58% Calm Zone with dark directional gradient,
      - Line 1 in 76pt Bold White, Line 2 in 118pt Extra-Bold Accent (1.4x larger),
      - Split Comparison Card / Simplified Vector Chart on Right Third,
      - Bottom-right corner kept 100% free of text (YouTube duration badge safe),
      - Final unsharp mask for mobile screens (<2MB, JPEG quality=95).
    """
    logger.info(f"🎨 [ImageEditPro Engine] Rendering 16:9 Long-Form Thumbnail for: {output_slug}")
    hook = _extract_hook_elements(headline_words, hook_data, vertical)
    accent_rgb = hook["accent_rgb"]

    yt_thumb_path = IMAGES_DIR / f"{output_slug}_yt_thumb.jpg"
    discover_img_path = IMAGES_DIR / f"{output_slug}_discover.jpg"
    legacy_yt = THUMBS_DIR / f"{output_slug}_yt_thumb.jpg"
    legacy_disc = THUMBS_DIR / f"{output_slug}_discover.jpg"

    def _render_16_9(width: int, height: int) -> Image.Image:
        # 1. Background: Blurred + Darkened Calm Zone Composite
        img = _create_calm_zone_background((width, height), chart_bg_path, blur_radius=14.0, brightness=0.35)
        draw = ImageDraw.Draw(img)

        # 2. Right Third Focal Subject Zone (x=730 to 1220, y=110 to 520)
        # Leave bottom-right corner (x > 1050, y > 600) 100% free for timestamp!
        focal_rect = (int(width * 0.58), int(height * 0.16), int(width * 0.95), int(height * 0.68))
        if hook.get("pair") and isinstance(hook["pair"], dict) and hook["pair"].get("left"):
            _render_split_comparison_card(draw, focal_rect, hook["pair"], accent_rgb)
        else:
            _render_chart_spike_card(draw, focal_rect, accent_rgb)

        # Avatar cutout overlapping right side (anchored at right edge)
        img = _composite_studio_avatar(
            img, avatar_path,
            target_h=int(height * 0.82),
            right_x=int(width * 1.01),
            bottom_y=int(height * 1.02)
        )
        draw = ImageDraw.Draw(img)

        # 3. Left 58% Calm Zone Typography Hierarchy
        # Top Category Pill at (54, 48)
        font_pill = _get_font(24)
        cat_text = hook["category"]
        p_bbox = draw.textbbox((0, 0), cat_text, font=font_pill)
        pw = p_bbox[2] - p_bbox[0] + 28
        draw.rounded_rectangle([52, 44, 52 + pw, 44 + 42], radius=10, fill=(15, 23, 42, 230), outline=accent_rgb, width=2)
        draw.text((66, 52), cat_text, font=font_pill, fill=WHITE)

        # Line 1: Setup Word(s) in 76pt Bold White
        font_line1 = _get_font(76)
        line1_text = hook["line1"]
        # Crisp 3px dark stroke + drop shadow
        draw.text((54 + 4, 116 + 4), line1_text, font=font_line1, fill=BLACK)
        draw.text((54, 116), line1_text, font=font_line1, fill=WHITE, stroke_width=2, stroke_fill=BLACK)

        # Line 2: Power Word / Number in 118pt Extra-Bold Accent (1.4x larger!)
        font_line2 = _get_font(118)
        line2_text = hook["line2"]
        # 4px shadow + 3px stroke
        draw.text((54 + 6, 214 + 6), line2_text, font=font_line2, fill=BLACK)
        draw.text((54, 214), line2_text, font=font_line2, fill=accent_rgb, stroke_width=3, stroke_fill=BLACK)

        # Comparison / Stat Callout Pill below Line 2
        badge_text = hook["badge"]
        if badge_text:
            font_stat = _get_font(30)
            b_bbox = draw.textbbox((0, 0), badge_text, font=font_stat)
            bw = b_bbox[2] - b_bbox[0] + 36
            draw.rounded_rectangle([52, 366, 52 + bw, 366 + 54], radius=12, fill=(19, 29, 46, 240), outline=accent_rgb, width=2)
            draw.text((70, 376), badge_text, font=font_stat, fill=WHITE)

        # Brand micro-bar bottom-left (never near bottom-right)
        font_brand = _get_font(22)
        draw.text((54, height - 52), "THE BULL PRINT • INSTITUTIONAL FORENSICS", font=font_brand, fill=MUTED_SLATE)

        # 4. Final Mobile Sharpness: Unsharp Mask
        final_sharp = img.convert("RGB").filter(ImageFilter.UnsharpMask(radius=1.5, percent=130, threshold=3))
        return final_sharp

    yt_img = _render_16_9(1280, 720)
    yt_img.save(yt_thumb_path, "JPEG", quality=95)

    disc_img = _render_16_9(1200, 675)
    disc_img.save(discover_img_path, "JPEG", quality=95)

    shutil.copy2(yt_thumb_path, legacy_yt)
    shutil.copy2(discover_img_path, legacy_disc)

    logger.success(f"✓ [ImageEditPro 16:9] Thumbnails generated: {yt_thumb_path.name} (size: {os.path.getsize(yt_thumb_path)/1024:.1f} KB)")
    return yt_thumb_path, discover_img_path


def generate_persistent_short_header(
    headline: str,
    vertical: str,
    output_path: str,
    hook_data: Optional[Dict] = None,
) -> str:
    """
    Generates a 1080x420 transparent/gradient PNG overlay pinned at the top of 9:16 Shorts
    from t=0 to the very end of the video.
    Guarantees that YouTube's auto-frame sampler (sampling at 15%, 50%, 85%) captures
    a crystal-clear, deliberate viral cover on the Shorts grid!
    """
    width, height = 1080, 420
    words = str(headline or "").split()
    hook = _extract_hook_elements(words, hook_data, vertical)
    accent_rgb = hook["accent_rgb"]

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Vertical gradient: dark at top fading to transparent at y=420
    for y in range(height):
        ratio = y / float(height)
        alpha = int(235 * ((1.0 - ratio) ** 1.3))
        draw.line([(0, y), (width, y)], fill=(BG_DARK[0], BG_DARK[1], BG_DARK[2], alpha))

    # Top Category Pill at y=32
    font_pill = _get_font(28)
    cat_text = hook["category"]
    p_bbox = draw.textbbox((0, 0), cat_text, font=font_pill)
    pw = p_bbox[2] - p_bbox[0] + 32
    px = (width - pw) // 2
    draw.rounded_rectangle([px, 28, px + pw, 28 + 44], radius=10, fill=(15, 23, 42, 230), outline=accent_rgb, width=2)
    draw.text((px + 16, 36), cat_text, font=font_pill, fill=WHITE)

    # Line 1: Setup in 64pt Bold White at y=96
    font_l1 = _get_font(64)
    l1_text = hook["line1"]
    l1_bbox = draw.textbbox((0, 0), l1_text, font=font_l1)
    l1_x = (width - (l1_bbox[2] - l1_bbox[0])) // 2
    draw.text((l1_x + 3, 96 + 3), l1_text, font=font_l1, fill=BLACK)
    draw.text((l1_x, 96), l1_text, font=font_l1, fill=WHITE, stroke_width=2, stroke_fill=BLACK)

    # Line 2: Giant 104pt Power Word in Accent Color at y=176
    font_l2 = _get_font(104)
    l2_text = hook["line2"]
    l2_bbox = draw.textbbox((0, 0), l2_text, font=font_l2)
    l2_x = (width - (l2_bbox[2] - l2_bbox[0])) // 2
    draw.text((l2_x + 5, 176 + 5), l2_text, font=font_l2, fill=BLACK)
    draw.text((l2_x, 176), l2_text, font=font_l2, fill=accent_rgb, stroke_width=3, stroke_fill=BLACK)

    # Stat / Comparison Badge at y=312
    badge_text = hook["badge"]
    if badge_text:
        font_b = _get_font(30)
        b_bbox = draw.textbbox((0, 0), badge_text, font=font_b)
        bw = b_bbox[2] - b_bbox[0] + 36
        bx = (width - bw) // 2
        draw.rounded_rectangle([bx, 306, bx + bw, 306 + 52], radius=12, fill=(19, 29, 46, 240), outline=accent_rgb, width=2)
        draw.text((bx + 18, 316), badge_text, font=font_b, fill=WHITE)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "PNG")
    logger.info(f"🎨 [Persistent Shorts Hook Header] saved at {output_path}")
    return output_path


def generate_high_ctr_short_cover(
    headline: str,
    vertical: str,
    output_path: str,
    hook_data: Optional[Dict] = None,
    chart_bg_path: Optional[Path] = None,
    avatar_path: Optional[Path] = None,
) -> str:
    """
    Full 9:16 (1080x1920) YouTube Shorts Cover image.
    Used as the poster frame for t=0 to 1.2s.
    """
    width, height = 1080, 1920
    words = str(headline or "").split()
    hook = _extract_hook_elements(words, hook_data, vertical)
    accent_rgb = hook["accent_rgb"]

    # 1. Base Calm Zone 9:16 Composite
    img = _create_calm_zone_background((width, height), chart_bg_path, blur_radius=18.0, brightness=0.30)
    draw = ImageDraw.Draw(img)

    # 2. Top Hook Header Zone (y=80 to y=460)
    font_pill = _get_font(34)
    cat_text = hook["category"]
    p_bbox = draw.textbbox((0, 0), cat_text, font=font_pill)
    pw = p_bbox[2] - p_bbox[0] + 36
    px = (width - pw) // 2
    draw.rounded_rectangle([px, 90, px + pw, 90 + 56], radius=14, fill=(15, 23, 42, 230), outline=accent_rgb, width=2)
    draw.text((px + 18, 102), cat_text, font=font_pill, fill=WHITE)

    # Line 1: Setup in 78pt Bold White at y=175
    font_l1 = _get_font(78)
    l1_text = hook["line1"]
    l1_bbox = draw.textbbox((0, 0), l1_text, font=font_l1)
    l1_x = (width - (l1_bbox[2] - l1_bbox[0])) // 2
    draw.text((l1_x + 4, 175 + 4), l1_text, font=font_l1, fill=BLACK)
    draw.text((l1_x, 175), l1_text, font=font_l1, fill=WHITE, stroke_width=2, stroke_fill=BLACK)

    # Line 2: Giant 116pt Power Word in Accent Color at y=275
    font_l2 = _get_font(116)
    l2_text = hook["line2"]
    l2_bbox = draw.textbbox((0, 0), l2_text, font=font_l2)
    l2_x = (width - (l2_bbox[2] - l2_bbox[0])) // 2
    draw.text((l2_x + 6, 275 + 6), l2_text, font=font_l2, fill=BLACK)
    draw.text((l2_x, 275), l2_text, font=font_l2, fill=accent_rgb, stroke_width=3, stroke_fill=BLACK)

    # Stat / Comparison Badge at y=420
    badge_text = hook["badge"]
    if badge_text:
        font_b = _get_font(34)
        b_bbox = draw.textbbox((0, 0), badge_text, font=font_b)
        bw = b_bbox[2] - b_bbox[0] + 44
        bx = (width - bw) // 2
        draw.rounded_rectangle([bx, 412, bx + bw, 412 + 62], radius=14, fill=(19, 29, 46, 240), outline=accent_rgb, width=2)
        draw.text((bx + 22, 424), badge_text, font=font_b, fill=WHITE)

    # 3. Center Stage (y=530 to y=1180): Sharp Uncropped Comparison / Chart Card
    center_rect = (40, 530, width - 40, 1150)
    if hook.get("pair") and isinstance(hook["pair"], dict) and hook["pair"].get("left"):
        _render_split_comparison_card(draw, center_rect, hook["pair"], accent_rgb)
    else:
        _render_chart_spike_card(draw, center_rect, accent_rgb)

    # 4. Avatar on bottom right
    img = _composite_studio_avatar(
        img, avatar_path,
        target_h=int(height * 0.40),
        right_x=width - 20,
        bottom_y=height - 80
    )
    draw = ImageDraw.Draw(img)

    # 5. Bottom Brand & Callout
    font_sub = _get_font(30)
    draw.text((60, height - 120), "THE BULL PRINT • INSTITUTIONAL FORENSICS", font=font_sub, fill=MUTED_SLATE)

    # Mobile sharpness
    final_sharp = img.convert("RGB").filter(ImageFilter.UnsharpMask(radius=1.5, percent=130, threshold=3))
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    final_sharp.save(output_path, "JPEG", quality=95)
    logger.info(f"🎨 [High-CTR Shorts Cover] saved at {output_path}")
    return output_path


def create_short_thumbnail(
    chart_bg_path: Path,
    avatar_path: Path,
    headline_words: List[str],
    output_slug: str,
    punch_color: Optional[str] = None,
    hook_data: Optional[Dict] = None,
    vertical: str = "stock_market",
) -> Tuple[Path, Path]:
    """
    Renders BOTH:
      1. 1080x1920 Cover image (short_thumb_{slug}.jpg)
      2. 1080x420 Persistent Hook Header overlay (short_header_{slug}.png)
    Returns: (cover_path, header_path)
    """
    logger.info(f"🎨 [High-CTR Shorts Studio] Generating shelf cover & persistent header for: {output_slug}")
    cover_path = IMAGES_DIR / f"{output_slug}.jpg"
    header_path = IMAGES_DIR / f"{output_slug}_header.png"
    headline = " ".join(headline_words)

    generate_high_ctr_short_cover(
        headline=headline,
        vertical=vertical,
        output_path=str(cover_path),
        hook_data=hook_data,
        chart_bg_path=chart_bg_path,
        avatar_path=avatar_path,
    )

    generate_persistent_short_header(
        headline=headline,
        vertical=vertical,
        output_path=str(header_path),
        hook_data=hook_data,
    )

    # Legacy mirror copy
    legacy_cover = THUMBS_DIR / f"{output_slug}.jpg"
    legacy_header = THUMBS_DIR / f"{output_slug}_header.png"
    shutil.copy2(cover_path, legacy_cover)
    shutil.copy2(header_path, legacy_header)

    return cover_path, header_path
