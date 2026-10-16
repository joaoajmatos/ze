"""Ze framework defaults.

All framework-level constants live here. Modules import from this file so
every magic number has a name and a single point of change.
"""

# ── Routing ───────────────────────────────────────────────────────────────────

ROUTING_THRESHOLD: float = 0.73
"""Minimum cosine similarity for a confident single-agent match.

Calibrated on intfloat/multilingual-e5-base (query:/passage:). Measured clear
tops sit in ~0.78–0.84; MiniLM's 0.55 floor was below the whole E5 band.
"""

ROUTING_GAP_THRESHOLD: float = 0.02
"""Minimum score gap between top-two agents before triggering LLM decomposition.

Measured E5 gaps: clear calendar EN 0.033, calendar PT 0.023; mixed
research-then-email 0.003. MiniLM's 0.10 gap and the YAML 0.03 overlay both
marked ordinary PT calendar turns as compound.
"""

# ── Models ────────────────────────────────────────────────────────────────────

MODEL_AGENT_DEFAULT: str = "anthropic/claude-sonnet-4-5"
"""Default model for agent execution when no override is declared."""

MODEL_AGENT_TIMEOUT: int = 30
"""Default per-agent execution timeout in seconds."""

MODEL_ROUTER_FALLBACK: str = "anthropic/claude-haiku-4-5"
"""Model used for LLM-based routing decomposition (haiku fallback)."""

MODEL_SYNTHESIS: str = "anthropic/claude-haiku-4-5"
"""Model used for memory synthesis, episode summarisation, and profile updates."""

MODEL_VISION_CAPTION: str = "google/gemini-flash-1.5"
"""Model used to caption images before embedding-based routing."""

MODEL_WHISPER: str = "openai/whisper-1"
"""Model used to transcribe audio before routing."""

# ── Workflow ──────────────────────────────────────────────────────────────────

MODEL_WORKFLOW_PLAN: str = "anthropic/claude-haiku-4-5"
"""Model used to decompose workflow descriptions into steps and extract schedules."""

MODEL_WORKFLOW_VERIFY: str = "anthropic/claude-haiku-4-5"
"""Model used to verify step output and synthesize final workflow responses."""

# ── Goals ─────────────────────────────────────────────────────────────────────

MODEL_GOAL_PLAN: str = "anthropic/claude-haiku-4-5"
"""Model used to decompose goals into milestones and extract learnings."""

# ── Persona ───────────────────────────────────────────────────────────────────

PERSONA_DEFAULT_PROFILE: str = "default"
"""Name of the persona profile used when no override is active."""

PERSONA_KNOWN_DIALS: frozenset = frozenset(
    {"humor", "directness", "formality", "depth"}
)
"""Dial names the framework recognises. Applications may extend by subclassing PersonaStore."""
