"""
Thumbnail & Discover Image Generator — 2-Stage Hybrid AI 3D Scene + Metallic Typography Compositor.
Engineered for The Bull Print according to ImageEditPro guidelines & 3D cinematic standards:

Stage 1 (AI 3D Cinematic Scene Backdrop):
  - Uses `gemini-flash-lite-latest` Art Director to turn title + vertical into a 3D prompt:
    * Insurance: Giant metallic cracked 3D shield with glowing red cross, stainless steel scissors slicing bill, embers, #070B14 grid.
    * Stock Market: Glowing golden/emerald cybernetic bull breaking out of a steel bear trap or cliff edge with candlestick lightning.
    * Crypto: Glowing 3D Bitcoin vault under laser tax audit beams, dramatic gold/crimson lightning, volumetric dark atmosphere.
    * Strict Rule: Clean composition zone on left for overlays, NO text inside raw 3D scene.
  - Fetches 1280x720 / 1080x1920 AI scene from Pollinations Flux API (`model=flux`, `nologo=true`) with instant fallback.

Stage 2 (Razor-Sharp 3D Metallic Typography & Red Warning Pill Overlay):
  - Directional dark calm-zone gradient over left 60% for extreme contrast.
  - Line 1 Setup: Vertical gold-to-amber metallic gradient (#FFFBEB -> #FACC15 -> #D97706) with deep 3D extruded black drop-shadow & ambient glow.
  - Line 2 Power: Crisp silver/white metallic gradient (#FFFFFF -> #CBD5E1) with deep 3D extruded black drop-shadow.
  - Bottom Warning Pill: Glowing red rounded pill badge with neon red border and bold white text.
  - Bottom-right corner kept 100% text-free (YouTube duration badge safe).
  - UnsharpMask filter on final export (< 2MB JPEG).
"""

import os
import re
import io
import json
import shutil
import tomllib
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from loguru import logger

BASE_DIR = Path(__file__).resolve().parent
IMAGES_DIR = BASE_DIR / "output" / "images"
THUMBS_DIR = BASE_DIR / "output" / "thumbnails"
for _d in (IMAGES_DIR, THUMBS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Color Palette Standards
BG_DARK = (7, 11, 20)             # Dominant dark tone #070B14
CARD_DARK = (15, 23, 42)          # Surface slate #0F172A
WHITE = (255, 255, 255)
ACCENT_YELLOW = (250, 204, 21)    # Electric Gold #FACC15
ACCENT_RED = (255, 59, 48)        # Alert Red #FF3B30
ACCENT_GREEN = (16, 185, 129)     # Emerald #10B981
MUTED_SLATE = (148, 163, 184)     # #94A3B8
BLACK = (0, 0, 0)

# Metallic Gradients (Top, Mid, Bot)
GOLD_METALLIC = ((255, 251, 235), (250, 204, 21), (217, 119, 6))      # #FFFBEB -> #FACC15 -> #D97706
SILVER_METALLIC = ((255, 255, 255), (226, 232, 240), (148, 163, 184)) # #FFFFFF -> #E2E8F0 -> #94A3B8
RED_METALLIC = ((255, 230, 230), (255, 59, 48), (180, 15, 25))


def get_gemini_api_key() -> str:
    """Retrieves GEMINI_API_KEY from config.toml or environment."""
    key = os.getenv("GEMINI_API_KEY", "")
    if key:
        return key
    cfg_path = BASE_DIR / "config.toml"
    if cfg_path.exists():
        try:
            with open(cfg_path, "rb") as f:
                cfg = tomllib.load(f)
                return cfg.get("app", {}).get("gemini_api_key", "")
        except Exception:
            pass
    return ""


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


def create_vertical_gradient(width: int, height: int, top_color: Tuple[int, int, int], mid_color: Tuple[int, int, int], bot_color: Tuple[int, int, int]) -> Image.Image:
    """Creates a smooth 3-stop vertical gradient image."""
    grad = Image.new("RGBA", (max(1, width), max(1, height)))
    draw = ImageDraw.Draw(grad)
    half = height // 2
    for y in range(height):
        if y < half:
            t = y / max(1, half)
            r = int(top_color[0] + t * (mid_color[0] - top_color[0]))
            g = int(top_color[1] + t * (mid_color[1] - top_color[1]))
            b = int(top_color[2] + t * (mid_color[2] - top_color[2]))
        else:
            t = (y - half) / max(1, (height - half))
            r = int(mid_color[0] + t * (bot_color[0] - mid_color[0]))
            g = int(mid_color[1] + t * (bot_color[1] - mid_color[1]))
            b = int(mid_color[2] + t * (bot_color[2] - mid_color[2]))
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))
    return grad


