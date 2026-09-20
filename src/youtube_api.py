import os
import requests
from dotenv import load_dotenv

# ============================================================
# API Configuration
# ============================================================

load_dotenv()

API_KEY = os.getenv("YOUTUBE_API_KEY")
if not API_KEY:
    raise ValueError("YOUTUBE_API_KEY was not found in the environment.")

YOUTUBE_VIDEOS_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNELS_ENDPOINT = "https://www.googleapis.com/youtube/v3/channels"

BATCH_SIZE = 50

# ============================================================
# Video Metadata Requests
# ============================================================

# The YouTube Data API accepts up to 50 video IDs in a single videos.list
# request, so IDs are combined into comma-separated batches.
def create_video_batches(dataframe):
    combined_video_ids_batch = []

    for start_index in range(0, len(dataframe), BATCH_SIZE):
        video_ids_batch = dataframe["video_ids"][
            start_index:start_index + BATCH_SIZE
        ]

        combined_video_ids = ",".join(video_ids_batch)
        combined_video_ids_batch.append(combined_video_ids)

    return combined_video_ids_batch

def create_video_request(video_ids):
    # snippet provides title/channel/category metadata,
    # while contentDetails provides video duration used later in the classification pipeline.
    params_dict = {
        "part": "snippet,contentDetails",
        "id": video_ids,
        "key": API_KEY,
    }

    return params_dict

def fetch_video_metadata(video_id):
    request_params = create_video_request(video_id)

    response = requests.get(url=YOUTUBE_VIDEOS_ENDPOINT, params=request_params)
    response.raise_for_status()

    return response.json()

# ============================================================
# Channel Metadata Requests
# ============================================================

# Channel IDs are batched to reduce the number of API requests required
# when retrieving topic metadata.
def create_channel_batches(channel_ids):
    channel_ids = list(channel_ids)
    channel_id_batches = []

    for start_index in range(0, len(channel_ids), BATCH_SIZE):
        channel_ids_batch = channel_ids[
            start_index:start_index + BATCH_SIZE
        ]

        combined_channel_ids = ",".join(channel_ids_batch)
        channel_id_batches.append(combined_channel_ids)

    return channel_id_batches

def create_channel_request(channel_id):
    # topicDetails provides YouTube topic IDs used to identify music-focused channels.
    channel_params = {
        "part": "snippet,topicDetails",
        "id": channel_id,
        "key": API_KEY,
    }

    return channel_params

def fetch_channel_metadata(channel_id):
    request_params = create_channel_request(channel_id)

    response = requests.get(url=YOUTUBE_CHANNELS_ENDPOINT, params=request_params)

    response.raise_for_status()

    return response.json()

# ============================================================
# YouTube Shorts Detection
# ============================================================

# The YouTube Data API does not directly identify whether a video is a Short.
# Requesting its /shorts/ URL and checking the resulting URL provides a way to distinguish Shorts from normal videos.
def is_short(video_id, max_attempts=2):
    video_url = f"https://www.youtube.com/shorts/{video_id}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/140.0 Safari/537.36"
        )
    }

    for attempt in range(max_attempts):
        try:
            response = requests.get(
                video_url,
                headers=headers,
                timeout=10
            )

            return "/shorts/" in response.url

        except requests.RequestException as error:
            print(
                f"Shorts check failed for {video_id} "
                f"(attempt {attempt + 1}/{max_attempts}): {error}"
            )

    return False

##Filler is_short function to bypass making lots of indivudal calls to Youtube's API slowing down the function
def fake_is_short(video_id):
    return False
