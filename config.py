"""The models the agent loop uses, kept in one place so they are easy to swap.

The orchestrator (Google ADK) manages the agents and checks their work.
The three workers use specialized free-tier models across different providers.
"""

import os

# Google AI Studio (15 RPM)
ORCHESTRATOR_MODEL = os.environ.get("ORCHESTRATOR_MODEL", "gemini-2.5-flash")

# Groq API (30 RPM)
FLIGHT_WORKER_MODEL = os.environ.get("FLIGHT_WORKER_MODEL", "llama-3.3-70b-versatile")

# Cerebras Cloud (High token throughput)
ACCOMMODATION_WORKER_MODEL = os.environ.get("ACCOMMODATION_WORKER_MODEL", "llama-3.3-70b")

# SambaNova Cloud (High reasoning)
ATTRACTION_WORKER_MODEL = os.environ.get("ATTRACTION_WORKER_MODEL", "Meta-Llama-3.3-70B-Instruct")

# OpenRouter (Dedicated QA endpoint)
QA_AGENT_MODEL = os.environ.get("QA_AGENT_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
