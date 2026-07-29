import os, asyncio
from dotenv import load_dotenv
load_dotenv(override=True)

from langchain_openai import ChatOpenAI

async def test():
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        base_url="https://api.deepseek.com/v1",
    )
    resp = await llm.ainvoke("say hello in one word")
    print("Response:", resp.content)

asyncio.run(test())
