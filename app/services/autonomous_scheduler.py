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
        {"name": "pre_market", "time": "08:30", "days": [0, 1, 2, 3, 4]},
        {"name": "morning_momentum", "time": "11:00", "days": [0, 1, 2, 3, 4]},
        {"name": "midday_update", "time": "13:30", "days": [0, 1, 2, 3, 4]},
        {"name": "market_close", "time": "16:00", "days": [0, 1, 2, 3, 4]},
        {"name": "evening_wrap", "time": "19:30", "days": [0, 1, 2, 3, 4]},
        {"name": "weekend_masterclass", "time": "11:00", "days": [5]},  # Saturday
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

    def run_slot(self, slot_name: str) -> Dict:
        """Trigger an immediate market cycle for a specific slot."""
        logger.info(f"[Scheduler] Triggering scheduled slot: '{slot_name}'")
        res = pipeline_orchestrator.run_market_cycle(slot_name=slot_name)
        self.last_run_slot = slot_name
        self.last_run_time = self.get_ist_now().strftime("%Y-%m-%d %H:%M:%S IST")
        return res

    def start_daemon(self, check_interval_sec: int = 45):
        """Continuous background daemon checking the clock against IST slots."""
        self.running = True
        logger.info("[Scheduler] Autonomous market daemon started. Monitoring IST market slots...")

        executed_today = set()
        current_date_str = ""

        while self.running:
            try:
                now = self.get_ist_now()
                today_str = now.strftime("%Y-%m-%d")
                current_hm = now.strftime("%H:%M")
                weekday = now.weekday()  # 0=Monday, 6=Sunday

                # Reset executed set at midnight
                if today_str != current_date_str:
                    executed_today.clear()
                    current_date_str = today_str

                # Check if current time matches any slot
                for slot in self.SLOTS:
                    slot_name = slot["name"]
                    slot_time = slot["time"]
                    allowed_days = slot["days"]

                    if weekday in allowed_days and current_hm == slot_time:
                        execution_key = f"{today_str}_{slot_name}"
                        if execution_key not in executed_today:
                            logger.info(f"[Scheduler] Alarm triggered for slot '{slot_name}' at {current_hm} IST")
                            executed_today.add(execution_key)
                            self.run_slot(slot_name)

                time.sleep(check_interval_sec)
            except KeyboardInterrupt:
                logger.info("[Scheduler] Daemon stopped by user.")
                break
            except Exception as e:
                logger.error(f"[Scheduler] Daemon error: {e}")
                time.sleep(check_interval_sec)


# Global instance
scheduler = AutonomousScheduler()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        slot = sys.argv[2] if len(sys.argv) > 2 else "manual_trigger"
        print(f"Triggering immediate cycle for slot: {slot}")
        result = scheduler.run_slot(slot)
        print("Result:", result)
    else:
        scheduler.start_daemon()
