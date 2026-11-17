"""Exercise real HTMX/Alpine/browser behavior against an isolated legacy database."""

import os
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from smoke_helpers import CRYPTO, ROOT, seed_legacy


class FeedHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        content = (
            "<p>A calm story with enough detail to test reading position and returning to an article.</p>"
            * 90
        )
        items = "".join(
            f'<item><guid isPermaLink="false">new-{i}</guid><title>{title}</title><link>https://example.com/{i}</link><description><![CDATA[{content}]]></description></item>'
            for i, title in enumerate(["A long new story", "Another quiet story"])
        )
        body = f'<rss version="2.0"><channel><title>Test source</title><link>https://example.com</link><description>Test feed</description>{items}</channel></rss>'.encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/rss+xml")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


def assert_typography(page, selector, family, size, line_height):
    """Keep the original app's type roles and metrics on the rendered elements."""
    page.evaluate("document.fonts.ready")
    actual = page.locator(selector).first.evaluate("""el => {
        const style = getComputedStyle(el);
        return {family: style.fontFamily, size: style.fontSize,
                weight: style.fontWeight, lineHeight: style.lineHeight};
    }""")
    expected_family = (
        page.locator("body").evaluate("el => getComputedStyle(el).fontFamily")
        if family == "body"
        else family
    )
    assert expected_family in actual["family"], (selector, actual)
    assert (actual["size"], actual["weight"], actual["lineHeight"]) == (size, "400", line_height), (
        selector,
        actual,
    )
    if family != "body":
        loaded = page.locator(selector).first.evaluate(
            """async (el, font) => {
                const faces = await document.fonts.load(`400 ${font.size} "${font.family}"`, el.textContent);
                return faces.length > 0 && faces.every(face => face.status === 'loaded');
            }""",
            {"size": size, "family": family},
        )
        assert loaded, f"{family} did not load for {selector}"


