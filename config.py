"""The models the agent loop uses, kept in one place so they are easy to swap.

The orchestrator (Google ADK) manages the agents and checks their work.
The three workers use specialized free-tier models.
"""

import os

# Free tier Gemini for orchestration and QA
ORCHESTRATOR_MODEL = os.environ.get("ORCHESTRATOR_MODEL", "gemini-2.5-flash")

# Free tier models for specific tasks (ensure you have litellm/groq set up, or just use gemini-2.5-flash if preferred)
FLIGHT_WORKER_MODEL = os.environ.get("FLIGHT_WORKER_MODEL", "groq:llama3-70b-8192")
ACCOMMODATION_WORKER_MODEL = os.environ.get("ACCOMMODATION_WORKER_MODEL", "gemini-2.5-flash")
ATTRACTION_WORKER_MODEL = os.environ.get("ATTRACTION_WORKER_MODEL", "groq:mixtral-8x7b-32768")
