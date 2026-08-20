"""The Flight Worker: finds optimal flights based on user constraints."""

import argparse
import os
import sys
from pathlib import Path

# Set up environment and model
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
    def record_flight_cost(amount: float, description: str) -> str:
        """Record the flight cost in the shared budget ledger."""
        board.record_expense("flight_worker", "Flight", amount, description)
        return f"Recorded flight expense: ${amount}"

    def complete_task(result: str) -> str:
        """Mark the assigned flight task as done on the board."""
        board.complete_todo(goal_id, result)
        return "Task marked complete."

    return [record_flight_cost, complete_task]

async def run() -> None:
    args = parse_args()
    
    # Claim the task so the orchestrator knows we're working on it
    board.claim_todo(args.goal_id)
    
    # Read the task details from the board
    todos = board.list_todos()
    task = next((t["task"] for t in todos if t["id"] == args.goal_id), "")
    
    if not task:
        print(f"Task {args.goal_id} not found.")
        return

    instruction = """
    You are the Flight Worker. Your job is to find the best flight based on the user's constraints.
    Extract the departure/arrival times, exact price, and provide a direct booking link (you can simulate this with a mock kayak.com URL for now).
    Once you find a flight, you MUST:
    1. Call record_flight_cost to add the cost to the budget ledger.
    2. Call complete_task with a summary of the flight and the booking link.
    """
    
    # Using the specific worker model from config
    agent = LlmAgent(
        name="flight_worker",
        model=config.FLIGHT_WORKER_MODEL,
        instruction=instruction,
        tools=make_tools(args.goal_id)
    )
    
    runner = InMemoryRunner(agent=agent, app_name="flight_worker")
    session = await runner.session_service.create_session(app_name="flight_worker", user_id="flight")
    
    try:
        async for event in runner.run_async(
            user_id="flight",
            session_id=session.id,
            new_message=types.UserContent(f"Please find a flight for this request: {task}")
        ):
            pass # We let the agent run and use its tools
    finally:
        await runner.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
