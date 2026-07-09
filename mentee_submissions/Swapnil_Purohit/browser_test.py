import sys
import webbrowser
from playwright.sync_api import sync_playwright

def scrape_hacker_news():
    print("Launching Chromium browser to scrape Hacker News...")
    with sync_playwright() as p:
        # Launch browser in headless mode
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Navigate to Hacker News
        print("Navigating to https://news.ycombinator.com/ ...")
        page.goto("https://news.ycombinator.com/")
        
        # Wait for the main story links to load
        page.wait_for_selector(".titleline > a")
        
        # Extract the headlines and links
        story_elements = page.locator(".titleline > a").all()
        
        print("\n--- Top 10 Hacker News Headlines ---\n")
        
        top_stories = []
        for i, element in enumerate(story_elements[:10]):
            title = element.inner_text()
            link = element.get_attribute("href")
            # If it's a relative link (like "item?id=..."), make it absolute
            if link and link.startswith("item?"):
                link = "https://news.ycombinator.com/" + link
                
            top_stories.append({"title": title, "link": link})
            print(f"{i + 1}. {title}")
        
        print("-" * 36)
        
        browser.close()
        return top_stories

if __name__ == "__main__":
    stories = scrape_hacker_news()
    
    if stories:
        choice = input("\nEnter the number of the article you want to read (or press Enter to quit): ")
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(stories):
                url_to_open = stories[index]['link']
                print(f"Opening {url_to_open} in your default browser...")
                webbrowser.open(url_to_open)
            else:
                print("Invalid number.")
        else:
            print("Quitting.")
    else:
        print("Failed to fetch stories.")
