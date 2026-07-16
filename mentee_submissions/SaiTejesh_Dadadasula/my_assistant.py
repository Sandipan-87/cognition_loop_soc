import os
import json
import random
from groq import Groq
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

client=Groq(
    api_key=os.environ['GROQ_API_KEY_1']
)

MODEL='qwen/qwen3-32b'
MEMORY_FILE='memory.json'
GOALS_FILE='goals.json'

## remember and recall tools
#file2
def remember(fact):
    memory=recall_list()
    memory.append(fact)
    with open(MEMORY_FILE,"w") as f:
        json.dump(memory,f,indent=2)
    return f"Succesfully remembered"

def recall_list():
    with open(MEMORY_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def recall():
    facts=recall_list()
    if facts:
        return str(facts)
    else:
        return "I dont remember anything"

##

##
#file3
#random no
def let_fate_decide(options_list : list):
    if len(options_list)==0:
        return "No options given in the list!!!!"
    x=str(random.choice(options_list))
    return x
#



#file4

def load_goals():
    with open(GOALS_FILE,"r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}
        
def save_goals(data):
    with open(GOALS_FILE,"w") as f:
        json.dump(data,f,indent=2)

def add_goal(goal):
    data=load_goals()
    data[goal]="Not Done"
    save_goals(data)
    return "Added Goal Succesfully!"

def list_goals():
    data=load_goals()
    string_data=json.dumps(data)
    return string_data

def complete_goal(number):
    data=load_goals()
    if 0<=number and number<len(data):
        key=list(data)[number]
    if data[key]=="Not Done":
        data[key]="Done"
        save_goals(data)
        return "Goal Marked Done!"
    if data[key]=="Done":
        return "Goal is Aldready Done and marked Done before!"
    
    return "number arg is sent wrong!"

    

#
# Tool search_the_web
def search_the_web(search_string : str):

    with sync_playwright() as p:
        browser=p.chromium.launch(headless=False)
        context=browser.new_context()
        
        page=context.new_page()
        
        page.goto('https://html.duckduckgo.com/html/')

        page.locator('#search_form_input_homepage').fill(search_string)
        page.locator('#search_button_homepage').click()

        # page.wait_for_timeout(1000)
        # page.locator('.result:not(.result--ad) .result__a').nth(0).click()
        # page.wait_for_timeout(1000)
        return page.locator('body').inner_text()

def open_page(url : str):
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=False)
        context=browser.new_context()
        page=context.new_page()
        try:
            page.goto(url,timeout=5000)
        except:
            print(f"Page load timed out after 5 seconds. Returning partial content...")
            return page.locator('body').inner_text()[:4000]
        return page.locator('body').inner_text()[:4000]

tools=[
    {
        "type" : "function",
        "function" : {
            "name" : "search_the_web",
            "description" :"searches in duckduckgo and returns search page results body text",
            "parameters" : {
                "type" : "object",
                "properties":{
                    "search_string" : {
                        "type" : "string" ,
                        "description" : "string used for searching in web "
                    }
                },
                "required" : ["search_string"]
            }
        }
    },
    {
        "type" : "function",
        "function" : {
            "name" : "open_page",
            "description" : "opens a url directly and returns body of the text",
            "parameters" : {
                "type" : "object",
                "properties":{
                    "url" : {
                        "type" : "string",
                        "description" : "string which is the direct link url for the site which we are opening "
                                        "Take the url from previous text u searched from the web "
                                        "if one url didnt work take another url from the text searched from the web.."
                    }
                },
                "required" : ["url"]
            }
        }
    },
    {
        "type" : "function",
        "function":{
            "name":"recall",
            "description":"Call this tool At the start of conversation "
                          "So that we will get to know the memory of past conversations",
            "parameters":{
                "type" : "object",
                "properties" : {}
            }
        }
    },
    {
        "type" : "function",
        "function":{
            "name":"remember",
            "description": "Call this tool after u got the answer from using other tools just before answering call this tool"
                           "It will Store the facts it got to know About the user to a file"
                           "Take the user prompt and see if he gives any information"
                           "This tool is called for every userprompt at last only if something worth remembering is there",

            "parameters":{
                "type":"object",
                "properties":{
                    "fact" : {
                        "type" : "string",
                        "description" : "It is a short string "
                                        "It is a fact about the user"
                                        "Understand it from the user prompt"
                                        "Fact Can be informational or psycological or Any other liking or disliking or any other informatio "
                    }
                },
                "required" : ["fact"]
            }
        }
    },
    {
        "type" : "function" ,
        "function" : {
            "name" : "let_fate_decide",
            "description" : "When user asks to choose between some option use this tool to choose randomly without a bias"
                            "it returns a string from the list of options it have",
            "parameters" : {
                "type" : "object" ,
                "properties" : {
                    "options_list" : {
                        "type" : "array",
                        "description" : "This is the List of the options from which we have to choose One option randomly"
                                        "Give the options cleverly based on the context see carefully!!!"
                                        "if the options list need to be corrected based on past do it and send it!",
                        "items" : {
                            "type" : "string"
                        }
                    }
                },
                "required" : ["options_list"]
            }

        }
    },
    {
        "type":"function",
        "function" : {
            "name" : "add_goal",
            "description": "If User mentions Something about He wants to do or Some goal of Him, Use this tool to Add the goal to the json file"
                            "This only needs to be done when user mentions some new goal other than the goals listed aldready which u can get from the tool list_goals()",
            "parameters" : {
                "type" : "object" ,
                "properties" : {
                    "goal" : {
                        "type" : "string",
                        "description" : "This is a short string representing the goal of the user which needs to be added!"
                    }
                },
                "required" : ["goal"]
            }
        }       
    } ,
    {
        "type" : "function",
        "function" : {
            "name" : "list_goals",
            "description":  "If user asks about the goals list , Use this tool to return the string of dictionary of the goals"
                            " Whenever Any Discussion on goals came run this tool to see the status"
                            "This can also be used to find the index of the goal when it needs to be marked So that u can use the tool complete_goal(number) to mark using index"
                            "This should be used also before adding a goal to make sure it is a new goal or a goal i aldready have..",
            "parameters":{
                "type":"object",
                "properties":{

                }
            }
        }
    },
    {
        "type" : "function",
        "function" : {
            "name" : "complete_goal",
            "description" : "When user needs to mark some goal as done , U need to use this tool",
            "parameters":{
                "type":"object",
                "properties" : {
                    "number" : {
                        "type" : "integer",
                        "description" : "This is the index of goals which need to be marked Done, we can get these from the tool list_goals()",
                    }
                },

                "required" : ["number"]
            }
        }
    }
]

availale_func={
    "search_the_web" : search_the_web,
    "open_page" : open_page,
    "remember" : remember,
    "recall" : recall,
    "let_fate_decide" : let_fate_decide,
    "add_goal": add_goal,
    "list_goals" : list_goals,
    "complete_goal" : complete_goal
}

SYSTEM="""You are a chat agent  which answers questions and can also take followup questions and then answer 
But if u dont have data u uses tools to search the web and open urls and take the test from it
and then answers the question
You must only use the exact tool names provided to you. Do not alter, modify, or append any text to the tool names under any circumstances.
You give the answer in genz way slangs and short forms """ 
memory_data=recall()
SYSTEM=SYSTEM+f"\n\nHere is what you already know about the user:\n{memory_data}"
SYSTEM=SYSTEM+f"\n\nThe user's current quest log:\n{list_goals()}"

def run_agent():
    messages=[
        {
            "role" : "system",
            "content" : SYSTEM
        },

    ]

    max_steps=4
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"quit", "exit", "q"}:
            break
        messages.append({"role" : "user" , "content": user_input})
        steps=0
        while steps<max_steps:
            response = client.chat.completions.create(
                messages=messages,
                tools=tools,
                tool_choice="auto",
                model=MODEL,
                # response_format={"type":"json_object"}
            )

            response_message = response.choices[0].message
            tool_calls= response_message.tool_calls

            messages.append(response_message)

            if not tool_calls:
                print(response_message.content)
                break

            for tool_call in tool_calls:
                print(f"using tool {tool_call.function.name}")
                func_name= tool_call.function.name
                func_args= json.loads(tool_call.function.arguments)

                #cleaning func_args
                if func_args==None:
                    func_args={}
                func_args = {k: v for k, v in func_args.items() if k != ""}
                #
                func_to_call= availale_func[func_name]
                func_response= func_to_call(**func_args)

                messages.append(
                    {
                        "role" : "tool",
                        "tool_call_id" : tool_call.id,
                        "name" : func_name,
                        "content" : func_response
                    }
                )
            steps+=1
        else:
            print("Max steps reached so forcing answer!")
            messages.append({
                "role": "user",
                "content": "Based only on what you've already found above, give me the final answer now. Do not search again."
            })
            final=client.chat.completions.create(
                messages=messages,
                model=MODEL
            )
            print(final.choices[0].message.content)

if __name__=="__main__":
    run_agent()