"""
Real-Time Webhook Trigger (webhook_trigger.py).
Listens for inbound webhooks from RSS watchers, n8n, Make.com, or breaking news alerts.
Executes the master media publishing pipeline in a non-blocking background task.
"""

import os
import subprocess
from pathlib import Path
from pydantic import BaseModel
from fastapi import FastAPI, BackgroundTasks, HTTPException
from loguru import logger

BASE_DIR = Path(__file__).parent
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "flipzon_secure_macro_webhook_2026")

app = FastAPI(title="Flipzon Real-Time Media Engine Webhook Listener")


class TriggerPayload(BaseModel):
    secret: str
    topic: str
    market_notes: str = ""


def run_pipeline_task(topic: str, notes: str):
    """Executes the master pipeline in background."""
    logger.info(f"🔔 Inbound Webhook: Launching publishing pipeline for topic: '{topic}'")
    try:
        cmd = [
            str(BASE_DIR / ".venv" / "bin" / "python") if (BASE_DIR / ".venv").exists() else "python3",
            str(BASE_DIR / "master_engine.py")
        ]
        res = subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True, check=True)
        logger.success(f"✓ Pipeline run successful for: {topic}\n{res.stdout[-300:]}")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Pipeline execution failed: {e}\n{e.stderr}")


@app.post("/api/trigger-run")
async def trigger_run(payload: TriggerPayload, background_tasks: BackgroundTasks):
    """
    Receives incoming webhook, verifies the authentication token,
    and dispatches the pipeline asynchronously.
    """
    if payload.secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret token.")
    
    background_tasks.add_task(run_pipeline_task, payload.topic, payload.market_notes)
    return {
        "status": "success",
        "message": f"Pipeline triggered in background for topic: '{payload.topic}'"
    }


@app.get("/api/health")
def health():
    return {"status": "online", "service": "webhook_trigger"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
