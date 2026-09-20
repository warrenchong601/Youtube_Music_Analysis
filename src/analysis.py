import pandas as pd
import re

# ============================================================
# Analysis Configuration
# ============================================================

# Google Takeout records when a video was watched, but not how long it was actually played.
# These dataset-specific exceptions replace the full video duration with manually estimated listening durations.
DURATION_EXCEPTIONS = {
    "Prison Labor - Persona 5 Royal OST [Extended]": 10 * 60,
    "that one dinky ass kirby song except it loops": 12 * 60,
    "POV: you're in love with a memory | Playlist": 2 * 60,
    "Mobile Suit Gundam Iron Blooded Orphans Urdr Hunt OST - Red vs Blue [Extended]": 2 * 60,
    "At Bantam 🍷✨ Yakuza Bar/Cafe OST Mix": 5 * 60,
    "Pokemon Black and White - Low HP Music EXTENDED": 2 * 60,
    "57 minutes of silence occasionally interrupted by weird route cue": 2 * 60,
    "Go To Sleep, She Isn't Coming Back.": 2 * 60,
    "Coldplay – Viva La Vida Loop on Cat Piano ($1000 request)": 2 * 60,
    "【YOASOBI🌷】全有名曲メドレー ｜Study with me｜Work with me｜リラックスタイム｜安眠・癒し・作業用BGM｜勉強用BGM｜AnnieChan_playlist ⑤": 10 * 60
}

WEEKDAY_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

SESSION_GAP_MINUTES = 30


# ============================================================
# Basic Listening Statistics
# ============================================================
def get_listening_summary(music_dataframe):
    music_plays = len(music_dataframe)
    unique_videos = music_dataframe["video_ids"].nunique()
    unique_channels = music_dataframe["channel_id"].nunique()

    listening_summary = {
        "music_plays" : music_plays,
        "unique_videos" : unique_videos,
        "unique_channels" : unique_channels,
    }

    return listening_summary

def get_top_songs(music_dataframe, limit = 10):
    title_counts = music_dataframe["title"].value_counts().head(limit)

    return title_counts

def get_top_channels(music_dataframe, limit = 10):
    channel_counts = music_dataframe["channel"].value_counts().head(limit)

    return channel_counts

def get_top_song_concentration(music_dataframe, limits= (1,3,5,10,25)):
    title_counts = music_dataframe["title"].value_counts()
    total_plays = title_counts.sum()

    concentration_stats = {}

    for limit in limits:
        top_n_plays = title_counts.head(limit).sum()
        top_n_plays_percentage = top_n_plays / total_plays * 100

        concentration_stats[limit] = {
            "plays": top_n_plays,
            "percentage": top_n_plays_percentage,
        }

    return concentration_stats

# ============================================================
# Listening Duration Analysis
# ============================================================
def convert_iso8601_to_seconds(duration):
    match = re.match(
        r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",
        duration
    )

    duration_parts = match.groups()

    seconds = 0
    multipliers = [3600, 60, 1]

    for index in range(3):
        if duration_parts[index] is not None:
            seconds += int(duration_parts[index]) * multipliers[index]

    return seconds

def convert_seconds_to_hms(seconds):
    seconds = int(seconds)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    return f"{hours:02d}H:{minutes:02d}M:{seconds:02d}S"

def add_duration_seconds(music_dataframe):
    music_dataframe["duration_seconds"] = (
        music_dataframe["video_duration"]
        .apply(convert_iso8601_to_seconds)
    )

    return music_dataframe

def add_adjusted_duration(music_dataframe):
    music_dataframe["adjusted_duration_seconds"] = (
        music_dataframe["duration_seconds"].copy()
    )

    for title, adjusted_duration in DURATION_EXCEPTIONS.items():
        music_dataframe.loc[
            music_dataframe["title"] == title,
            "adjusted_duration_seconds"
        ] = adjusted_duration

    return music_dataframe

def get_total_listening_seconds(music_dataframe):
    return music_dataframe["adjusted_duration_seconds"].sum()
# ============================================================
# Temporal Analysis
# ============================================================

def get_listens_by_hour(music_dataframe):
    hourly_counts = (
        music_dataframe["watched_at"]
        .dt.hour
        .value_counts()
        .sort_index()
    )

    return hourly_counts

def get_listens_by_weekday(music_dataframe):
    weekday_counts = (
        music_dataframe["watched_at"]
        .dt.day_name()
        .value_counts()
    )

    return weekday_counts.reindex(WEEKDAY_ORDER, fill_value=0)

def get_listens_by_date(music_dataframe):
    daily_counts = (
        music_dataframe["watched_at"]
        .dt.date
        .value_counts()
        .sort_index()
    )

    return daily_counts

# ============================================================
# Listening Session Analysis
# ============================================================

def add_session_ids(music_dataframe):
    time_gaps = music_dataframe["watched_at"].diff()

    new_session = time_gaps > pd.Timedelta(
        minutes=SESSION_GAP_MINUTES
    )

    new_session.iloc[0] = True

    music_dataframe["session_id"] = new_session.cumsum()

    return music_dataframe

