"""
Generate a 20-minute weekly Indian stock market update video.
Uses Hermes agent news + web data → LLM script → Coqui TTS → stock footage → avatar overlay.
"""

import os
import sys
import json
import time
import datetime

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))

from app.services.hermes_agent import get_agent, NewsFetcher
from app.services.llm import _generate_response
from app.services.task import start
from app.models.schema import VideoParams, VideoAspect
from app.services import avatar
from app.utils import utils

TASK_ID = f"weekly_market_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

def create_placeholder_avatar():
    """Create a simple placeholder avatar if none exists."""
    avatars = avatar.get_available_avatars()
    if avatars:
        print(f"[✓] {len(avatars)} avatar(s) found, using daily rotation")
        return avatars[0]

    print("[!] No avatar images found — creating placeholder...")
    os.makedirs(avatar.AVATAR_DIR, exist_ok=True)
    img = Image.new("RGB", (600, 800), color=(40, 40, 50))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 600, 400], fill=(60, 60, 70))
    draw.rectangle([0, 550, 600, 800], fill=(90, 60, 30))
    draw.rectangle([0, 540, 600, 555], fill=(110, 80, 40))
    draw.ellipse([220, 100, 380, 280], fill=(200, 160, 130))
    draw.polygon([(180, 280), (420, 280), (380, 580), (220, 580)], fill=(50, 80, 120))
    draw.polygon([(260, 280), (300, 340), (340, 280)], fill=(200, 200, 200))
    draw.ellipse([215, 80, 385, 230], fill=(30, 20, 15))
    draw.ellipse([255, 170, 280, 195], fill=(40, 40, 40))
    draw.ellipse([320, 170, 345, 195], fill=(40, 40, 40))
    draw.arc([265, 200, 335, 230], 0, 180, fill=(180, 100, 80), width=3)
    draw.rectangle([200, 420, 400, 460], fill=(30, 30, 35))
    draw.rectangle([210, 460, 390, 480], fill=(20, 20, 25))
    path = os.path.join(avatar.AVATAR_DIR, "placeholder.jpg")
    img.save(path, quality=95)
    print(f"[✓] Placeholder avatar saved: {path}")
    return path


def gather_market_context() -> str:
    """Gather Indian stock market news from Hermes agent + web data."""
    print("\n=== Gathering market intelligence ===")
    fetcher = NewsFetcher()
    all_news = fetcher.fetch_indian_news()
    print(f"  Fetched {len(all_news)} total news items")

    # Sort by source for organized context
    context_lines = ["## INDIAN STOCK MARKET NEWS (Week of June 8-12, 2026)", ""]
    for item in all_news[:30]:
        context_lines.append(f"- [{item.source}] {item.title}")
        if item.summary:
            context_lines.append(f"  {item.summary[:200]}")
        context_lines.append("")

    # Add key market data from our web search findings
    context_lines.extend([
        "## KEY MARKET DATA (June 8-12, 2026 Week)", "",
        "- Monday June 8: Sensex crashed 719 pts (-0.97%) to 73,524, Nifty down 243 pts (-1.04%) to 23,123",
        "  Cause: Fresh US-Israel-Iran tensions, crude oil spike, Asian sell-off",
        "- Tuesday June 9: Nifty recovered to 23,242 (+0.52%), gradual recovery",
        "- Wednesday June 10-11: Continued recovery, Bank Nifty bounced from 53,027 low",
        "- Thursday June 11: Bank Nifty weekly high 54,865, strong buying in banking stocks",
        "- Friday June 12: MASSIVE RALLY! Sensex surged 857-992 pts, Nifty reclaimed 23,400",
        "  Triggers: US-Iran peace deal hopes, crude oil prices cooling from $93/bbl",
        "  Top gainers: IndiGo (+3.2%), Shriram Finance (+2.7%), Bajaj Finance (+2.3%)",
        "  Top losers: ONGC (-3.1%), Tech Mahindra (-1.6%)",
        "- Nifty 50 closed week at ~23,623 (cumulative gain of +1.99% on Friday alone)",
        "- FPI outflows: Rs 62,800 cr pulled out in first fortnight of June",
        "- RBI: FCNR(B) and ECB swap window to attract foreign inflows, support rupee",
        "- Rupee strengthened against USD on crude price drop + peace deal hopes",
        "- India VIX eased, volatility declining as sentiment improved",
        "- Eight of top-10 most valued firms gained Rs 1.90 lakh cr in market cap; ICICI Bank led",
        "",
        "## LOOKING AHEAD (Week of June 15-19, 2026)", "",
        "- Vedanta Group mega 4-way demerger: Vedanta Aluminium, Power, Oil & Gas, Iron & Steel listing on Monday",
        "  Vedanta Aluminium expected at Rs 1.74 lakh cr market cap",
        "- 31 stocks going ex-record date for dividends/bonus this week (HDFC Bank, Tata group, Brigade Enterprises)",
        "- Iran peace deal developments — potential Strait of Hormuz reopening",
        "- Crude oil price movement (currently ~$92-93/bbl) — key for inflation and rupee",
        "- FII/DII flow data — will FPI selling continue or reverse?",
        "- Technical levels: Nifty support at 23,200-23,000; resistance at 23,900-24,100",
        "  Bank Nifty support at 53,900-53,000; resistance at 55,000-55,800",
        "- CLSA brand to vanish after 40 years — being rebranded under Citic Securities from 2027",
        "- Market bias: Sideways to positive, momentum from Friday's rally may continue",
    ])

    return "\n".join(context_lines)


