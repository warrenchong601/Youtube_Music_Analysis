# YouTube Music Analysis

A Python project for exploring my YouTube listening history. It takes a Google
Takeout export, identifies which videos are likely to be music, and displays the
results in a dashboard.

The project started with exploring the data in Jupyter notebooks. I then moved
the parsing, classification and analysis into reusable Python files, added a
FastAPI backend, and built a frontend to display the results.

## What it shows

The dashboard includes:

- Most played songs and channels
- Estimated listening time
- Listening activity by date, hour and weekday
- Listening sessions, including the largest and longest sessions
- How often I return to the same songs
- Weekly favourites and changes in song rankings

You can view the original report or upload your own watch history to generate
another report.

## How it works

1. Read the watch history from a Google Takeout HTML or JSON file.
2. Use the YouTube API to get video and channel metadata.
3. Filter music candidates using YouTube's music category, check for Shorts,
   and classify the remaining videos using their titles, descriptions and channels.
4. Match the accepted videos back to the watch history so repeated listens are
   still counted.
5. Calculate the listening statistics and display them in the dashboard.

The classification is based on rules, so it will not get every video right.
YouTube's music category is a starting point rather than proof that a video is a
song. Videos with an inconclusive Shorts check are left out of the report, but
are not treated as confirmed non-music. A short duration alone does not exclude
a song.

Listening time is also an estimate. Takeout records when a video was watched,
not how much of it was played. My original report includes a few manual duration
adjustments for long videos; these are not applied to uploaded histories.

## Running the project

You will need Python 3.10 or later. From the project folder, install the
dependencies:

```powershell
python -m pip install -r requirements.txt
```

To import or reprocess watch history, create a `.env` file in the project folder
and add your YouTube Data API key:

```dotenv
YOUTUBE_API_KEY=your_api_key_here
```

Keep this key private and do not commit the `.env` file. The existing report can
be viewed without making new YouTube API requests.

Start the backend:

```powershell
python -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```

Then open [the dashboard](http://127.0.0.1:8000/dashboard/) in your browser.
Use a single server worker, as the import queue is managed by that process.

## Using your own history

1. Go to [Google Takeout](https://takeout.google.com/) and export your YouTube
   and YouTube Music watch history. JSON is recommended, but HTML also works.
2. Extract the downloaded archive.
3. Upload `watch-history.json` or `watch-history.html` through the dashboard.
   Upload the history file itself, not the ZIP archive.
4. For HTML exports, choose the timezone used by the export, such as
   `Europe/Dublin`.

The dashboard shows progress while the import runs. It accepts files up to
25 MB and at most 100,000 recognised watch records, with two imports allowed to
run at once. Imported reports use UTC. Records with invalid dates or local times
that cannot be resolved around daylight-saving changes are skipped.

Keep the browser tab open while using your imported report. The tab remembers
which import belongs to you; closing it can lose that reference. Use **Delete my
imported data** when you want to remove the saved report.

The raw upload is not saved to disk. The processed CSV, classification decisions
and import status are saved under `data/imports/` until deleted. Completed imports
can be reopened after a server restart if the tab still has their reference.
Interrupted imports need to be deleted and imported again.

This is intended to run locally. It does not have user accounts, and anyone who
can access the server can view the original report.

## Project structure

- `notebooks/` — the original data exploration and analysis
- `src/google_takeout.py` — reading and cleaning watch history
- `src/youtube_api.py` — YouTube metadata requests and Shorts checks
- `src/classifier.py` — music classification rules
- `src/music_pipeline.py` and `src/music_export.py` — building the music dataset
- `src/analysis.py` and `src/analysis_pipeline.py` — listening statistics
- `src/api.py` and `src/imports.py` — dashboard endpoints and history uploads
- `src/main.py` — running the original history through the pipeline
- `frontend/` — the dashboard's HTML, CSS and JavaScript
- `tests/` — automated tests and reference results
- `data/` — local history files and generated reports

## Rebuilding the original report

Place the original HTML export at `data/raw/watch-history.html`, then run:

```powershell
python -m src.main
```

This fetches fresh YouTube metadata and overwrites
`data/processed/music_history.csv`. It needs an API key and may take several
minutes.

## Running the tests

```powershell
python -m unittest discover -s tests -v
```

The tests cover parsing, classification, imports, analysis responses and error
handling. They use mocked YouTube responses, so they do not need an API key or
make live YouTube requests.

`tests/fixtures/analysis_reference.json` contains expected results from a small
artificial dataset, captured before the refactor. `tests/test_refactor.py`
compares the current results against it to check that the refactor has preserved
the calculations and classification behaviour. These files belong together and
should both be committed.