def get_events_per_session(music_dataframe):
    events_per_session = (
        music_dataframe
        .groupby("session_id")
        .size()
    )

    return events_per_session

def get_listening_time_per_session(music_dataframe):
    listening_time_per_session = (
        music_dataframe
        .groupby("session_id")["adjusted_duration_seconds"]
        .sum()
    )

    return listening_time_per_session

def get_session_summary(music_dataframe):
    events_per_session = get_events_per_session(music_dataframe)
    time_per_session = get_listening_time_per_session(music_dataframe)

    session_summary = {
        "total_sessions": music_dataframe["session_id"].nunique(),
        "average_events": events_per_session.mean(),
        "median_events": events_per_session.median(),
        "largest_session_events": events_per_session.max(),
        "average_session_seconds": time_per_session.mean(),
        "longest_session_seconds": time_per_session.max(),
    }

    return session_summary

def get_session_details(music_dataframe, session_id):
    session = music_dataframe[
        music_dataframe["session_id"] == session_id
    ]

    top_songs = (
        session["title"]
        .value_counts()
        .head(5)
    )

    return {
        "session_id": session_id,
        "date": session["watched_at"].iloc[0].date(),
        "start_time": session["watched_at"].min(),
        "end_time": session["watched_at"].max(),
        "events": len(session),
        "listening_seconds": session["adjusted_duration_seconds"].sum(),
        "top_songs": top_songs.to_dict(),
    }

def get_largest_session(music_dataframe):
    events_per_session = get_events_per_session(music_dataframe)

    largest_session_id = events_per_session.idxmax()

    return get_session_details(
        music_dataframe,
        largest_session_id
    )

def get_longest_session(music_dataframe):
    time_per_session = get_listening_time_per_session(music_dataframe)

    longest_session_id = time_per_session.idxmax()

    return get_session_details(
        music_dataframe,
        longest_session_id
    )

# ============================================================
# Listening Trend Analysis - Weekly groupings are used to track changes in song popularity over time.
# ============================================================

def add_week_period(music_dataframe):
    music_dataframe["week"] = (
        music_dataframe["watched_at"]
        .dt.to_period("W")
    )

    return music_dataframe

def get_weekly_song_counts(music_dataframe):
    weekly_song_counts = (
        music_dataframe
        .groupby(["week", "title"])
        .size()
    )

    return weekly_song_counts

def get_top_songs_by_week(music_dataframe, limit=5):
    weekly_song_counts = get_weekly_song_counts(music_dataframe)

    top_weekly_songs = (
        weekly_song_counts
        .groupby(level="week", group_keys=False)
        .nlargest(limit)
    )

    return top_weekly_songs

def get_song_weekly_trend(music_dataframe, title):
    weekly_song_counts = get_weekly_song_counts(
        music_dataframe
    )

    all_weeks = (
        music_dataframe["week"]
        .sort_values()
        .unique()
    )

    try:
        song_trend = weekly_song_counts.xs(
            title,
            level="title"
        )
    except KeyError:
        return pd.Series(
            0,
            index=all_weeks,
            dtype=int
        )

    return song_trend.reindex(
        all_weeks,
        fill_value=0
    )
def get_song_loyalty_summary(music_dataframe):
    song_counts = music_dataframe["title"].value_counts()

    one_time_songs = (song_counts == 1).sum()
    repeated_songs = (song_counts > 1).sum()

    total_plays = song_counts.sum()
    first_plays = len(song_counts)
    repeat_plays = total_plays - first_plays

    return {
        "unique_songs": len(song_counts),
        "one_time_songs": one_time_songs,
        "repeated_songs": repeated_songs,
        "first_plays": first_plays,
        "repeat_plays": repeat_plays,
        "repeat_play_percentage": repeat_plays / total_plays * 100,
    }

def get_song_week_persistence(music_dataframe, limit=10):
    weekly_song_counts = get_weekly_song_counts(music_dataframe)

    weeks_per_song = (
        weekly_song_counts
        .groupby(level="title")
        .size()
        .sort_values(ascending=False)
        .head(limit)
    )

    return weeks_per_song

def get_song_rankings_by_week(music_dataframe, limit=5):
    dataframe = music_dataframe.copy()

    dataframe["week"] = (
        dataframe["watched_at"]
        .dt.to_period("W")
    )

    # Find overall top songs
    top_songs = (
        dataframe["title"]
        .value_counts()
        .head(limit)
        .index
    )

    # Count every song within every week
    weekly_song_counts = (
        dataframe
        .groupby(["week", "title"])
        .size()
        .rename("plays")
        .reset_index()
    )

    # Rank ALL songs within each week
    weekly_song_counts["rank"] = (
        weekly_song_counts
        .groupby("week")["plays"]
        .rank(method="min", ascending=False)
    )

    # Only keep our overall top songs
    rankings = weekly_song_counts[
        weekly_song_counts["title"].isin(top_songs)
    ].copy()

    rankings["rank"] = rankings["rank"].astype(int)

    return rankings