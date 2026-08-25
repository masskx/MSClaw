import os
import subprocess
from unittest import result

from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv(override=True)

if os.getenv("ANTHROPIC_API_KEY") is None:
    raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")

client = Anthropic(
    base_url = os.getenv("ANTHROPIC_BASE_URL"),
    api_key = os.getenv("ANTHROPIC_API_KEY"),
)

MODEL = os.getenv("MODEL_ID")

SYSTEM = "你是一个coding agent at {os.getcwd()}, 你可以使用bash命令来执行任务。"

TOOLS = [{
    "name": "bash",
    "description":"run a shell command",
    "input_schema":{
        "type":"object",
        "properties":{
            "command":{
                "type":"string"
            }
        },
        "required":["command"]
    }
}]

def run_bash(command:str)->str:
    dangerous = ["rm -rf /","sudo","shutdown","reboot","> /dev/"]
    if any(d in command for d in dangerous):
        return "Error :Dangerous command blocked"
    try:
        r = subprocess.run(
                command,
                shell=True,
                cwd=os.getcwd(),
                capture_output=True,
                text=True,
                timeout=120
            )
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else ("No output")
    except subprocess.TimeoutExpired:
        return "Error: Command timed out"
    except (FileNotFoundError, OSError) as e:
        return f"Error: {e}"

def agent_loop(messages:list):
    while True:
        response = client.messages.create( # 大模型回复，里面带所有的历史消息
            model = MODEL,
            system = SYSTEM,
            messages=messages,
            tools = TOOLS,
            max_tokens = 8000
        )
        messages.append({ # 把LLM消息也放进去
            "role":"assistant",
            "content":response.content
        })
        if response.stop_reason != "tool_use":
            return
        results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"\003[33m${block.input['command']}\003[0m")
                output = run_bash(block.input['command'])
                print(output[:200])
                results.append({
                    "type":"tool_result",
                    "tool_use_id":block.id,
                    "content":output
                })
        messages.append({"role":"user","content":results})


if __name__ == "__main__":
    print("s01:Agent_loop")
    print("输入问题，回车发送，输入q退出。\n")

    history = [] # 用户消息用list存储
    while True: # 持续接受用户输入
        try:
            query = input("\033[36ms01 >> \033[0m")
        except (EOFError,KeyboardInterrupt):
            break
        if query.strip().lower() in ("q","exit",""):
            break # 如果是特殊的退出指令就退出
        history.append({"role":"user","content":query})
        agent_loop(history) # 传入AgentLoop循环

        response_content = history[-1]["content"]
        if isinstance(response_content,list):
            for block in response_content:
                if getattr(block,"type",None) == "text":
                    print(block.text)
        print()

# messages = [
#     {
#         "role":"user",
#         "content":query
#     }
# ]

# response = client.messages.create(
#     model = MODEL,
#     system = SYSTEM,
#     messages = messages,
#     tools = TOOLS,
#     max_tokens = 8000,
# )

# messages.append(
#     {
#         "role":"assistant",
#         "content":response.content
#     }
# )

# if response.stop_reason != "tool_use":
#     return 


# results = []
# for block in response.content:
#     if block.type == "tool_use":
#         output = run_bash(block.input["command"])
#         result.append({
#             "type": "tool_output",
#             "tool_call_id": block.id,
#             "content": output
#         })

# messages.append(
#     {
#         "role":"user",
#         "content": results
#     }
# )
# def agent_loop(messages):
#     while True:
#         response = client.messages.create(
#             model = MODEL,
#             system = SYSTEM,
#             messages=messages,
#             tools = TOOLS,
#             max_tokens = 8000,
#         )
#         messages.append({
#             "role":"assistant",
#             "content":response.content
#         })
#         if response.stop_reason != "tool_use":
#             return
#         results = []
#         for block in response.content:
#             if block.type == "tool_use":
#                 output = run_bash(block.input["command"])
#                 results.append({
#                     "type":"tool_result",
#                     "tool_use_id": block.id,
#                     "content": output,
#                 })
#         messages.append({
#             "role":"user",
#             "content": results
#         })