def render_3d_extruded_gradient_text(
    base_img: Image.Image,
    xy: Tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    gradient_colors: Tuple[Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int]],
    extrusion_depth: int = 8,
    stroke_color: Tuple[int, int, int, int] = (0, 0, 0, 255),
    glow_color: Tuple[int, int, int, int] = (250, 204, 21, 140)
) -> int:
    """
    Renders 3D extruded metallic gradient text:
    1. Outer ambient glow layer.
    2. Deep 3D extruded shadow (diagonal step-down).
    3. Sharp metallic vertical gradient face with dark outline stroke.
    """
    x, y = xy
    draw_test = ImageDraw.Draw(base_img)
    bbox = draw_test.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0] + 50
    th = bbox[3] - bbox[1] + 50
    pad = 25

    # 1. Ambient Glow
    glow_img = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(glow_img)
    g_draw.text((pad, pad), text, font=font, fill=glow_color)
    glow_blurred = glow_img.filter(ImageFilter.GaussianBlur(12))
    base_img.alpha_composite(glow_blurred, (x - pad, y - pad))

    # 2. 3D Extrusion Shadow
    for d in range(extrusion_depth, 0, -1):
        ext_img = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        e_draw = ImageDraw.Draw(ext_img)
        e_draw.text((pad, pad), text, font=font, fill=(0, 0, 0, 240))
        base_img.alpha_composite(ext_img, (x + d - pad, y + d - pad))

    # 3. Metallic Gradient Face
    grad_img = create_vertical_gradient(tw, th, gradient_colors[0], gradient_colors[1], gradient_colors[2])
    mask = Image.new("L", (tw, th), 0)
    m_draw = ImageDraw.Draw(mask)
    m_draw.text((pad, pad), text, font=font, fill=255)

    face_layer = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    f_draw = ImageDraw.Draw(face_layer)
    f_draw.text((pad, pad), text, font=font, fill=stroke_color, stroke_width=3, stroke_fill=stroke_color)
    face_layer.paste(grad_img, (0, 0), mask)

    base_img.alpha_composite(face_layer, (x - pad, y - pad))
    return th


