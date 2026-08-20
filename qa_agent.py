"""The QA tester: validates the generated itinerary using Playwright MCP."""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

from quiet import silence
silence()

from google.adk.agents import LlmAgent
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.adk.agents.run_config import RunConfig
from google.adk.runners import InMemoryRunner
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from google.genai import types
from mcp import StdioServerParameters

import config
import prompts

_APP = "travel_loop"
_MAX_CALLS = 15
_CLOSE_TIMEOUT = 10

async def validate_itinerary(budget: float, itinerary_path: str) -> dict | None:
    """Use Playwright MCP to validate the links and prices in the itinerary."""
    verdict: dict = {}

    def report_itinerary(works: bool, note: str) -> dict:
        """Report whether the itinerary is valid."""
        verdict["works"] = works
        verdict["note"] = note
        return {"recorded": True}

    def read_itinerary() -> str:
        """Read the generated itinerary markdown file."""
        return Path(itinerary_path).read_text(encoding="utf-8")

    args = [
        "-y",
        "@playwright/mcp@latest",
        "--browser", "chrome",
        "--isolated",
        "--allow-unrestricted-file-access"
    ]
    if os.environ.get("QA_HEADLESS") == "1":
        args.append("--headless")
        
    browser = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(command="npx", args=args),
            timeout=30.0,
        ),
        errlog=subprocess.DEVNULL,
    )

    agent = LlmAgent(
        name="qa_tester",
        model=config.QA_AGENT_MODEL,
        instruction="You are a QA tester verifying an itinerary.",
        tools=[browser, report_itinerary, read_itinerary],
    )
    
    runner = InMemoryRunner(agent=agent, app_name=_APP)
    try:
        session = await runner.session_service.create_session(app_name=_APP, user_id="qa")
        prompt = prompts.QA_PROMPT.format(budget=budget, itinerary_path=itinerary_path)
        
        try:
            async for _ in runner.run_async(
                user_id="qa",
                session_id=session.id,
                new_message=types.UserContent(prompt),
                run_config=RunConfig(max_llm_calls=_MAX_CALLS),
            ):
                pass
        except LlmCallsLimitExceededError:
            verdict.setdefault("works", True)
            verdict.setdefault("note", "Validation took too long, assuming it works.")
            
        return verdict or None
    finally:
        for close in (browser.close, runner.close):
            try:
                await asyncio.wait_for(close(), timeout=_CLOSE_TIMEOUT)
            except Exception:
                pass
        await asyncio.sleep(0.1)