def main():
    with tempfile.TemporaryDirectory(prefix="quiet-feed-browser-") as directory:
        path = seed_legacy(Path(directory) / "quiet-feed.db")
        feed_server = ThreadingHTTPServer(("127.0.0.1", 0), FeedHandler)
        threading.Thread(target=feed_server.serve_forever, daemon=True).start()
        with sqlite3.connect(path) as connection:
            connection.execute(
                "UPDATE feeds SET url=?", (f"http://127.0.0.1:{feed_server.server_port}/feed",)
            )
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        origin = f"http://127.0.0.1:{port}"
        env = {
            **os.environ,
            "DATABASE_PATH": str(path),
            "BETTER_AUTH_SECRET": CRYPTO["secret"],
            "ENCRYPTION_KEY": "",
            "ORIGIN": origin,
            "SECURE_COOKIES": "false",
            "ENABLE_INTERNAL_SCHEDULER": "false",
            "HOST": "127.0.0.1",
            "PORT": str(port),
        }
        artifacts = ROOT / "test-results"
        artifacts.mkdir(exist_ok=True)
        with (Path(directory) / "server.log").open("w+") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", "quiet_feed"], cwd=ROOT, env=env, stdout=log, stderr=log
            )
            try:
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    try:
                        urllib.request.urlopen(origin + "/healthz", timeout=1).close()
                        break
                    except OSError:
                        if process.poll() is not None:
                            raise RuntimeError("App exited before startup")
                        time.sleep(0.1)
                else:
                    raise RuntimeError("App did not start")
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(
                        channel=os.getenv("QUIET_FEED_BROWSER_CHANNEL") or None
                    )
                    context = browser.new_context(viewport={"width": 1280, "height": 900})
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(origin + "/login")
                    assert_typography(page, ".auth-shell h1", "Fraunces Variable", "30px", "36px")
                    assert_typography(page, "input[name=email]", "body", "16px", "24px")
                    page.get_by_label("Email", exact=True).fill("reader@example.com")
                    page.get_by_label("Password", exact=True).fill(
                        CRYPTO["passwords"][0]["password"]
                    )
                    page.get_by_role("button", name="Sign in", exact=True).click()
                    page.get_by_role("button", name="Fetch now instead").click()
                    expect(
                        page.get_by_role("link", name=re.compile("A long new story"))
                    ).to_be_visible()
                    assert_typography(page, ".page-heading h1", "Fraunces Variable", "30px", "36px")
                    assert_typography(page, ".story h3", "Fraunces Variable", "18px", "24.75px")
                    heading = page.get_by_role("button", name=re.compile("^Technology"))
                    heading.click()
                    expect(
                        page.get_by_role("link", name=re.compile("A long new story"))
                    ).to_be_hidden()
                    heading.click()
                    expect(
                        page.get_by_role("link", name=re.compile("A long new story"))
                    ).to_be_visible()
                    page.screenshot(path=str(artifacts / "edition-desktop.png"), full_page=True)
                    page.get_by_role("link", name=re.compile("A long new story")).click()
                    with page.expect_response(
                        lambda response: (
                            response.url.endswith("/progress") and response.request.method == "POST"
                        )
                    ):
                        page.evaluate("window.scrollTo(0, 1200)")
                    page.reload()
                    page.wait_for_function("window.scrollY > 1000")
                    page.get_by_role("button", name="Mark as read", exact=True).evaluate(
                        "el => el.click()"
                    )
                    expect(
                        page.get_by_role("button", name="Mark unread", exact=True)
                    ).to_be_attached()
                    page.screenshot(path=str(artifacts / "reader-desktop.png"), full_page=True)
                    page.goto(origin + "/")
                    page.get_by_role("button", name="Close today’s edition").click()
                    expect(page.get_by_text("That’s enough for today.")).to_be_visible()
                    page.get_by_role("link", name="Revisit this edition").click()
                    expect(
                        page.get_by_role("link", name=re.compile("A long new story"))
                    ).to_be_visible()
                    page.goto(origin + "/feeds")
                    assert_typography(page, ".page-heading h1", "Fraunces Variable", "24px", "32px")
                    assert_typography(page, ".feed-info h3", "body", "16px", "24px")
                    page.get_by_role("button", name="Edit", exact=True).click()
                    page.get_by_label("Title", exact=True).fill("Renamed source")
                    assert_typography(
                        page, ".feed-editor input[name=title]", "body", "14px", "20px"
                    )
                    page.get_by_role("button", name="Save changes").click()
                    expect(page.get_by_role("heading", name="Renamed source")).to_be_visible()
                    assert page.locator("main").count() == 1
                    with page.expect_download() as download:
                        page.get_by_role("link", name="Export subscriptions ↓").click()
                    destination = Path(directory) / "export.opml"
                    download.value.save_as(destination)
                    page.get_by_label("OPML file").set_input_files(destination)
                    page.get_by_role("button", name="Import OPML").click()
                    expect(page.get_by_text("Imported 0 of 1 feeds.")).to_be_visible()
                    page.goto(origin + "/settings")
                    assert_typography(page, ".page-heading h1", "Fraunces Variable", "24px", "32px")
                    page.get_by_role("combobox", name=re.compile("^Theme")).select_option("light")
                    page.get_by_label(re.compile("^Articles per edition")).fill("6")
                    page.get_by_role("button", name="Save settings").click()
                    expect(page.get_by_text("Settings saved.")).to_be_visible()
                    expect(page.locator("html")).to_have_attribute("data-theme", "light")
                    page.set_viewport_size({"width": 390, "height": 844})
                    page.get_by_role("button", name="Toggle navigation menu").click()
                    page.locator("#mobile-nav").get_by_role(
                        "link", name="Feeds", exact=True
                    ).click()
                    page.screenshot(path=str(artifacts / "feeds-mobile.png"), full_page=True)
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth"
                    )
                    page.goto(origin + "/archive/2025-01-01")
                    expect(
                        page.get_by_role("link", name=re.compile("Existing story"))
                    ).to_be_visible()
                    page.get_by_role("button", name="Toggle navigation menu").click()
                    page.locator("#mobile-nav").get_by_role("button", name="Sign out").click()
                    expect(page.get_by_role("heading", name="Welcome back.")).to_be_visible()
                    assert not errors, errors
                    browser.close()
                print(
                    "Browser smoke passed: legacy login, edition compilation/closure, category persistence, scroll restoration, HTMX feed editing and OPML, settings, mobile navigation, logout."
                )
            except Exception:
                log.flush()
                log.seek(0)
                print(log.read(), file=sys.stderr)
                raise
            finally:
                process.terminate()
                process.wait(timeout=20)
                feed_server.shutdown()


if __name__ == "__main__":
    main()
