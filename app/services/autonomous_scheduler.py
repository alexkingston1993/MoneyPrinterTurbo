"""
Autonomous Market Scheduler Daemon.

Orchestrates 5 autonomous publishing cycles aligned with Indian Market Hours (IST):
1. 08:30 IST — Pre-Market Morning Brief (Global cues, Gift Nifty, expectations)
2. 11:00 IST — Morning Momentum & Sector Rotation
3. 13:30 IST — Mid-Day Session & European Opening Impact
4. 16:00 IST — Post-Market Closing Wrap & Top Movers
5. 19:30 IST — Evening FII/DII Deep-Dive & Global Outlook
6. Saturday 11:00 IST — Weekend Wealth & Technical Masterclass

Runs continuously in the background on cloud or local systems.
"""

import datetime
import time
from typing import Dict, List, Optional
from loguru import logger
import pytz

from app.services.pipeline_orchestrator import pipeline_orchestrator


IST = pytz.timezone("Asia/Kolkata") if "Asia/Kolkata" in pytz.all_timezones else None


class AutonomousScheduler:
    """Schedules and executes market cycles according to IST trading hours."""

    SLOTS = [
        # ── Pre-Market & Opening ──
        {"name": "pre_market", "time": "08:30", "days": [0, 1, 2, 3, 4], "desc": "Gift Nifty & Morning Brief"},
        {"name": "breakout_radar", "time": "10:00", "days": [0, 1, 2, 3, 4], "desc": "Opening Range Breakout Radar"},
        {"name": "morning_momentum", "time": "11:00", "days": [0, 1, 2, 3, 4], "desc": "Sector Rotation & Momentum"},
        # ── Mid-Day & European Open ──
        {"name": "viral_trend", "time": "12:00", "days": [0, 1, 2, 3, 4], "desc": "Google Trends & Viral Pulse Radar"},
        {"name": "midday_update", "time": "12:30", "days": [0, 1, 2, 3, 4], "desc": "European Opening Impact"},
        {"name": "block_deals", "time": "14:00", "days": [0, 1, 2, 3, 4], "desc": "Dark Pool & Block Deals Radar"},
        # ── Market Close & Derivatives ──
        {"name": "market_close", "time": "15:45", "days": [0, 1, 2, 3, 4], "desc": "Closing Bell Institutional Flow"},
        {"name": "options_trap", "time": "17:30", "days": [0, 1, 2, 3, 4], "desc": "Option Chain & Greeks Trap"},
        {"name": "gold_macro_radar", "time": "18:45", "days": [0, 1, 2, 3, 4], "desc": "Money Pechu Gold & Macro Pulse"},
        # ── Evening Wrap & Global Markets ──
        {"name": "evening_wrap", "time": "19:15", "days": [0, 1, 2, 3, 4], "desc": "FII vs DII Positioning Showdown"},
        {"name": "us_market_open", "time": "20:30", "days": [0, 1, 2, 3, 4], "desc": "Wall Street Bell & Global Macro"},
        {"name": "night_compounder", "time": "22:00", "days": [0, 1, 2, 3, 4], "desc": "Bluechip Wealth Compounding Secrets"},
        # ── Weekends ──
        {"name": "weekend_masterclass", "time": "11:00", "days": [5], "desc": "Saturday 10-Min Masterclass"},
        {"name": "sunday_study", "time": "11:00", "days": [6], "desc": "Sunday 10-Year Wealth Architecture"},
    ]

    def __init__(self):
        self.running = False
        self.last_run_slot: Optional[str] = None
        self.last_run_time: Optional[str] = None

    def get_ist_now(self) -> datetime.datetime:
        """Get current datetime in Indian Standard Time (IST)."""
        if IST:
            return datetime.datetime.now(IST)
        # Fallback to UTC + 5:30
        utc_now = datetime.datetime.utcnow()
        return utc_now + datetime.timedelta(hours=5, minutes=30)

    def resolve_slot(self, slot_name: str) -> str:
        """Resolves generic trigger names (e.g. auto, scheduled_cron) to the appropriate IST market slot."""
        if slot_name and slot_name not in ["auto", "scheduled_cron", "manual_trigger", "live_update"]:
            return slot_name
        now = self.get_ist_now()
        weekday = now.weekday()
        if weekday == 5:  # Saturday
            return "weekend_masterclass"
        if weekday == 6:  # Sunday
            return "sunday_study"
        hour = now.hour
        minute = now.minute
        time_decimal = hour + minute / 60.0

        if time_decimal < 9.5:
            return "pre_market"
        elif time_decimal < 10.5:
            return "breakout_radar"
        elif time_decimal < 11.75:
            return "morning_momentum"
        elif time_decimal < 13.5:
            return "midday_update"
        elif time_decimal < 15.0:
            return "block_deals"
        elif time_decimal < 16.75:
            return "market_close"
        elif time_decimal < 18.0:
            return "options_trap"
        elif time_decimal < 19.0:
            return "gold_macro_radar"
        elif time_decimal < 20.0:
            return "evening_wrap"
        elif time_decimal < 21.5:
            return "us_market_open"
        else:
            return "night_compounder"

    def schedule_batch_shorts(
        self,
        count: int = 10,
        start_delay_hours: float = 1.0,
        interval_hours: float = 2.5,
        slots: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Batch-produces and schedules high-cadence shorts on YouTube.
        Uploads each video as 'private' with RFC 3339 publishAt timestamps spaced apart
        to avoid the YouTube algorithmic spam filter trap and ensure steady view velocity.
        """
        available_slots = slots or [
            "viral_trend", "gold_macro_radar", "breakout_radar", "morning_momentum",
            "midday_update", "block_deals", "market_close", "options_trap",
            "evening_wrap", "us_market_open", "night_compounder", "pre_market"
        ]
        results = []
        now_utc = datetime.datetime.now(datetime.timezone.utc)

        logger.info(f"[Scheduler] 🚀 Initiating scheduled batch production of {count} shorts (Spaced every {interval_hours}h)...")

        for i in range(min(count, len(available_slots))):
            slot = available_slots[i]
            scheduled_time = now_utc + datetime.timedelta(hours=start_delay_hours + (i * interval_hours))
            publish_at_iso = scheduled_time.strftime("%Y-%m-%dT%H:%M:%SZ")

            logger.info(
                f"[Scheduler] 🎬 Producing slot '{slot}' ({i+1}/{count}) -> "
                f"Scheduled for YouTube publication at: {publish_at_iso} UTC"
            )
            try:
                res = pipeline_orchestrator.run_market_cycle(slot_name=slot, publish_at=publish_at_iso)
                results.append({
                    "slot": slot,
                    "scheduled_publish_utc": publish_at_iso,
                    "result": res,
                })
            except Exception as e:
                logger.error(f"[Scheduler] Batch scheduling error for '{slot}': {e}")
                results.append({"slot": slot, "error": str(e)})

        return results

    def run_slot(self, slot_name: str, publish_at: Optional[str] = None) -> Dict:
        """Trigger an immediate market cycle for a specific slot."""
        if slot_name in ["batch_all", "run_all_remaining"]:
            slots_to_run = ["market_close", "evening_wrap", "morning_momentum", "long_form"]
            logger.info(f"[Scheduler] Executing complete batch of remaining cycles in cloud: {slots_to_run}")
            batch_results = []
            for s in slots_to_run:
                logger.info(f"[Scheduler] >>> Starting batch video production for slot: '{s}'")
                try:
                    res = pipeline_orchestrator.run_market_cycle(slot_name=s)
                    batch_results.append({"slot": s, "result": res})
                except Exception as ex:
                    logger.error(f"[Scheduler] Error executing batch slot '{s}': {ex}")
            self.last_run_slot = "batch_all"
            self.last_run_time = self.get_ist_now().strftime("%Y-%m-%d %H:%M:%S IST")
            return {"batch_success": True, "count": len(batch_results), "executed": batch_results}

        resolved_slot = self.resolve_slot(slot_name)
        logger.info(f"[Scheduler] Triggering scheduled slot: '{resolved_slot}' (raw input: '{slot_name}')")
        res = pipeline_orchestrator.run_market_cycle(slot_name=resolved_slot, publish_at=publish_at)
        self.last_run_slot = resolved_slot
        self.last_run_time = self.get_ist_now().strftime("%Y-%m-%d %H:%M:%S IST")
        return res

    def start_daemon(self, check_interval_sec: int = 45):
        """Continuous background daemon checking the clock against IST slots."""
        self.running = True
        logger.info(f"[Scheduler] Autonomous market daemon started. Monitoring {len(self.SLOTS)} IST slots daily...")

        import json, os
        ledger_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "executed_slots.json")
        executed_today = set()
        if os.path.exists(ledger_path):
            try:
                with open(ledger_path, "r") as f:
                    executed_today = set(json.load(f))
            except Exception:
                pass
        current_date_str = ""

        while self.running:
            try:
                now = self.get_ist_now()
                today_str = now.strftime("%Y-%m-%d")
                current_hm = now.strftime("%H:%M")
                weekday = now.weekday()  # 0=Monday, 6=Sunday

                # Reset executed set at midnight
                if today_str != current_date_str:
                    executed_today = {k for k in executed_today if k.startswith(today_str)}
                    current_date_str = today_str

                # Check if current time matches any slot
                for slot in self.SLOTS:
                    slot_name = slot["name"]
                    slot_time = slot["time"]
                    allowed_days = slot["days"]

                    if weekday in allowed_days and current_hm == slot_time:
                        execution_key = f"{today_str}_{slot_name}"
                        if execution_key not in executed_today:
                            logger.info(f"[Scheduler] ⏰ Alarm triggered for slot '{slot_name}' ({slot.get('desc')}) at {current_hm} IST")
                            executed_today.add(execution_key)
                            try:
                                with open(ledger_path, "w") as f:
                                    json.dump(list(executed_today), f)
                            except Exception:
                                pass
                            self.run_slot(slot_name)

                time.sleep(check_interval_sec)
            except KeyboardInterrupt:
                logger.info("[Scheduler] Daemon stopped by user.")
                break
            except Exception as e:
                logger.error(f"[Scheduler] Daemon error: {e}")
                time.sleep(check_interval_sec)

    def get_analytics_performance_report(self) -> Dict:
        """Fetch real-time channel analytics and top-performing topic recommendations."""
        from app.services.analytics_optimizer import analytics_optimizer
        return analytics_optimizer.get_channel_performance_report()

    def get_recommended_topics(self) -> List[str]:
        """Fetch data-driven topic recommendations based on audience retention and engagement."""
        from app.services.analytics_optimizer import analytics_optimizer
        return analytics_optimizer.get_top_performing_topics()


# Global instance
scheduler = AutonomousScheduler()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        slot = sys.argv[2] if len(sys.argv) > 2 else "manual_trigger"
        print(f"Triggering immediate cycle for slot: {slot}")
        result = scheduler.run_slot(slot)
        print("Result:", result)
    elif len(sys.argv) > 1 and sys.argv[1] == "--schedule-batch":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        print(f"Pre-producing and scheduling batch of {count} shorts spaced across the day...")
        result = scheduler.schedule_batch_shorts(count=count)
        print("Batch Results:", result)
    elif len(sys.argv) > 1 and sys.argv[1] == "--analytics":
        print("Auditing channel performance & data-driven topic suggestions...")
        report = scheduler.get_analytics_performance_report()
        print(f"Total Views: {report.get('channel_total_views')}")
        print(f"Subscribers: {report.get('channel_subscribers')}")
        print(f"Top Performing Content Theme: {report.get('top_performing_theme')}")
        print("\nTop Themes by Average Views:")
        for t in report.get("top_themes", []):
            print(f"  * {t['display_name']} -> Avg Views: {t.get('avg_views', 0)}")
        print("\nRecommended High-CTR Topics:")
        for top in scheduler.get_recommended_topics():
            print(f"  - {top}")
    else:
        scheduler.start_daemon()
