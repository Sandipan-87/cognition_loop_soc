import os
import time

from dotenv import load_dotenv
from google import genai


def main() -> None:
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY in environment or .env file.")

    client = genai.Client(api_key=api_key)
    total_calls = 15
    attempt = 0
    completed = 0

    while completed < total_calls:
        attempt += 1
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"Return a short hello for call #{completed + 1}.",
            )
            print(f"[ok] call {completed + 1}/{total_calls}: {response.text}")
            completed += 1
        except Exception as exc:
            message = str(exc).lower()
            if "429" in message or "rate" in message or "quota" in message:
                wait_seconds = 5
                print(
                    f"[rate-limit] attempt {attempt}, pausing {wait_seconds}s before retry: {exc}"
                )
                time.sleep(wait_seconds)
                continue
            raise

    print("All calls completed.")


if __name__ == "__main__":
    main()
