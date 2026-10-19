import requests
import time
import sys

API_URL = "http://127.0.0.1:8080/api/v1/videos"

# 10 Detailed Scripts for the Video Series
from app.services.compliance import enforce_strict_compliance

# 10 SEBI-Compliant Detailed Scripts for the Video Series
SCRIPTS = [
    {
        "subject": "Reliance Industries: The Future of Indian Business",
        "script": "Can Reliance Industries sustain long-term wealth compounding over the next ten years? Let's analyze it. Currently, Reliance is not just an oil giant; it's dominating retail and telecommunications with Jio. Fundamentally, it boasts strong cash flows and consistent profit growth. Looking at market research, their entry into green energy gives them an incredible competitive moat. Technical analysis shows strong long-term support levels. Finally, promoter integrity: under Mukesh Ambani, execution has been proven. I would hold this stock for the next decade, please do your own due diligence and market research as I am not a SEBI-registered financial advisor.",
        "terms": ["business building", "telecommunications network", "green energy solar", "stock chart analysis", "indian businessman"]
    },
    {
        "subject": "HDFC Bank: The Gold Standard of Private Banking",
        "script": "Why is HDFC Bank considered a benchmark of Indian private banking? Let's break it down. Their financials are solid with a stable return on equity and disciplined asset quality. Our market research shows their massive branch network and recent merger expands their reach in rural and urban credit. Technically, the stock is consolidating around long-term valuation averages. The management has maintained a transparent execution track record. In my personal perspective, holding high-quality franchises over a decade can be rewarding, but please do your own due diligence and market research.",
        "terms": ["banking finance", "business growth", "financial graph upward", "office meeting", "money counting"]
    },
    {
        "subject": "TCS: The Tech Titan's 10-Year Outlook",
        "script": "Can Tata Consultancy Services maintain its leadership over the next 10 years? Fundamentally, TCS generates resilient free cash flow and operates with practically zero debt. Research shows their aggressive pivot into artificial intelligence and cloud computing secures their massive moat globally. Technical analysis reveals a stock that respects long-term moving averages. As part of the Tata Group, their promoter integrity is legendary. Personally, I would consider TCS a core study for long horizons, please do your own due diligence and market research.",
        "terms": ["artificial intelligence", "global business technology", "stock market chart", "office skyline", "tata"]
    },
    {
        "subject": "ICICI Bank: The Growth Engine of India",
        "script": "Why is ICICI Bank capturing institutional attention for the next ten years? Here is the quantitative analysis. Financially, ICICI has consistently improved its asset quality with steady loan book expansion. Market research proves their digital platforms are onboarding retail customers rapidly. Technicals show an enduring long-term uptrend. With capable management steering operations, ICICI Bank is well-positioned, but please do your own due diligence and market research as I am not a SEBI-registered advisor.",
        "terms": ["digital banking app", "financial growth graph", "indian economy", "stock analysis", "business handshake"]
    },
    {
        "subject": "Bajaj Finance: The Consumer Credit King",
        "script": "Can Bajaj Finance sustain its compound growth trajectory over the next decade? Let’s examine the fundamentals. Their historical net interest margins remain industry-leading. Market research highlights their dominant omnichannel network in consumer durable financing. From a technical perspective, institutional volumes frequently accumulate near key moving averages. Supported by the trusted Bajaj Group, corporate governance is high. Please conduct your own due diligence and market research before taking any financial decision.",
        "terms": ["consumer shopping", "credit card transaction", "finance chart upward", "business team success", "money growth"]
    },
    {
        "subject": "Larsen and Toubro: Building the Future of India",
        "script": "How will Larsen and Toubro capitalize on India's capital expenditure boom? Let’s analyze the setup. Fundamentally, their order book stands at record highs, offering visible multi-year revenue visibility. Research shows unmatched engineering capability across mega-infrastructure projects. Technical analysis highlights constructive multi-year chart structures. Run by seasoned management with high integrity, I would personally consider holding this stock for the next decade, but please do your own due diligence and market research.",
        "terms": ["construction infrastructure", "engineering blueprint", "stock chart rising", "corporate building", "india development"]
    },
    {
        "subject": "Infosys: The Consistent Wealth Creator",
        "script": "Why does Infosys remain a staple for long-term quantitative study? Let's dive in. Their balance sheet exhibits high return on capital employed and a clear capital allocation policy. Market research indicates deep enterprise relationships across Fortune 500 organizations. Technically, the stock respects key cyclical support bands. Founded on exemplary corporate governance standards, Infosys represents a resilient case study, but please do your own due diligence and market research.",
        "terms": ["software coding", "global corporate office", "financial chart analysis", "technology consulting", "wealth growth"]
    },
    {
        "subject": "Hindustan Unilever: The Defensive Giant",
        "script": "How does Hindustan Unilever navigate long-term market cycles? Fundamentally, HUL produces steady free cash flow with virtually zero leverage. Research indicates their distribution touches nearly nine out of ten Indian households—a distribution moat that is formidable. Technicals indicate this stock historically provides capital stability during high-volatility regimes. For capital preservation and compounding potential, I would hold it, but please do your own due diligence and market research.",
        "terms": ["supermarket shopping", "household products", "stable stock chart", "indian family", "defensive investment"]
    },
    {
        "subject": "ITC: The High Dividend Powerhouse",
        "script": "Why has ITC emerged as a favorite for cash-flow focused portfolios? Let's analyze. Financially, ITC is an exceptional cash generator with consistent dividend yields. Research indicates their non-cigarette FMCG, paper, and agribusiness segments are scaling to improve margin diversification. Technicals demonstrate a clear multi-year structure breakout. Led by professional stewardship with high integrity, it remains a valuable study, but please do your own due diligence and market research.",
        "terms": ["fmcg products", "luxury hotel", "dividend income chart", "business success", "stock market investing"]
    },
    {
        "subject": "Bharti Airtel: The Telecom Monopoly Player",
        "script": "Could Bharti Airtel be a prime beneficiary of digital data consumption? Let's break it down. Their fundamental metrics are improving with steady average revenue per user expansion. Market structure shows the Indian telecom landscape operates as an effective duopoly, giving Airtel durable pricing leverage. Technical charts reflect disciplined accumulation. For the digital decade, I would hold this stock, but please do your own due diligence and market research as I am not a SEBI-registered advisor.",
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
