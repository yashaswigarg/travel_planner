"""The Attraction & Logistics Worker: plans the itinerary and estimates daily costs."""

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
    def record_activity_cost(amount: float, description: str) -> str:
        """Record an activity, food, or transit cost in the shared budget ledger."""
        board.record_expense("attraction_worker", "Activity/Food/Transit", amount, description)
        return f"Recorded activity expense: ${amount}"

    def add_itinerary_block(day: int, time_of_day: str, activity: str, cost: float) -> str:
        """Add an activity to the master itinerary (time_of_day should be Morning, Afternoon, or Evening)."""
        board.add_itinerary_item(day, time_of_day, activity, url="", cost=cost)
        return f"Added {activity} to Day {day} {time_of_day}."

    def complete_task(result: str) -> str:
        """Mark the assigned itinerary task as done on the board."""
        board.complete_todo(goal_id, result)
        return "Task marked complete."

    return [record_activity_cost, add_itinerary_block, complete_task]

async def run() -> None:
    args = parse_args()
    
    board.claim_todo(args.goal_id)
    
    todos = board.list_todos()
    task = next((t["task"] for t in todos if t["id"] == args.goal_id), "")
    
    if not task:
        print(f"Task {args.goal_id} not found.")
        return

    instruction = """
    You are the Attraction & Logistics Worker. Your job is to plan the daily itinerary.
    Pay close attention to user preferences for food (veg/non-veg) and famous restaurants.
    Group geographical locations logically into Morning, Afternoon, and Evening blocks.
    You MUST:
    1. Call add_itinerary_block for EVERY activity or meal you plan (Morning/Afternoon/Evening).
    2. Call record_activity_cost to sum up all transit, food, and ticket costs.
    3. Call complete_task with a summary when you are done.
    """
    
    agent = LlmAgent(
        name="attraction_worker",
        model=config.ATTRACTION_WORKER_MODEL,
        instruction=instruction,
        tools=make_tools(args.goal_id)
    )
    
    runner = InMemoryRunner(agent=agent, app_name="attraction_worker")
    session = await runner.session_service.create_session(app_name="attraction_worker", user_id="attraction")
    
    try:
        async for event in runner.run_async(
            user_id="attraction",
            session_id=session.id,
            new_message=types.UserContent(f"Please plan the itinerary for this request: {task}")
        ):
            pass
    finally:
        await runner.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
