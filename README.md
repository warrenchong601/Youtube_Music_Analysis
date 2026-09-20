# YouTube Music Analysis

## Run locally

Use Python 3.10 or later. From the project root:

    python -m pip install -r requirements.txt
    python -m uvicorn src.api:app --host 127.0.0.1 --port 8000

Open http://127.0.0.1:8000/dashboard/. Set YOUTUBE_API_KEY in the project's .env
before importing history. Keep the key on the server.

## Import your own history

In Google Takeout, select YouTube and YouTube Music history and request JSON
(recommended) or HTML. Extract the archive and upload watch-history.json or
watch-history.html using the dashboard. ZIP archives are not accepted.

For HTML, select the timezone used by the export, such as Europe/Dublin.
Abbreviations such as IST are ambiguous; ISO timestamps in JSON preserve
their explicit offsets. Imported reports display UTC. Invalid dates and
ambiguous daylight-saving timestamps are skipped.

Imports run in the background with progress, up to two at once, with limits of
25 MB and 100,000 usable-format watch records. Duplicate video metadata requests
are avoided while repeated watch events remain in the report.

Each import uses a random capability token kept in this browser tab's session
storage. The token selects an isolated dataset; an invalid token never falls
back to the original report. Delete my imported data removes its CSV, decisions
and status. Raw uploads are held in memory and are not saved to disk.
Processed data remains in data/imports until deleted. Closing the tab can lose
the token; the server owner can remove abandoned import directories manually.

Run a single server worker. Completed imports survive server restarts.
Interrupted imports become failed and can be deleted and retried. This is a
local-server implementation, not an authenticated multi-user hosting service.
The original report remains available to visitors of this server.

## Classification

Explicit /shorts/ history URLs and titles labelled #short or #shorts are
excluded. Videos longer than three minutes skip the Shorts request. Remaining candidates
are checked through the YouTube Shorts URL redirect heuristic, retrying an
unexpected or consent redirect with the HTTP client's default user agent. HTTP failures, consent redirects and unexpected URLs are
unknown, excluded from accepted music, and counted in the import summary.
Unknown does not mean confirmed non-music. The redirect heuristic cannot
guarantee perfect Shorts detection and depends on YouTube's web behaviour.

Classification decisions are retained in data/imports/<token>/decisions.json.
A short song is not excluded solely because of its duration.
The cover keyword now uses word boundaries, so discovered does not match it.
Uploaded reports do not use the original user's personal duration overrides.
Listening time remains an estimate from video durations, not actual playback.

The existing report had two explicitly labelled Shorts removed. Its prior
version is data/processed/music_history.before-shorts-fix.csv. To reclassify
the complete original Takeout file with live metadata, run:

    python -m src.main

This uses data/raw/watch-history.html and overwrites the processed report.
It requires YouTube API access and may take several minutes.

## Tests

    python -m unittest discover -s tests -v

Tests mock YouTube responses, covering classification errors, HTML/JSON parsing,
timezone handling, repeated listens, upload validation, dataset isolation,
restart persistence, deletion and all dashboard endpoints with an empty report.