def generate_script(context: str) -> str:
    """Generate a 20-minute script using the LLM with Alex's persona."""
    print("\n=== Generating 20-minute script ===")

    prompt = f"""You are Alex from Chennai, a retail investor who shares his personal analysis about the Indian stock market. You are NOT an expert or advisor — just a regular guy sharing what you've learned.

Below is the latest market data and news. Write a 20-minute (3000+ words) YouTube video script in your unique style.

YOUR PERSONA:
- Warm, humble, conversational — like talking to a friend over chai
- Explain things simply — "see, here's what I've noticed..."
- Say "I believe", "in my view", "I would", "I think" — never "you should" or "you must"
- Occasionally share personal observations from your investing journey
- Use phrases like: "See, here's the thing...", "Now, I've been watching this for a while...", "What's interesting is..."
- Indian English, natural and relatable

SCRIPT STRUCTURE (aim for 20 minutes / 3000+ words):

[0:00-1:00] INTRO + DISCLAIMER
- "Hey folks, I'm Alex from Chennai. Before we dive in — this is purely for educational purposes. I'm not a SEBI-registered advisor..."
- Today's date context: Sunday June 14, 2026 — Monday market tomorrow

[1:00-4:00] WEEK IN REVIEW: NIFTY & SENSEX
- Started weak on Monday (Iran tensions), ended with a bang on Friday (peace deal hopes)
- Nifty went from 23,123 to ~23,623 — a rollercoaster
- What drove each day

[4:00-7:00] SECTOR WATCH
- Banking (ICICI Bank shining), IT (Tech Mahindra struggled), Pharma (held up well)
- Aviation (IndiGo soared on crude drop), Oil & Gas (ONGC hit)
- Auto (mixed), FMCG, Metals

[7:00-9:00] FII/DII & MACRO STORY
- FPI exodus: Rs 62,800 cr pulled out in June first fortnight
- RBI's FCNR(B) swap window — smart move to attract dollars
- Rupee strengthening on crude drop and peace hopes

[9:00-12:00] KEY EVENTS ANALYSIS
- US-Iran peace deal: what it means for Indian markets
- Vedanta mega demerger (4 entities listing Monday)
- RBI policy unchanged — maintaining status quo
- Global tech correction (Broadcom, AI stocks) — India IT impact

[12:00-14:00] STOCKS IN FOCUS
- ICICI Bank leading the rally, Bajaj Finance bouncing back
- Penny stocks warning: 12 stocks down 25-70% in 3 months
- Dividend stocks going ex-date this week

[14:00-17:00] TECHNICAL OUTLOOK FOR NEXT WEEK
- Nifty support 23,200 / resistance 23,900-24,100
- Bank Nifty support 53,900 / resistance 55,000-55,800
- Key events to watch: Vedanta listing, Iran peace deal progress, crude oil
- My personal view: where I think the market might head

[17:00-19:00] INVESTING WISDOM SEGMENT
- Personal lesson: Why I stopped trying to trade every move
- The power of staying invested during volatility
- How I approach a week like this

[19:00-20:00] OUTRO
- Summary of key takeaways
- "What are your thoughts? Drop a comment below..."
- "This is Alex from Chennai, signing off. Remember — this is for education only, please do your own research before investing."

SEBI COMPLIANCE RULES (MANDATORY):
- Start with the full disclaimer: "I'm not a SEBI-registered advisor, this is for educational purposes only"
- End with: "Please do your own research before investing"
- Never say "you should buy", "you should sell", "you must", "you need to"
- Always frame as "I would", "in my view", "I think", "I believe"
- No price targets or return predictions
- No promises or guarantees of any kind
- Include "please do your own research" at least once

CONTEXT DATA:
{context}

Now write the full 20-minute script:"""

    script = _generate_response(prompt)
    word_count = len(script.split())
    print(f"  Generated {word_count} words")
    return script


