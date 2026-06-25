import requests
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_groq import ChatGroq
from dotenv import load_dotenv
load_dotenv()
import os

API_KEY=os.getenv("COINGECKO_API_KEY")
URL="https://api.coingecko.com/api/v3/simple/price"

llm=ChatGroq(model="llama-3.3-70b-versatile")

def get_crypto_price(coin_name):
    """
    Fetches the current real-time price of a cryptocurrency in USD from CoinGecko.
    Args:
        coin_name (str): The name of the cryptocurrency in lowercase (e.g., 'bitcoin', 
        'ethereum', 'solana')."""
    

    API_KEY=os.getenv("COINGECKO_API_KEY")
    URL="https://api.coingecko.com/api/v3/simple/price"
    header={
        "x-cg-demo-api-key": API_KEY,
        "Accept": "application/json"
        }
    parameters = {
        "ids": coin_name.lower(),
        "vs_currencies": "usd"
    }    
    response=requests.get(URL,headers=header,params=parameters)

    if response.status_code==200:
        text=response.json()
        print(text)
    else:
        print(f"error: {response.status_code}")
llm_with_tools = llm.bind_tools([get_crypto_price])



if __name__ == "__main__":
    print("User: How much does a bitcoin cost right now?")
    
    # 1. Setup the conversation history
    messages = [HumanMessage(content="How much does a bitcoin cost right now?")]
    
    # 2. First API Call (The Decision)
    ai_msg = llm_with_tools.invoke(messages)
    messages.append(ai_msg) # Save the AI's request to the history
    
    # 3. Check if the AI decided to use a tool
    if ai_msg.tool_calls:
        # Extract the specific tool call details
        tool_call = ai_msg.tool_calls[0]
        tool_name = tool_call["name"]
        requested_coin = tool_call["args"]["coin_name"]
        tool_id = tool_call["id"]
        
        print(f"\n[System: AI decided to use tool '{tool_name}' for '{requested_coin}']")
        
        # 4. RUN YOUR REAL PYTHON FUNCTION
        live_price_data = get_crypto_price(requested_coin)
        print(f"[System: Tool returned data: {live_price_data}]\n")
        
        # 5. Create a ToolMessage to hand the data back to the AI
        tool_msg = ToolMessage(
            content=live_price_data, 
            tool_call_id=tool_id # We must pass the ID so the AI knows which request this answers
        )
        messages.append(tool_msg) # Add the tool's answer to the history
        
        # 6. Second API Call (The Final Answer)
        # We pass the full history: [User Question, AI Tool Request, Tool Answer]
        final_response = llm_with_tools.invoke(messages)
        
        print(f"AI: {final_response.content}")
        
    else:
        # If the AI didn't need a tool, just print its normal response
        print(f"AI: {ai_msg.content}")