import os
import logging
from dotenv import load_dotenv
load_dotenv(override=True)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
print(TELEGRAM_BOT_TOKEN)

from telegram import Update
from telegram.ext import Application,CommandHandler,MessageHandler,filters
from typing import Any
"""
context 是callback内容，拿到历史消息
"""
async def start(update:Update,context):
    """处理/start命令"""
    await update.message.reply_text("Hello! I'm your bot.我是你爸爸")

async def handle_message(update:Update,context):
    """处理用户消息，直接回显"""
    await update.message.reply_text(update.message.text + "这是回显消息")

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