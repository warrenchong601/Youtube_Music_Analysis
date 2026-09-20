import logging
import os
from collections.abc import Iterable
from urllib.parse import parse_qs, urlparse

import pandas as pd
import requests
from dotenv import load_dotenv

# ============================================================
# API Configuration
# ============================================================

load_dotenv()

API_KEY = os.getenv("YOUTUBE_API_KEY")


YOUTUBE_VIDEOS_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNELS_ENDPOINT = "https://www.googleapis.com/youtube/v3/channels"

BATCH_SIZE = 50
METADATA_TIMEOUT_SECONDS = 20
SHORTS_TIMEOUT_SECONDS = 10
YOUTUBE_HOSTS = {"www.youtube.com", "youtube.com", "m.youtube.com"}
logger = logging.getLogger(__name__)

# ============================================================
# Shared Request Helpers
# ============================================================


def create_id_batches(identifiers: Iterable[str]) -> list[str]:
    identifiers = list(identifiers)
    return [
        ",".join(identifiers[start_index:start_index + BATCH_SIZE])
        for start_index in range(0, len(identifiers), BATCH_SIZE)
    ]


def fetch_metadata(endpoint: str, request_params: dict) -> dict:
    if not API_KEY:
        raise ValueError("Set YOUTUBE_API_KEY on the server before importing history.")

    response = requests.get(
        timeout=METADATA_TIMEOUT_SECONDS, url=endpoint, params=request_params
    )
    # API failures must stop the import rather than resemble a successful
    # empty response, which would silently remove videos from the report.
    response.raise_for_status()
    try:
        metadata = response.json()
    except ValueError as error:
        raise ValueError("YouTube returned invalid JSON metadata. Please try again.") from error
    if not isinstance(metadata, dict) or not isinstance(metadata.get("items"), list):
        raise ValueError("YouTube returned malformed metadata: expected an items array.")
    return metadata


# ============================================================
# Video Metadata Requests
# ============================================================

# The YouTube Data API accepts up to 50 video IDs in a single videos.list
# request, so IDs are combined into comma-separated batches.
def create_video_batches(dataframe: pd.DataFrame) -> list[str]:
    return create_id_batches(dataframe["video_ids"])


def create_video_request(video_ids: str) -> dict:
    # snippet provides title/channel/category metadata,
    # while contentDetails provides video duration used later in the classification pipeline.
    params_dict = {
        "part": "snippet,contentDetails",
        "id": video_ids,
        "key": API_KEY,
    }

    return params_dict

def fetch_video_metadata(video_id: str) -> dict:
    request_params = create_video_request(video_id)
    return fetch_metadata(YOUTUBE_VIDEOS_ENDPOINT, request_params)

# ============================================================
# Channel Metadata Requests
# ============================================================

# Channel IDs are batched to reduce the number of API requests required
# when retrieving topic metadata.
def create_channel_batches(channel_ids: Iterable[str]) -> list[str]:
    return create_id_batches(channel_ids)


def create_channel_request(channel_id: str) -> dict:
    # topicDetails provides YouTube topic IDs used to identify music-focused channels.
    channel_params = {
        "part": "snippet,topicDetails",
        "id": channel_id,
        "key": API_KEY,
    }

    return channel_params

def fetch_channel_metadata(channel_id: str) -> dict:
    request_params = create_channel_request(channel_id)
    return fetch_metadata(YOUTUBE_CHANNELS_ENDPOINT, request_params)

# ============================================================
# YouTube Shorts Detection
# ============================================================

# The YouTube Data API does not directly identify whether a video is a Short.
# Redirects provide a heuristic only. None means the check was inconclusive.
# Retry consent/unexpected responses with the default HTTP client user agent.
def is_short(video_id: str, max_attempts: int = 2) -> bool | None:
    video_url = f"https://www.youtube.com/shorts/{video_id}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/140.0 Safari/537.36"
        )
    }

    for attempt in range(max_attempts):
        try:
            response = requests.get(
                video_url,
                headers=headers if attempt == 0 else {},
                timeout=SHORTS_TIMEOUT_SECONDS
            )

            response.raise_for_status()
            final_url = urlparse(response.url)
            # Consent and unrelated redirects do not identify the video
            # format, even when the HTTP request itself succeeded.
            if final_url.hostname not in YOUTUBE_HOSTS:
                continue
            if final_url.path.rstrip("/") == f"/shorts/{video_id}":
                return True
            if final_url.path == "/watch" and parse_qs(final_url.query).get("v") == [video_id]:
                return False

        except (requests.RequestException, ValueError) as error:
            logger.warning(
                "Shorts check failed for %s (attempt %s/%s): %s",
                video_id, attempt + 1, max_attempts, error,
            )

    return None