def get_ai_art_direction(title: str, vertical: str = "stock_market") -> Dict[str, str]:
    """
    Stage 1 Art Director:
    Uses `gemini-flash-lite-latest` to read any title and return:
    - line1: 1-2 words setup hook
    - line2: 1-2 words power punch
    - pill_badge: 2-4 words warning badge
    - category: 1-3 words category badge
    - scene_prompt: 3D octane render prompt for Pollinations Flux (NO text in background).
    """
    vert = (vertical or "stock_market").lower()
    key = get_gemini_api_key()
    
    if key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=key, transport="rest")
            model = genai.GenerativeModel("gemini-flash-lite-latest")
            
            prompt = f"""You are the Art Director for a premium finance channel called 'The Bull Print'.
Video Title: "{title}"
Vertical: "{vert}"

Task: Convert this title into:
1. "line1": 1 to 2 words setup hook in uppercase (e.g. "CLAIM CUTS", "NIFTY 50", "CRYPTO TAX", "HDFC BANK")
2. "line2": 1 to 2 words power punch in uppercase (e.g. "EXPOSED!", "TRAP EXPOSED!", "30% SHOCK!", "BREAKOUT?")
3. "pill_badge": 2 to 4 words warning pill in uppercase (e.g. "ROOM RENT CAPS!", "LIQUIDITY TRAP 22,400", "SECTION 115BBH")
4. "category": 1 to 3 words category label without emojis (e.g. "POLICY FORENSICS", "ORDER FLOW RADAR", "ON-CHAIN FORENSICS")
5. "scene_prompt": A photorealistic 3D octane render prompt for a 16:9 cinematic background matching the vertical:
   - For insurance: giant metallic cracked 3D shield with glowing red medical cross, stainless steel scissors slicing a hospital bill, volumetric embers, dark telemetry grid #070B14
   - For stock market: glowing golden/emerald cybernetic bull breaking out of a steel bear trap or standing at a dramatic cliff edge with glowing red/green candlestick lightning bolts, dark order-flow depth matrix
   - For crypto: glowing 3D Bitcoin/blockchain vault under laser tax audit beams, dramatic red/gold lightning and volumetric dark studio atmosphere
   STRICT RULE: The scene_prompt must specify NO text, NO typography, clean dark composition zone on left for overlays, dark background #070B14.

Return ONLY a valid JSON object with keys "line1", "line2", "pill_badge", "category", "scene_prompt".
"""
            resp = model.generate_content(prompt)
            txt = resp.text.strip()
            txt = re.sub(r"^```(?:json)?\s*", "", txt, flags=re.MULTILINE)
            txt = re.sub(r"\s*```$", "", txt, flags=re.MULTILINE).strip()
            data = json.loads(txt)
            if data.get("line1") and data.get("line2") and data.get("scene_prompt"):
                return data
        except Exception as e:
            logger.warning(f"[Thumbs] Gemini Art Director error, using intelligent fallback: {e}")

    # High quality fallback tailored to title & vertical
    t_lower = title.lower()
    if "insurance" in vert or "claim" in t_lower or "room rent" in t_lower or "irdai" in t_lower:
        return {
            "line1": "CLAIM CUTS",
            "line2": "EXPOSED!",
            "pill_badge": "ROOM RENT CAPS!",
            "category": "POLICY FORENSICS",
            "scene_prompt": "photorealistic 3D octane render, giant metallic cracked shield with glowing red cross, stainless steel scissors slicing a hospital invoice, volumetric embers, dark cinematic lighting, clean composition on left side, dark background #070B14, 8k, no text"
        }
    elif "crypto" in vert or "funding rate" in t_lower or "tax" in t_lower or "bitcoin" in t_lower or "115bbh" in t_lower:
        return {
            "line1": "CRYPTO TAX",
            "line2": "30% SHOCK!",
            "pill_badge": "SECTION 115BBH!",
            "category": "ON-CHAIN FORENSICS",
            "scene_prompt": "photorealistic 3D octane render, glowing 3D Bitcoin vault under red laser audit beams, dramatic gold and crimson lightning, volumetric dark studio atmosphere, clean left side composition zone, dark background #070B14, 8k, no text"
        }
    else:
        return {
            "line1": "NIFTY 50",
            "line2": "TRAP EXPOSED!",
            "pill_badge": "LIQUIDITY TRAP 22,400",
            "category": "ORDER FLOW RADAR",
            "scene_prompt": "photorealistic 3D octane render, glowing golden cybernetic bull breaking out of a steel bear trap, dramatic cliff edge, glowing candlestick lightning bolts, dark order-flow depth matrix, dark cinematic lighting, clean left side composition zone, dark background #070B14, 8k, no text"
        }


