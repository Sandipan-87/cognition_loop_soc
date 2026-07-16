import sys
import time
from playwright.sync_api import sync_playwright

def play_video(query: str):
    print(f"Initiating YouTube autoplay for search query: '{query}'")
    with sync_playwright() as p:
        # Attempt to launch with headless=False so the user can watch the video play.
        # Fall back to headless=True if display/X11 environment is not configured.
        try:
            print("Attempting to launch Chromium in GUI mode (headless=False)...")
            browser = p.chromium.launch(headless=False)
        except Exception as e:
            print(f"Failed to launch in GUI mode (likely headless environment): {e}")
            print("Falling back to running Chromium in headless mode...")
            browser = p.chromium.launch(headless=True)
            
        page = browser.new_page()
        
        # Set viewport size to standard HD
        page.set_viewport_size({"width": 1280, "height": 720})
        
        print("Navigating to YouTube...")
        page.goto("https://www.youtube.com", timeout=45000)
        
        # Wait and handle potential cookie consent screens
        time.sleep(3)
        try:
            # Common YouTube consent buttons
            consent_buttons = [
                "button[aria-label='Reject the use of cookies and other data for the purposes described']",
                "button[aria-label='Accept the use of cookies and other data for the purposes described']",
                "button:has-text('Reject all')",
                "button:has-text('Accept all')",
                "button:has-text('I agree')",
                "button:has-text('Consent')"
            ]
            for selector in consent_buttons:
                btn = page.locator(selector).first
                if btn.is_visible():
                    print("Cookie consent banner detected. Clicking to dismiss...")
                    btn.click()
                    time.sleep(2)
                    break
        except Exception as consent_err:
            print(f"Cookie banner handling skipped: {consent_err}")

        # Locate search bar, enter query, and press Enter
        print("Searching for query...")
        search_selector = "input[name='search_query']"
        page.wait_for_selector(search_selector, timeout=15000)
        search_input = page.locator(search_selector).first
        search_input.fill(query)
        search_input.press("Enter")
        
        # Wait for search results to load
        print("Waiting for search results...")
        video_link_selector = "ytd-video-renderer a#video-title"
        page.wait_for_selector(video_link_selector, timeout=15000)
        
        # Select the first video search result
        first_video = page.locator(video_link_selector).first
        video_title = first_video.inner_text().strip()
        video_href = first_video.get_attribute("href")
        
        print(f"\nFound Top Video: '{video_title}'")
        print(f"Link: https://www.youtube.com{video_href}")
        
        # Click and play the video
        print("Clicking the video to play...")
        first_video.click()
        
        # Wait to let the video play for a demonstration period
        watch_duration = 15
        print(f"Playing video in background/GUI for {watch_duration} seconds...")
        
        # Optional: Ad skipping simulation loop (checks every second)
        for second in range(watch_duration):
            time.sleep(1)
            try:
                # Common selectors for Youtube skip button
                skip_btn = page.locator(".ytp-ad-skip-button, .ytp-ad-skip-button-modern").first
                if skip_btn.is_visible():
                    print("  [Ad Detected] Skip button visible. Clicking to skip ad...")
                    skip_btn.click()
            except Exception:
                pass
                
        print("Video play finished. Closing browser...")
        browser.close()

def main():
    query_input = input("Enter YouTube search topic (default: 'never gonna give you up'): ").strip()
    if not query_input:
        query_input = "never gonna give you up"
    
    try:
        play_video(query_input)
        print("Autoplay completed successfully!")
    except Exception as e:
        print(f"An error occurred during video autoplay: {e}")

if __name__ == "__main__":
    main()
