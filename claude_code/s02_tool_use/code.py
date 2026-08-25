# S02在S01Agent_LOOP的基础上增加了四个工具
import os
import subprocess
from pathlib import Path


from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)

WORKDIR = Path.cwd()

client = Anthropic(
    base_url = os.getenv("ANTHROPIC_BASE_URL"),
    api_key = os.getenv("ANTHROPIC_API_KEY"),
)

MODEL = os.getenv("MODEL_ID")

SYSTEM = f"你是一个coding agent at {WORKDIR}, 你可以使用工具来执行任务。不要解释"

def run_bash(command:str)->str:
    """运行bash命令的方法"""
    dangerous = ["rm -rf /","sudo","shutdown","reboot","> /dev/"] # 危险指令
    if any(d in command for d in dangerous): # 指令危险
        return "Error :Dangerous command blocked" # 如果是危险指令就不执行
    try:
        r = subprocess.run( # 运行bash命令
            command,
            shell=True,
            cwd=WORKDIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120
        )
        out = (r.stdout+r.stderr).strip() # 运行指令的标准输入和输出
        return out[:50000] if out else ("No output")
    except subprocess.TimeoutExpired: # 如果指令超时报错
        return "Error: Timeout(120s)"
    except (FileNotFoundError, OSError) as e: # 如果指令执行错误
        return f"Error: {e}"

def safe_path(p:str)->Path: 
    """
    返回安全路径
    输入：路径
    输出：安全路径
    """
    path = (WORKDIR / p).resolve() # 获取绝对路径
    if not path.is_relative_to(WORKDIR): # 如果路径不是工作目录的子路径
        raise ValueError(f"Path escapes working directory: {p}") # 报错
    return path # 返回安全路径


def run_read(path:str,limit:int|None=None)->str:
    """
    运行读取文件
    输入：路径
    输出：文件内容
    """
    try:
        lines = safe_path(path).read_text().splitlines() # 读取文件内容并按行分割
        if limit and limit < len(lines): # 如果限制行数小于行数
            lines = lines[:limit] + [f"...({len(lines)-limit} more lines)"] # 限制行数
        return "\n".join(lines) # 返回文件内容
    except Exception as e: # 如果文件读取错误
        return f"Error: {e}" # 报错

def run_write(path:str,content:str)->str:
    """
    运行写入文件
    输入：路径，内容
    输出：写入结果
    """
    try:
        file_path = safe_path(path) # 获取文件路径
        file_path.parent.mkdir(parents=True,exist_ok=True) # 创建文件路径
        file_path.write_text(content) # 写入文件
        return f"Wrote {len(content)} bytes to {path}" #    返回写入结果
    except Exception as e:
        return f"Error: {e}"

def run_edit(path:str,old_text:str,new_text:str)->str:
    try:
        file_path = safe_path(path) # 获取文件路径
        text = file_path.read_text() # 读取文件内容
        if old_text not in text: # 如果旧文本不在文件中
            return f"Error:Text not found in {path}" # 报错
        file_path.write_text(text.replace(old_text,new_text,1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"



def run_glob(pattern:str)->str:
    import glob as g
    try:
        results = []
        for match in g.glob(pattern,root_dir=WORKDIR):
            if (WORKDIR / match).resolve().is_relative_to(WORKDIR):
                results.append(match)
        return "\n".join(results) if results else "(No matches)"
    except Exception as e:
        return f"Error: {e}"

TOOLS = [
    {"name": "bash", "description": "Run a shell command.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read file contents.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write content to a file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace exact text in a file once.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
    {"name": "glob", "description": "Find files matching a glob pattern.",
     "input_schema": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}},
]

TOOL_HANDLERS={
    "bash": run_bash,
    "read_file": run_read,
    "write_file": run_write,
    "edit_file": run_edit,
    "glob": run_glob
}

def agent_loop(messages:list):
    while True:
        response = client.messages.create(
            model = MODEL,
            system = SYSTEM,
            messages=messages,
            tools = TOOLS,
            max_tokens = 8000
        )
        messages.append({
            "role":"assistant",
            "content":response.content
        })
        if response.stop_reason != "tool_use":
            return
        results = []
        for block in response.content:
            if block.type == "tool_use":
                handler = TOOL_HANDLERS.get(block.name)
                output = TOOL_HANDLERS[block.name](**block.input) if handler else f"UnKnown:{block.name}"
                results.append({
                    "type":"tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                })
        messages.append({
            "role":"user",
            "content": results
        })

if __name__ == "__main__":
    print("s02: Tool Use — 在 s01 基础上加了 4 个工具")
    print("输入问题，回车发送。输入 q 退出。\n")
    history = []
    while True:
        try:
            query = input("\033[36ms02 >> \033[0m")
        except (EOFError,KeyboardInterrupt):
            break
        if query.strip().lower() in ("q","exit",""):
            break
        history.append({"role":"user","content":query}) 
        agent_loop(history)
        for block in history[-1]["content"]:
            if getattr(block,"type",None) == "text":
                print(f"\033[36ms02 >> \033[0m{block.text}")
        print()

