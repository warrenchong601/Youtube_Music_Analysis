from pathlib import Path

from src import analysis, analysis_pipeline, google_takeout, music_pipeline


# ============================================================
# Command-Line Report
# ============================================================


def print_analysis_summary(analysis_results: dict) -> None:
    """Display the completed report for command-line users."""

    print("\n-------------------------------------------------------------")
    print("Analysis Results")
    print("-------------------------------------------------------------")

    summary = analysis_results["summary"]

    print("\n## Listening Summary")
    print(f"Total music plays: {summary['music_plays']}")
    print(f"Unique videos: {summary['unique_videos']}")
    print(f"Unique channels: {summary['unique_channels']}")

    print("\n## Listening Time")
    total_seconds = analysis_results["total_listening_seconds"]

    print(
        "Adjusted estimated listening time:",
        analysis.convert_seconds_to_hms(total_seconds)
    )

    print("\n## Top 5 Songs")
    print(analysis_results["top_songs"].head(5))

    print("\n## Top 5 Channels")
    print(analysis_results["top_channels"].head(5))

    print("\n## Session Statistics")
    session_summary = analysis_results["sessions"]

    print(f"Total sessions: {session_summary['total_sessions']}")
    print(
        f"Average events per session: "
        f"{session_summary['average_events']:.1f}"
    )
    print(
        f"Median events per session: "
        f"{session_summary['median_events']:.1f}"
    )
    print(
        f"Largest session: "
        f"{session_summary['largest_session_events']} events"
    )
    print(
        "Average estimated session listening time:",
        analysis.convert_seconds_to_hms(
            session_summary["average_session_seconds"]
        )
    )
    print(
        "Longest estimated session listening time:",
        analysis.convert_seconds_to_hms(
            session_summary["longest_session_seconds"]
        )
    )

    print("\n## Largest Session by Events")
    print(analysis_results["largest_session"])

    print("\n## Longest Session by Listening Time")
    print(analysis_results["longest_session"])


def main() -> None:
    print("-------------------------------------------------------------")
    print("YouTube Music Analysis")
    print("-------------------------------------------------------------")

    # --------------------------------------------------------
    # Project Paths
    # --------------------------------------------------------

    # Resolve data paths from this file so the command can be launched
    # from a different working directory without selecting another dataset.
    project_root = Path(__file__).resolve().parent.parent

    watch_path = (
        project_root
        / "data"
        / "raw"
        / "watch-history.html"
    )

    music_history_path = (
        project_root
        / "data"
        / "processed"
        / "music_history.csv"
    )

    # --------------------------------------------------------
    # Google Takeout Parsing
    # --------------------------------------------------------

    print("\n## Parsing Google Takeout watch history")

    watch_history = google_takeout.parse_watch_history(
        watch_path
    )

    records_dataframe = google_takeout.create_dataframe(
        watch_history
    )

    records_dataframe = google_takeout.stage_one_clean(
        records_dataframe
    )

    print(
        f"Cleaned watch history contains "
        f"{len(records_dataframe)} records"
    )

    # --------------------------------------------------------
    # Music Classification Pipeline
    # --------------------------------------------------------

    print("\n## Running music classification pipeline")

    music_dataframe, classified_candidates = (
        music_pipeline.run_music_pipeline(
            records_dataframe,
            music_history_path
        )
    )

    print(
        f"Music history contains "
        f"{len(music_dataframe)} listening events"
    )

    print(
        f"Classified {len(classified_candidates)} "
        f"music candidates"
    )

    # --------------------------------------------------------
    # Analysis Preparation
    # --------------------------------------------------------

    print("\n## Preparing music data for analysis")

    music_dataframe = (
        analysis_pipeline.prepare_analysis_dataframe(
            music_dataframe
        )
    )

    # --------------------------------------------------------
    # Music Analysis
    # --------------------------------------------------------

    print("\n## Running music analysis")

    analysis_results = (
        analysis_pipeline.run_music_analysis(
            music_dataframe
        )
    )

    # --------------------------------------------------------
    # Analysis Summary
    # --------------------------------------------------------

    print_analysis_summary(analysis_results)


if __name__ == "__main__":
    main()