def generate_ai_scene_backdrop(
    scene_prompt: str,
    width: int = 1280,
    height: int = 720,
    seed: int = 42,
) -> Image.Image:
    """
    Fetches the 1280x720 / 1080x1920 3D scene from Pollinations Flux API.
    Fast, reliable failover ensures zero downtime.
    """
    candidates = [
        f"https://image.pollinations.ai/prompt/{urllib.parse.quote(scene_prompt)}?width={width}&height={height}&model=flux&nologo=true&seed={seed}",
        f"https://image.pollinations.ai/prompt/{urllib.parse.quote(scene_prompt[:120])}?width={width}&height={height}&nologo=true&seed={seed}",
    ]
    for url in candidates:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = resp.read()
                if len(data) > 5000:
                    ai_img = Image.open(io.BytesIO(data)).convert("RGBA")
                    if ai_img.size != (width, height):
                        ai_img = ai_img.resize((width, height), Image.Resampling.LANCZOS)
                    return ai_img
        except Exception as e:
            logger.warning(f"[Thumbs] Candidate URL attempt note ({url[:60]}...): {e}")

    # High quality procedural dark telemetry background
    canvas = Image.new("RGBA", (width, height), BG_DARK + (255,))
    cdraw = ImageDraw.Draw(canvas)
    for x in range(0, width, 60):
        cdraw.line([(x, 0), (x, height)], fill=(15, 23, 42, 60), width=1)
    for y in range(0, height, 60):
        cdraw.line([(0, y), (width, y)], fill=(15, 23, 42, 60), width=1)
    return canvas


def apply_calm_zone_gradient(img: Image.Image, width: int, height: int, calm_ratio: float = 0.65) -> Image.Image:
    """
    Overlays directional dark gradient over the left zone so that
    typography has unmatched readability while the 3D subject shines on the right.
    """
    calm = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(calm)
    calm_w = int(width * calm_ratio)
    for x in range(calm_w):
        ratio = x / float(calm_w)
        alpha = int(245 * ((1.0 - ratio) ** 1.5))
        cdraw.line([(x, 0), (x, height)], fill=(BG_DARK[0], BG_DARK[1], BG_DARK[2], alpha))

    # Mask out bottom-right corner for YouTube duration badge
    cdraw.rectangle([int(width * 0.82), int(height * 0.82), width, height], fill=(BG_DARK[0], BG_DARK[1], BG_DARK[2], 160))
    return Image.alpha_composite(img, calm)


