import requests
import time
import sys

API_URL = "http://127.0.0.1:8080/api/v1/videos"

# 10 Detailed Scripts for the Video Series
SCRIPTS = [
    {
        "subject": "Reliance Industries: The Future of Indian Business",
        "script": "Could Reliance Industries make you a millionaire in the next ten years? Let's analyze it. Currently, Reliance is not just an oil giant; it's dominating retail and telecommunications with Jio. Fundamentally, it boasts strong cash flows and consistent profit growth. Looking at market research, their entry into green energy gives them an incredible competitive moat. Technical analysis shows strong long-term support levels, acting as a massive wealth compounder. Finally, promoter integrity: under Mukesh Ambani, execution has been flawless. Hold this stock for the next decade.",
        "terms": ["business building", "telecommunications network", "green energy solar", "stock chart analysis", "indian businessman"]
    },
    {
        "subject": "HDFC Bank: The Gold Standard of Private Banking",
        "script": "Why is HDFC Bank considered the gold standard of Indian banking for the next decade? Let's break it down. Their financials are rock solid with a highly stable return on equity and low non-performing assets. Our market research shows their massive branch network and recent merger makes them unstoppable in rural and urban credit. Technically, the stock is consolidating for its next massive bull run. The promoters and management have a flawless track record of transparent execution. If you hold it for ten years, HDFC is a compounding machine.",
        "terms": ["banking finance", "business growth", "financial graph upward", "office meeting", "money counting"]
    },
    {
        "subject": "TCS: The Tech Titan's 10-Year Outlook",
        "script": "Is Tata Consultancy Services still a buy for the next 10 years? Absolutely. Fundamentally, TCS generates incredible free cash flow and operates with practically zero debt. Research shows their aggressive pivot into artificial intelligence and cloud computing secures their massive moat globally. Technical analysis reveals a stock that bounces perfectly off its 200-day moving average. As part of the Tata Group, their promoter integrity is legendary and unmatched. For long-term wealth, TCS remains a fundamental anchor.",
        "terms": ["artificial intelligence", "global business technology", "stock market chart", "office skyline", "tata"]
    },
    {
        "subject": "ICICI Bank: The Growth Engine of India",
        "script": "Why should ICICI Bank be in your portfolio for the next ten years? Here is the quick analysis. Financially, ICICI has dramatically improved its asset quality and loan growth is exploding. Market research proves their digital banking platforms are attracting young India at an unprecedented rate. Technicals show a beautiful long-term uptrend with higher highs. With strong management steering the ship with high integrity, ICICI Bank is poised to lead the financial revolution. It’s a pure long-term play.",
        "terms": ["digital banking app", "financial growth graph", "indian economy", "stock analysis", "business handshake"]
    },
    {
        "subject": "Bajaj Finance: The Consumer Credit King",
        "script": "Can Bajaj Finance multiply your wealth over the next decade? Let’s look at the facts. Their fundamental growth is staggering, maintaining high net interest margins year after year. Our market research shows they have an unbreakable monopoly in consumer durable financing. From a technical perspective, every dip is aggressively bought by institutional investors. Supported by the trusted Bajaj Group, promoter integrity is top-tier. As Indian consumption skyrockets, Bajaj Finance will fund it.",
        "terms": ["consumer shopping", "credit card transaction", "finance chart upward", "business team success", "money growth"]
    },
    {
        "subject": "Larsen and Toubro: Building the Future of India",
        "script": "How will Larsen and Toubro capitalize on India's trillion-dollar infrastructure boom? Let’s analyze. Fundamentally, their order book is at an all-time high, guaranteeing revenues for years. Research shows no other company has the scale to execute mega-projects like L&T, giving them a massive moat. Technical analysis points to a sustained breakout on the monthly charts. Run by professional management with supreme integrity, L&T is the ultimate proxy for India's growth story. Hold it for 10 years.",
        "terms": ["construction infrastructure", "engineering blueprint", "stock chart rising", "corporate building", "india development"]
    },
    {
        "subject": "Infosys: The Consistent Wealth Creator",
        "script": "Why is Infosys still a staple for long-term investors? Let's dive in. Their financials show phenomenal return on capital employed and consistent dividend payouts. Market research indicates their deep relationships with Fortune 500 companies make their revenue highly predictable. Technically, the stock is a classic buy-on-dips candidate. Founded on the highest standards of corporate governance and promoter integrity, Infosys is a sleep-well-at-night stock for the next decade.",
        "terms": ["software coding", "global corporate office", "financial chart analysis", "technology consulting", "wealth growth"]
    },
    {
        "subject": "Hindustan Unilever: The Defensive Giant",
        "script": "Is Hindustan Unilever the safest stock for the next 10 years? Let’s find out. Fundamentally, HUL generates massive cash flow with zero debt. Our research shows their products are in 9 out of 10 Indian households—a moat that cannot be replicated. Technical analysis shows this stock stabilizes portfolios during market crashes. With a clean management record and global Unilever backing, its integrity is unquestionable. For stable, compounding returns, HUL is a must-have.",
        "terms": ["supermarket shopping", "household products", "stable stock chart", "indian family", "defensive investment"]
    },
    {
        "subject": "ITC: The High Dividend Powerhouse",
        "script": "Why has ITC become a favorite for long-term compounding? Let's analyze. Financially, ITC is a cash-generating monster with highly attractive dividend yields. Market research shows their FMCG and hotel businesses are finally scaling, reducing reliance on their core monopoly. Technically, the stock broke out of a multi-year consolidation, signaling a massive new bull run. Run by professional management with outstanding integrity, ITC offers both safety and growth for the next ten years.",
        "terms": ["fmcg products", "luxury hotel", "dividend income chart", "business success", "stock market investing"]
    },
    {
        "subject": "Bharti Airtel: The Telecom Monopoly Player",
        "script": "Could Bharti Airtel be the biggest telecom winner of the decade? Let's break it down. Their fundamental metrics are improving rapidly as average revenue per user skyrockets. Research shows the telecom sector is essentially a duopoly, giving Airtel a massive moat and pricing power. Technicals show strong upward momentum fueled by 5G rollout success. Sunil Mittal's management has proven high integrity and survival instincts. For the digital decade, Airtel is a massive buy.",
        "terms": ["telecom tower", "5g technology", "stock growth graph", "mobile internet", "digital transformation"]
    }
]

