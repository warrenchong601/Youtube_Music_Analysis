
from src import classifier, music_export, youtube_api

# ============================================================
# Music Classification Pipeline
# ============================================================

# Classify music from cleaned watch history and export the final dataset.
def run_music_pipeline(records_dataframe, output_path):

    # Retrieve YouTube metadata and select Category 10 music candidates.
    music_candidates = []
    for batch in youtube_api.create_video_batches(records_dataframe):
        metadata = youtube_api.fetch_video_metadata(batch)
        music_candidates.extend(classifier.extract_music_candidates(metadata))

    print(f"Category 10 candidates: {len(music_candidates)}")
    print(
        f"Unique Category 10 videos: "
        f"{len({candidate['video_ID'] for candidate in music_candidates})}"
    )

    # Remove Shorts that may be classified as music due to their backing audio.
    non_short_candidates = classifier.remove_shorts_video_candidates(music_candidates, youtube_api.is_short)

    print(f"Non-short candidates: {len(non_short_candidates)}")
    print(
        f"Unique non-short videos: "
        f"{len({candidate['video_ID'] for candidate in non_short_candidates})}"
    )

    # Retrieve channel metadata once per unique candidate channel.
    channel_ids = {candidate["channel_id"] for candidate in non_short_candidates}
    music_channel_ids = set()

    for batch in youtube_api.create_channel_batches(channel_ids):
        metadata = youtube_api.fetch_channel_metadata(batch)
        music_channel_ids.update(classifier.extract_music_channel_ids(metadata))

    print(f"Unique candidate channels: {len(channel_ids)}")

    # Combine channel, title and description evidence into a final decision
    classified_candidates = classifier.classify_candidates(
        non_short_candidates,
        music_channel_ids
    )

    print(f"Music channels identified: {len(music_channel_ids)}")

    # Rejoin accepted music videos with the original watch events and export.
    music_dataframe = music_export.export_music_history(
        records_dataframe,
        classified_candidates,
        output_path
    )

    from collections import Counter

    classification_counts = Counter(
        candidate["classification"]
        for candidate in classified_candidates
    )

    print(f"Final music watch events: {len(music_dataframe)}")
    print(f"Final unique music videos: {music_dataframe['video_ids'].nunique()}")

    print("Classification counts:")
    print(classification_counts)

    # Return all decisions too, so review/non_music records remain inspectable.
    return music_dataframe, classified_candidates
