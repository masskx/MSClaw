# MCP工具与文件操作
import os
from typing import Any, AsyncGenerator

from dotenv import load_dotenv

from ep1 import handle_message

load_dotenv(override=True)
from telegram import Update # 用来
from telegram.constants import ChatAction # 用来发送
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, Updater

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,  # 工具提示词
    ResultMessage,  # 结果包含了耗时Token用量这些
    TextBlock,
    create_sdk_mcp_server,  # 进程内创建MCP服务器，直接在python 中运行
    query,
    tool, AgentDefinition,
)
#配置
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL")
OWNER_ID = int(os.getenv("OWNER_ID"))
# 工作目录设置
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = BASE_DIR / "workspace"


# MCP工具定义
"""
  MCP (Model Context Protocol) 是 Anthropic 定义的标准协议：

  ┌─────────────┐     MCP Protocol     ┌─────────────┐
  │  Claude CLI │  ←────────────────→  │ MCP Server  │
  │  (子进程)    │   (JSON-RPC/stdio)   │ (Python进程) │
  └─────────────┘                      └─────────────┘
                                        │
                                        ↓
                                     你的工具函数
"""
def create_mcp_tools(bot:Any,chat_id:int)->list:
    """创建MCP工具，绑定bot和上下文聊天"""
    @tool("send_message","发送消息给用户",{"text":str})
    async def send_message(args:dict[str,Any])->dict[str,Any]:
        """通过telegram发送消息给用户"""
        await bot.send_message(chat_id=chat_id,text=args["text"])
        return {"content":[{"type":"text","text":"消息已发送"}]}
    return[send_message]

#Agent执行
async def run_agent(prompt:str,bot:Any,chat_id:int)->str:
    """运行Claude Agent工具"""
    tools = create_mcp_tools(bot,chat_id)
    mcp_server = create_sdk_mcp_server(name="assistant",tools=tools)
    env = {
        "ANTHROPIC_API_KEY":ANTHROPIC_API_KEY,
        "ANTHROPIC_BASE_URL":ANTHROPIC_BASE_URL
        }

    # 构建增强的prompt，明确指定工作目录
    enhanced_prompt = f"""工作目录: {WORKSPACE_DIR}

重要提示: 当创建或操作文件时，请使用相对路径或确保文件在工作目录 {WORKSPACE_DIR} 内。

用户请求: {prompt}"""

    options = ClaudeAgentOptions(
        cwd=str(WORKSPACE_DIR),
        allowed_tools=[
            "read","write","edit","glob","grep",# 文件操作
            "mcp_assistant_send_message",
        ],
        permission_mode="acceptEdits",#自动接受文件编辑
        mcp_servers={"assistant":mcp_server},
        env=env,
    )
    agents = {
        "coder":AgentDefinition(
            description="专业程序员",
            prompt="你是一个程序员",
            tools=["read","write","bash"],
        )
    }
    async def _make_prompt(text:str)->AsyncGenerator[dict,None]:
        """构造异步生成器prompt"""
        yield {
            "type":"user",
            "message":{"role":"user","content":text},
        }
    response_parts:list[str]=[]
    result_text:str|None=None
    async for message in query(prompt=_make_prompt(enhanced_prompt), options=options):
        # 打印所有消息类型以便调试
        print(f"[DEBUG] 收到消息类型: {type(message).__name__}")
        print(f"[DEBUG] 消息内容: {message}")

        if isinstance(message,AssistantMessage):
            for block in message.content:
                if isinstance(block,TextBlock):
                    response_parts.append(block.text)
        elif isinstance(message,ResultMessage):
            if message.result:
                result_text = message.result

    # 检查工作目录中的文件
    import os
    files = os.listdir(WORKSPACE_DIR)
    print(f"[DEBUG] workspace中的文件: {files}")

    return "".join(response_parts) or result_text or "完成"

#消息处理
def is_owner(update):
    return update.effective_user is not None and update.effective_user.id == OWNER_ID

async def start(update:Update,context)->None:
    """处理start命令"""
    if not is_owner(update):
        return
    await update.message.reply_text(
        "你好你好你好"
    )
async def handle_message(update:Update,context:CallbackContext)->None:
    """用claude处理消息"""
    if not is_owner(update):
        return #忽略非主人消息
    if not update.message or not update.message.text:
        return
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id,action=ChatAction.TYPING)
    response = await run_agent(update.message.text,context.bot,chat_id)
    max_length = 4096
    for i in range(0,len(response),max_length):
        await update.message.reply_text(response[i:i+max_length])
def main()->None:
    """启动机器人"""
    WORKSPACE_DIR.mkdir(parents=True,exist_ok=True)
    builder = Application.builder().token(TELEGRAM_BOT_TOKEN)


    app = builder.build()

    app.add_handler(CommandHandler("start",start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_message))
    print(f"Tool Bot启动了工作目录{WORKSPACE_DIR}")
    app.run_polling()

if __name__ == "__main__":
    main()