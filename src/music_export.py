
from pathlib import Path

import pandas as pd


# ============================================================
# Export Configuration
# ============================================================

# Only accepted music classifications are included in the final dataset.
MUSIC_CLASSIFICATIONS = ["confirmed_music", "probable_music"]

# Metadata retained from the classification pipeline when rebuilding the listening history.
METADATA_COLUMNS = [
    "video_title", "video_ID", "channel_name", "channel_id", "description", "video_duration",
    "classification", "classification_reason", "classification_evidence",
]

# ============================================================
# Music History DataFrame Creation
# ============================================================

# Join accepted music metadata back onto every matching watch event.
def create_music_dataframe(records_dataframe, classified_candidates):

    music_candidates = [
        candidate for candidate in classified_candidates
        if candidate["classification"] in MUSIC_CLASSIFICATIONS
    ]

    # Remove duplicate video metadata before merging,
    # while preserving repeated watches of the same video in the listening history.

    music_metadata_dataframe = (pd.DataFrame( music_candidates, columns=METADATA_COLUMNS)
                                .drop_duplicates(subset="video_ID")
                                .reset_index(drop=True))

    music_dataframe = pd.merge(
        records_dataframe,
        music_metadata_dataframe,
        left_on="video_ids",
        right_on="video_ID",
        how="inner",
        validate="many_to_one",
    )

    music_dataframe["channel"] = music_dataframe["channel"].fillna(music_dataframe["channel_name"])
    return (
        music_dataframe.drop(columns=[
            "video_title", "video_ID", "channel_name", "description", "action"
        ])
        .sort_values("watched_at")
        .reset_index(drop=True)
    )

# ============================================================
# Music History Export
# ============================================================

def export_music_history(records_dataframe, classified_candidates, output_path):
    """Save without a pandas index and return the exported DataFrame."""
    music_dataframe = create_music_dataframe(
        records_dataframe, classified_candidates
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    music_dataframe.to_csv(output_path, index=False)
    return music_dataframe
