import os
import logging
from dotenv import load_dotenv
load_dotenv(override=True)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
print(TELEGRAM_BOT_TOKEN)

from telegram import Update
from telegram.ext import Application,CommandHandler,MessageHandler,filters
from typing import Any
from claude_agent_sdk import (AssistantMessage,ClaudeAgentOptions,ResultMessage,TextBlock,query)

"""
context 是callback内容，拿到历史消息
"""

async def start(update:Update,context):
    """处理/start命令"""
    await update.message.reply_text("Hello! I'm your bot.我是你爸爸")

async def ask_claude(prompt:str)->str:
    """
    调用 Claude Agent SDK，用 query() 流式获取回复。

    query() 返回两种消息类型：
      - AssistantMessage: 流式输出的中间文本块（工具调用过程中的增量输出）
      - ResultMessage:    最终汇总结果（Agent 完成所有工具调用后的最终回复）

    ⚠️ 重复回复的根因：
    AssistantMessage 的 TextBlock 已经包含了 Claude 的完整回复文字，
    ResultMessage.result 也包含同样的内容。如果两处都 append 再拼起来，
    就会得到 "回复内容\n回复内容" 的重复文本。
    """
    env = {
        "ANTHROPIC_API_KEY":os.getenv("ANTHROPIC_API_KEY"),
        "ANTHROPIC_BASE_URL":os.getenv("ANTHROPIC_BASE_URL")
    }
    options = ClaudeAgentOptions(
        permission_mode="acceptEdits", # 表示自动批准
        env = env #注入环境变量字典
    )

    # ---- 修复后：只取 ResultMessage 最终结果 ----
    async for message in query(prompt=prompt,options = options):
        if isinstance(message,ResultMessage):
            if message.result:
                print("claude最终结果：",message.result)
                return message.result
    return "我没有得到Claude回复"

    # ---- 旧代码（有重复bug，保留作为学习笔记）----
    # response_parts:list[str] = []
    # async for message in query(prompt=prompt,options = options):
    #     # ❌ 问题1：AssistantMessage 的 TextBlock 已包含完整回复
    #     if isinstance(message,AssistantMessage):
    #         for block in message.content:
    #             if isinstance(block,TextBlock):
    #                 response_parts.append(block.text)   # ← 第1份回复
    #     # ❌ 问题2：ResultMessage.result 又是同一份回复内容
    #     elif isinstance(message,ResultMessage):
    #         if message.result:
    #             print("claude最终结果：",message.result)
    #             response_parts.append(message.result)  # ← 第2份回复
    # # ❌ 结果：两份拼在一起 → "\n".join → 消息重复
    # return "\n".join(response_parts) or "我没有得到Claude回复"

async def handle_message(update:Update,context):
    """用claude 处理用户消息"""
    if not update.message or not update.message.text:
        return
    response = await ask_claude(update.message.text)
    max_length = 4000
    for i in range(0,len(response),max_length):
        await update.message.reply_text(response[i:i + max_length])
    pass

async def end(update:Update,context):
    """处理"""
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
