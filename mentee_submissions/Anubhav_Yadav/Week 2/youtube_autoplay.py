import sys
import time

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

YOUTUBE_URL = "https://www.youtube.com"


def dismiss_cookie_banner(page) -> None:
    """Try common YouTube consent buttons; continue if none appear."""
    selectors = [
        'button:has-text("Accept all")',
        'button:has-text("Reject all")',
        'button:has-text("I agree")',
        'button[aria-label*="Accept"]',
    ]
    for selector in selectors:
        try:
            button = page.locator(selector).first
            if button.is_visible(timeout=2000):
                button.click(timeout=3000)
                page.wait_for_timeout(1000)
                return
        except (PlaywrightTimeoutError, PlaywrightError):
            continue


def try_skip_ad(page) -> None:
    """Click skip when available; otherwise wait briefly for the ad to finish."""
    skip_button = page.locator(
        ".ytp-ad-skip-button, .ytp-ad-skip-button-modern, button.ytp-ad-skip-button-modern"
    ).first

    for _ in range(12):
        try:
            if skip_button.is_visible(timeout=1000):
                skip_button.click()
                print("Skipped ad.")
                return
        except (PlaywrightTimeoutError, PlaywrightError):
            pass
        time.sleep(1)

    print("No skip button yet — waiting a few seconds for playback to continue...")


def search_and_play(query: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(YOUTUBE_URL, wait_until="domcontentloaded", timeout=60000)

        dismiss_cookie_banner(page)

        search_box = page.locator('input[name="search_query"]')
        search_box.wait_for(state="visible", timeout=15000)
        search_box.click()
        search_box.fill(query)
        search_box.press("Enter")

        page.wait_for_selector("ytd-video-renderer a#video-title", timeout=30000)
        first_result = page.locator("ytd-video-renderer a#video-title").first
        video_title = first_result.inner_text().strip()
        print(f"Playing: {video_title}")
        first_result.click()

        page.wait_for_selector("video", timeout=30000)
        page.wait_for_timeout(2000)

        try_skip_ad(page)

        try:
            page.locator("button.ytp-fullscreen-button").click(timeout=5000)
            print("Entered fullscreen.")
        except (PlaywrightTimeoutError, PlaywrightError):
            print("Fullscreen button not found — video should still be playing.")

        print("Video is playing. Close the browser window when you are done.")
        try:
            page.wait_for_timeout(30000)
        except PlaywrightError:
            print("Browser closed.")
        browser.close()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    query = input("Enter a YouTube search term: ").strip()
    if not query:
        print("Search term cannot be empty.")
        return

    search_and_play(query)


if __name__ == "__main__":
    main()