def generate_videos():
    print("Waiting for API to start...")
    time.sleep(5)  # Wait for uvicorn to fully boot

    for i, data in enumerate(SCRIPTS):
        print(f"\nSubmitting Video {i+1}/10: {data['subject']}")
        
        payload = {
            "video_subject": data["subject"],
            "video_script": data["script"],
            "video_terms": data["terms"],
            "video_aspect": "9:16",
            "video_concat_mode": "random",
            "video_clip_duration": 5,
            "video_count": 1,
            "video_source": "pexels",
            "video_language": "",
            "voice_name": "en-US-AriaNeural-Female", # Good English voice
            "bgm_type": "random",
            "subtitle_enabled": True,
            "subtitle_position": "center",
            "font_size": 75,
            "text_fore_color": "#FFFFFF",
            "text_background_color": True,
            "stroke_color": "#000000",
            "stroke_width": 2.0
        }
        
        try:
            response = requests.post(API_URL, json=payload, timeout=10)
            if response.status_code == 200:
                result = response.json()
                task_id = result.get('data', {}).get('task_id')
                print(f"✅ Successfully queued! Task ID: {task_id}")
            else:
                print(f"❌ Failed to queue. Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            print(f"❌ Connection error: {e}")
        
        # Slight delay between submissions to avoid overwhelming the server queue logic
        time.sleep(2)

if __name__ == "__main__":
    generate_videos()
