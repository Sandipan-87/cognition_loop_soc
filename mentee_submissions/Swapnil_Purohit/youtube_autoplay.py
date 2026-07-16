import sys
import time
from playwright.sync_api import sync_playwright

def autoplay_youtube(query: str):
    print(f"Launching visible browser to search YouTube for: '{query}'")
    with sync_playwright() as p:
        # Launch Chromium in visible mode (headless=False)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            print("Navigating to YouTube...")
            page.goto("https://www.youtube.com/")
            
            # 1. Handle cookie popups if they appear
            try:
                # YouTube often shows a cookie consent dialog. 
                # We can try to click the "Accept all" or "Reject all" button if it appears.
                accept_button = page.locator("button:has-text('Accept all')").first
                if accept_button.is_visible(timeout=3000):
                    print("Found cookie consent popup, accepting...")
                    accept_button.click()
            except Exception:
                # Ignore if no popup is found
                pass

            # 2. Search for the query
            print("Entering search query...")
            # Wait for search box to be ready
            search_box = page.locator("input[name='search_query']").first
            search_box.wait_for(state="visible")
            search_box.fill(query)
            search_box.press("Enter")
            
            # 3. Wait for results to load and click the first video
            print("Waiting for search results...")
            # Wait for the video renderer elements to appear
            page.wait_for_selector("ytd-video-renderer", timeout=10000)
            
            # Select the first video title link and click it
            first_video = page.locator("ytd-video-renderer a#video-title").first
            video_title = first_video.inner_text()
            print(f"Clicking on first video: {video_title}")
            first_video.click()
            
            # 4. Let the video play for a while so the user can see it works
            print("Video should be playing now! Keeping browser open for 15 seconds...")
            time.sleep(15)
            
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            print("Closing browser.")
            browser.close()

if __name__ == "__main__":
    query = input("Enter a search term for YouTube (or press Enter for default (surprise).): ")
    if not query.strip():
        query = "Rickroll"
    
    autoplay_youtube(query)
