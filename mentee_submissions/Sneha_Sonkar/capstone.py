import os
import time
from dotenv import load_dotenv
from groq import Groq, RateLimitError

# Load environment variables
load_dotenv()

# Global Constants
MODEL = "llama-3.3-70b-versatile"

def get_client() -> Groq:
    """Initialize and return the Groq client instance safely."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("CRITICAL: GROQ_API_KEY missing from environment setup.")
    return Groq(api_key=api_key)

def call_llm(client, messages, tools=None, max_retries=5):
    """One Groq call, hardened against HTTP 429 with exponential backoff."""
    delay = 2  # seconds
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto" if tools else None,
            )
        except RateLimitError:
            if attempt == max_retries - 1:
                raise  # give up after the last attempt
            print(f"    rate-limited (429). backing off {delay}s…")
            time.sleep(delay)
            delay *= 2  # 2s → 4s → 8s → 16s …
    raise RuntimeError("Exhausted all API connection retries.")

def main():
    print("=========================================================")
    print("📈 Initializing Capstone Milestone Checkpoint...")
    print("=========================================================\n")
    
    try:
        client = get_client()
        
        # Make exactly one successful call to verify the infrastructure connection
        test_message = [{"role": "user", "content": "Respond with exactly the word: 'CONNECTED'."}]
        response = call_llm(client, test_message)
        
        print(f"Groq API Connection Test: {response.choices[0].message.content.strip()}")
        print("\n✅ July 14th Checkpoint Verification Successful.")
        
    except Exception as e:
        print(f"❌ Verification Failure: {str(e)}")

if __name__ == "__main__":
    main()