import asyncio
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from bot.core.youtube import YouTube


class YouTubeResolverTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        with patch.object(pathlib.Path, "mkdir"):
            self.youtube = YouTube()
        self.youtube.download_dir = pathlib.Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_valid_watch_and_short_urls(self):
        self.assertTrue(self.youtube.valid("https://www.youtube.com/watch?v=abcdefghijk"))
        self.assertTrue(self.youtube.valid("https://youtu.be/abcdefghijk"))

    def test_invalid_non_youtube_url(self):
        with self.assertRaises(ValueError):
            self.youtube._normalize_query("https://example.com/video")

    def test_normalize_bare_youtube_url(self):
        self.assertEqual(
            self.youtube._normalize_query("youtu.be/abcdefghijk"),
            "https://youtu.be/abcdefghijk",
        )

    def test_reject_non_http_scheme(self):
        with self.assertRaises(ValueError):
            self.youtube._normalize_query("file:///etc/passwd")

    def test_view_count_formatting(self):
        self.assertEqual(self.youtube._format_view_count(12500), "12.5K views")
        self.assertEqual(self.youtube._format_view_count(None), "")

    def test_empty_or_invalid_download_id_returns_none(self):
        self.assertIsNone(asyncio.run(self.youtube.download("")))
        self.assertIsNone(asyncio.run(self.youtube.download("../abcdefghij")))

    def test_download_reuses_existing_nonempty_file(self):
        media = pathlib.Path(self.tempdir.name) / "abcdefghijk.webm"
        media.write_bytes(b"audio")
        self.assertEqual(
            asyncio.run(self.youtube.download("abcdefghijk")),
            str(media),
        )

    def test_download_ignores_empty_existing_file(self):
        media = pathlib.Path(self.tempdir.name) / "abcdefghijk.webm"
        media.touch()
        self.assertIsNone(asyncio.run(self.youtube.download("abcdefghijk")))


if __name__ == "__main__":
    unittest.main()
