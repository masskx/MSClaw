from nt import write
import os
import logging
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(override=True)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

from telegram import Update
from telegram.ext import Application,CommandHandler,MessageHandler,filters
from typing import Any
from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage, # claude回复的消息
    ClaudeAgentOptions,
    PermissionResultAllow, # 启动claude的配置项（MCP，工具，系统提示词等）
    ResultMessage, # 最终的执行结果
    TextBlock, # 文本块的内容
    query, # 核心函数，发送消息给claue Agent 然后获取回复
    create_sdk_mcp_server,
    tool #创建mcp使用的内容
)
def is_owner(update: Update) -> bool:
    """检查发送者是否为 Bot 主人"""
    return update.effective_user.id == OWNER_ID

# 启动函数映射
async def start(update:Update,context):
    """处理/start命令"""
    if not is_owner(update):
        await update.message.reply_text("你没有权限使用此Bot")
        return
    await update.message.reply_text("Hello! I'm your bot.我是你爸爸")

#添加功能
#1.让别人没办法使用我的Bot
#2.能够执行bash命令
#3.进行网络搜索

def create_mcp_server_tools(bot,chat_id:int)->list:
    @tool("send_message","发送消息给用户",{"text":str})
    async def send_message(args)->dict[str,Any]:
        # 主动给用户发消息
        await bot.send_message(chat_id=chat_id,text=args["text"])
        # 返回值是告诉Agent发送消息的结果
        return {
            "content":[
                {
                    "type":"text",
                    "text":f"已经向用户发送消息：{args["text"]}"
                }
            ]
        }
    return[send_message]

# 工作目录，在这里操作文件
BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = BASE_DIR/"workspace"
async def ask_claude(prompt:str,bot:Any,chat_id:int)->str: # 调用模型
    env = {
        "ANTHROPIC_API_KEY":os.getenv("ANTHROPIC_API_KEY"),
        "ANTHROPIC_BASE_URL":os.getenv("ANTHROPIC_BASE_URL")
    }
    # 创建mcp工具有哪些tools
    tools = create_mcp_server_tools(bot,chat_id)
    async def _allow_all_tools(*_):
        return PermissionResultAllow(behavior="allow")
    # 实际上bash命令还是不能执行
    options = ClaudeAgentOptions(
        # 当前的工作目录
        cwd=str(WORKSPACE_DIR),
        # 可用的工具
        can_use_tool=_allow_all_tools, # 使用mcp工具需要调用权限
        allowed_tools=[
            "read", # 读取文件
            "write",# 覆盖写入对应文件
            "edit", # 编辑对应文件
            "glob", # 查找对应文件
            "grep",  # 在文件中搜索内容
            "web_search", # 搜索
            "web_fetch", # 获取url里面的内容
            "bash",
            "mcp__assistant__send_message" # ← 授权：告诉Claude"你可以用这些"
            # 具体名字取决于 SDK 的命名规则，可能需要调试确认，常见格式是 mcp__<服务器名>__<工具名>
        
        ],#允许使用的工具
        agents={
            "coder":AgentDefinition(
                description="专业程序员",
                prompt="你是一个经验丰富的python开发者",
                tools=["read","write","bash"]
            )
        },
        permission_mode="acceptEdits", # 表示自动批准
        env = env, #注入环境变量字典
        mcp_servers={# ← 注册：告诉SDK"这个工具存在"
            "assistant":create_sdk_mcp_server(
                name="assistant",
                tools=tools
            )
        },
        system_prompt="""你是一个运行在 Telegram 中的助手Bot。请遵守以下规则：
        1. 工具优先：当用户要求你做任何操作（发消息、读写文件等），必须调用对应的工具来完成，不要用纯文字模拟
        2. 主动反馈：每次完成一个步骤，先用 send_message 告诉用户当前进度
        3. 失败了也要说：工具调用失败时，用 send_message 告诉用户发生了什么
        4. 完成任务后：用 send_message 发送最终结果给用户""",
    )
    async def _make_prompt(text:str):
        """构造异步生成器"""
        yield {
            "type":"user",
            "message":{"role":"user","content":text},
        }
    # ---- 只取 ResultMessage 最终结果 ----
    async for message in query(prompt=_make_prompt(prompt),options = options):
        if isinstance(message,ResultMessage):
            if message.result:
                print("claude最终结果：",message.result)
                return message.result
    return "我没有得到Claude回复"

async def handle_message(update:Update,context):
    """用claude 处理用户消息"""
    if not is_owner(update):
        await update.message.reply_text("你没有权限使用此Bot")
        return
    if not update.message or not update.message.text: # 如果用户的消息为空
        return
    response = await ask_claude(prompt=update.message.text,bot=context.bot,chat_id=update.effective_chat.id)
    max_length = 4000
    for i in range(0,len(response),max_length):
        await update.message.reply_text(response[i:i + max_length])
    pass

async def end(update:Update,context):
    """处理/end命令"""
    if not is_owner(update):
        await update.message.reply_text("你没有权限使用此Bot")
        return
    await update.message.reply_text("再见啦北鼻")

def main():
    """主函数"""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    #app注册器
    # add_handler 添加处理程序
    app.add_handler(CommandHandler("end",end)) # 处理/end命令
    app.add_handler(CommandHandler("start",start)) # 处理/start命令
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_message)) #处理用户消息
    print("Bot is running...")
    app.run_polling()

# 只有作为主程序运行时，才执行main函数
if __name__ == "__main__":
    main()
