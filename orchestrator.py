"""The Orchestrator: a Google ADK agent that runs the Travel Planner team."""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from quiet import silence
silence()

from google.adk.agents import LlmAgent
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.adk.agents.run_config import RunConfig
from google.adk.runners import InMemoryRunner
from google.genai import types
from rich.live import Live

import board
import config
import live_board
import prompts
import qa_agent

_APP = "travel_loop"
_MAX_TURNS = 50
WORKER_TIMEOUT = int(os.environ.get("WORKER_TIMEOUT_S", "300"))
QA_TIMEOUT = int(os.environ.get("QA_TIMEOUT_S", "150"))

def _launch(goal_id: int, script_name: str, board_path: Path) -> subprocess.Popen:
    """Start one worker as a subprocess against the shared board."""
    argv = ["uv", "run", script_name, str(goal_id), str(board_path)]
    cwd = str(board_path.parent.parent) # Should be projects/travel_planner
    group = {} if sys.platform == "win32" else {"start_new_session": True}
    return subprocess.Popen(
        argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=cwd, **group
    )

def _terminate(proc: subprocess.Popen) -> None:
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, OSError):
        pass

class Team:
    def __init__(self, user_prompt: str, site_dir: Path, board_path: Path) -> None:
        self.user_prompt = user_prompt
        self.site_dir = site_dir
        self.board_path = board_path
        self.pending: list[subprocess.Popen] = []
        self.registry: dict[int, dict] = {}
        self.workers = ["flight", "accommodation", "attraction"]

def make_tools(team: Team) -> list:
    def launch_worker(role: str) -> str:
        """Start a specialized worker (flight, accommodation, or attraction)."""
        if role not in team.workers:
            return f"Invalid role '{role}'. Use flight, accommodation, or attraction."
        
        script = f"{role}_worker.py"
        task = prompts.WORKER_TASK.format(user_prompt=team.user_prompt)
        goal_id = board.add_goal(f"{role.capitalize()} Assignment: {task}")
        team.registry[goal_id] = {"name": f"{role.capitalize()} Worker", "colour": "blue" if role=="flight" else "green" if role=="accommodation" else "magenta"}
        team.pending.append(_launch(goal_id, script, team.board_path))
        return f"Launched {role} worker."

    async def wait_for_team() -> str:
        """Wait until every builder you have started has finished."""
        procs = team.pending
        team.pending = []
        if not procs:
            return "No workers pending."
        started = time.monotonic()
        stopped = False
        with Live(live_board.render(team.registry), console=live_board.console, refresh_per_second=8) as live:
            while any(p.poll() is None for p in procs):
                live.update(live_board.render(team.registry))
                if not stopped and time.monotonic() - started > WORKER_TIMEOUT:
                    for p in procs:
                        if p.poll() is None:
                            _terminate(p)
                    stopped = True
                await asyncio.sleep(0.15)
            live.update(live_board.render(team.registry))
        return "All workers have finished their tasks."

    def generate_markdown_itinerary() -> str:
        """Generate the final itinerary.md from the board data."""
        itinerary = board.get_itinerary(team.board_path)
        total = board.get_total_expenses(team.board_path)
        
        lines = ["# Your Travel Itinerary\n"]
        lines.append(f"**Total Estimated Cost:** ${total:.2f}\n")
        
        current_day = None
        for item in itinerary:
            if item["day"] != current_day:
                current_day = item["day"]
                lines.append(f"## Day {current_day}")
            lines.append(f"- **{item['time_of_day']}**: {item['activity']} (${item['cost']:.2f})")
            if item['url']:
                lines.append(f"  - [Link]({item['url']})")
        
        out_path = team.site_dir / "itinerary.md"
        out_path.write_text("\n".join(lines), encoding="utf-8")
        return f"Generated itinerary at {out_path}"

    async def test_itinerary(budget: float) -> str:
        """Test the generated itinerary using the QA agent (Playwright)."""
        itinerary_path = team.site_dir / "itinerary.md"
        if not itinerary_path.exists():
            return "itinerary.md does not exist yet."
        
        live_board.console.print(f"Validating itinerary against ${budget} budget...", style="cyan")
        try:
            verdict = await asyncio.wait_for(
                qa_agent.validate_itinerary(budget, str(itinerary_path)),
                timeout=QA_TIMEOUT,
            )
        except Exception as exc:
            return f"QA failed with exception: {exc}"
            
        works = bool(verdict.get("works"))
        note = verdict.get("note", "")
        return f"QA Check: {'WORKS' if works else 'BROKEN'}. {note}"

    def relaunch_worker(role: str, problem: str) -> str:
        """Relaunch a worker if the QA check fails."""
        script = f"{role}_worker.py"
        task = f"FIX REQUIRED: The QA agent found an issue with your previous output: {problem}. Please find an alternative that satisfies the original constraints: {team.user_prompt}"
        goal_id = board.add_goal(f"{role.capitalize()} FIX: {task}")
        team.registry[goal_id] = {"name": f"{role.capitalize()} Worker (Fix)", "colour": "red"}
        team.pending.append(_launch(goal_id, script, team.board_path))
        return f"Relaunched {role} worker to fix the issue."

    return [launch_worker, wait_for_team, generate_markdown_itinerary, test_itinerary, relaunch_worker]

def _build_agent(team: Team) -> LlmAgent:
    instruction = prompts.ORCHESTRATOR_PROMPT.format(user_prompt=team.user_prompt)
    return LlmAgent(name="orchestrator", model=config.ORCHESTRATOR_MODEL, instruction=instruction, tools=make_tools(team))

async def _run(team: Team) -> None:
    runner = InMemoryRunner(agent=_build_agent(team), app_name=_APP)
    try:
        session = await runner.session_service.create_session(app_name=_APP, user_id="orchestrator")
        async for event in runner.run_async(
            user_id="orchestrator",
            session_id=session.id,
            new_message=types.UserContent(f"Please process this travel request: {team.user_prompt}"),
            run_config=RunConfig(max_llm_calls=_MAX_TURNS),
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text and part.text.strip():
                        live_board.console.print(part.text.strip(), style="dim italic")
    except LlmCallsLimitExceededError:
        print(f"\n  NOTE: the orchestrator reached its {_MAX_TURNS}-step budget.")
    finally:
        try:
            await runner.close()
        except Exception:
            pass

def run(user_prompt: str, site_dir: Path, board_path: Path) -> Team:
    site_dir.mkdir(parents=True, exist_ok=True)
    board.reset_board(board_path)
    team = Team(user_prompt, site_dir, board_path)
    asyncio.run(_run(team))
    return team
