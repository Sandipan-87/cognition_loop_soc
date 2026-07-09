import os
import json
import time
from groq import Groq,RateLimitError,BadRequestError
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright,TimeoutError as PlaywrightTimeoutError

load_dotenv()
client=Groq(api_key=os.environ["GROQ_API_KEY_final"])

MODEL='openai/gpt-oss-120b'
PLAN_JSON="plan.json"
NO_OF_LINKS=5


def call_llm(client,messages,tools=None,tool_choice="none",max_retries=5,response_format=None):
    delay=2 

    for attempt in range(max_retries):
        kwargs = {
            "model": MODEL,
            "messages": messages,
            "response_format": response_format,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        try:
            return client.chat.completions.create(**kwargs)
        except RateLimitError:
            if attempt==max_retries-1:
                raise 

            print(f"    rate-limited (429). backing off {delay}s…")
            time.sleep(delay)
            delay*=2
    
    raise RuntimeError("exhaustive entries")




def make_brief_city_timeline_plan(prompt):
    messages_1=[
                {
                    "role": "system",
                    "content": """
                You are a travel itinerary planner. Given a user prompt, extract:
                - Starting place (city/town)
                - Final destination (if given as a country/state, resolve it to the main
                city/town that best represents it)
                - Total number of days
                - Any additional preferences mentioned by the user

                OUTPUT FORMAT (strict):
                PLACEA TO PLACEB - TRANSIT TIME (in days, fractions allowed) (mode of transport,
                ONLY if you are certain of it — e.g. flight/train/car/bus; omit if unsure)
                PLACEB - STAY - DAYS
                PLACEB TO PLACEC - TRANSIT TIME (mode, if known)
                PLACEC - STAY - DAYS
                ...
                PLACEX TO PLACEA - TRANSIT TIME (mode, if known)  [return to starting place]

                RULES:

                1. PLACES ARE ALWAYS CITY/TOWN/VILLAGE LEVEL — never a state or country name
                in the output, even if the user mentioned one.

                2. ROUTE BUILDING:
                - Step 1: Find a sensible path from the start to the destination. If no
                    direct route makes sense, include ONE brief intermediate transit stop
                    (not a real stay — 1 day max).
                - Step 2: Identify a number of worthwhile nearby cities/towns near the main
                    destination based on the days we have ,that fit the traveler's pace and total day count.
                - Do not overload the trip with cities, and do not under-use the days
                    given. Medium pace = enough to see each place without rushing.

                3. DAY ALLOCATION (apply this consistently to every stay in the plan):
                - available_stay_days = total_days - sum(all transit days)
                - Classify each place as MAJOR (large/primary city) or MINOR (smaller
                    town/day-trip-style place).
                - Give MAJOR places roughly 1.5x the days of MINOR places — not more.
                    A rough split for a typical trip: MAJOR = 2-3 days, MINOR = 1-2 days.
                - Distribute available_stay_days across all places using that ratio.
                    Round sensibly so days add up to available_stay_days.
                - Never let one place absorb the majority of the trip unless the user
                    explicitly asked to spend most of the trip there.

                4. If the user gives additional info (specific interests, pace preference,
                must-see places, fixed days somewhere, etc.), that OVERRIDES the default
                pacing/day rules above — adjust the plan and day counts accordingly,
                consistently across the whole itinerary.

                5. OUTPUT SCOPE: This is a brief high-level outline only — city names, stay
                days, transit days, and transport mode (if certain). No descriptions,
                no activities, no other detail.
                """
                },
                {
                    "role" : "user",
                    "content" : prompt
                }
        ]

    response=call_llm(client,messages_1)
    response_message=response.choices[0].message

    messages_1.append(
        {
            "role" : "assistant",
            "content" : response_message.content
        }
    )
    return response_message.content



plan_schema={
    "type" : "json_schema" ,
    "json_schema" :{
        "name" : "project_data",
        "strict" : True,
        "schema":{
            "type" : "object",
            "properties" : {
                "goal" : {
                    "type" : "string",
                    "description" : "overall goal of the objective"
                },
                "status" : {
                    "type" : "string" , "enum" : ["in_progress","done"],
                    "description" : "status of entire project",
                },
                "current_step" : {
                    "type" : "integer",
                    "description" : "step id of the current step which the model is working"
                },
                "steps" : {
                    "type" : "array",
                    "description" : "array of each step of the plan of the project",
                    "items" : {
                        "type" :"object" ,             
                        "properties" : {
                            "id" : {
                                "type" : "integer",
                                "description" : "a unique 1-based number in numeric order for arrays"
                            },
                            "task" : {
                                "type" : "string",
                                "description" : "One sub task of the whole project"
                            },
                            "status" : {
                                "type" : "string" , 
                                "enum" : ["pending","in_progress","done"],
                                "description" : "status of this step"
                            },
                            "result" : {
                                "type" : ["string" , "null"],
                                "description" : "initially null but after step is over it will be having result of the task"
                            }
                        },
                        "required" :["id", "task", "status", "result"],
                        "additionalProperties": False
                    }
                }
            },
            "required" : ["goal", "status", "current_step", "steps"],
            "additionalProperties": False
        }
    }
}

def make_plan(timeline_content):
    messages_2=[
        {
            "role": "system",
            "content": """
        Your task is to convert a brief itinerary timeline (given by the user) into a
        structured starting JSON plan.

        OUTPUT SCHEMA:
        | Field              | Type                              | Meaning                                    |
        |---------------------|-----------------------------------|---------------------------------------------|
        | goal                | string                             | The user's original request, verbatim.       |
        | status              | "in_progress" | "done"            | Whole-plan status.                           |
        | current_step        | integer                            | id of the step currently being worked on.    |
        | steps[].id          | integer                            | Stable, 1-based. Never renumber.             |
        | steps[].task        | string                              | A single, self-contained instruction.        |
        | steps[].status      | "pending"|"in_progress"|"done"    | Per-step status (makes the plan resumable).  |
        | steps[].result      | string | null                     | Output of the step. null until done.         |

        GLOBAL RULES (apply to every step you generate):
        - Only use information present in the user's prompt/timeline. Do not invent
        or add details that weren't given.
        - Include every piece of relevant info that WAS given (city names, days,
        transport mode, any extra preferences) — don't drop anything.
        - Initialize all other fields of each step properly (status="pending",
        result=null, correct id).

        BUILD ORDER:

        0. Top-level fields:
        - goal = {user_prompt}
        - status = "in_progress"
        - current_step = 1

        1. TRANSIT step (for each leg of travel):
        - Note: starting point, destination, transport mode (only if explicitly
            mentioned in the prompt).
        - Task format: "Find transport from Place A to Place B (+ additional
            info if given)"

        2. STAY step (for each place stayed):
        - Note: city name, number of days, any additional info.
        - Task format: "Find hotels and stay in Place A with names and cost
            (+ additional info if given)"

        3. AROUND step (for each place stayed) — this is the main content step,
        never skip it:
        - Note: city, days, any additional info.
        - Task format: "Find places to go around in Place A in [days]
            (+ additional info if given)"

        4. Repeat steps 1-3 for each leg of the outbound journey, up through the
        last destination before the return trip.

        5. Return leg: repeat step 1's format once, for the trip back to the
        starting place. (No stay/around steps needed for the return unless the
        prompt specifies one.)

        Steps 1-5 only affect the `steps` array — goal/status/current_step are set
        once in step 0.
        """
        },
        {
            "role" : "user" ,
            "content" : timeline_content
        }
    ]

    response=call_llm(client,messages_2,None,"none",5,response_format=plan_schema)
    response_message=response.choices[0].message

    return response_message.content

######Tools#####

def extract_links(search_string):

    with sync_playwright() as p:
        browser=p.chromium.launch(headless=False)
        context=browser.new_context()
        page=context.new_page()
        try:
            page.goto("https://html.duckduckgo.com/html/",timeout=15000)

            search_input=page.wait_for_selector('#search_form_input_homepage',timeout=15000)
            search_input.fill(search_string)

            with page.expect_navigation(timeout=15000):
                page.locator('#search_button_homepage').click()
            
            locators = page.locator('#links .result:not(.result--ad) .result__a').all()[:NO_OF_LINKS]
        
            links = ""
            for loc in locators:
                href = loc.get_attribute('href')
                if href:
                    links+=(href)
                    links+=(" , ")
            return links
        except PlaywrightTimeoutError:
            print("Timeout occured during search")
            return "ERROR: Error occured , u must change the search string before searching one more time"
        except Exception as e:
            print(f"{e} occured")
            return "ERROR: Error occured , u must change the search string before searching one more time"

def extract_info(url):
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=False)
        context=browser.new_context()
        page=context.new_page()

        try:
            page.goto(url,timeout=15000)
            txt=page.locator('body').inner_text()[:4000]
            return txt
        except PlaywrightTimeoutError:
            print(f"Page load timed out after 10 seconds. Returning partial content... ")
            txt=page.locator('body').inner_text()[:4000]
            return txt
        except Exception as e:
            print(f"{e} occured")
            return "ERROR: Error occured , u must change the url before going to it Dont go to same url again"   ################################


