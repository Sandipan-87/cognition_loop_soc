from playwright.sync_api import sync_playwright

query = input("Enter search term: ")

with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=False
    )

    page = browser.new_page()

    page.goto("https://www.youtube.com")

    page.wait_for_timeout(3000)

    search_box = page.locator("input[name='search_query']")

    search_box.fill(query)

    search_box.press("Enter")

    page.wait_for_timeout(5000)

    first_video = page.locator("a#video-title").first

    first_video.click()

    print("Playing first video...")

    page.wait_for_timeout(30000)

    browser.close()
