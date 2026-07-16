"""
youtube_autoplay.py – Video playback tool for the Competitive Intelligence Agent.

Opens YouTube in a visible browser, searches for a company-related video,
plays the first result, handles cookie popups, skips ads, and goes fullscreen.
Returns the video title.
"""
import logging
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)


def play_company_video(company: str) -> str:
    """
    Automate YouTube playback for a company-related video.

    Args:
        company: Name of the company to search for on YouTube.

    Returns:
        Title of the video that is played, or an error message string.
    """
    logger.info(f"Playing YouTube video for company: {company}")
    video_title = "Unknown"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # visible browser
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            # Step 1: Open YouTube
            page.goto(
                "https://www.youtube.com",
                wait_until="domcontentloaded",
                timeout=30000,
            )

            # Handle cookie consent popup (common in EU regions)
            try:
                consent_button = page.wait_for_selector(
                    'button:has-text("Accept all"), button:has-text("I agree"), '
                    'button:has-text("OK"), ytd-button-renderer:has-text("Accept all")',
                    timeout=5000,
                )
                if consent_button:
                    consent_button.click()
                    logger.debug("Cookie consent accepted.")
                    page.wait_for_timeout(1000)
            except PlaywrightTimeout:
                logger.debug("No cookie popup appeared.")

            # Step 2: Type search query
            search_query = f"{company} news latest"
            search_box = page.wait_for_selector(
                'input[name="search_query"]', timeout=10000
            )
            search_box.click()
            search_box.fill(search_query)
            page.keyboard.press("Enter")

            # Step 3: Wait for results and click the first video
            page.wait_for_selector("ytd-video-renderer", timeout=10000)
            first_video = page.wait_for_selector(
                "ytd-video-renderer #video-title", timeout=10000
            )
            if first_video:
                video_title = first_video.inner_text().strip()
                logger.info(f"Clicking video: {video_title}")
                first_video.click()
            else:
                raise Exception("No video results found.")

            # Step 4: Handle ads – try to skip after a delay
            try:
                skip_button = page.wait_for_selector(
                    ".ytp-ad-skip-button, .ytp-ad-skip-button-modern",
                    timeout=15000,
                )
                if skip_button:
                    # YouTube usually requires 5 seconds before skip
                    page.wait_for_timeout(6000)
                    skip_button.click()
                    logger.info("Ad skipped.")
            except PlaywrightTimeout:
                logger.debug("No skippable ad appeared.")

            # Step 5: Go fullscreen after a short delay to ensure player is ready
            page.wait_for_timeout(3000)
            page.keyboard.press("f")
            logger.info("Fullscreen toggled (pressed 'f').")

            # Let the video play for a few seconds so the user can see it
            page.wait_for_timeout(5000)

        except PlaywrightTimeout as e:
            logger.error(f"Timeout during YouTube automation: {e}")
            video_title = f"Error: Timeout - {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in YouTube automation: {e}")
            video_title = f"Error: {str(e)}"
        finally:
            # Keep browser open so the video continues playing.
            # Close it if needed: browser.close()
            logger.info("Automation completed. Browser remains open for observation.")
            # Uncomment the line below to close the browser automatically
            # browser.close()

    return video_title


if __name__ == "__main__":
    # Simple test
    logging.basicConfig(level=logging.INFO)
    played = play_company_video("OpenAI")
    print(f"Played: {played}")