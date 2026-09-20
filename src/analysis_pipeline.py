from src import analysis


# ============================================================
# Analysis Pipeline
# ============================================================

def prepare_analysis_dataframe(music_dataframe):
    """Add derived fields required by the analysis functions."""

    music_dataframe = analysis.add_duration_seconds(
        music_dataframe
    )

    music_dataframe = analysis.add_adjusted_duration(
        music_dataframe
    )

    music_dataframe = analysis.add_session_ids(
        music_dataframe
    )

    music_dataframe = analysis.add_week_period(
        music_dataframe
    )

    return music_dataframe

def run_music_analysis(music_dataframe):
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