tools=[
    {

        "type":"function",
        "function":{
            "name" : "extract_links",
            "description" : " Takes a search string , returns list of urls in string ",
            "parameters" : {
                "type" : "object",
                "properties" : {
                    "search_string" : {
                        "type" : "string",
                        "description" : "string which need to be searched "
                    }
                },
                "required" : ["search_string"]
            }
        }

    },
    {
        "type" : "function",
        "function":{
            "name" : "extract_info",
            "description":  "Takes a url , returns a scrape of body text",
            "parameters" : {
                "type" : "object" ,
                "properties" : {
                    "url" : {
                        "type" : "string",
                        "description" : "a valid url"
                    }
                },
                "required" : ["url"]
            }
        }
    }
]

available_tools={
    "extract_links":extract_links,
    "extract_info" : extract_info
}



###############

def complete_task(json_step : dict,plan_data):
    messages_3=[
        {
            "role": "system",
            "content": f"""
        You are a task completer. Given a task, return a single string answer.

        HARD CONSTRAINT: Your final answer must be at most 150 characters. No exceptions.

        PROCESS:
        1. Determine if the task requires live/current data.
        2. If it does, call extract_links to get {NO_OF_LINKS} links (comma-separated).
        3. Visit links one at a time, in order, using extract_info to scrape each.
        4. After each link, check if you now have enough information to answer:
        - If yes, stop immediately and return the answer. Do not keep making
            tool calls just because links remain — 1-2 links is normal and
            sufficient in most cases.
        - If a link returns no useful content, discard it and move to the next
            one. Never revisit a link you've already tried.
        5. Only continue past 2 links if the ones you tried failed to load or
        returned unusable data — not because you want more confirmation.
        6. If you exhaust all {NO_OF_LINKS} links without enough information, call
        extract_links again for a new batch and repeat.

        OUTPUT: A single, well-formed summary answering the task using the live
        data gathered. Medium length, not terse, not padded — but always within
        the 150-character hard limit above.
        """
        },
        {
            "role" : "user",
            "content" : json_step["task"] 
        }
    ]

    max_steps=4
    steps=0

    while steps<max_steps:
        response=call_llm(client,messages_3,tools,"auto")

        response_message=response.choices[0].message
        tool_calls=response_message.tool_calls

        messages_3.append(response_message)

        if not tool_calls:
            return response_message.content
        
        for tool_call in tool_calls:
            print(f"using tool {tool_call.function.name}")
            func_name=tool_call.function.name
            func_args= json.loads(tool_call.function.arguments)

            if func_args==None:
                func_args={}
            func_args = {k: v for k, v in func_args.items() if k != ""}

            func_to_call=available_tools[func_name]
            func_result=func_to_call(**func_args)

            messages_3.append(
                {
                    "role" : "tool" ,
                    "tool_call_id" : tool_call.id ,
                    "name" : func_name ,
                    "content" : func_result
                }
            )

        steps+=1
    else:
            findings = "\n\n".join(
                (m["content"] if isinstance(m, dict) else m.content) for m in messages_3
                if (m["role"] if isinstance(m, dict) else m.role) == "tool" 
                and (m["content"] if isinstance(m, dict) else m.content)
            )

            fallback_messages = [
                {
                    "role": "system",
                    "content": "You are a summarizer. You have no tools available. "
                            "Based only on the findings given, write the best "
                            "approximate answer in plain text. Do not mention tools."
                            "write within 150 characters"
                },
                {
                    "role": "user",
                    "content": f"Task: {json_step['task']}\n\nFindings so far:\n{findings or '(no useful data found)'}"
                }
            ]

            try:
                response_message = call_llm(client, fallback_messages, None, "none").choices[0].message
                return response_message.content[:300]
            except BadRequestError:
                return findings[:300] if findings else "Could not determine an answer for this step."
        



