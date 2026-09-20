from fastapi import FastAPI

from pathlib import Path
import pandas as pd

from src import analysis_pipeline
from src import analysis

app = FastAPI()

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MUSIC_HISTORY_PATH = (
    PROJECT_ROOT
    /"data"
    /"processed"
    /"music_history.csv"
)

@app.get("/")
def root():
    return {
        "message": "YouTube Music Analysis API"
    }

def load_music_data():
    music_dataframe = pd.read_csv(MUSIC_HISTORY_PATH, parse_dates=["watched_at"])

    music_dataframe = (analysis_pipeline.prepare_analysis_dataframe(music_dataframe))

    return music_dataframe

@app.get("/api/summary")
def get_summary():
    music_dataframe = load_music_data()
    analysis_results = (analysis_pipeline.run_music_analysis(music_dataframe))

    return analysis_results["summary"]

@app.get("/api/listening-time")
def get_listening_time():
    music_dataframe = load_music_data()

    total_seconds = analysis.get_total_listening_seconds(music_dataframe)

    return{
        "total_seconds": int(total_seconds),
        "formatted_time": analysis.convert_seconds_to_hms(total_seconds)
    }

@app.get("/api/top-songs")
def get_top_songs(limit: int = 10):
    music_dataframe = load_music_data()

    top_songs = analysis.get_top_songs(music_dataframe, limit)

    songs = []

    for title, plays in top_songs.items():
        songs.append({
            "title": title,
            "plays": int(plays)
        })

    return songs

@app.get("/api/song-concentration")
def get_song_concentration():
    music_dataframe = load_music_data()

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
def get_top_channels():
    music_dataframe = load_music_data()

    top_channels = analysis.get_top_channels(music_dataframe)

    channels = []

    for channel, plays in top_channels.items():
        channels.append({
            "channel": channel,
            "plays": int(plays)
        })

    return channels

@app.get("/api/listening-by-hour")
def get_listening_by_hour():
    music_dataframe = load_music_data()

    hourly_counts = analysis.get_listens_by_hour(music_dataframe)

    hourly_data = []

    for hour, plays in hourly_counts.items():
        hourly_data.append({
            "hour": int(hour),
            "plays": int(plays)
        })

    return hourly_data

@app.get("/api/listening-by-weekday")
def get_listening_by_weekday():
    music_dataframe = load_music_data()

    weekday_counts = analysis.get_listens_by_weekday(music_dataframe)

    weekday_data = []
    for weekday, plays in weekday_counts.items():
        weekday_data.append({
            "weekday": weekday,
            "plays": int(plays)
        })

    return weekday_data

@app.get("/api/listening-by-date")
def get_listening_by_date():
    music_dataframe = load_music_data()

    date_counts = analysis.get_listens_by_date(music_dataframe)

    date_data = []
    for date, plays in date_counts.items():
        date_data.append({
            "date": date.isoformat(),
            "plays": int(plays)
        })

    return date_data

@app.get("/api/listening-by-week")
def get_listening_by_week(limit: int = 5):
    music_dataframe = load_music_data()

    weekly_songs = analysis.get_top_songs_by_week(music_dataframe, limit)

    weekly_data = []

    for week in weekly_songs.index.get_level_values("week").unique():
        week_songs = weekly_songs.loc[week]

        songs = []

        for title, plays in week_songs.items():
            songs.append({
                "title": title,
                "plays": int(plays)
            })
        weekly_data.append([{
            "week": str(week),
            "songs": songs
        }])

    return weekly_data

@app.get("/api/sessions")
def get_sessions():
    music_dataframe = load_music_data()

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
def get_session_highlights():
    music_dataframe = load_music_data()

    largest_session = analysis.get_largest_session(music_dataframe)

    longest_session = analysis.get_longest_session(music_dataframe)

    return {
        "largest_session": serialize_session(largest_session),
        "longest_session": serialize_session(longest_session),
    }

@app.get("/api/loyalty")
def get_loyalty():
    music_dataframe = load_music_data()

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
def get_persistent_songs(limit: int = 10):
    music_dataframe = load_music_data()

    persistent_songs = analysis.get_song_week_persistence(music_dataframe, limit)

    songs = []

    for title, weeks in persistent_songs.items():
        songs.append({
            "title": title,
            "weeks": int(weeks)
        })

    return songs

@app.get("/api/song-trend")
def get_song_trend(title: str):
    music_dataframe = load_music_data()

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