def composite_3d_metallic_branding(
    base_img: Image.Image,
    art: Dict[str, str],
    width: int = 1280,
    height: int = 720,
    is_short: bool = False,
) -> Image.Image:
    """
    Composites 3D metallic typography, Glowing Red Warning Pill, Category badge,
    and institutional branding onto the 3D scene.
    """
    img = base_img.copy()

    if not is_short:
        # 16:9 Long-Form Layout
        font_cat = _get_font(24)
        font_l1 = _get_font(84)
        font_l2 = _get_font(120)
        font_pill = _get_font(32)
        font_brand = _get_font(22)

        draw = ImageDraw.Draw(img)

        # 1. Category Tag Pill
        cat_text = art.get("category", "INSTITUTIONAL FORENSICS").upper()
        c_bbox = draw.textbbox((0, 0), cat_text, font=font_cat)
        cw = c_bbox[2] - c_bbox[0] + 36
        draw.rounded_rectangle([70, 48, 70 + cw, 48 + 42], radius=10, fill=(15, 23, 42, 230), outline=ACCENT_RED, width=2)
        draw.text((88, 56), cat_text, font=font_cat, fill=WHITE)

        # 2. Line 1: Gold 3D Extruded Metallic Text
        render_3d_extruded_gradient_text(
            img, (70, 114), art.get("line1", "NIFTY 50"),
            font_l1, GOLD_METALLIC, extrusion_depth=7,
            glow_color=(250, 204, 21, 150)
        )

        # 3. Line 2: Silver/White 3D Extruded Metallic Text
        render_3d_extruded_gradient_text(
            img, (70, 224), art.get("line2", "TRAP EXPOSED!"),
            font_l2, SILVER_METALLIC, extrusion_depth=8,
            glow_color=(255, 255, 255, 140)
        )

        # 4. Glowing Red Warning Pill Badge
        pill_text = art.get("pill_badge", "LIQUIDITY TRAP!").upper()
        p_bbox = draw.textbbox((0, 0), pill_text, font=font_pill)
        pw = p_bbox[2] - p_bbox[0] + 50
        ph = p_bbox[3] - p_bbox[1] + 28
        px, py = 70, 396

        pill_glow = Image.new("RGBA", (pw + 40, ph + 40), (0, 0, 0, 0))
        pg_draw = ImageDraw.Draw(pill_glow)
        pg_draw.rounded_rectangle([20, 20, 20 + pw, 20 + ph], radius=16, fill=(255, 40, 40, 130))
        pill_glow = pill_glow.filter(ImageFilter.GaussianBlur(14))
        img.alpha_composite(pill_glow, (px - 20, py - 20))

        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([px, py, px + pw, py + ph], radius=16, fill=(180, 15, 25, 245), outline=(255, 80, 80, 255), width=3)
        draw.text((px + 25, py + 12), pill_text, font=font_pill, fill=WHITE)

        # 5. Bottom Brand Watermark
        draw.text((70, height - 52), "THE BULL PRINT • INSTITUTIONAL FORENSICS", font=font_brand, fill=MUTED_SLATE)

    else:
        # 9:16 Shorts Cover Layout
        font_cat = _get_font(30)
        font_l1 = _get_font(90)
        font_l2 = _get_font(126)
        font_pill = _get_font(38)
        font_brand = _get_font(28)

        draw = ImageDraw.Draw(img)

        # Category Tag Pill (centered)
        cat_text = art.get("category", "INSTITUTIONAL FORENSICS").upper()
        c_bbox = draw.textbbox((0, 0), cat_text, font=font_cat)
        cw = c_bbox[2] - c_bbox[0] + 44
        cx = (width - cw) // 2
        draw.rounded_rectangle([cx, 90, cx + cw, 90 + 52], radius=12, fill=(15, 23, 42, 230), outline=ACCENT_RED, width=2)
        draw.text((cx + 22, 102), cat_text, font=font_cat, fill=WHITE)

        # Line 1 (centered)
        l1_text = art.get("line1", "NIFTY 50")
        l1_bbox = draw.textbbox((0, 0), l1_text, font=font_l1)
        l1_x = (width - (l1_bbox[2] - l1_bbox[0])) // 2
        render_3d_extruded_gradient_text(
            img, (l1_x, 180), l1_text,
            font_l1, GOLD_METALLIC, extrusion_depth=8,
            glow_color=(250, 204, 21, 150)
        )

        # Line 2 (centered)
        l2_text = art.get("line2", "TRAP EXPOSED!")
        l2_bbox = draw.textbbox((0, 0), l2_text, font=font_l2)
        l2_x = (width - (l2_bbox[2] - l2_bbox[0])) // 2
        render_3d_extruded_gradient_text(
            img, (l2_x, 300), l2_text,
            font_l2, SILVER_METALLIC, extrusion_depth=9,
            glow_color=(255, 255, 255, 140)
        )

        # Red Warning Pill (centered)
        pill_text = art.get("pill_badge", "LIQUIDITY TRAP!").upper()
        p_bbox = draw.textbbox((0, 0), pill_text, font=font_pill)
        pw = p_bbox[2] - p_bbox[0] + 60
        ph = p_bbox[3] - p_bbox[1] + 34
        px = (width - pw) // 2
        py = 480

        pill_glow = Image.new("RGBA", (pw + 40, ph + 40), (0, 0, 0, 0))
        pg_draw = ImageDraw.Draw(pill_glow)
        pg_draw.rounded_rectangle([20, 20, 20 + pw, 20 + ph], radius=18, fill=(255, 40, 40, 130))
        pill_glow = pill_glow.filter(ImageFilter.GaussianBlur(16))
        img.alpha_composite(pill_glow, (px - 20, py - 20))

        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([px, py, px + pw, py + ph], radius=18, fill=(180, 15, 25, 245), outline=(255, 80, 80, 255), width=3)
        draw.text((px + 30, py + 14), pill_text, font=font_pill, fill=WHITE)

        # Bottom Brand
        draw.text((60, height - 120), "THE BULL PRINT • INSTITUTIONAL FORENSICS", font=font_brand, fill=MUTED_SLATE)

    # Final Mobile Sharpness: Unsharp Mask
    final_img = img.convert("RGB").filter(ImageFilter.UnsharpMask(radius=1.5, percent=130, threshold=3))
    return final_img


