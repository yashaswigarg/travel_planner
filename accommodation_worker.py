"""The Accommodation Worker: finds hotels/hostels based on user preferences."""

import argparse
import os
import sys
from pathlib import Path

import config
import board
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("goal_id", type=int, help="The task ID on the board to claim")
    parser.add_argument("board_path", type=str, help="Path to the shared board")
    return parser.parse_args()

def make_tools(goal_id: int):
    def record_accommodation_cost(amount: float, description: str) -> str:
        """Record the total accommodation cost in the shared budget ledger."""
        board.record_expense("accommodation_worker", "Accommodation", amount, description)
        return f"Recorded accommodation expense: ${amount}"

    def complete_task(result: str) -> str:
        """Mark the assigned accommodation task as done on the board."""
        board.complete_todo(goal_id, result)
        return "Task marked complete."

    return [record_accommodation_cost, complete_task]

async def run() -> None:
    args = parse_args()
    
    board.claim_todo(args.goal_id)
    
    todos = board.list_todos()
    task = next((t["task"] for t in todos if t["id"] == args.goal_id), "")
    
    if not task:
        print(f"Task {args.goal_id} not found.")
        return

    instruction = """
    You are the Accommodation Worker. Your job is to find the best stay based on user preferences (hostel/hotel).
    Extract nightly rates, total cost, distance from city center, and provide a direct booking link (you can mock a booking.com link for now).
    Once you find a stay, you MUST:
    1. Call record_accommodation_cost to add the TOTAL cost to the budget ledger.
    2. Call complete_task with a summary of the accommodation and the booking link.
    """
    
    agent = LlmAgent(
        name="accommodation_worker",
        model=config.ACCOMMODATION_WORKER_MODEL,
        instruction=instruction,
        tools=make_tools(args.goal_id)
    )
    
    runner = InMemoryRunner(agent=agent, app_name="accommodation_worker")
    session = await runner.session_service.create_session(app_name="accommodation_worker", user_id="accommodation")
    
    try:
        async for event in runner.run_async(
            user_id="accommodation",
            session_id=session.id,
            new_message=types.UserContent(f"Please find accommodation for this request: {task}")
        ):
            pass
    finally:
        await runner.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
