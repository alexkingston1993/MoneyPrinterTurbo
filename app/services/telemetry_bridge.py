#!/usr/bin/env python3
"""
Zero-Database Real-Time Telemetry & Interactive Control Bridge.
Manages bidirectional telemetry syncing between cloud runners (cloud_orchestrator.py,
kaggle_worker.py) and the Mission Control Dashboard via the isolated 'telemetry-live' orphan branch.
"""

from __future__ import annotations

import base64
import json
import os
import time
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests
from loguru import logger

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOCAL_CACHE_DIR = BASE_DIR / "data" / "telemetry_cache"
LOCAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_REPO = "alexkingston1993/MoneyPrinterTurbo"
BRANCH = "telemetry-live"


class TelemetryBridge:
    def __init__(self, slot: int, repo: Optional[str] = None, token: Optional[str] = None):
        self.slot = int(slot)
        self.repo = repo or os.getenv("GITHUB_REPO") or DEFAULT_REPO
        self.token = token or os.getenv("GITHUB_PAT_TOKEN") or os.getenv("GITHUB_TOKEN") or ""
        self.base_url = f"https://api.github.com/repos/{self.repo}/contents"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "TheBullPrint-TelemetryBridge",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

        self.last_push_ts = 0.0
        self.push_throttle_sec = 2.0
        self.sha_cache: Dict[str, str] = {}
        self.detail_state: Dict[str, Any] = self._load_local_or_default()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _load_local_or_default(self) -> Dict[str, Any]:
        local_file = LOCAL_CACHE_DIR / f"slot_{self.slot}_detail.json"
        if local_file.exists():
            try:
                return json.loads(local_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "slot": self.slot,
            "run_id": os.getenv("GITHUB_RUN_ID"),
            "vertical": "stock_market",
            "vertical_label": f"Slot #{self.slot}",
            "shorts_count": 2,
            "status": "RUNNING",
            "overall_pct": 0,
            "stage_pct": 0,
            "current_stage_index": 1,
            "current_stage_name": "SEO Topic Harvester",
            "current_subtask_label": "Initializing runner",
            "started_at": self._now_iso(),
            "updated_at": self._now_iso(),
            "eta_seconds": 0,
            "stages": [
                {"id": 1, "name": "SEO Topic Harvester (open-seo)", "status": "RUNNING", "pct": 0, "started_at": self._now_iso(), "completed_at": None, "metrics": {}},
                {"id": 2, "name": "Gemini Script & Dossier Synthesis", "status": "PENDING", "pct": 0, "started_at": None, "completed_at": None, "metrics": {}},
                {"id": 3, "name": "Authenticity & SEBI/IRDAI Compliance Gate", "status": "PENDING", "pct": 0, "started_at": None, "completed_at": None, "metrics": {}},
                {"id": 4, "name": "Chart & High-CTR Thumbnail Studio", "status": "PENDING", "pct": 0, "started_at": None, "completed_at": None, "metrics": {}},
                {"id": 5, "name": "Kaggle T4 GPU Render Farm", "status": "PENDING", "pct": 0, "started_at": None, "completed_at": None, "metrics": {}},
                {"id": 6, "name": "OpenMontage Post-Render QA Gate", "status": "PENDING", "pct": 0, "started_at": None, "completed_at": None, "metrics": {}},
                {"id": 7, "name": "Multi-Channel Distribution", "status": "PENDING", "pct": 0, "started_at": None, "completed_at": None, "metrics": {}},
            ],
            "live_logs": [],
        }

    def _fetch_file(self, rel_path: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        if not self.token:
            return None, None
        url = f"{self.base_url}/{rel_path}?ref={BRANCH}"
        try:
            r = requests.get(url, headers=self.headers, timeout=8)
            if r.status_code == 200:
                data = r.json()
                sha = data.get("sha")
                raw = base64.b64decode(data.get("content", "")).decode("utf-8")
                return json.loads(raw), sha
        except Exception as e:
            logger.debug(f"[TelemetryBridge] Fetch {rel_path} error: {e}")
        return None, None

    def _push_file(self, rel_path: str, content_dict: Dict[str, Any], message: str) -> bool:
        local_file = LOCAL_CACHE_DIR / Path(rel_path).name
        local_file.write_text(json.dumps(content_dict, indent=2), encoding="utf-8")

        if not self.token:
            return False

        url = f"{self.base_url}/{rel_path}"

        for attempt in range(1, 4):
            sha = self.sha_cache.get(rel_path) if attempt == 1 else None
            if not sha:
                if rel_path == "state/slots.json" and attempt > 1:
                    latest_slots, fresh_sha = self._fetch_file(rel_path)
                    if latest_slots and "slots" in latest_slots:
                        if "slots" in content_dict and str(self.slot) in content_dict["slots"]:
                            latest_slots["slots"][str(self.slot)] = content_dict["slots"][str(self.slot)]
                            latest_slots["updated_at"] = self._now_iso()
                            content_dict = latest_slots
                    sha = fresh_sha
                else:
                    _, sha = self._fetch_file(rel_path)

            raw_bytes = json.dumps(content_dict, indent=2).encode("utf-8")
            payload = {
                "message": message,
                "content": base64.b64encode(raw_bytes).decode("ascii"),
                "branch": BRANCH,
            }
            if sha:
                payload["sha"] = sha

            try:
                r = requests.put(url, headers=self.headers, json=payload, timeout=10)
                if r.status_code in (200, 201):
                    res_data = r.json()
                    self.sha_cache[rel_path] = res_data.get("content", {}).get("sha", "")
                    return True
                elif r.status_code == 409:
                    self.sha_cache.pop(rel_path, None)
                    sleep_time = (0.4 * (2 ** (attempt - 1))) + (random.uniform(0.1, 0.3))
                    logger.debug(f"[TelemetryBridge] 409 conflict for {rel_path}, retrying in {sleep_time:.2f}s (attempt {attempt}/3)")
                    time.sleep(sleep_time)
                    continue
                else:
                    logger.debug(f"[TelemetryBridge] Push {rel_path} error {r.status_code}: {r.text[:100]}")
            except Exception as e:
                logger.debug(f"[TelemetryBridge] Push exception for {rel_path}: {e}")
                time.sleep(0.5)

        return False

    def init_slot(
        self,
        vertical: str,
        shorts_count: int,
        topic: str = "",
        archetype: str = "",
        run_id: Optional[str] = None,
    ) -> None:
        self.detail_state["vertical"] = vertical
        self.detail_state["shorts_count"] = shorts_count
        self.detail_state["status"] = "RUNNING"
        self.detail_state["overall_pct"] = 2
        self.detail_state["stage_pct"] = 10
        self.detail_state["current_stage_index"] = 1
        self.detail_state["current_stage_name"] = "SEO Topic Harvester (open-seo)"
        self.detail_state["current_subtask_label"] = "Harvesting search intent & clusters"
        self.detail_state["started_at"] = self._now_iso()
        self.detail_state["updated_at"] = self._now_iso()
        if run_id:
            self.detail_state["run_id"] = str(run_id)

        self.add_log("INFO", f"Slot #{self.slot} ({vertical}) initialized. Target: 1 Long + {shorts_count} Shorts.")
        self.sync_now(force=True)

    def update_progress(
        self,
        overall_pct: int,
        stage_pct: int,
        stage_idx: int,
        stage_name: str,
        subtask_label: str,
        eta_sec: int = 0,
    ) -> None:
        self.detail_state["overall_pct"] = max(0, min(100, int(overall_pct)))
        self.detail_state["stage_pct"] = max(0, min(100, int(stage_pct)))
        self.detail_state["current_stage_index"] = stage_idx
        self.detail_state["current_stage_name"] = stage_name
        self.detail_state["current_subtask_label"] = subtask_label
        self.detail_state["updated_at"] = self._now_iso()
        if eta_sec > 0:
            self.detail_state["eta_seconds"] = int(eta_sec)

        # Update stages array status
        for st in self.detail_state.get("stages", []):
            sid = st.get("id")
            if sid < stage_idx:
                st["status"] = "COMPLETED"
                st["pct"] = 100
                if not st.get("completed_at"):
                    st["completed_at"] = self._now_iso()
            elif sid == stage_idx:
                st["status"] = "RUNNING"
                st["pct"] = max(0, min(100, int(stage_pct)))
                if not st.get("started_at"):
                    st["started_at"] = self._now_iso()
            else:
                st["status"] = "PENDING"
                st["pct"] = 0

        self.sync_now(force=False)

    def update_stage_metrics(self, stage_idx: int, metrics: Dict[str, Any]) -> None:
        for st in self.detail_state.get("stages", []):
            if st.get("id") == stage_idx:
                st.setdefault("metrics", {}).update(metrics)
                break
        self.sync_now(force=False)

    def add_log(self, level: str, msg: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        logs = self.detail_state.setdefault("live_logs", [])
        logs.append({"ts": ts, "level": level.upper(), "msg": msg})
        if len(logs) > 60:
            self.detail_state["live_logs"] = logs[-60:]
        self.sync_now(force=False)

    def set_status(self, status: str, subtask_label: Optional[str] = None) -> None:
        self.detail_state["status"] = status
        if subtask_label:
            self.detail_state["current_subtask_label"] = subtask_label
        self.detail_state["updated_at"] = self._now_iso()
        if status in ("COMPLETED", "FAILED", "HALTED"):
            self.detail_state["overall_pct"] = 100 if status == "COMPLETED" else self.detail_state["overall_pct"]
            self.detail_state["stage_pct"] = 100 if status == "COMPLETED" else self.detail_state["stage_pct"]
        self.sync_now(force=True)

    def check_command(self) -> Dict[str, Any]:
        """Polls control/slot_{n}_cmd.json from the telemetry-live branch."""
        rel_path = f"control/slot_{self.slot}_cmd.json"
        cmd_data, _ = self._fetch_file(rel_path)
        if cmd_data and cmd_data.get("action") not in (None, "", "NONE"):
            return cmd_data
        return {"action": "NONE"}

    def clear_command(self) -> None:
        rel_path = f"control/slot_{self.slot}_cmd.json"
        self._push_file(rel_path, {"action": "NONE", "timestamp": int(time.time())}, f"ack cmd slot {self.slot}")

    def sync_now(self, force: bool = False) -> None:
        now = time.time()
        if not force and (now - self.last_push_ts < self.push_throttle_sec):
            return

        self.last_push_ts = now
        detail_path = f"state/slot_{self.slot}_detail.json"
        self._push_file(detail_path, self.detail_state, f"telemetry: slot {self.slot} {self.detail_state.get('overall_pct', 0)}%")

        # Also update state/slots.json slot summary
        slots_json, _ = self._fetch_file("state/slots.json")
        if slots_json and "slots" in slots_json:
            s_dict = slots_json["slots"].setdefault(str(self.slot), {})
            s_dict.update({
                "slot": self.slot,
                "status": self.detail_state.get("status", "IDLE"),
                "overall_pct": self.detail_state.get("overall_pct", 0),
                "stage_pct": self.detail_state.get("stage_pct", 0),
                "current_stage": self.detail_state.get("current_stage_name", "Standby"),
                "current_stage_index": self.detail_state.get("current_stage_index", 1),
                "run_id": self.detail_state.get("run_id"),
            })
            slots_json["updated_at"] = self._now_iso()
            self._push_file("state/slots.json", slots_json, f"telemetry summary slot {self.slot}")
