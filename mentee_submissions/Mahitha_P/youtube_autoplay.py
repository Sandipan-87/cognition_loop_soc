from playwright.sync_api import sync_playwright

query = input("Enter YouTube search query: ")

with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=False
    )

    page = browser.new_page()

    print("Opening YouTube...")

    page.goto(
        "https://www.youtube.com",
        wait_until="networkidle"
    )

    # Handle cookie popup if present
    try:
        page.get_by_role(
            "button",
            name="Accept all"
        ).click(timeout=5000)

        print("Accepted cookies.")

    except:
        pass

    # Search
    search_box = page.locator(
        "input[name='search_query']"
    )

    search_box.fill(query)

    search_box.press("Enter")

    page.wait_for_load_state(
        "networkidle"
    )

    print("Search completed.")

    # Click first video
    first_video = page.locator(
        "ytd-video-renderer a#video-title"
    ).first

    first_video.click()

    page.wait_for_load_state(
        "networkidle"
    )

    # Print title
    try:
        title = page.locator(
            "h1.ytd-watch-metadata"
        ).inner_text()

        print(f"\nNow Playing: {title}")

    except:
        print("Could not fetch title.")

    # Wait for player to initialize
    page.wait_for_timeout(5000)

    print("Checking for advertisements...")

    ad_skipped = False

    # Check repeatedly for skip button
    for _ in range(6):

        try:
            if page.locator(".ad-showing").count() > 0:

                print("Ad detected.")

                skip_btn = page.locator(
                    ".ytp-ad-skip-button, .ytp-skip-ad-button"
                )

                if skip_btn.count() > 0:

                    skip_btn.first.click()

                    print("Ad skipped!")

                    ad_skipped = True

                    break

        except:
            pass

        page.wait_for_timeout(5000)

    if not ad_skipped:
        print("No skippable ad found.")

    # Fullscreen
    try:
        page.keyboard.press("f")
        print("Fullscreen enabled.")
    except:
        print("Could not enable fullscreen.")

    print("Playing video for 60 seconds...")

    page.wait_for_timeout(60000)

    browser.close()

    print("Browser closed.")