import webbrowser
from playwright.sync_api import sync_playwright

with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=True
    )

    page = browser.new_page()

    page.goto(
        "https://news.ycombinator.com",
        wait_until="networkidle"
    )

    headlines = page.locator(
        ".titleline a"
    ).all()

    news_items = []

    print("\nTop Headlines\n")

    for i, headline in enumerate(
        headlines[:15],
        start=1
    ):

        title = headline.inner_text()

        link = headline.get_attribute(
            "href"
        )

        news_items.append(
            (title, link)
        )

        print(
            f"{i}. {title}"
        )

    browser.close()

choice = input(
    "\nEnter article number to open (or press Enter to quit): "
)

if choice.strip():

    idx = int(choice) - 1

    if 0 <= idx < len(news_items):

        webbrowser.open(
            news_items[idx][1]
        )

        print(
            "Opening article..."
        )