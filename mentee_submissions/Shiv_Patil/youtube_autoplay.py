from playwright.sync_api import sync_playwright
import time

def play_youtube_video(search_term):
    print(f"Launching Chromium to search for: '{search_term}'...")

    # Start the Playwright manager
    with sync_playwright() as p:
        # Launch browser in headed mode so we can watch it happen
        browser = p.chromium.launch(headless=False)
        
        # Create a context with a standard desktop viewport
        context = browser.new_context(viewport={'width': 1280, 'height': 720})
        page = context.new_page()

        print("Navigating to YouTube...")
        page.goto("https://www.youtube.com/")

        # --- Challenge 1: Handling Cookie Pop-ups ---
        # Depending on your region, YouTube might throw a full-screen cookie consent dialog.
        # We try to find and click the 'Accept All' or 'Reject All' button.
        try:
            # We use a short timeout so the script doesn't freeze if the pop-up doesn't exist
            cookie_button = page.locator('button:has-text("Accept all"), button:has-text("Reject all")').first
            if cookie_button.is_visible(timeout=3000):
                cookie_button.click()
                print("Handled cookie pop-up.")
        except Exception:
            pass # No pop-up appeared, which is completely fine

        # --- Search Phase ---
        print("Typing search query...")
        
        # 1. Use the more reliable 'name' attribute
        # 2. Explicitly wait for it to be visible before trying to click
        page.wait_for_selector('input[name="search_query"]', state="visible")
        
        search_box = page.locator('input[name="search_query"]')
        search_box.click()
        search_box.fill(search_term)
        search_box.press("Enter")

        # --- Click the First Video ---
        print("Waiting for results and clicking the first video...")
        # Wait for the specific HTML element that holds video results to load
        page.wait_for_selector('ytd-video-renderer')

        # Grab the first video thumbnail link and click it
        first_video = page.locator('ytd-video-renderer a#thumbnail').first
        first_video.click()

        # --- Challenge 2: Fullscreen ---
        print("Video is loading... entering Fullscreen mode.")
        # Wait for the actual HTML5 video player to render on the DOM
        page.wait_for_selector('.html5-video-player')
        time.sleep(2) # Give the player a brief moment to grab focus
        page.keyboard.press('f') # YouTube's native keyboard shortcut for fullscreen

        print("\nWatching the video. (Press Ctrl+C in your terminal to stop)")

        # --- Challenge 3: Handle Ads (The Infinite Loop) ---
        # We keep the script alive and constantly scan the DOM for the "Skip Ad" button
        try:
            while True:
                # YouTube uses a few different classes for the skip button, so we look for either
                skip_button = page.locator('.ytp-skip-ad-button, .ytp-ad-skip-button-modern')
                
                if skip_button.is_visible():
                    print("Ad detected! Skipping...")
                    skip_button.click()
                
                # Sleep briefly to avoid maxing out your CPU with rapid DOM checks
                time.sleep(1)
                
        except KeyboardInterrupt:
            # This cleanly catches when you press Ctrl+C in the terminal
            print("\nClosing browser...")

        # Shut down the browser process
        browser.close()

if __name__ == "__main__":
    print("--- YouTube Autoplay Agent ---")
    user_query = input("Enter a search term: ")
    
    if user_query.strip():
        play_youtube_video(user_query)
    else:
        print("Search term cannot be empty!")