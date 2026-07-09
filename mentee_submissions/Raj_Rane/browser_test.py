"""
Week 2 - Task 2: browser_test.py
Scrapes current headlines from Hacker News using Playwright.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from playwright.sync_api import sync_playwright


def scrape_hacker_news(num_headlines: int = 15):
    """Scrape top headlines from Hacker News."""
    print("[*] Launching browser and navigating to Hacker News...\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://news.ycombinator.com/", timeout=30000)
        page.wait_for_selector(".titleline > a")

        # Select headline elements
        headlines = page.query_selector_all(".titleline > a")

        print(f"--- Top {num_headlines} Hacker News Headlines ---\n")
        print("-" * 60)

        results = []
        for i, headline in enumerate(headlines[:num_headlines], 1):
            title = headline.inner_text()
            link = headline.get_attribute("href")
            # Some HN links are relative
            if link and not link.startswith("http"):
                link = f"https://news.ycombinator.com/{link}"
            print(f"  {i:2}. {title}")
            print(f"      Link: {link}\n")
            results.append({"title": title, "link": link})

        print("-" * 60)
        browser.close()

    # Let the user pick a headline to open
    try:
        choice = input("\n>> Enter a headline number to open in browser (or press Enter to skip): ").strip()
        if choice and choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(results):
                import webbrowser
                url = results[idx]["link"]
                print(f"[*] Opening: {url}")
                webbrowser.open(url)
            else:
                print("[!] Invalid number.")
    except (EOFError, KeyboardInterrupt):
        print("\n[*] Skipped.")

    return results


if __name__ == "__main__":
    scrape_hacker_news()
