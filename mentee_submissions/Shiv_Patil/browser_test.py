from playwright.sync_api import sync_playwright
import webbrowser

def scrape_hacker_news():
    print("Launching Chromium browser...")
    
    # 1. Start the Playwright manager
    with sync_playwright() as p:
        # Launch browser. headless=False means you actually see it open!
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        print("Navigating to Hacker News...")
        page.goto("https://news.ycombinator.com/")
        
        # Wait a moment to ensure the page is fully loaded
        page.wait_for_selector(".titleline > a")

        # 2. Grab all the headline elements
        # On Hacker News, links are <a> tags inside a <span> with class="titleline"
        headline_elements = page.locator(".titleline > a").all()
        
        scraped_data = []
        
        # 3. Loop through the top 15 elements and extract data
        for element in headline_elements[:15]: 
            title = element.inner_text()
            link = element.get_attribute("href")
            
            # Catch: Some Hacker News links are internal discussions, not full URLs.
            # We fix those so they open correctly later.
            if link and link.startswith("item?"):
                link = f"https://news.ycombinator.com/{link}"
                
            scraped_data.append({"title": title, "link": link})
            
        # Close the robot browser
        browser.close()
        
        return scraped_data

if __name__ == "__main__":
    # Run the scraper
    news_items = scrape_hacker_news()
    
    # 4. Print the formatted results
    print("\n--- Top 15 Hacker News Headlines ---")
    for index, item in enumerate(news_items):
        print(f"{index + 1}. {item['title']}")
        
    # 5. Interactive Bonus!
    print("\n------------------------------------")
    user_choice = input("Enter the number of an article to read it (or press Enter to quit): ")
    
    if user_choice.isdigit():
        choice_index = int(user_choice) - 1
        
        # Make sure they picked a valid number
        if 0 <= choice_index < len(news_items):
            target_url = news_items[choice_index]['link']
            print(f"Opening: {target_url}")
            
            # This opens the link in your actual default browser (Chrome/Edge/Safari)
            webbrowser.open(target_url)
        else:
            print("Invalid number selected.")
    else:
        print("Goodbye!")