def run_loop():
    with open(PLAN_JSON,"r") as f:
        plan_data=json.load(f)

    count=0
    for step in plan_data["steps"]:
        if step["status"]!="done":
            result=complete_task(step,plan_data)
            plan_data["steps"][count]["status"]="done"
            plan_data["steps"][count]["result"]=result
            with open(PLAN_JSON,"w",encoding='utf-8') as f:
                json.dump(dict(plan_data),f,indent=4,ensure_ascii=False)   ## this is important becuz otherwise we loose all the steps in ram..

        count+=1

def summarize():
    with open(PLAN_JSON,"r") as f:
        plan_data_string=json.dumps(json.load(f))
    messages_4=[
        {
            "role" : "system" ,
            "content" : """
                            U have the plan json filled file data which is filled by doing each tsk from a big goal
                            U have to summarize all this and give the final answer
                            neat and clean , not too big , not too small,correctly as needed 
                            """
        },
        {
            "role" : "user" ,
            "content" : plan_data_string
        }
    ]
    response_message=call_llm(client,messages_4).choices[0].message
    with open("summary.md","w") as f:
        f.write(str(response_message.content))

if __name__=="__main__":
    user_prompt=input("Which trip U want to plan (say Initial Place and Destination and No of days)? : ")
    if os.path.exists(PLAN_JSON) and os.stat(PLAN_JSON).st_size > 0:
        with open(PLAN_JSON, "r",encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {} 
    
    if data!={} and data["status"]=="done":
        with open(PLAN_JSON,"w") as f:
            f.write("")
            data={}
    
    if data=={}:
        timeline_content= make_brief_city_timeline_plan(user_prompt)
        print(timeline_content)
        with open(PLAN_JSON,"w",encoding="utf-8") as f:
            json.dump(json.loads(make_plan(user_prompt+" "+timeline_content)),f,indent=4,ensure_ascii=False)



    run_loop()
    summarize()
    with open(PLAN_JSON,"r",encoding='utf8') as f:
        plan_data=json.load(f)
        plan_data["status"]="done"
    with open(PLAN_JSON,"w",encoding='utf8') as f:
        json.dump(plan_data,f,indent=4,ensure_ascii=False)
    
    
    



