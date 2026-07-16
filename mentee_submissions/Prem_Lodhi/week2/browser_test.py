"""
browser_test.py – Reliable news scraping via Google News RSS.
Uses Playwright to fetch the RSS feed, then parses XML.
"""
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

def scrape_news(company: str, limit: int = 5) -> List[Dict[str, Optional[str]]]:
    headlines = []
    logger.info(f"Scraping news for company: {company}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            # RSS feed URL – always returns valid XML, no JS required
            rss_url = (
                f"https://news.google.com/rss/search?q={company}&hl=en-US&gl=US&ceid=US:en"
            )
            logger.debug(f"Fetching RSS: {rss_url}")
            page.goto(rss_url, wait_until="load", timeout=20000)

            # Get page content (the XML)
            xml_content = page.content()

            # Parse XML
            root = ET.fromstring(xml_content)
            items = root.findall(".//item")  # Standard RSS items

            for item in items[:limit]:
                title = item.findtext("title", default="No title").strip()
                link = item.findtext("link", default=None)
                pub_date = item.findtext("pubDate", default="No time")

                headlines.append({
                    "title": title,
                    "link": link,
                    "time": pub_date,
                })

            logger.info(f"Parsed {len(headlines)} headlines from RSS.")

        except Exception as e:
            logger.error(f"RSS scraping error: {e}")
        finally:
            browser.close()

    return headlines


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = scrape_news("Nvidia")
    for i, h in enumerate(results, 1):
        print(f"{i}. {h['title']} ({h['time']})")
        print(f"   Link: {h['link']}\n")