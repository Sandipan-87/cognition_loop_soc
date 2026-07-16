from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    
    browser=p.chromium.launch(headless=False)

    context=browser.new_context()

    page=context.new_page()

    page.goto("https://bbc.com/news")

    loc_headline = page.get_by_test_id("card-headline")
    loc_description = page.get_by_test_id("card-description")

    headlines = loc_headline.all_inner_texts()
    descriptions = loc_description.all_inner_texts()

    print("TOP 10 HEADLINES")
    for i in range(10):
        print(f"{i+1}. {headlines[i]}")
        print()
        print(descriptions[i])
        print()
        print()

