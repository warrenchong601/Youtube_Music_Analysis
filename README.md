# YouTube Music Analysis

A Python project for exploring my YouTube listening history. It takes a Google
Takeout export, identifies which videos are likely to be music, and displays the
results in a dashboard.

The project started with exploring the data in Jupyter notebooks. I then moved
the parsing, classification and analysis into reusable Python files, added a
FastAPI backend, and built a frontend to display the results.

## Live Demo

[Open the YouTube Music Analysis dashboard](https://youtube-music-analysis.onrender.com/)

The demo is hosted on Render's free tier. The first request after a period of
inactivity may take some time while the service starts.

Uploaded histories on the live demo are temporary. Render's free service uses
ephemeral storage, so imported reports are lost when the service restarts,
redeploys or spins down. Keep your original export if you want to import it again.
See [Render's free service documentation](https://render.com/docs/free) for details.

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

The repository includes a processed snapshot of my listening data at
`data/processed/music_history.csv` for the original report. Raw Google Takeout
history is not included; `data/raw/` is excluded through `.gitignore`.

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

Explicit Shorts URLs and titles labelled `#short` or `#shorts` are excluded.
Other candidates longer than three minutes skip the Shorts request; remaining
candidates are checked using YouTube's redirects. This check depends on YouTube's
web behaviour and is not a guaranteed way to identify Shorts. Only confirmed or
probable music is included in the final report; candidates marked for review are
left out. Import decisions are saved in `data/imports/<token>/decisions.json`.

Listening time is also an estimate. Takeout records when a video was watched,
not how much of it was played. My original report includes a few manual duration
adjustments for long videos; these are not applied to uploaded histories.

## Running the project

The project specifies Python **3.14.5** in `.python-version`. Use that version
locally to match the configured runtime. From the project folder, install the
dependencies listed in `requirements.txt`, preferably in a virtual environment:

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

## Deployment

The application runs as one Render web service. FastAPI serves both the API and
the frontend files at `/dashboard/`, and `/` redirects to the dashboard. The
frontend sends requests to the same service, so it does not need a separate host
or build step.

For a Render Python web service, use this build command:

```sh
python -m pip install -r requirements.txt
```

And this start command:

```sh
python -m uvicorn src.api:app --host 0.0.0.0 --port $PORT --workers 1
```

Set `YOUTUBE_API_KEY` in Render's environment settings rather than uploading the
local `.env` file. The processed snapshot provides the default report without
new API requests. Imports need the server's API key and available YouTube API
quota. The repository does not contain a `render.yaml`; deployment settings are
managed in Render's dashboard.

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
and import status are saved under `data/imports/`, which is excluded from Git.
When running locally, these files remain until deleted, and completed imports can
be reopened after a server restart if the tab still has their reference. On the
hosted Render version, these files are temporary and are lost on restart,
redeployment or spin-down. The original report comes from the repository snapshot
and is included again with each deployment.

Interrupted imports cannot resume because the raw upload is held only in memory.
Delete the failed import and try again. If Render has already removed its files,
open a new browser tab and upload the history again.

The application does not have user accounts. Each imported report is accessed
using a random token stored in that browser tab; anyone with that token can access
the import while it exists. The original report is public on the live demo.

## Technologies Used

- Python and pandas for the data pipeline and analysis
- Beautiful Soup and lxml for HTML parsing, and Requests for YouTube requests
- FastAPI and Uvicorn for the backend
- HTML, CSS, JavaScript and Chart.js for the dashboard
- Jupyter notebooks and Matplotlib for the original exploration
- Python's `unittest` and FastAPI's test client for automated tests

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
- `data/processed/music_history.csv` — the processed snapshot used by the default report
- `data/raw/` — local Takeout exports, not included in Git
- `data/imports/` — generated import files, not included in Git
- `.python-version` — the configured Python version, 3.14.5
- `requirements.txt` — Python dependencies
- `.env` — the local API key configuration, not included in Git

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
