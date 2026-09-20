import json
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
import pandas as pd

COLUMNS = ["action", "title", "channel", "watched_at", "video_url"]

def video_id_from_url(value):
    parsed = urlparse(str(value))
    if parsed.hostname == "youtu.be":
        candidate = parsed.path.strip("/")
    elif parsed.hostname in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        candidate = (parsed.path.split("/")[2] if parsed.path.startswith("/shorts/")
                     else parse_qs(parsed.query).get("v", [""])[0])
    else:
        return None
    return candidate if re.fullmatch(r"[\w-]{11}", candidate, flags=re.ASCII) else None

def parse_watch_history(watch_path):
    path = Path(watch_path)
    return parse_watch_history_content(path.read_bytes(), path.suffix)

def parse_watch_history_content(content, suffix):
    try:
        text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
    except UnicodeDecodeError as error:
        raise ValueError("The history file must use UTF-8 encoding.") from error
    records = []
    if suffix.lower() == ".json":
        try:
            entries = json.loads(text)
        except json.JSONDecodeError as error:
            raise ValueError("This file is not valid JSON.") from error
        if not isinstance(entries, list):
            raise ValueError("Expected a Google Takeout watch-history JSON array.")
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            url = entry.get("titleUrl", "")
            if not video_id_from_url(url):
                continue
            subtitles = entry.get("subtitles") or []
            records.append(dict(action="Watched", title=re.sub(r"^Watched\s+", "", str(entry.get("title", ""))),
                                channel=subtitles[0].get("name") if subtitles and isinstance(subtitles[0], dict) else None,
                                watched_at=entry.get("time"), video_url=url))
    else:
        soup = BeautifulSoup(text, "lxml")
        for card in soup.select("div.outer-cell"):
            cell = card.select_one("div.content-cell")
            if cell is None:
                continue
            links = cell.select("a[href]")
            video = next((a for a in links if video_id_from_url(a.get("href"))), None)
            if video is None:
                continue
            parts = list(cell.stripped_strings)
            channel = next((a.get_text(strip=True) for a in links if a is not video), None)
            records.append(dict(action="Watched", title=video.get_text(strip=True), channel=channel,
                                watched_at=parts[-1] if parts else None, video_url=video["href"]))
    return records

def create_dataframe(watch_records):
    return pd.DataFrame(watch_records, columns=COLUMNS)

def remove_missing_channel_records(dataframe):
    # Missing channel metadata does not prove a record is an advertisement.
    return dataframe.copy()

def convert_watch_timestamps(dataframe, timezone="Europe/Dublin"):
    from zoneinfo import ZoneInfo
    ZoneInfo(timezone)  # Validate the supplied timezone before parsing any records.
    def parse(value):
        if not isinstance(value, str):
            return pd.NaT
        value = value.replace("Sept ", "Sep ").replace("\u202f", " ")
        value = re.sub(r"\s+(UTC|GMT)$", " +00:00", value)
        # Abbreviations such as IST are ambiguous. Use the export timezone supplied by the user.
        value = re.sub(r"\s+[A-Z]{2,5}$", "", value)
        stamp = pd.to_datetime(value, format="mixed", errors="coerce", dayfirst=not bool(re.match(r"^\d{4}-", value)))
        if pd.isna(stamp):
            return pd.NaT
        if stamp.tzinfo is None:
            stamp = stamp.tz_localize(timezone, ambiguous="NaT", nonexistent="NaT")
        return stamp.tz_convert("UTC") if not pd.isna(stamp) else pd.NaT
    dataframe = dataframe.copy()
    dataframe["watched_at"] = pd.to_datetime(dataframe["watched_at"].map(parse), utc=True)
    return dataframe

def add_video_id_column(dataframe):
    dataframe = dataframe.copy()
    dataframe["video_ids"] = dataframe["video_url"].map(video_id_from_url)
    return dataframe

def stage_one_clean(dataframe, timezone="Europe/Dublin"):
    dataframe = add_video_id_column(convert_watch_timestamps(dataframe, timezone))
    return dataframe.dropna(subset=["video_ids", "watched_at"]).sort_values("watched_at").reset_index(drop=True)
