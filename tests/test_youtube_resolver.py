import ast
import asyncio
import pathlib
import re
import unittest
from unittest.mock import patch

SOURCE = pathlib.Path("bot/core/youtube.py").read_text(encoding="utf-8")
MODULE = ast.parse(SOURCE)
CLASS_NODE = next(
    node for node in MODULE.body
    if isinstance(node, ast.ClassDef) and node.name == "YouTube"
)
NAMESPACE = {"asyncio": asyncio, "os": __import__("os"), "random": __import__("random"),
             "re": re, "Path": pathlib.Path, "parse_qs": __import__("urllib.parse", fromlist=["parse_qs"]).parse_qs,
             "urlparse": __import__("urllib.parse", fromlist=["urlparse"]).urlparse,
             "aiohttp": __import__("aiohttp"), "yt_dlp": __import__("yt_dlp"),
             "logger": __import__("logging").getLogger("test-youtube"),
             "Track": type("Track", (), {}), "utils": type("Utils", (), {"format_eta": staticmethod(lambda n: f"{n}s")})}
exec(compile(ast.Module(body=[CLASS_NODE], type_ignores=[]), "bot/core/youtube.py", "exec"), NAMESPACE)
YouTube = NAMESPACE["YouTube"]


class YouTubeResolverTests(unittest.TestCase):
    def setUp(self):
        with patch.object(pathlib.Path, "mkdir"):
            self.youtube = YouTube()

    def test_valid_youtube_watch_url(self):
        self.assertTrue(self.youtube.valid("https://www.youtube.com/watch?v=abcdefghijk"))

    def test_valid_short_url(self):
        self.assertTrue(self.youtube.valid("https://youtu.be/abcdefghijk"))

    def test_invalid_non_youtube_url(self):
        with self.assertRaises(ValueError):
            self.youtube._normalize_query("https://example.com/video")

    def test_normalize_bare_youtube_url(self):
        self.assertEqual(self.youtube._normalize_query("youtu.be/abcdefghijk"),
                         "https://youtu.be/abcdefghijk")

    def test_view_count_formatting(self):
        self.assertEqual(self.youtube._format_view_count(12500), "12.5K views")
        self.assertEqual(self.youtube._format_view_count(None), "")

    def test_empty_download_id_returns_none(self):
        self.assertIsNone(asyncio.run(self.youtube.download("")))


if __name__ == "__main__":
    unittest.main()
