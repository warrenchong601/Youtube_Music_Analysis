import pandas as pd

from src import analysis


# ============================================================
# Analysis Pipeline
# ============================================================

def prepare_analysis_dataframe(
    music_dataframe: pd.DataFrame,
    use_personal_overrides: bool = True,
) -> pd.DataFrame:
    """Add derived fields required by the analysis functions."""

    # Derived columns should not alter the caller's original watch records.
    music_dataframe = music_dataframe.copy()
    # Convert to UTC before removing timezone information so weekly
    # periods and other date groupings use the same reference time.
    if music_dataframe["watched_at"].dt.tz is not None:
        music_dataframe["watched_at"] = (
            music_dataframe["watched_at"]
            .dt.tz_convert("UTC")
            .dt.tz_localize(None)
        )

    music_dataframe = analysis.add_duration_seconds(
        music_dataframe
    )

    music_dataframe = analysis.add_adjusted_duration(
        music_dataframe, use_personal_overrides=use_personal_overrides
    )

    music_dataframe = analysis.add_session_ids(
        music_dataframe
    )

    music_dataframe = analysis.add_week_period(
        music_dataframe
    )

    return music_dataframe

def run_music_analysis(music_dataframe: pd.DataFrame):
    """Calculate the statistics exposed by the music analysis."""

    analysis_results = {
        "summary": analysis.get_listening_summary(music_dataframe),

        "top_songs": analysis.get_top_songs(music_dataframe),
        "top_channels": analysis.get_top_channels(music_dataframe),

        "song_concentration":
            analysis.get_top_song_concentration(music_dataframe),

        "total_listening_seconds":
            analysis.get_total_listening_seconds(music_dataframe),

        "listens_by_hour":
            analysis.get_listens_by_hour(music_dataframe),

        "listens_by_weekday":
            analysis.get_listens_by_weekday(music_dataframe),

        "listens_by_date":
            analysis.get_listens_by_date(music_dataframe),

        "sessions":
            analysis.get_session_summary(music_dataframe),

        "largest_session":
            analysis.get_largest_session(music_dataframe),

        "longest_session":
            analysis.get_longest_session(music_dataframe),

        "top_songs_by_week":
            analysis.get_top_songs_by_week(music_dataframe),
    }

    return analysis_results
