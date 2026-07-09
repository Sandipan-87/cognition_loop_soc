"""
Week 2 - Task 3: youtube_autoplay.py
Searches YouTube for a user query and auto-plays the first video result.
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import time
from playwright.sync_api import sync_playwright


def youtube_autoplay(search_query: str):
    """Search YouTube and auto-play the first video result."""
    print(f"🎬 Searching YouTube for: '{search_query}'...\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
        )
        page = context.new_page()

        # Navigate to YouTube
        page.goto("https://www.youtube.com", timeout=30000)

        # Handle cookie consent popup if it appears
        try:
            accept_btn = page.locator("button:has-text('Accept all')")
            if accept_btn.is_visible(timeout=3000):
                accept_btn.click()
                print("🍪 Accepted cookie consent.")
                time.sleep(1)
        except Exception:
            pass  # No cookie popup

        # Type the search query
        search_box = page.locator('input[name="search_query"]')
        search_box.wait_for(timeout=10000)
        search_box.click()
        search_box.fill(search_query)
        search_box.press("Enter")
        print("🔍 Search submitted, waiting for results...")

        # Wait for search results to load
        page.wait_for_selector("ytd-video-renderer", timeout=15000)
        time.sleep(2)

        # Click the first video result
        first_video = page.locator("ytd-video-renderer a#video-title").first
        video_title = first_video.inner_text()
        print(f"▶️  Playing: {video_title}")
        first_video.click()

        # Wait for the video player to load
        page.wait_for_selector("video", timeout=15000)
        time.sleep(3)

        # Try to skip ads if present
        try:
            skip_btn = page.locator("button.ytp-skip-ad-button, button.ytp-ad-skip-button-modern")
            if skip_btn.is_visible(timeout=6000):
                skip_btn.click()
                print("⏭️  Skipped ad.")
        except Exception:
            pass  # No ad or no skip button

        # Try to go fullscreen
        try:
            fullscreen_btn = page.locator("button.ytp-fullscreen-button")
            if fullscreen_btn.is_visible(timeout=3000):
                fullscreen_btn.click()
                print("📺 Entered fullscreen.")
        except Exception:
            pass

        print(f"\n🎵 Now playing: {video_title}")
        print("   Press Ctrl+C in the terminal to stop.\n")

        # Keep the browser open so the video plays
        try:
            while True:
                time.sleep(5)
        except KeyboardInterrupt:
            print("\n👋 Stopping playback.")

        browser.close()


if __name__ == "__main__":
    query = input("🎵 Enter your YouTube search query: ").strip()
    if not query:
        query = "lofi hip hop radio beats to relax"
    youtube_autoplay(query)
