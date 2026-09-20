"""Bounded imports for the local dashboard; a token grants access to one dataset."""
import json
import re
import logging
import secrets
from pathlib import Path
from threading import Lock
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from src import google_takeout, music_pipeline

router = APIRouter()
IMPORT_ROOT = Path(__file__).resolve().parent.parent / "data" / "imports"
MAX_BYTES = 25 * 1024 * 1024
jobs = {}
lock = Lock()
active = 0

def get_job(token):
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise HTTPException(404, "Import not found.")
    with lock:
        if token not in jobs:
            status_path = IMPORT_ROOT / token / "status.json"
            if not status_path.is_file():
                raise HTTPException(404, "Import not found.")
            jobs[token] = json.loads(status_path.read_text(encoding="utf-8"))
            if jobs[token]["status"] == "processing":
                jobs[token].update(status="failed", message="The server restarted during this import. Delete it and import again.")
        return dict(jobs[token])

def dataset_path(token):
    if get_job(token)["status"] != "complete":
        raise HTTPException(409, "Dataset is not ready.")
    return IMPORT_ROOT / token / "music_history.csv"

def process_import(token, content, suffix, timezone):
    global active
    def progress(message):
        with lock:
            jobs[token]["message"] = message
    try:
        progress("Reading watch history")
        records = google_takeout.parse_watch_history_content(content, suffix)
        if len(records) > 100_000:
            raise ValueError("Please import at most 100,000 watch events at a time.")
        frame = google_takeout.stage_one_clean(google_takeout.create_dataframe(records), timezone=timezone)
        if frame.empty:
            raise ValueError("No usable watch events found. Choose a YouTube watch-history HTML or JSON file.")
        result, decisions = music_pipeline.run_music_pipeline(frame, IMPORT_ROOT / token / "music_history.csv", progress=progress)
        (IMPORT_ROOT / token / "decisions.json").write_text(json.dumps(decisions, ensure_ascii=False), encoding="utf-8")
        final = dict(status="complete", message="Import complete", summary={
                "watch_events": len(frame), "music_plays": len(result),
                "excluded_shorts": sum(d.get("short_status") == "short" for d in decisions),
                "unverified_videos": sum(d.get("short_status") == "unknown" for d in decisions),
                "skipped_records": len(records) - len(frame)})
    except ValueError as error:
        final = dict(status="failed", message=str(error))
    except Exception:
        logging.exception("Takeout import failed")
        final = dict(status="failed", message="Import failed. Check the server API key, quota and connection, then try again.")
    finally:
        try:
            status_path = IMPORT_ROOT / token / "status.json"
            status_path.parent.mkdir(parents=True, exist_ok=True)
            with lock:
                jobs[token].update(final)
                status_path.write_text(json.dumps(jobs[token]), encoding="utf-8")
        finally:
            with lock:
                active -= 1

@router.post("/api/imports", status_code=202)
async def create_import(request: Request, background_tasks: BackgroundTasks, filename: str = "watch-history.json", timezone: str = "UTC"):
    global active
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(400, "Choose a valid export timezone, such as Europe/Dublin.")
    suffix = Path(filename).suffix.lower()
    if suffix not in {".html", ".json"}:
        raise HTTPException(400, "Choose an extracted watch-history.html or watch-history.json file.")
    with lock:
        if active >= 2:
            raise HTTPException(429, "Two imports are running. Please try again later.")
        active += 1
    try:
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > MAX_BYTES:
                raise HTTPException(413, "The history file must be smaller than 25 MB.")
        if not content:
            raise HTTPException(400, "The selected file is empty.")
        token = secrets.token_urlsafe(32)
        with lock:
            jobs[token] = {"status": "processing", "message": "Queued"}
        folder = IMPORT_ROOT / token
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "status.json").write_text(json.dumps(jobs[token]), encoding="utf-8")
        background_tasks.add_task(process_import, token, bytes(content), suffix, timezone)
        return {"dataset_token": token}
    except BaseException:
        with lock:
            active -= 1
        raise

@router.get("/api/imports/current")
def import_status(x_dataset_token: str = Header()):
    return get_job(x_dataset_token)

@router.delete("/api/imports/current")
def delete_import(x_dataset_token: str = Header()):
    if get_job(x_dataset_token)["status"] == "processing":
        raise HTTPException(409, "Wait for processing to finish.")
    path = IMPORT_ROOT / x_dataset_token / "music_history.csv"
    path.unlink(missing_ok=True)
    (path.parent / "status.json").unlink(missing_ok=True)
    (path.parent / "decisions.json").unlink(missing_ok=True)
    if path.parent.exists():
        path.parent.rmdir()
    with lock:
        jobs.pop(x_dataset_token, None)
    return {"deleted": True}