def create_marketing_images(
    chart_bg_path: Path,
    avatar_path: Path,
    headline_words: List[str],
    output_slug: str,
    punch_color: Optional[str] = None,
    hook_data: Optional[Dict] = None,
    vertical: str = "stock_market",
    video_title: Optional[str] = None,
) -> Tuple[Path, Path]:
    """
    2-Stage Hybrid AI 3D Scene + Metallic Typography Compositor.
    Generates:
      1. YouTube 16:9 Thumbnail (1280x720, < 2MB JPEG)
      2. Google Discover Image (1200x675, < 2MB JPEG)
    """
    logger.info(f"🎨 [Hybrid 3D Engine] Rendering 16:9 Thumbnail for: {output_slug}")
    title = video_title or " ".join(headline_words)
    art = get_ai_art_direction(title, vertical)

    # Override with explicit hook_data if provided
    if hook_data and isinstance(hook_data, dict):
        if hook_data.get("line1_setup"):
            art["line1"] = str(hook_data["line1_setup"]).upper()
        if hook_data.get("line2_power"):
            art["line2"] = str(hook_data["line2_power"]).upper()
        if hook_data.get("badge") or hook_data.get("comparison_badge"):
            art["pill_badge"] = str(hook_data.get("badge") or hook_data.get("comparison_badge")).upper()

    yt_thumb_path = IMAGES_DIR / f"{output_slug}_yt_thumb.jpg"
    discover_img_path = IMAGES_DIR / f"{output_slug}_discover.jpg"
    legacy_yt = THUMBS_DIR / f"{output_slug}_yt_thumb.jpg"
    legacy_disc = THUMBS_DIR / f"{output_slug}_discover.jpg"

    def _render(w: int, h: int) -> Image.Image:
        # Stage 1: AI 3D scene backdrop
        seed = abs(hash(output_slug)) % 100000 + 42
        raw_bg = generate_ai_scene_backdrop(art["scene_prompt"], width=w, height=h, seed=seed)
        # Apply directional left calm-zone gradient
        bg = apply_calm_zone_gradient(raw_bg, width=w, height=h, calm_ratio=0.62)
        # Stage 2: 3D Metallic typography & red warning pill
        final_img = composite_3d_metallic_branding(bg, art, width=w, height=h, is_short=False)
        return final_img

    yt_img = _render(1280, 720)
    yt_img.save(yt_thumb_path, "JPEG", quality=95)

    disc_img = _render(1200, 675)
    disc_img.save(discover_img_path, "JPEG", quality=95)

    shutil.copy2(yt_thumb_path, legacy_yt)
    shutil.copy2(discover_img_path, legacy_disc)

    logger.success(f"✓ [Hybrid 3D 16:9] Thumbnails created: {yt_thumb_path.name} ({os.path.getsize(yt_thumb_path)/1024:.1f} KB)")
    return yt_thumb_path, discover_img_path


