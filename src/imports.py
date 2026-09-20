import json
import logging
import re
import secrets
from pathlib import Path
from threading import Lock
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from src import google_takeout, music_pipeline

# ============================================================
# Import Configuration and State
# ============================================================

# Bounded imports for the local dashboard; a token grants access to one dataset.
IMPORT_ROOT = Path(__file__).resolve().parent.parent / "data" / "imports"
MAX_BYTES = 25 * 1024 * 1024
MAX_WATCH_EVENTS = 100_000
MAX_ACTIVE_IMPORTS = 2
IMPORT_FAILURE_MESSAGE = "Import failed. Check the server API key, quota and connection, then try again."
IMPORT_FILES = ("music_history.csv", "status.json", "decisions.json")

router = APIRouter()
logger = logging.getLogger(__name__)
jobs = {}
lock = Lock()
active = 0

# ============================================================
# Import Status Persistence
# ============================================================


def write_import_status(token: str, status: dict) -> None:
    status_path = IMPORT_ROOT / token / "status.json"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    # Replace only after writing so a restart cannot leave a partial status file.
    temporary_path = status_path.with_suffix(".tmp")
    try:
        temporary_path.write_text(json.dumps(status), encoding="utf-8")
        temporary_path.replace(status_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def read_import_status(token: str) -> dict:
    status_path = IMPORT_ROOT / token / "status.json"
    if not status_path.is_file():
        raise HTTPException(404, "Import not found.")
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if (
            not isinstance(status, dict)
            or status.get("status") not in {"processing", "complete", "failed"}
            or not isinstance(status.get("message"), str)
        ):
            raise ValueError("Invalid saved import status.")
    except (OSError, ValueError, TypeError) as error:
        logger.exception("Could not read import status")
        raise HTTPException(500, "Could not read the saved import status.") from error
    # Upload bytes live only in memory, so an interrupted job cannot be
    # resumed from its saved status after the server restarts.
    if status["status"] == "processing":
        status.update(
            status="failed",
            message="The server restarted during this import. Delete it and import again.",
        )
    return status


def get_job(token: str) -> dict:
    # Tokens also select a directory; validate their generated format
    # before using them in a filesystem path.
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise HTTPException(404, "Import not found.")
    with lock:
        if token not in jobs:
            jobs[token] = read_import_status(token)
        return dict(jobs[token])


def dataset_path(token: str) -> Path:
    if get_job(token)["status"] != "complete":
        raise HTTPException(409, "Dataset is not ready.")
    return IMPORT_ROOT / token / "music_history.csv"

# ============================================================
# Background Import Processing
# ============================================================


def prepare_import_records(content: bytes, suffix: str, timezone: str) -> tuple[pd.DataFrame, int]:
    watch_records = google_takeout.parse_watch_history_content(content, suffix)
    if len(watch_records) > MAX_WATCH_EVENTS:
        raise ValueError("Please import at most 100,000 watch events at a time.")
    records_dataframe = google_takeout.stage_one_clean(
        google_takeout.create_dataframe(watch_records), timezone=timezone
    )
    if records_dataframe.empty:
        raise ValueError("No usable watch events found. Choose a YouTube watch-history HTML or JSON file.")
    return records_dataframe, len(watch_records) - len(records_dataframe)


# Watch and music counts describe listening events, whereas format
# exclusions describe distinct videos checked once by the pipeline.
def create_import_summary(
    records_dataframe: pd.DataFrame,
    music_dataframe: pd.DataFrame,
    decisions: list[dict],
    skipped_records: int,
) -> dict:
    return {
        "watch_events": len(records_dataframe),
        "music_plays": len(music_dataframe),
        "excluded_shorts": sum(decision.get("short_status") == "short" for decision in decisions),
        "unverified_videos": sum(decision.get("short_status") == "unknown" for decision in decisions),
        "skipped_records": skipped_records,
    }


def finish_import(token: str, final_status: dict) -> None:
    global active
    try:
        with lock:
            jobs[token].update(final_status)
            try:
                write_import_status(token, jobs[token])
            except OSError:
                logger.exception("Could not save import status")
                jobs[token].update(
                    status="failed",
                    message="Could not save the import status. Check server storage and try again.",
                )
    finally:
        with lock:
            active -= 1


def process_import(token: str, content: bytes, suffix: str, timezone: str) -> None:
    def progress(message: str) -> None:
        with lock:
            jobs[token]["message"] = message

    final_status = {"status": "failed", "message": IMPORT_FAILURE_MESSAGE}
    try:
        progress("Reading watch history")
        records_dataframe, skipped_records = prepare_import_records(content, suffix, timezone)
        music_dataframe, decisions = music_pipeline.run_music_pipeline(
            records_dataframe, IMPORT_ROOT / token / "music_history.csv", progress=progress
        )
        decisions_path = IMPORT_ROOT / token / "decisions.json"
        decisions_path.write_text(json.dumps(decisions, ensure_ascii=False), encoding="utf-8")
        final_status = {
            "status": "complete",
            "message": "Import complete",
            "summary": create_import_summary(
                records_dataframe, music_dataframe, decisions, skipped_records
            ),
        }
    except ValueError as error:
        final_status = {"status": "failed", "message": str(error)}
    except Exception:
        # Background failures must be visible through polling as well as server logs.
        logger.exception("Takeout import failed")
    finally:
        finish_import(token, final_status)

# ============================================================
# Upload Validation
# ============================================================


def validate_import_options(filename: str, timezone: str) -> str:
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise HTTPException(400, "Choose a valid export timezone, such as Europe/Dublin.") from error
    suffix = Path(filename).suffix.lower()
    if suffix not in {".html", ".json"}:
        raise HTTPException(400, "Choose an extracted watch-history.html or watch-history.json file.")
    return suffix


async def read_upload_content(request: Request) -> bytes:
    # Enforce the limit as bytes arrive instead of trusting Content-Length
    # or buffering an arbitrarily large request before checking its size.
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > MAX_BYTES:
            raise HTTPException(413, "The history file must be smaller than 25 MB.")
    if not content:
        raise HTTPException(400, "The selected file is empty.")
    return bytes(content)

# ============================================================
# Import Routes
# ============================================================


@router.post("/api/imports", status_code=202)
async def create_import(
    request: Request,
    background_tasks: BackgroundTasks,
    filename: str = "watch-history.json",
    timezone: str = "UTC",
):
    global active
    suffix = validate_import_options(filename, timezone)
    with lock:
        # Reserve capacity before reading the body so concurrent uploads
        # count toward the same limit as background processing.
        if active >= MAX_ACTIVE_IMPORTS:
            raise HTTPException(429, "Two imports are running. Please try again later.")
        active += 1
    token = None
    try:
        content = await read_upload_content(request)
        token = secrets.token_urlsafe(32)
        initial_status = {"status": "processing", "message": "Queued"}
        try:
            write_import_status(token, initial_status)
        except OSError as error:
            logger.exception("Could not create import status")
            raise HTTPException(500, "Could not create the import. Check server storage and try again.") from error
        with lock:
            jobs[token] = initial_status
        background_tasks.add_task(process_import, token, content, suffix, timezone)
        return {"dataset_token": token}
    except BaseException:
        # Release the slot even when the client disconnects or cancels the upload.
        with lock:
            active -= 1
            if token is not None:
                jobs.pop(token, None)
        raise


@router.get("/api/imports/current")
def import_status(x_dataset_token: str = Header()):
    return get_job(x_dataset_token)


@router.delete("/api/imports/current")
def delete_import(x_dataset_token: str = Header()):
    if get_job(x_dataset_token)["status"] == "processing":
        raise HTTPException(409, "Wait for processing to finish.")
    import_folder = IMPORT_ROOT / x_dataset_token
    try:
        for filename in IMPORT_FILES:
            (import_folder / filename).unlink(missing_ok=True)
        if import_folder.exists():
            import_folder.rmdir()
    except OSError as error:
        logger.exception("Could not delete imported data")
        raise HTTPException(500, "Could not delete imported data. Check server storage and try again.") from error
    with lock:
        jobs.pop(x_dataset_token, None)
    return {"deleted": True}
