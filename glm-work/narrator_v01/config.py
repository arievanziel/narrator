"""Narrator v0.1 — Configuration."""
from pathlib import Path
import os

# Paths
GLM_WORK = Path(__file__).resolve().parent.parent
TRACKS_DIR = GLM_WORK / "outputs" / "ambience_demo" / "tracks"
SFX_DIR = GLM_WORK / "outputs" / "epic_scene" / "sfx"
OUTPUT_DIR = GLM_WORK / "outputs" / "narrator_v01"
SEGMENTS_DIR = OUTPUT_DIR / "segments"
QWEN3_MODEL_PATH = str(GLM_WORK / "models" / "qwen3_voicedesign_8bit")
CAST_FILE = Path(__file__).parent / "cast.json"
ENV_FILE = GLM_WORK / ".env"

# Create output dirs
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)

# DM brain providers (free tier)
PROVIDERS = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "env_var": "GOOGLE_API_KEY",
        "label": "Google Gemini (free)",
        "models": ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.5-pro"],
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "env_var": "GROQ_API_KEY",
        "label": "Groq (free, fast)",
        "models": ["openai/gpt-oss-120b", "groq/compound-mini", "qwen/qwen3.6-27b"],
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1/",
        "env_var": "ANTHROPIC_API_KEY",
        "label": "Anthropic Claude (paid)",
        "models": ["claude-haiku-4-5", "claude-sonnet-5", "claude-opus-5"],
    },
}

# Pricing per million tokens (input, output) in USD — only for paid providers
PRICING = {
    "anthropic": {
        "claude-haiku-4-5": (1.0, 5.0),
        "claude-sonnet-5": (2.0, 10.0),
        "claude-opus-5": (5.0, 25.0),
    },
}

# Default model
DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_PROVIDER = "gemini"

# TTS settings
TTS_ENGINES = ["qwen3", "kokoro", "silent"]
DEFAULT_TTS_ENGINE = "qwen3"
TTS_SPEED = 1.0

# Narrator voice description for Qwen3 VoiceDesign
NARRATOR_VOICE = "A warm, calm, deep male narrator voice with a measured storytelling tone. Not dramatic or shouty — like a seasoned audiobook reader."

# Default character voices (gender-based fallback)
DEFAULT_MALE_VOICE = "A rugged male adventurer's voice, confident and clear"
DEFAULT_FEMALE_VOICE = "A clear, expressive female voice with warmth and intelligence"

# Known character name genders (for auto-voice assignment)
KNOWN_MALE = ["Kael", "Goblin", "Innkeeper", "Guard", "Merchant", "King", "Wizard", "Warrior", "Thief", "Captain", "Old", "Sage", "Knight", "Barkeep", "Druid"]
KNOWN_FEMALE = ["Lyra", "Elara", "Mira", "Priestess", "Witch", "Queen", "Maiden", "Sorceress", "Ranger", "Healer", "Bard"]

# Music tracks (CC0/CC-BY library)
MUSIC_TRACKS = {
    "tavern": TRACKS_DIR / "tavern_old_tower_inn.mp3",
    "dark_woods": TRACKS_DIR / "dark_woods.mp3",
    "dungeon": TRACKS_DIR / "dungeon_ambient.ogg",
    "battle": TRACKS_DIR / "battle_theme_cc0.mp3",
    "mystery": TRACKS_DIR / "dark_chamber_mystery.mp3",
    "exploration": TRACKS_DIR / "exploration_peaceful.mp3",
    "sad": TRACKS_DIR / "i_want_to_go_home_cc0.wav",
    "emotional": TRACKS_DIR / "i_want_to_go_home_cc0.wav",
    "march": TRACKS_DIR / "battle_march_epic.wav",
}

# Scene mood → music track mapping
SCENE_MUSIC_MAP = {
    "combat": "battle",
    "battle": "battle",
    "tense": "march",
    "horror": "dark_woods",
    "mystery": "mystery",
    "exploration": "exploration",
    "tavern": "tavern",
    "inn": "tavern",
    "town": "tavern",
    "emotional": "emotional",
    "sad": "sad",
    "victory": "exploration",
    "dungeon": "dungeon",
    "calm": "exploration",
    "default": "exploration",
}

# Audio mixing settings
NARRATOR_MUSIC_VOL = 0.15
CHARACTER_MUSIC_VOL = 0.08
DEFAULT_MUSIC_VOL = 0.12
SFX_VOL = 0.6
SPEECH_GAP = 0.3  # seconds between speech segments

# Budget settings (USD)
DEFAULT_BUDGET = 5.0
