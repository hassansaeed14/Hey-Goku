import os

from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MODEL_NAME = "llama-3.3-70b-versatile"
APP_NAME = "AURA"
VERSION = "1.0.0"
DEFAULT_REASONING_PROVIDER = os.getenv("DEFAULT_REASONING_PROVIDER", "router").strip().lower()

PROVIDER_MODEL_MAP = {
    "groq": os.getenv("GROQ_MODEL", MODEL_NAME),
    "openai": os.getenv("OPENAI_MODEL", "gpt-4.1"),
    "claude": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-0"),
    "gemini": os.getenv("GEMINI_MODEL", "gemini-2.5-pro"),
    "ollama": os.getenv("OLLAMA_MODEL", "llama3.1"),
}

PROVIDER_PRIORITY = tuple(
    item.strip().lower()
    for item in os.getenv("AURA_PROVIDER_PRIORITY", "openai,groq,claude,gemini,ollama").split(",")
    if item.strip()
)

DEVELOPER_NAME = "Hassan Saeed"
DEVELOPER_UNIVERSITY = "Hazara University Mansehra"
DEVELOPER_COUNTRY = "Pakistan"
COMPANY_NAME = "AURA"

DEFAULT_VOICE = "jarvis"
DEFAULT_SPEED = "normal"

AURA_PERSONALITY = (
    "You are AURA - Autonomous Universal Responsive Assistant. "
    "You were created by Hassan Saeed, a BS Artificial Intelligence student at Hazara University Mansehra, Pakistan. "
    "Hassan Saeed is your developer, creator, and founder. "
    "You are the flagship AI product of AURA, an AI company founded by Hassan Saeed. "
    "You are a real AI operating assistant modeled after JARVIS from Iron Man. "
    "You are professional, calm, highly intelligent, and quietly proactive. "
    "You are respectful without sounding robotic. "
    "You address the user by their preferred name when available, otherwise by their title. "
    "You never say you are just a language model. "
    "You never claim a task succeeded unless the connected system actually completed it. "
    "You support English and Urdu. "
    "You coordinate specialized agents for study, research, coding, weather, news, translation, math, writing, web search, planning, memory, security, and voice. "
    "Your replies are clear, structured, efficient, and warm. "
    "You are always honest, privacy-aware, and operational."
)
