import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

import requests
from fastapi.testclient import TestClient
from src import api, classifier, google_takeout, imports, music_pipeline, youtube_api

VIDEO = "abcdefghijk"
def history(video=VIDEO, title="Watched Example"):
    return json.dumps([{"title": title, "titleUrl": "https://www.youtube.com/watch?v=" + video,
                        "time": "2026-09-07T12:00:00Z"}]).encode()

def metadata(video=VIDEO, title="Example official audio"):
    return {"items": [{"id": video, "snippet": {"title": title, "categoryId": "10",
            "channelTitle": "Artist", "channelId": "channel", "description": ""},
            "contentDetails": {"duration": "PT2M"}}]}

class ClassificationTests(unittest.TestCase):
    def test_cover_does_not_match_discovered(self):
        self.assertEqual(classifier.classify_title("Loki discovered something")["classification"], "uncertain")
        self.assertEqual(classifier.classify_title("A song (cover)")["classification"], "music")

    def test_network_failure_is_unknown(self):
        with patch.object(youtube_api.requests, "get", side_effect=requests.Timeout):
            self.assertIsNone(youtube_api.is_short(VIDEO))

    def test_http_error_is_unknown(self):
        response = Mock(url="https://www.youtube.com/watch?v=" + VIDEO)
        response.raise_for_status.side_effect = requests.HTTPError()
        with patch.object(youtube_api.requests, "get", return_value=response):
            self.assertIsNone(youtube_api.is_short(VIDEO))

    def test_redirects(self):
        for url, expected in [
            ("https://www.youtube.com/shorts/" + VIDEO, True),
            ("https://www.youtube.com/watch?v=" + VIDEO, False),
            ("https://consent.youtube.com/", None),
            ("https://www.youtube.com/watch?v=wrong", None)]:
            with self.subTest(url=url), patch.object(youtube_api.requests, "get", return_value=Mock(url=url)):
                self.assertIs(youtube_api.is_short(VIDEO), expected)

    def test_unknown_does_not_pass_legacy_filter(self):
        self.assertEqual(classifier.remove_shorts_video_candidates([{"video_ID":VIDEO}], lambda _: None), [])

    def test_consent_redirect_retries_before_giving_up(self):
        responses = [Mock(url="https://consent.youtube.com/m"),
                     Mock(url="https://www.youtube.com/shorts/" + VIDEO)]
        with patch.object(youtube_api.requests, "get", side_effect=responses) as get:
            self.assertTrue(youtube_api.is_short(VIDEO))
            self.assertEqual(get.call_count, 2)
            self.assertEqual(get.call_args.kwargs["headers"], {})

class ParserTests(unittest.TestCase):
    def test_url_forms(self):
        for url in ["https://www.youtube.com/watch?v=" + VIDEO + "&list=xyz",
                    "https://www.youtube.com/shorts/" + VIDEO, "https://youtu.be/" + VIDEO]:
            self.assertEqual(google_takeout.video_id_from_url(url), VIDEO)
        self.assertIsNone(google_takeout.video_id_from_url("https://example.com/watch?v=" + VIDEO))

    def test_json_repeats_and_missing_channel(self):
        records = google_takeout.parse_watch_history_content(history(), ".json")
        frame = google_takeout.stage_one_clean(google_takeout.create_dataframe(records * 2))
        self.assertEqual(len(frame), 2)
        self.assertEqual(frame.iloc[0]["watched_at"].isoformat(), "2026-09-07T12:00:00+00:00")

    def test_html_timezone_and_missing_cards(self):
        html = ('<div class="outer-cell"></div><div class="outer-cell"><div class="content-cell">'
                '<a href="https://www.youtube.com/watch?v=' + VIDEO + '">Song</a><br>'
                '7 Sept 2026, 13:51:45 IST</div></div>')
        records = google_takeout.parse_watch_history_content(html, ".html")
        frame = google_takeout.stage_one_clean(google_takeout.create_dataframe(records), timezone="Europe/Dublin")
        self.assertEqual(len(frame), 1)
        self.assertEqual(frame.iloc[0]["watched_at"].hour, 12)

    def test_invalid_json(self):
        with self.assertRaises(ValueError):
            google_takeout.parse_watch_history_content(b"{}", ".json")

