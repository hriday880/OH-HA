import asyncio
from bot.config import load_config
from bot.agent.pipeline import SplitBrainAgentPipeline

async def main():
    config = load_config(llm_provider="groq", llm_api_key="gsk_invalid_key")
    pipeline = SplitBrainAgentPipeline(config=config)
    print("Sending message...")
    res = await pipeline.process_message("Hello!")
    print(f"Response: {res.content}")

if __name__ == "__main__":
    asyncio.run(main())
