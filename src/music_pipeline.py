import re
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from src import classifier, music_export, youtube_api

# ============================================================
# Pipeline Configuration
# ============================================================

MAX_SHORT_SECONDS = 180
DURATION_PATTERN = r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
DURATION_MULTIPLIERS = (3600, 60, 1)

# ============================================================
# Music Candidate Collection
# ============================================================

# Classify each distinct video once, then restore every listening event.
def fetch_music_candidates(records_dataframe: pd.DataFrame, progress: Callable[[str], None]) -> list[dict]:
    unique_videos = records_dataframe.drop_duplicates("video_ids").reset_index(drop=True)
    video_batches = youtube_api.create_video_batches(unique_videos)
    music_candidates = []

    for index, video_batch in enumerate(video_batches, 1):
        progress(f"Fetching video metadata: batch {index}/{len(video_batches)}")
        video_metadata = youtube_api.fetch_video_metadata(video_batch)
        music_candidates.extend(classifier.extract_music_candidates(video_metadata))

    return music_candidates

# ============================================================
# Shorts Filtering
# ============================================================


def get_short_status(candidate: dict, source_shorts: set[str]) -> bool | None:
    labelled_short = re.search(r"#shorts?\b", candidate["video_title"], re.IGNORECASE)
    duration_match = re.fullmatch(DURATION_PATTERN, candidate["video_duration"])
    duration_seconds = None
    if duration_match:
        duration_seconds = sum(
            int(value or 0) * multiplier
            for value, multiplier in zip(duration_match.groups(), DURATION_MULTIPLIERS)
        )

    # Explicit Short labels take precedence over the duration shortcut;
    # only candidates without that evidence can skip the redirect check.
    if labelled_short or candidate["video_ID"] in source_shorts:
        return True
    if duration_seconds is not None and duration_seconds > MAX_SHORT_SECONDS:
        # Shorts are at most three minutes. Shorter duration alone proves nothing.
        return False
    return youtube_api.is_short(candidate["video_ID"])


def filter_short_candidates(
    music_candidates: list[dict],
    source_shorts: set[str],
    progress: Callable[[str], None],
) -> tuple[list[dict], list[dict]]:
    accepted_candidates = []
    excluded_candidates = []

    for index, candidate in enumerate(music_candidates, 1):
        progress(f"Checking video format: {index}/{len(music_candidates)}")
        short_status = get_short_status(candidate, source_shorts)
        # None means unverified, not long-form. Accept only a definite
        # False and retain inconclusive checks in the decision report.
        if short_status is False:
            candidate["short_status"] = "not_short"
            accepted_candidates.append(candidate)
            continue

        candidate["short_status"] = "short" if short_status is True else "unknown"
        excluded_candidates.append({
            **candidate,
            "classification": "excluded_short" if short_status is True else "review",
            "classification_reason": "short_format" if short_status is True else "short_check_inconclusive",
            "classification_evidence": candidate["short_status"],
        })

    return accepted_candidates, excluded_candidates

# ============================================================
# Channel Evidence and Pipeline
# ============================================================


def fetch_music_channel_ids(candidates: list[dict], progress: Callable[[str], None]) -> set[str]:
    channel_ids = {candidate["channel_id"] for candidate in candidates}
    music_channel_ids = set()
    for channel_batch in youtube_api.create_channel_batches(channel_ids):
        progress("Checking music channels")
        channel_metadata = youtube_api.fetch_channel_metadata(channel_batch)
        music_channel_ids.update(classifier.extract_music_channel_ids(channel_metadata))
    return music_channel_ids


def run_music_pipeline(
    records_dataframe: pd.DataFrame,
    output_path: str | Path,
    progress: Callable[[str], None] = print,
) -> tuple[pd.DataFrame, list[dict]]:
    music_candidates = fetch_music_candidates(records_dataframe, progress)
    # Inspect every watch URL: deduplicating first could discard a Shorts
    # URL when the same video also appeared through a normal watch link.
    source_shorts = set(records_dataframe.loc[
        records_dataframe["video_url"].str.contains(r"/shorts/", na=False),
        "video_ids",
    ])
    accepted_candidates, excluded_candidates = filter_short_candidates(
        music_candidates, source_shorts, progress
    )
    music_channel_ids = fetch_music_channel_ids(accepted_candidates, progress)
    classified_candidates = classifier.classify_candidates(accepted_candidates, music_channel_ids)

    progress("Building listening report")
    music_dataframe = music_export.export_music_history(
        records_dataframe, classified_candidates, output_path
    )
    return music_dataframe, classified_candidates + excluded_candidates
