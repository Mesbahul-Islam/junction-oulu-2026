from html.parser import HTMLParser
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.labels = []
        self.assets = []
        self.inline_code = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "label" and "for" in attrs:
            self.labels.append(attrs["for"])
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.assets.append(attrs["href"])
        if tag == "script":
            self.assets.append(attrs.get("src", ""))
        if tag == "style" or (tag == "script" and "src" not in attrs):
            self.inline_code.append(tag)


class NewsroomPageTests(SimpleTestCase):
    def test_dashboard_serves_separate_assets_and_connected_labels(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        page = Markup()
        page.feed(response.content.decode())
        self.assertEqual(len(page.ids), len(set(page.ids)))
        self.assertTrue(set(page.labels) <= set(page.ids))
        self.assertEqual(page.inline_code, [])
        for asset in ("newsroom/admin.css", "newsroom/admin.js"):
            urls = [url for url in page.assets if url.split("?")[0] == "/static/" + asset]
            self.assertEqual(len(urls), 1)
            import hashlib
            version = hashlib.sha256((settings.BASE_DIR / "frontend" / "static" / asset).read_bytes()).hexdigest()[:12]
            self.assertEqual(urls[0], "/static/" + asset + "?v=" + version)
            self.assertEqual(Path(finders.find(asset)), settings.BASE_DIR / "frontend" / "static" / asset)
