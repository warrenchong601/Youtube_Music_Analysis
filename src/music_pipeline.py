"""Classify each distinct video once, then restore every listening event."""
import re
from src import classifier, music_export, youtube_api

def run_music_pipeline(records_dataframe, output_path, progress=print):
    unique = records_dataframe.drop_duplicates("video_ids").reset_index(drop=True)
    music_candidates = []
    batches = youtube_api.create_video_batches(unique)
    for index, batch in enumerate(batches, 1):
        progress(f"Fetching video metadata: batch {index}/{len(batches)}")
        metadata = youtube_api.fetch_video_metadata(batch)
        music_candidates.extend(classifier.extract_music_candidates(metadata))
    source_shorts = set(records_dataframe.loc[
        records_dataframe["video_url"].str.contains(r"/shorts/", na=False), "video_ids"])
    accepted, excluded = [], []
    for index, candidate in enumerate(music_candidates, 1):
        progress(f"Checking video format: {index}/{len(music_candidates)}")
        labelled = re.search(r"#shorts?\b", candidate["video_title"], re.IGNORECASE)
        duration = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", candidate["video_duration"])
        seconds = sum(int(value or 0) * multiplier for value, multiplier in zip(duration.groups(), (3600, 60, 1))) if duration else None
        if labelled or candidate["video_ID"] in source_shorts:
            status = True
        elif seconds is not None and seconds > 180:
            # Shorts are at most three minutes. Shorter duration alone proves nothing.
            status = False
        else:
            status = youtube_api.is_short(candidate["video_ID"])
        candidate["short_status"] = "short" if status is True else "not_short" if status is False else "unknown"
        if status is False:
            accepted.append(candidate)
        else:
            excluded.append({**candidate, "classification": "excluded_short" if status is True else "review",
                             "classification_reason": "short_format" if status is True else "short_check_inconclusive",
                             "classification_evidence": candidate["short_status"]})
    music_channel_ids = set()
    for batch in youtube_api.create_channel_batches({c["channel_id"] for c in accepted}):
        progress("Checking music channels")
        music_channel_ids.update(classifier.extract_music_channel_ids(youtube_api.fetch_channel_metadata(batch)))
    classified = classifier.classify_candidates(accepted, music_channel_ids)
    progress("Building listening report")
    dataframe = music_export.export_music_history(records_dataframe, classified, output_path)
    return dataframe, classified + excluded
