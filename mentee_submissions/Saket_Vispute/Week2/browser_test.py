import sys
from playwright.sync_api import sync_playwright

def scrape_hacker_news():
    print("Launching headless Chromium browser...")
    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        url = "https://news.ycombinator.com/"
        print(f"Navigating to {url}...")
        page.goto(url, timeout=30000)
        
        print("Waiting for story element selectors...")
        page.wait_for_selector(".athing", timeout=15000)
        
        # Locate the story rows
        story_rows = page.locator(".athing").all()
        
        stories = []
        # Extract top 15 stories
        for row in story_rows[:15]:
            title_element = row.locator(".titleline > a").first
            title = title_element.inner_text()
            link = title_element.get_attribute("href")
            stories.append({
                "title": title,
                "link": link
            })
            
        browser.close()
        return stories

def main():
    try:
        stories = scrape_hacker_news()
        if not stories:
            print("No stories were successfully scraped.")
            return
            
        print("\n================== HACKER NEWS TOP HEADLINES ==================")
        for idx, story in enumerate(stories, 1):
            print(f"{idx:2}. {story['title']}")
            print(f"    Source: {story['link']}")
            
        print("===============================================================\n")
        
        user_choice = input("Enter story number (1-15) to inspect or 'q' to exit: ").strip()
        if user_choice.lower() in ["q", "quit", "exit"]:
            print("Exiting. Have a nice day!")
            return
            
        try:
            choice_idx = int(user_choice) - 1
            if 0 <= choice_idx < len(stories):
                selected = stories[choice_idx]
                print("\n---------------- Selected Headline Detail ----------------")
                print(f"Title: {selected['title']}")
                print(f"Link:  {selected['link']}")
                print("----------------------------------------------------------")
            else:
                print(f"Invalid selection. Please run the script again and select a number from 1 to {len(stories)}.")
        except ValueError:
            print("Invalid input. Please enter a valid number next time.")
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