def generate_persistent_short_header(
    headline: str,
    vertical: str,
    output_path: str,
    hook_data: Optional[Dict] = None,
) -> str:
    """
    Generates a 1080x420 transparent overlay pinned at the top of 9:16 Shorts from t=0 to end.
    """
    width, height = 1080, 420
    art = get_ai_art_direction(headline, vertical)
    if hook_data and isinstance(hook_data, dict):
        if hook_data.get("line1_setup"):
            art["line1"] = str(hook_data["line1_setup"]).upper()
        if hook_data.get("line2_power"):
            art["line2"] = str(hook_data["line2_power"]).upper()
        if hook_data.get("badge"):
            art["pill_badge"] = str(hook_data["badge"]).upper()

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    for y in range(height):
        ratio = y / float(height)
        alpha = int(240 * ((1.0 - ratio) ** 1.3))
        draw.line([(0, y), (width, y)], fill=(BG_DARK[0], BG_DARK[1], BG_DARK[2], alpha))

    # Category Pill
    font_cat = _get_font(26)
    cat_text = art.get("category", "INSTITUTIONAL FORENSICS").upper()
    c_bbox = draw.textbbox((0, 0), cat_text, font=font_cat)
    cw = c_bbox[2] - c_bbox[0] + 36
    cx = (width - cw) // 2
    draw.rounded_rectangle([cx, 28, cx + cw, 28 + 44], radius=10, fill=(15, 23, 42, 230), outline=ACCENT_RED, width=2)
    draw.text((cx + 18, 36), cat_text, font=font_cat, fill=WHITE)

    # Line 1
    font_l1 = _get_font(64)
    l1_text = art.get("line1", "NIFTY 50")
    l1_bbox = draw.textbbox((0, 0), l1_text, font=font_l1)
    l1_x = (width - (l1_bbox[2] - l1_bbox[0])) // 2
    render_3d_extruded_gradient_text(img, (l1_x, 96), l1_text, font_l1, GOLD_METALLIC, extrusion_depth=6)

    # Line 2
    font_l2 = _get_font(98)
    l2_text = art.get("line2", "TRAP EXPOSED!")
    l2_bbox = draw.textbbox((0, 0), l2_text, font=font_l2)
    l2_x = (width - (l2_bbox[2] - l2_bbox[0])) // 2
    render_3d_extruded_gradient_text(img, (l2_x, 176), l2_text, font_l2, SILVER_METALLIC, extrusion_depth=7)

    # Warning Pill
    pill_text = art.get("pill_badge", "LIQUIDITY TRAP!").upper()
    font_pill = _get_font(30)
    p_bbox = draw.textbbox((0, 0), pill_text, font=font_pill)
    pw = p_bbox[2] - p_bbox[0] + 44
    ph = p_bbox[3] - p_bbox[1] + 24
    px = (width - pw) // 2
    py = 308

    draw.rounded_rectangle([px, py, px + pw, py + ph], radius=12, fill=(180, 15, 25, 240), outline=(255, 80, 80, 255), width=2)
    draw.text((px + 22, py + 10), pill_text, font=font_pill, fill=WHITE)

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
    Generates full 9:16 (1080x1920) YouTube Shorts Cover image using 3D scene + metallic text.
    """
    width, height = 1080, 1920
    art = get_ai_art_direction(headline, vertical)
    if hook_data and isinstance(hook_data, dict):
        if hook_data.get("line1_setup"):
            art["line1"] = str(hook_data["line1_setup"]).upper()
        if hook_data.get("line2_power"):
            art["line2"] = str(hook_data["line2_power"]).upper()
        if hook_data.get("badge"):
            art["pill_badge"] = str(hook_data["badge"]).upper()

    seed = abs(hash(headline)) % 100000 + 42
    raw_bg = generate_ai_scene_backdrop(art["scene_prompt"], width=width, height=height, seed=seed)
    
    # Apply vertical top-to-bottom darkening gradient for text contrast
    calm = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(calm)
    for y in range(int(height * 0.40)):
        ratio = y / float(height * 0.40)
        alpha = int(245 * ((1.0 - ratio) ** 1.3))
        cdraw.line([(0, y), (width, y)], fill=(BG_DARK[0], BG_DARK[1], BG_DARK[2], alpha))
    bg = Image.alpha_composite(raw_bg, calm)

    final_img = composite_3d_metallic_branding(bg, art, width=width, height=height, is_short=True)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    final_img.save(output_path, "JPEG", quality=95)
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

    legacy_cover = THUMBS_DIR / f"{output_slug}.jpg"
    legacy_header = THUMBS_DIR / f"{output_slug}_header.png"
    shutil.copy2(cover_path, legacy_cover)
    shutil.copy2(header_path, legacy_header)

    return cover_path, header_path
