"""The agent loop: a Google ADK orchestrator agent that plans travel itineraries.

Usage:
    uv run travel_loop.py --prompt "3-day trip to Singapore from NY, budget $800, prefer hostels and veg food"
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv(override=True)
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

import config
HERE = Path(__file__).resolve().parent
SITE = HERE / "output"
BOARD_PATH = SITE / "board.sqlite"

os.environ["BOARD_PATH"] = str(BOARD_PATH)

import orchestrator

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a travel itinerary with an AI team.")
    parser.add_argument("--prompt", required=True, help="The user's travel request")
    parser.add_argument("--dry-run", action="store_true", help="show the plan; do not run the agent")
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    
    print(f"Planning trip based on: '{args.prompt}'")
    if args.dry_run:
        print("\nDry run: stopping before the agent runs.")
        return

    print(f"\n{config.ORCHESTRATOR_MODEL} is leading the team. Watch the board fill in:\n")
    orchestrator.run(args.prompt, SITE, BOARD_PATH)

    index = SITE / "itinerary.md"
    print("\nThe team has finished. Open this to see your itinerary:")
    print(f"  {index.resolve().as_uri()}")

if __name__ == "__main__":
    main()
