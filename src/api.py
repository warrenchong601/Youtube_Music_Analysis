import logging
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src import analysis, analysis_pipeline
from src.imports import dataset_path, router as imports_router

# ============================================================
# API Configuration
# ============================================================

logger = logging.getLogger(__name__)

app = FastAPI()
app.include_router(imports_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MUSIC_HISTORY_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "music_history.csv"
)

@app.get("/")
def root():
    return {
        "message": "YouTube Music Analysis API"
    }

# ============================================================
# Dataset Loading and Response Helpers
# ============================================================


def load_music_data(x_dataset_token: str | None = Header(default=None)):
    # An invalid import token must fail instead of showing the original
    # report, which would make the user think their upload had succeeded.
    history_path = dataset_path(x_dataset_token) if x_dataset_token else MUSIC_HISTORY_PATH
    try:
        music_dataframe = pd.read_csv(history_path, parse_dates=["watched_at"])
        music_dataframe["watched_at"] = pd.to_datetime(
            music_dataframe["watched_at"], utc=bool(x_dataset_token)
        )
        # The original report's manual duration estimates are personal
        # to that dataset and must not carry over to uploaded histories.
        return analysis_pipeline.prepare_analysis_dataframe(
            music_dataframe, use_personal_overrides=not x_dataset_token
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        logger.exception("Could not load music history")
        raise HTTPException(500, "Could not load music history. Check the server report file.") from error


# Convert pandas counts to ordinary integers at the API boundary so
# responses remain JSON-compatible without changing the analysis results.
def serialize_counts(counts: pd.Series, label_key: str, count_key: str = "plays") -> list[dict]:
    return [
        {label_key: label, count_key: int(count)}
        for label, count in counts.items()
    ]

# ============================================================
# Listening Statistics Routes
# ============================================================


@app.get("/api/summary")
def get_summary(music_dataframe=Depends(load_music_data)):
    analysis_results = analysis_pipeline.run_music_analysis(music_dataframe)

    return analysis_results["summary"]

@app.get("/api/listening-time")
def get_listening_time(music_dataframe=Depends(load_music_data)):

    total_seconds = analysis.get_total_listening_seconds(music_dataframe)

    return {
        "total_seconds": int(total_seconds),
        "formatted_time": analysis.convert_seconds_to_hms(total_seconds)
    }

@app.get("/api/top-songs")
def get_top_songs(limit: int = 10, music_dataframe=Depends(load_music_data)):

    top_songs = analysis.get_top_songs(music_dataframe, limit)

    return serialize_counts(top_songs, "title")

@app.get("/api/song-concentration")
def get_song_concentration(music_dataframe=Depends(load_music_data)):

    concentration = analysis.get_top_song_concentration(
        music_dataframe
    )

    concentration_data = []

    for limit, statistics in concentration.items():
        concentration_data.append({
            "top_n": int(limit),
            "plays": int(statistics["plays"]),
            "percentage": float(statistics["percentage"])
        })

    return concentration_data

@app.get("/api/top-channels")
def get_top_channels(music_dataframe=Depends(load_music_data)):

    top_channels = analysis.get_top_channels(music_dataframe)

    return serialize_counts(top_channels, "channel")

# ============================================================
# Temporal Analysis Routes
# ============================================================

@app.get("/api/listening-by-hour")
def get_listening_by_hour(music_dataframe=Depends(load_music_data)):

    hourly_counts = analysis.get_listens_by_hour(music_dataframe)

    hourly_data = []

    for hour, plays in hourly_counts.items():
        hourly_data.append({
            "hour": int(hour),
            "plays": int(plays)
        })

    return hourly_data

@app.get("/api/listening-by-weekday")
def get_listening_by_weekday(music_dataframe=Depends(load_music_data)):

    weekday_counts = analysis.get_listens_by_weekday(music_dataframe)

    return serialize_counts(weekday_counts, "weekday")

@app.get("/api/listening-by-date")
def get_listening_by_date(music_dataframe=Depends(load_music_data)):

    date_counts = analysis.get_listens_by_date(music_dataframe)

    date_data = []
    for date, plays in date_counts.items():
        date_data.append({
            "date": date.isoformat(),
            "plays": int(plays)
        })

    return date_data

@app.get("/api/listening-by-week")
def get_listening_by_week(limit: int = 5, music_dataframe=Depends(load_music_data)):
    if music_dataframe.empty:
        return []

    weekly_songs = analysis.get_top_songs_by_week(music_dataframe, limit)

    weekly_data = []

    for week in weekly_songs.index.get_level_values("week").unique():
        week_songs = weekly_songs.loc[week]

        songs = serialize_counts(week_songs, "title")
        weekly_data.append({
            "week": str(week),
            "songs": songs
        })

    return weekly_data

# ============================================================
# Listening Session Routes
# ============================================================

@app.get("/api/sessions")
def get_sessions(music_dataframe=Depends(load_music_data)):

    session_summary = analysis.get_session_summary(music_dataframe)

    return {
        "total_sessions": int(session_summary["total_sessions"]),
        "average_events": float(session_summary["average_events"]),
        "median_events": float(session_summary["median_events"]),
        "largest_session_events": int(session_summary["largest_session_events"]),
        "average_sessions_seconds": float(session_summary["average_session_seconds"]),
        "longest_session_seconds": int(session_summary["longest_session_seconds"]),
    }

def serialize_session(session):
    if session is None:
        return None
    return {
        "session_id": int(session["session_id"]),
        "date": session["date"].isoformat(),
        "start_time": session["start_time"].isoformat(),
        "end_time": session["end_time"].isoformat(),
        "events": int(session["events"]),
        "listening_seconds": int(session["listening_seconds"]),
        "formatted_listening_time": analysis.convert_seconds_to_hms(
            session["listening_seconds"]
        ),
        "top_songs": {
            title: int(plays)
            for title, plays in session["top_songs"].items()
        },
    }

@app.get("/api/session-highlights")
def get_session_highlights(music_dataframe=Depends(load_music_data)):

    largest_session = analysis.get_largest_session(music_dataframe)

    longest_session = analysis.get_longest_session(music_dataframe)

    return {
        "largest_session": serialize_session(largest_session),
        "longest_session": serialize_session(longest_session),
    }

# ============================================================
# Song Loyalty and Trend Routes
# ============================================================

@app.get("/api/loyalty")
def get_loyalty(music_dataframe=Depends(load_music_data)):

    loyalty = analysis.get_song_loyalty_summary(music_dataframe)

    return {
        "unique_songs": int(loyalty["unique_songs"]),
        "one_time_songs": int(loyalty["one_time_songs"]),
        "repeated_songs": int(loyalty["repeated_songs"]),
        "first_plays": int(loyalty["first_plays"]),
        "repeat_plays": int(loyalty["repeat_plays"]),
        "repeat_play_percentage": float(
            loyalty["repeat_play_percentage"]
        ),
    }

@app.get("/api/persistent-songs")
def get_persistent_songs(limit: int = 10, music_dataframe=Depends(load_music_data)):

    persistent_songs = analysis.get_song_week_persistence(music_dataframe, limit)

    return serialize_counts(persistent_songs, "title", "weeks")

@app.get("/api/song-trend")
def get_song_trend(title: str, music_dataframe=Depends(load_music_data)):

    song_trend = analysis.get_song_weekly_trend(music_dataframe, title)

    trend_data = []

    for week, plays in song_trend.items():
        trend_data.append({
            "week": str(week),
            "plays": int(plays)
        })

    return {
        "title": title,
        "trend_data": trend_data
    }

@app.get("/api/song-rankings-by-week")
def get_song_rankings_by_week(limit: int = 5, music_dataframe=Depends(load_music_data)):

    rankings = analysis.get_song_rankings_by_week(
        music_dataframe,
        limit
    )

    ranking_data = []

    for _, row in rankings.iterrows():
        ranking_data.append({
            "week": str(row["week"]),
            "title": row["title"],
            "plays": int(row["plays"]),
            "rank": int(row["rank"])
        })

    return ranking_data


# Serve the dashboard from the same origin as the API.
app.mount("/dashboard", StaticFiles(directory=PROJECT_ROOT / "frontend", html=True), name="dashboard")