class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root_patch = patch.object(imports, "IMPORT_ROOT", Path(self.temp.name))
        self.root_patch.start()
        imports.jobs.clear()
        imports.active = 0
        self.client = TestClient(api.app)

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def upload(self, short=False, title="Example official audio"):
        with patch.object(youtube_api, "fetch_video_metadata", return_value=metadata(title=title)), \
             patch.object(youtube_api, "fetch_channel_metadata", return_value={"items":[]}), \
             patch.object(youtube_api, "is_short", return_value=short):
            response = self.client.post("/api/imports?filename=watch-history.json", content=history())
        self.assertEqual(response.status_code, 202)
        return response.json()["dataset_token"]

    def test_success_isolation_persistence_and_delete(self):
        first = self.upload()
        second = self.upload(short=True)
        headers = {"X-Dataset-Token": first}
        self.assertEqual(self.client.get("/api/summary", headers=headers).json()["music_plays"], 1)
        self.assertEqual(self.client.get("/api/summary", headers={"X-Dataset-Token": second}).json()["music_plays"], 0)
        imports.jobs.clear()
        self.assertEqual(self.client.get("/api/imports/current", headers=headers).json()["status"], "complete")
        self.assertEqual(self.client.delete("/api/imports/current", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/summary", headers=headers).status_code, 404)
        self.assertEqual(self.client.get("/api/summary", headers={"X-Dataset-Token":"../bad"}).status_code, 404)

    def test_empty_report_all_endpoints(self):
        token = self.upload(short=None)
        headers = {"X-Dataset-Token": token}
        self.assertEqual(self.client.get("/api/imports/current", headers=headers).json()["summary"]["unverified_videos"], 1)
        for route in api.app.routes:
            if getattr(route, "path", "").startswith("/api/") and "GET" in getattr(route, "methods", set()) and "imports" not in route.path:
                with self.subTest(route=route.path):
                    result = self.client.get(route.path, headers=headers, params={"title":"song"})
                    self.assertEqual(result.status_code, 200, result.text)

    def test_validation_and_failed_import(self):
        self.assertEqual(self.client.post("/api/imports?filename=archive.zip", content=b"x").status_code, 400)
        self.assertEqual(self.client.post("/api/imports", content=b"").status_code, 400)
        with patch.object(imports, "MAX_BYTES", 2):
            self.assertEqual(self.client.post("/api/imports", content=b"xxx").status_code, 413)
        result = self.client.post("/api/imports", content=b"not-json")
        token = result.json()["dataset_token"]
        self.assertEqual(self.client.get("/api/imports/current", headers={"X-Dataset-Token": token}).json()["status"], "failed")
        self.assertEqual(imports.active, 0)

    def test_long_song_needs_no_short_request(self):
        records = google_takeout.parse_watch_history_content(history(), ".json")
        frame = google_takeout.stage_one_clean(google_takeout.create_dataframe(records))
        data = metadata()
        data["items"][0]["contentDetails"]["duration"] = "PT3M1S"
        with patch.object(youtube_api, "fetch_video_metadata", return_value=data), \
             patch.object(youtube_api, "fetch_channel_metadata", return_value={"items": []}), \
             patch.object(youtube_api, "is_short") as checker:
            result, _ = music_pipeline.run_music_pipeline(frame, Path(self.temp.name) / "long.csv", progress=lambda _: None)
        checker.assert_not_called()
        self.assertEqual(len(result), 1)

    def test_repeats_only_checked_once_and_tagged_shorts_excluded(self):
        records = google_takeout.parse_watch_history_content(history(), ".json")
        frame = google_takeout.stage_one_clean(google_takeout.create_dataframe(records * 2))
        with patch.object(youtube_api, "fetch_video_metadata", return_value=metadata()), \
             patch.object(youtube_api, "fetch_channel_metadata", return_value={"items":[]}), \
             patch.object(youtube_api, "is_short", return_value=False) as checker:
            result, _ = music_pipeline.run_music_pipeline(frame, Path(self.temp.name)/"repeat.csv", progress=lambda _:None)
        self.assertEqual(len(result), 2)
        checker.assert_called_once_with(VIDEO)
        token = self.upload(short=False, title="Loki discovered something #shorts")
        self.assertEqual(self.client.get("/api/imports/current", headers={"X-Dataset-Token":token}).json()["summary"]["excluded_shorts"], 1)

if __name__ == "__main__":
    unittest.main()
