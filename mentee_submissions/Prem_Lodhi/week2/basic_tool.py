"""
basic_tool.py – Competitive Intelligence Agent using Groq.

This is the main orchestrator. It defines two tools:
  - scrape_news   (from browser_test.py)
  - play_company_video (from youtube_autoplay.py)

It runs an interactive conversation loop where the agent decides when
to call which tool based on the user's query, then delivers a natural-
language briefing.
"""
import os
import json
import logging
from typing import List, Dict, Any

from dotenv import load_dotenv
from groq import Groq

# Import the actual tool functions
from browser_test import scrape_news
from youtube_autoplay import play_company_video

# --------------------------------------------------------------------------- #
# Logging Configuration
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("Agent")

# --------------------------------------------------------------------------- #
# Environment & API Key
# --------------------------------------------------------------------------- #
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not found in .env file. Please set it and try again.")

client = Groq(api_key=GROQ_API_KEY)

# --------------------------------------------------------------------------- #
# Tool Definitions (Groq function-calling schema)
# --------------------------------------------------------------------------- #
TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "scrape_news",
            "description": (
                "Get the latest news headlines about a company from Google News. "
                "Returns a list of headlines with titles, links, and timestamps."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {
                        "type": "string",
                        "description": "Name of the company to search news for, e.g. 'Tesla', 'OpenAI'."
                    }
                },
                "required": ["company"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_company_video",
            "description": (
                "Open YouTube in a visible browser and auto-play a recent video "
                "about the company. Use this when the user wants to see a video, "
                "or asks for a 'review', 'demo', 'interview', or 'update' in video form."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {
                        "type": "string",
                        "description": "Name of the company to search for on YouTube."
                    }
                },
                "required": ["company"]
            }
        }
    }
]

SYSTEM_PROMPT = (
    "You are a Competitive Intelligence Assistant. You can fetch live news headlines "
    "and play YouTube videos.\n\n"
    "- If the user asks about the latest news, call scrape_news.\n"
    "- If the user asks to see a video, call play_company_video.\n"
    "- You may call both tools if the user wants a full briefing.\n"
    "- After receiving tool results, you MUST provide a concise, natural-language briefing. "
    "If you played a video, mention the video title.\n"
    "- If tool results are empty or contain an error, explain that gracefully.\n"
    "- Do not call the same tool twice for the same query."
)

# --------------------------------------------------------------------------- #
# Helper: Execute a tool call and return its result as a JSON string
# --------------------------------------------------------------------------- #
def execute_tool_call(tool_call: Any) -> str:
    """Execute the actual Python function corresponding to a tool call."""
    func_name = tool_call.function.name
    args = json.loads(tool_call.function.arguments)
    logger.info(f"Calling tool: {func_name}({args})")

    try:
        if func_name == "scrape_news":
            headlines = scrape_news(args["company"])
            if not headlines:
                return json.dumps({"error": "No headlines found for that company."})
            return json.dumps(headlines, indent=2)

        elif func_name == "play_company_video":
            video_title = play_company_video(args["company"])
            return json.dumps({"video_title": video_title})

        else:
            return json.dumps({"error": f"Unknown function: {func_name}"})

    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return json.dumps({"error": str(e)})

# --------------------------------------------------------------------------- #
# Main Conversation Loop
# --------------------------------------------------------------------------- #
def main() -> None:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    print("\n🔍 Competitive Intelligence Agent ready.")
    print("Ask about a company, e.g. 'What's new with Tesla?' or 'Show me a video about OpenAI.'")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ")
        if user_input.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        messages.append({"role": "user", "content": user_input})

        # First call – model decides whether to use tools
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",   # or "mixtral-8x7b-32768"
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.2,
            )
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            print("Agent: Sorry, I encountered an API error. Please try again.")
            continue

        msg = response.choices[0].message

        # If the model requests tool calls
        if msg.tool_calls:
            # Append assistant message with tool_calls (required by API)
            assistant_message = {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
            messages.append(assistant_message)

            # Execute each tool and add results
            for tool_call in msg.tool_calls:
                result_str = execute_tool_call(tool_call)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": result_str,
                })

            # Second call – get the final natural-language response
            try:
                final_response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                    temperature=0.4,
                )
                final_msg = final_response.choices[0].message
                print(f"Agent: {final_msg.content}")
                messages.append({"role": "assistant", "content": final_msg.content})

            except Exception as e:
                logger.error(f"Groq API error on final call: {e}")
                print("Agent: Sorry, I had trouble composing the briefing.")
                continue

        else:
            # No tool calls – just output the response
            print(f"Agent: {msg.content}")
            messages.append({"role": "assistant", "content": msg.content})

# --------------------------------------------------------------------------- #
# Entry Point
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    main()