def generate_video_script(script: str, subject: str):
    """Run the full pipeline to create the video."""
    print("\n=== Starting video pipeline ===")

    # Create task directory
    task_dir = utils.task_dir(TASK_ID)
    os.makedirs(task_dir, exist_ok=True)

    # Save the generated script
    script_path = os.path.join(task_dir, "generated_script.txt")
    with open(script_path, "w") as f:
        f.write(script)
    print(f"  Script saved: {script_path}")

    # Search terms for stock footage
    video_terms = [
        "Indian stock market trading",
        "Nifty 50 stock exchange",
        "business news India",
        "stock market chart analysis",
        "corporate office building",
        "financial data graphs",
        "Mumbai Dalal Street",
        "trading floor busy",
    ]

    params = VideoParams(
        video_subject=subject,
        video_script=script,
        video_terms=video_terms,
        video_aspect=VideoAspect.landscape.value,
        video_resolution="standard",
        video_concat_mode="sequential",
        video_transition_mode="FadeIn",
        video_clip_duration=8,
        video_count=1,
        video_source="pexels",
        video_language="en",
        voice_name="coqui:app/services/voices/alex_ref.wav:en",
        voice_volume=1.0,
        voice_rate=1.0,
        subtitle_enabled=True,
        subtitle_position="bottom",
        font_name="STHeitiMedium.ttc",
        text_fore_color="#FFFFFF",
        text_background_color=True,
        font_size=56,
        stroke_color="#000000",
        stroke_width=1.5,
        n_threads=2,
        paragraph_number=10,
        bgm_type="random",
        bgm_volume=0.15,
    )

    print(f"\n  Subject: {subject}")
    print(f"  Aspect: {params.video_aspect}")
    print(f"  Resolution: {params.video_resolution}")
    print(f"  Voice: {params.voice_name}")
    print(f"  Source: {params.video_source}")
    print()

    result = start(TASK_ID, params, stop_at="video")

    if result and result.get("videos"):
        print(f"\n{'='*60}")
        print(f"[✓] VIDEO GENERATED SUCCESSFULLY!")
        for path in result["videos"]:
            print(f"    {path}")
        print(f"{'='*60}\n")
    else:
        print(f"\n[!] Video generation returned: {result}")
        if result:
            for k, v in result.items():
                if v:
                    print(f"  {k}: {v}")


if __name__ == "__main__":
    import time

    # Step 1: Ensure avatar placeholder
    avatar_path = create_placeholder_avatar()

    # Step 2: Gather market intelligence
    context = gather_market_context()
    print(f"\n  Context size: {len(context)} chars")

    # Step 3: Generate the script
    subject = "Indian Stock Market Weekly Analysis: Will the Rally Continue? | June 14, 2026"
    script = generate_script(context)
    print(f"\n[✓] Script ready: {len(script.split())} words")

    # Save a preview
    preview_path = f"/tmp/market_script_preview_{TASK_ID}.txt"
    with open(preview_path, "w") as f:
        f.write(script)
    print(f"[✓] Preview saved: {preview_path}")

    # Show first 500 chars
    print(f"\n=== SCRIPT PREVIEW (first 500 chars) ===")
    print(script[:500])
    print("...")
    print(f"=== END PREVIEW ===\n")

    # Step 4: Run the video pipeline
    proceed = input("\nGenerate the full video? This will take a long time (hours). [y/N]: ")
    if proceed.lower() in ("y", "yes"):
        t0 = time.time()
        generate_video_script(script, subject)
        elapsed = time.time() - t0
        print(f"\nTotal time: {elapsed/60:.1f} minutes")
    else:
        print("\nSkipping video generation. Script is ready for review.")
        print(f"Run manually with: python run_weekly_market_update.py --generate")
