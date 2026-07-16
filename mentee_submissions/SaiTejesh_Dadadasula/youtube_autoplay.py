from playwright.sync_api import sync_playwright


yt_video_to_play = "faded"
with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled"
        ]
    )
    context = browser.new_context()
    page = context.new_page()

    page.goto("https://www.youtube.com")

    loc_search = page.get_by_placeholder("Search")
    loc_search.fill(yt_video_to_play)
    loc_search.press("Enter")
    page.wait_for_load_state("networkidle")

    page.locator("#video-title").first.click()

    page.wait_for_timeout(1000)
    x=page.locator(".video-ads").count()
    if x:
        page.locator(".ytp-skip-ad-button").wait_for(state="visible",timeout=30000)
        page.locator(".ytp-skip-ad-button").click()

    page.locator(".ytp-fullscreen-button").click()

    page.pause()

