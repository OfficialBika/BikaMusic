import asyncio
import unittest
from unittest.mock import patch

from bot.core.youtube import YouTube


class YouTubeResolverTests(unittest.TestCase):
    def setUp(self):
        self.youtube = YouTube()

    def test_valid_youtube_watch_url(self):
        self.assertTrue(self.youtube.valid("https://www.youtube.com/watch?v=abcdefghijk"))

    def test_valid_short_url(self):
        self.assertTrue(self.youtube.valid("https://youtu.be/abcdefghijk"))

    def test_invalid_non_youtube_url(self):
        with self.assertRaises(ValueError):
            self.youtube._normalize_query("https://example.com/video")

    def test_normalize_bare_youtube_url(self):
        self.assertEqual(
            self.youtube._normalize_query("youtu.be/abcdefghijk"),
            "https://youtu.be/abcdefghijk",
        )

    def test_view_count_formatting(self):
        self.assertEqual(self.youtube._format_view_count(12500), "12.5K views")
        self.assertEqual(self.youtube._format_view_count(None), "")

    def test_empty_download_id_returns_none(self):
        self.assertIsNone(asyncio.run(self.youtube.download("")))


if __name__ == "__main__":
    unittest.main()
