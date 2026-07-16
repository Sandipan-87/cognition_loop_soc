from playwright.sync_api import sync_playwright

with sync_playwright() as p:

    browser = p.chromium.launch(headless=False)

    page = browser.new_page()

    page.goto("https://news.ycombinator.com")

    page.wait_for_timeout(2000)

    headlines = page.locator(".titleline a")

    count = min(headlines.count(), 10)

    print("\nTop Hacker News Headlines\n")

    for i in range(count):

        headline = headlines.nth(i)

        print(f"{i+1}. {headline.inner_text()}")

        print(headline.get_attribute("href"))
        print()

    browser.close()
