import sys
import webbrowser
from dataclasses import dataclass

from playwright.sync_api import sync_playwright

NEWS_URL = "https://news.ycombinator.com/"


@dataclass
class Headline:
    title: str
    url: str


def scrape_hacker_news_headlines(limit: int = 15) -> list[Headline]:
    """Scrape top story titles and links from Hacker News."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(NEWS_URL, wait_until="domcontentloaded")

        rows = page.locator("tr.athing").all()[:limit]
        headlines: list[Headline] = []

        for row in rows:
            title_link = row.locator("span.titleline > a").first
            title = title_link.inner_text().strip()
            href = title_link.get_attribute("href") or ""

            if href.startswith("item?"):
                url = f"https://news.ycombinator.com/{href}"
            elif href.startswith("http"):
                url = href
            else:
                url = f"https://news.ycombinator.com/{href}"

            headlines.append(Headline(title=title, url=url))

        browser.close()

    return headlines


def print_headlines(headlines: list[Headline]) -> None:
    print(f"\nTop {len(headlines)} headlines from Hacker News:\n")
    for index, headline in enumerate(headlines, start=1):
        print(f"{index}. {headline.title}")
        print(f"   {headline.url}\n")


def open_selected_headline(headlines: list[Headline]) -> None:
    choice = input("Enter a headline number to open in your browser (or press Enter to skip): ").strip()
    if not choice:
        return

    if not choice.isdigit():
        print("Please enter a valid number.")
        return

    number = int(choice)
    if number < 1 or number > len(headlines):
        print(f"Pick a number between 1 and {len(headlines)}.")
        return

    selected = headlines[number - 1]
    print(f"Opening: {selected.title}")
    webbrowser.open(selected.url)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("Fetching latest headlines...")
    headlines = scrape_hacker_news_headlines()
    if not headlines:
        print("No headlines found. The page layout may have changed.")
        return

    print_headlines(headlines)
    open_selected_headline(headlines)


if __name__ == "__main__":
    main()
