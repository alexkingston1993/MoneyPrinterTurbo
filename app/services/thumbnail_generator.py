"""
Automated Financial Thumbnail Designer.
Inspired by YAAS (YouTube Agentic AI Studio) thumbnail designer.

Generates ultra-high CTR, high-contrast financial thumbnails in PIL:
- 16:9 (1280x720) for YouTube Long-Form Masterclasses
- 9:16 (1080x1920) for YouTube Shorts
- Deep slate canvas (#0A0F1D) with institutional grid lines and glowing candlestick charts
- Bold multi-tier typography with high-contrast drop-shadows and contrast badges
- Strictly Educational regulatory watermark badge
"""

import os
import random
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from loguru import logger


class ThumbnailGenerator:
    """Automated High-CTR Financial Thumbnail Designer."""

    # Colors
    BG_DARK = (10, 15, 29)          # Deep obsidian slate
    GRID_LINE = (22, 30, 52)        # Faint terminal grid
    GREEN_CANDLE = (34, 197, 94)    # Bullish neon green
    RED_CANDLE = (239, 68, 68)      # Bearish warning red
    TEXT_WHITE = (255, 255, 255)
    TEXT_YELLOW = (250, 204, 21)    # Neon gold/yellow
    TEXT_CYAN = (6, 182, 212)       # Cyan highlight
    BADGE_BG = (17, 24, 39, 230)    # Dark pill badge
    BORDER_CYAN = (14, 116, 144)

    @classmethod
    def _get_font(cls, size: int) -> ImageFont.FreeTypeFont:
        """Loads a clean bold sans-serif font, falling back gracefully."""
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

    @classmethod
    def generate_thumbnail(
        cls,
        title: str,
        aspect: str = "16:9",
        tag: str = "INSTITUTIONAL RADAR",
        sub_text: Optional[str] = None,
        output_path: Optional[str] = None,
        badge_text: Optional[str] = None,
    ) -> str:
        if badge_text:
            tag = badge_text
        """
        Creates an eye-catching, high-contrast financial thumbnail image.

        Args:
            title: Main headline (e.g. 'The 22,400 Liquidity Trap')
            aspect: '16:9' (1280x720) or '9:16' (1080x1920)
            tag: Top category pill (e.g. 'FII vs DII', 'MASTERCLASS', 'ORDER-FLOW')
            sub_text: Bottom contrast badge (e.g. '₹4,100 CR DATA POINT')
            output_path: Destination path for the JPG file

        Returns:
            str: Path to the generated thumbnail file
        """
        if aspect == "9:16":
            width, height = 1080, 1920
        else:
            width, height = 1280, 720

        # 1. Base Slate Canvas
        img = Image.new("RGB", (width, height), cls.BG_DARK)
        draw = ImageDraw.Draw(img, "RGBA")

        # 2. Draw Financial Grid Lines
        grid_step = 60 if aspect == "16:9" else 100
        for x in range(0, width, grid_step):
            draw.line([(x, 0), (x, height)], fill=cls.GRID_LINE, width=1)
        for y in range(0, height, grid_step):
            draw.line([(0, y), (width, y)], fill=cls.GRID_LINE, width=1)

        # 3. Draw Stylized Candlestick Chart in Background
        cls._draw_candlestick_motif(draw, width, height, aspect)

        # 4. Draw Radial Vignette / Gradient Overlay to enhance text readability
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        # Left-to-right dark gradient for 16:9, or center gradient for 9:16
        if aspect == "16:9":
            for i in range(int(width * 0.7)):
                alpha = int(220 * (1.0 - (i / (width * 0.7))))
                overlay_draw.line([(i, 0), (i, height)], fill=(10, 15, 29, alpha))
        else:
            for y in range(int(height * 0.3), int(height * 0.7)):
                overlay_draw.line([(0, y), (width, y)], fill=(10, 15, 29, 210))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img, "RGBA")

        # 5. Top Category Pill Badge
        font_badge = cls._get_font(22 if aspect == "16:9" else 36)
        tag_str = f"  {tag.upper()}  "
        bbox_tag = draw.textbbox((0, 0), tag_str, font=font_badge)
        tag_w = bbox_tag[2] - bbox_tag[0]
        tag_h = bbox_tag[3] - bbox_tag[1]

        tag_x = 60 if aspect == "16:9" else 80
        tag_y = 60 if aspect == "16:9" else 200

        draw.rounded_rectangle(
            [(tag_x, tag_y), (tag_x + tag_w + 20, tag_y + tag_h + 16)],
            radius=8,
            fill=(15, 23, 42, 240),
            outline=cls.TEXT_YELLOW,
            width=2,
        )
        draw.text((tag_x + 10, tag_y + 8), tag_str, font=font_badge, fill=cls.TEXT_YELLOW)

        # 6. Primary Headline (Large, Bold, High-Contrast)
        font_title = cls._get_font(62 if aspect == "16:9" else 80)
        cls._draw_multiline_headline(draw, title, font_title, tag_x, tag_y + tag_h + 40, width - 120, aspect)

        # 7. Subtitle / Numerical Contrast Badge
        if not sub_text:
            t_lower = title.lower()
            if "gold" in t_lower or "silver" in t_lower:
                sub_text = "PROTECT YOUR FAMILY SAVINGS"
            elif any(k in t_lower for k in ["trap", "loss", "mistake", "danger", "lose money", "90%"]):
                sub_text = "WHY BEGINNERS LOSE MONEY"
            elif any(k in t_lower for k in ["bank", "dump", "fii", "selling"]):
                sub_text = "BIG BANKS DATA EXPOSED"
            else:
                sub_text = "SIMPLE MARKET GUIDE FOR EVERYONE"

        font_sub = cls._get_font(26 if aspect == "16:9" else 42)
        sub_y = (height - 120) if aspect == "16:9" else (height - 300)
        draw.rounded_rectangle(
            [(tag_x, sub_y), (tag_x + 550, sub_y + 55)],
            radius=6,
            fill=(220, 38, 38, 230),  # Warning red pill
        )
        draw.text((tag_x + 15, sub_y + 12), f"⚡ {sub_text}", font=font_sub, fill=cls.TEXT_WHITE)

        # 8. Regulatory Compliance Watermark (Bottom Right)
        font_watermark = cls._get_font(18 if aspect == "16:9" else 28)
        watermark_text = "Strictly Educational • The Bull Print"
        bbox_wm = draw.textbbox((0, 0), watermark_text, font=font_watermark)
        wm_w = bbox_wm[2] - bbox_wm[0]
        wm_x = width - wm_w - 40
        wm_y = height - 45 if aspect == "16:9" else height - 80
        draw.text((wm_x, wm_y), watermark_text, font=font_watermark, fill=(148, 163, 184, 180))

        # Save to disk
        if not output_path:
            out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "output", "thumbnails")
            os.makedirs(out_dir, exist_ok=True)
            import uuid
            output_path = os.path.join(out_dir, f"thumb_{uuid.uuid4().hex[:8]}.jpg")

        img.save(output_path, "JPEG", quality=95)
        logger.success(f"[Thumbnail] High-CTR {aspect} thumbnail created: {output_path}")
        return output_path

    @classmethod
    def _draw_candlestick_motif(cls, draw: ImageDraw.ImageDraw, width: int, height: int, aspect: str):
        """Draws realistic background financial candlesticks across the right-hand canvas."""
        start_x = int(width * 0.45) if aspect == "16:9" else int(width * 0.2)
        candle_width = 24 if aspect == "16:9" else 36
        spacing = 18 if aspect == "16:9" else 26

        curr_y = int(height * 0.6)
        x = start_x
        while x < width - 40:
            direction = random.choice([1, 1, -1])  # upward bias
            body_h = random.randint(30, 110)
            wick_top = random.randint(15, 45)
            wick_bot = random.randint(15, 45)

            if direction == 1:
                color = cls.GREEN_CANDLE
                top_y = curr_y - body_h
                bot_y = curr_y
                curr_y = max(int(height * 0.25), curr_y - int(body_h * 0.6))
            else:
                color = cls.RED_CANDLE
                top_y = curr_y
                bot_y = curr_y + body_h
                curr_y = min(int(height * 0.8), curr_y + int(body_h * 0.6))

            # Wick
            draw.line([(x + candle_width // 2, top_y - wick_top), (x + candle_width // 2, bot_y + wick_bot)], fill=color, width=3)
            # Body
            draw.rectangle([(x, top_y), (x + candle_width, bot_y)], fill=color)

            x += candle_width + spacing

    @classmethod
    def _draw_multiline_headline(
        cls, draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
        x: int, y: int, max_w: int, aspect: str
    ):
        """Word-wraps headline into punchy, high-contrast rows with drop shadows."""
        words = text.split()
        lines = []
        curr_line = []

        max_words_per_line = 3 if aspect == "16:9" else 4
        for w in words:
            curr_line.append(w)
            if len(curr_line) >= max_words_per_line:
                lines.append(" ".join(curr_line))
                curr_line = []
        if curr_line:
            lines.append(" ".join(curr_line))

        # Limit to 3 prominent lines
        lines = lines[:3]

        line_y = y
        line_height = 76 if aspect == "16:9" else 100

        for idx, line in enumerate(lines):
            # Highlight keyword in line 2 or 3
            if any(k in line.lower() for k in ["trap", "dump", "banks", "gold", "beginners", "truth", "warning", "selling", "protect", "secret", "exposed", "fii", "rupee"]):
                fill_color = cls.TEXT_YELLOW
            else:
                fill_color = cls.TEXT_WHITE

            # Drop shadow
            draw.text((x + 4, line_y + 4), line, font=font, fill=(0, 0, 0, 220))
            draw.text((x, line_y), line, font=font, fill=fill_color)
            line_y += line_height


# Global instance and aliases
thumbnail_generator = ThumbnailGenerator()
thumbnail_designer = thumbnail_generator
