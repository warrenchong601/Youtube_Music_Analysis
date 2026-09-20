from bs4 import BeautifulSoup
import pandas as pd

def parse_watch_history(watch_path):
    watch_records = []

    if not watch_path.is_file():
        print(f"HTML File at {watch_path} Not Found")
        return

    html_content = watch_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_content, "lxml")
    history_cards = soup.select("div.outer-cell")

    for card in history_cards:
        content_cell = card.select_one("div.content-cell")
        record_parts = list(content_cell.stripped_strings)
        links = content_cell.select("a")

        if len(record_parts) not in (3, 4):
            continue

        if record_parts[0] != "Watched":
            continue

        if len(record_parts) == 4:
            record = {
                "action": record_parts[0],
                "title": record_parts[1],
                "channel": record_parts[2],
                "watched_at": record_parts[3],
                "video_url": links[0].get("href"),
            }

        elif len(record_parts) == 3:
            record = {
                "action": record_parts[0],
                "title": record_parts[1],
                "channel": None,
                "watched_at": record_parts[2],
                "video_url": links[0].get("href"),
            }

        watch_records.append(record)

    print("Records successfully retrieved from HTML File!")
    return watch_records

def create_dataframe(watch_records):
    watch_records_dataframe = pd.DataFrame(watch_records)

    return watch_records_dataframe

def remove_missing_channel_records(watch_records_dataframe):
    valid_channel_records = watch_records_dataframe[watch_records_dataframe["channel"].notna()]

    watch_records_dataframe = valid_channel_records

    watch_records_dataframe = watch_records_dataframe.reset_index(drop=True)

    return watch_records_dataframe

def convert_watch_timestamps(watch_records_dataframe):
    converted_watched_at_entries = pd.to_datetime(watch_records_dataframe["watched_at"].str[:-4], dayfirst=True)

    watch_records_dataframe["watched_at"] = converted_watched_at_entries

    return watch_records_dataframe

def add_video_id_column(watch_records_dataframe):
    video_ids = watch_records_dataframe["video_url"].str.split("v=").str[1]

    watch_records_dataframe["video_ids"] = video_ids

    return watch_records_dataframe

def stage_one_clean(watch_records_dataframe):
    # Removes Ads/Privated videos by checking for videos without a channel
    watch_records_dataframe = remove_missing_channel_records(watch_records_dataframe)

    #Removes timestamps from "watched_at" for future data analysis
    watch_records_dataframe = convert_watch_timestamps(watch_records_dataframe)

    watch_records_dataframe =  add_video_id_column(watch_records_dataframe)

    return watch_records_dataframe

