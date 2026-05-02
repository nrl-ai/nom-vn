"""Capture the full set of UI screenshots via system-installed Google Chrome.

Requirements: ``playwright`` (Python), system Google Chrome installed at
``/usr/bin/google-chrome``. Playwright's bundled browser install
fails on Ubuntu 26.04, so we use ``executable_path`` to point at the
system browser.

Usage::

    # 1. Start a server first (any port is fine; default below):
    NOM_LLM_MODEL=qwen3:1.7b nom serve --in-memory --port 8080 --no-browser &

    # 2. Run the capture script
    python scripts/capture_screenshots.py [--url http://127.0.0.1:8080] [--out docs/screenshots]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from playwright.sync_api import Page, sync_playwright

DEFAULT_URL = "http://127.0.0.1:8080"


def wait_for_server(base: str, *, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(f"{base}/api/health", timeout=1.5) as r:
                if r.status == 200:
                    return
        except URLError:
            time.sleep(0.4)
    raise SystemExit(f"server not reachable at {base} after {timeout}s")


def post_json(url: str, body: dict, *, timeout: float = 60.0) -> dict:
    req = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def click_task(page: Page, name_pattern: str) -> None:
    """Click a TaskNav button whose accessible name matches ``name_pattern``."""
    page.get_by_role("button", name=re.compile(name_pattern)).first.click()
    page.wait_for_timeout(250)


def click_sample(page: Page, label: str) -> None:
    """Click the first ``Sample`` button matching the given label.

    The accessible name is "Dùng mẫu <label>" (set via aria-label) — match
    on substring so we still hit the right button even if the prefix
    changes."""
    page.get_by_role("button", name=re.compile(rf"Dùng mẫu {re.escape(label)}")).first.click()
    page.wait_for_timeout(150)


def shoot(page: Page, out: Path, name: str) -> None:
    path = out / f"{name}.png"
    page.screenshot(path=str(path), full_page=False)
    print(f"  ✓ {path}")


def capture_all(url: str, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path="/usr/bin/google-chrome",
            args=["--no-sandbox", "--disable-gpu"],
        )
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        # 01 — welcome (chat task active, no space chosen)
        page.goto(url)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(400)
        shoot(page, out, "01-welcome")

        # 07 — diacritic restore with output
        click_task(page, r"Khôi phục dấu")
        page.wait_for_selector("main >> text=§ diacritic restore", timeout=5000)
        click_sample(page, "Business")
        page.wait_for_timeout(200)
        page.keyboard.press("Control+Enter")
        page.wait_for_selector("main >> text=§ restored", timeout=8000)
        shoot(page, out, "07-playground-diacritic")

        # 09 — tokenize (word mode) with output
        click_task(page, r"Tách từ")
        page.wait_for_selector("main >> text=§ word + sentence segmentation", timeout=5000)
        click_sample(page, "Business")
        page.wait_for_timeout(200)
        page.keyboard.press("Control+Enter")
        page.wait_for_selector("main >> text=§ từ", timeout=8000)
        shoot(page, out, "09-playground-tokenize")

        # 10 — normalize + detect with output
        click_task(page, r"Chuẩn hoá")
        page.wait_for_selector("main >> text=§ nfc normalize", timeout=5000)
        click_sample(page, "Conversational")
        page.wait_for_timeout(200)
        page.keyboard.press("Control+Enter")
        page.wait_for_selector("main >> text=§ nhận diện", timeout=8000)
        shoot(page, out, "10-playground-normalize")

        # 11 — strip
        click_task(page, r"Bỏ dấu")
        page.wait_for_selector("main >> text=§ strip diacritics", timeout=5000)
        click_sample(page, "Business")
        page.wait_for_timeout(200)
        page.keyboard.press("Control+Enter")
        page.wait_for_selector("main >> text=§ đã bỏ dấu", timeout=8000)
        shoot(page, out, "11-playground-strip")

        # 08 — noise generator
        click_task(page, r"Sinh nhiễu")
        page.wait_for_selector("main >> text=§ reproducible noise generator", timeout=5000)
        click_sample(page, "Business")
        page.wait_for_timeout(200)
        page.keyboard.press("Control+Enter")
        page.wait_for_selector("main >> text=§ văn bản đã nhiễu", timeout=8000)
        shoot(page, out, "08-playground-noise")

        # 12 — API & Setup page (top of page, install + LLM backends visible)
        click_task(page, r"API và cài đặt")
        page.wait_for_timeout(500)
        shoot(page, out, "12-playground-api")

        # 13 — Settings page (full layout: server health, auth, backend picker)
        click_task(page, r"Trạng thái máy chủ")
        page.wait_for_timeout(500)
        shoot(page, out, "13-playground-settings")

        # 02 — chat with a real LLM answer + citations
        click_task(page, r"Chat & RAG")
        page.wait_for_timeout(400)
        space_btn = (
            page.locator("aside")
            .get_by_role("button")
            .filter(has_text=re.compile(r"\d+ materials"))
            .first
        )
        if space_btn.count() > 0:
            space_btn.click()
            # Wait for the chat layout to settle — composer textarea is the
            # signal it rendered. Some materials need a moment to load.
            page.wait_for_selector(
                "textarea[placeholder*='Đặt câu hỏi']", state="visible", timeout=10_000
            )
            page.wait_for_timeout(500)

            # Pre-warm via HTTP so the screenshot capture isn't blocked on
            # cold model load.
            spaces = json.loads(urlopen(f"{url}/api/spaces", timeout=5).read())
            space_id = spaces[0]["id"]
            question = "Hợp đồng có giá trị bao nhiêu?"
            print(f"  → /api/spaces/{space_id}/ask (warmup)")
            try:
                post_json(
                    f"{url}/api/spaces/{space_id}/ask",
                    {"question": question, "top_k": 3},
                    timeout=180,
                )
            except Exception as exc:
                print(f"  ! warmup failed: {exc}")

            composer = page.locator("textarea[placeholder*='Đặt câu hỏi']").first
            composer.fill(question)
            page.wait_for_timeout(150)
            page.keyboard.press("Enter")
            # Wait for the pending pulse-dot animation to end (assistant
            # message arrived).
            try:
                page.wait_for_function(
                    "() => document.querySelectorAll('.animate-pulse-dot').length === 0",
                    timeout=120_000,
                )
            except Exception as exc:
                print(f"  ! ask completion wait timed out: {exc}")
            page.wait_for_timeout(600)
            shoot(page, out, "02-chat-with-answer")

            # 03 — citations expanded
            chip = page.locator("button").filter(has_text=re.compile(r"^\[\d+\]")).first
            if chip.count() > 0:
                chip.click()
                page.wait_for_timeout(400)
                shoot(page, out, "03-citations-expanded")
            else:
                print("  ! no citation chips found — skipping 03")
        else:
            print("  ! no spaces in sidebar — skipping 02 / 03")

        browser.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--out", default="docs/screenshots", type=Path)
    args = parser.parse_args(argv)

    print(f"→ probing server at {args.url}")
    wait_for_server(args.url)
    print(f"→ writing screenshots to {args.out}")
    capture_all(args.url, args.out)
    print("✔ done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
