import os
import json
import re
import urllib.parse
from dotenv import load_dotenv
import groq
from groq import Groq
from playwright.sync_api import sync_playwright

load_dotenv()

if "GROQ_API_KEY" not in os.environ:
    raise ValueError("GROQ_API_KEY environment variable not found. Please check your .env file.")
client = Groq(api_key=os.environ["GROQ_API_KEY"])

MODEL = "llama-3.3-70b-versatile"

def search_the_web(query: str) -> str:
    print(f"\n -> [Tool executing] search_the_web with query: '{query}'...")
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://search.yahoo.com/search?q={encoded_query}"
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            page.goto(url, timeout=15000)
            page.wait_for_timeout(2000)
            
            results = page.locator("#web ol > li")
            count = results.count()
            
            if count == 0:
                browser.close()
                return "No search results found. Try another query."
                
            formatted_results = []
            valid_count = 0
            for i in range(count):
                item = results.nth(i)
                link_el = item.locator("div.compTitle a")
                snippet_el = item.locator("div.compText")
                
                if link_el.count() > 0:
                    title = link_el.first.inner_text().strip()
                    href = link_el.first.get_attribute("href")
                    
                    h3_el = link_el.locator("h3")
                    if h3_el.count() > 0:
                        title = h3_el.first.inner_text().strip()
                        
                    snippet = snippet_el.first.inner_text().strip() if snippet_el.count() > 0 else "No description available."
                    
                    if title and href:
                        valid_count += 1
                        formatted_results.append(f"[{valid_count}] Title: {title}\nURL: {href}\nSnippet: {snippet}\n")
                        if valid_count >= 5:
                            break
            
            browser.close()
            if not formatted_results:
                return "No structured search results found."
            return "\n".join(formatted_results)
            
        except Exception as e:
            if 'browser' in locals():
                browser.close()
            return f"Error executing search: {str(e)}"

def open_page(url: str) -> str:
    print(f"\n -> [Tool executing] open_page for URL: '{url}'...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            page.goto(url, timeout=15000)
            page.wait_for_timeout(2000)
            
            body_text = page.locator("body").inner_text()
            
            cleaned = re.sub(r'\n+', '\n', body_text)
            cleaned = re.sub(r'[ \t]+', ' ', cleaned)
            cleaned = cleaned.strip()
            
            max_chars = 4000
            truncated = cleaned[:max_chars]
            if len(cleaned) > max_chars:
                truncated += "\n... [Webpage content truncated for length] ..."
                
            browser.close()
            return f"Page Content of {url}:\n\n{truncated}"
            
        except Exception as e:
            if 'browser' in locals():
                browser.close()
            return f"Error opening page: {str(e)}"

tools = [
    {
        "type": "function",
        "function": {
            "name": "search_the_web",
            "description": "Searches the web for a query using Yahoo Search and returns the top 5 titles, links, and page summaries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search terms or question to look up"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_page",
            "description": "Opens a specific webpage URL and extracts its main text content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The exact absolute HTTP/HTTPS URL of the page to open"
                    }
                },
                "required": ["url"]
            }
        }
    }
]

available_tools = {
    "search_the_web": search_the_web,
    "open_page": open_page
}

def main():
    print("==================================================")
    print("      ReAct Chat Agent with Tool Chaining         ")
    print("   Type 'quit' or 'exit' to end the conversation ")
    print("==================================================")
    
    messages = [
        {
            "role": "system",
            "content": (
                "You are an intelligent ReAct research assistant. "
                "You can search the web and open specific URLs to read their text contents. "
                "You should use these tools to answer questions that require current or detailed information. "
                "You can chain tools: first search, then open a promising link from the results, "
                "read the content, and then formulate a detailed reply. "
                "Keep your answers helpful, concise, and reference URLs when appropriate. "
                "You maintain a conversation history. Remember previous turns to answer follow-up questions."
            )
        }
    ]
    
    while True:
        try:
            user_input = input("\nUser: ")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting. Goodbye!")
            break
            
        if user_input.strip().lower() in ["quit", "exit"]:
            print("Exiting. Goodbye!")
            break
            
        if not user_input.strip():
            continue
            
        messages.append({"role": "user", "content": user_input})
        
        round_num = 1
        while True:
            try:
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto"
                )
                msg = response.choices[0].message
                messages.append(msg)
                
                if not msg.tool_calls:
                    print(f"\nAssistant: {msg.content}")
                    break
                    
                tool_calls_to_execute = msg.tool_calls
            except groq.BadRequestError as err:
                body = getattr(err, "body", None)
                parsed_calls = []
                if body and isinstance(body, dict) and "error" in body:
                    error_details = body["error"]
                    if error_details.get("code") == "tool_use_failed" and "failed_generation" in error_details:
                        failed_str = error_details["failed_generation"]
                        pattern = r"<function=(\w+).*?(\{.*?\})"
                        matches = re.findall(pattern, failed_str, re.DOTALL)
                        for name, args_str in matches:
                            try:
                                args = json.loads(args_str.strip())
                                parsed_calls.append((name, args))
                            except Exception:
                                pass
                
                if not parsed_calls:
                    raise err
                    
                print(f"\n[Fallback Parser] Caught Groq tool call format failure. Parsed {len(parsed_calls)} tool call(s) from failed generation.")
                
                mock_tool_calls = []
                for idx, (name, args) in enumerate(parsed_calls):
                    mock_tool_calls.append({
                        "id": f"mock_call_{round_num}_{idx}",
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": json.dumps(args)
                        }
                    })
                
                mock_assistant_msg = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": mock_tool_calls
                }
                messages.append(mock_assistant_msg)
                
                class MockFunction:
                    def __init__(self, name, arguments):
                        self.name = name
                        self.arguments = arguments
                        
                class MockToolCall:
                    def __init__(self, id, function):
                        self.id = id
                        self.function = function
                
                tool_calls_to_execute = [
                    MockToolCall(mock_call["id"], MockFunction(mock_call["function"]["name"], mock_call["function"]["arguments"]))
                    for mock_call in mock_tool_calls
                ]
                
            for call in tool_calls_to_execute:
                tool_name = call.function.name
                tool_args = json.loads(call.function.arguments)
                
                print(f"\n[Tool Call] Agent calls: '{tool_name}' with args {json.dumps(tool_args)}")
                
                if tool_name in available_tools:
                    tool_func = available_tools[tool_name]
                    try:
                        result = tool_func(**tool_args)
                    except Exception as err:
                        result = f"Error executing tool: {str(err)}"
                else:
                    result = f"Error: Tool '{tool_name}' is not supported."
                    
                print(f"[Tool Response] Tool execution completed.")
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": tool_name,
                    "content": result
                })
                
            round_num += 1

if __name__ == "__main__":
    main()
