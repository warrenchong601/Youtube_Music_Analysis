import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import pandas as pd
from bs4 import BeautifulSoup

# ============================================================
# Takeout Configuration
# ============================================================

COLUMNS = ["action", "title", "channel", "watched_at", "video_url"]
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}

# ============================================================
# Video URL Validation
# ============================================================


def video_id_from_url(value: object) -> str | None:
    try:
        parsed_url = urlparse(str(value))
    except ValueError:
        # Malformed URLs are skipped just like links to non-video activity.
        return None
    if parsed_url.hostname == "youtu.be":
        video_id = parsed_url.path.strip("/")
    elif parsed_url.hostname in YOUTUBE_HOSTS:
        if parsed_url.path.startswith("/shorts/"):
            video_id = parsed_url.path.split("/")[2]
        else:
            video_id = parse_qs(parsed_url.query).get("v", [""])[0]
    else:
        return None
    return video_id if re.fullmatch(r"[\w-]{11}", video_id, flags=re.ASCII) else None

# ============================================================
# JSON and HTML Watch History Parsing
# ============================================================


def parse_json_history(text: str) -> list[dict]:
    try:
        entries = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError("This file is not valid JSON.") from error
    if not isinstance(entries, list):
        raise ValueError("Expected a Google Takeout watch-history JSON array.")

    watch_records = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        video_url = entry.get("titleUrl", "")
        if not video_id_from_url(video_url):
            continue
        subtitles = entry.get("subtitles") or []
        channel_name = None
        if isinstance(subtitles, list) and subtitles and isinstance(subtitles[0], dict):
            channel_name = subtitles[0].get("name")
        watch_records.append({
            "action": "Watched",
            "title": re.sub(r"^Watched\s+", "", str(entry.get("title", ""))),
            "channel": channel_name,
            "watched_at": entry.get("time"),
            "video_url": video_url,
        })
    return watch_records


def parse_html_history(text: str) -> list[dict]:
    soup = BeautifulSoup(text, "lxml")
    watch_records = []
    for card in soup.select("div.outer-cell"):
        content_cell = card.select_one("div.content-cell")
        if content_cell is None:
            continue
        links = content_cell.select("a[href]")
        # Activity cards can contain channel links as well as video links;
        # selecting by URL avoids treating a channel name as the watched title.
        video_link = next((link for link in links if video_id_from_url(link.get("href"))), None)
        if video_link is None:
            continue
        text_parts = list(content_cell.stripped_strings)
        channel_name = next((link.get_text(strip=True) for link in links if link is not video_link), None)
        watch_records.append({
            "action": "Watched",
            "title": video_link.get_text(strip=True),
            "channel": channel_name,
            "watched_at": text_parts[-1] if text_parts else None,
            "video_url": video_link["href"],
        })
    return watch_records


def parse_watch_history_content(content: bytes | str, suffix: str) -> list[dict]:
    try:
        # Accept exports with a UTF-8 byte-order mark as well as plain UTF-8.
        text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
    except UnicodeDecodeError as error:
        raise ValueError("The history file must use UTF-8 encoding.") from error
    if suffix.lower() == ".json":
        return parse_json_history(text)
    return parse_html_history(text)


def parse_watch_history(watch_path: str | Path) -> list[dict]:
    watch_path = Path(watch_path)
    try:
        content = watch_path.read_bytes()
    except OSError as error:
        raise OSError(f"Could not read watch history: {watch_path}") from error
    return parse_watch_history_content(content, watch_path.suffix)

# ============================================================
# Timestamp Conversion and Record Cleaning
# ============================================================


def create_dataframe(watch_records: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(watch_records, columns=COLUMNS)


def remove_missing_channel_records(dataframe: pd.DataFrame) -> pd.DataFrame:
    # Missing channel metadata does not prove a record is an advertisement.
    return dataframe.copy()


def parse_watch_timestamp(value: object, timezone: str):
    if not isinstance(value, str):
        return pd.NaT
    timestamp_text = value.replace("Sept ", "Sep ").replace("\u202f", " ")
    timestamp_text = re.sub(r"\s+(UTC|GMT)$", " +00:00", timestamp_text)
    # Abbreviations such as IST are ambiguous. Use the export timezone supplied by the user.
    timestamp_text = re.sub(r"\s+[A-Z]{2,5}$", "", timestamp_text)
    timestamp = pd.to_datetime(
        timestamp_text,
        format="mixed",
        errors="coerce",
        dayfirst=not bool(re.match(r"^\d{4}-", timestamp_text)),
    )
    if pd.isna(timestamp):
        return pd.NaT
    # Explicit offsets already identify an instant. Only local timestamps
    # need the export timezone; ambiguous or nonexistent times stay invalid
    # rather than guessing an hour around daylight-saving changes.
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(timezone, ambiguous="NaT", nonexistent="NaT")
    return timestamp.tz_convert("UTC") if not pd.isna(timestamp) else pd.NaT


def convert_watch_timestamps(dataframe: pd.DataFrame, timezone: str = "Europe/Dublin") -> pd.DataFrame:
    ZoneInfo(timezone)  # Validate the supplied timezone before parsing any records.
    dataframe = dataframe.copy()
    dataframe["watched_at"] = pd.to_datetime(
        dataframe["watched_at"].map(lambda value: parse_watch_timestamp(value, timezone)),
        utc=True,
    )
    return dataframe


def add_video_id_column(dataframe: pd.DataFrame) -> pd.DataFrame:
    dataframe = dataframe.copy()
    dataframe["video_ids"] = dataframe["video_url"].map(video_id_from_url)
    return dataframe


def stage_one_clean(dataframe: pd.DataFrame, timezone: str = "Europe/Dublin") -> pd.DataFrame:
    dataframe = convert_watch_timestamps(dataframe, timezone)
    dataframe = add_video_id_column(dataframe)
    return (
        dataframe.dropna(subset=["video_ids", "watched_at"])
        .sort_values("watched_at")
        .reset_index(drop=True)
    )
