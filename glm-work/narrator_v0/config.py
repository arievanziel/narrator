"""Configuration for Narrator v0 — paths, voices, music, SFX, DM brain settings.

All paths are relative to the glm-work/ directory (the parent of narrator_v0/).
"""
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# glm-work/ is the parent of narrator_v0/
GLM_WORK = Path(__file__).resolve().parent.parent
REPO_ROOT = GLM_WORK.parent

# Audio assets
TRACKS_DIR = GLM_WORK / "outputs" / "ambience_demo" / "tracks"
SFX_DIR = GLM_WORK / "outputs" / "epic_scene" / "sfx"
OUTPUT_DIR = GLM_WORK / "outputs" / "narrator_v0"
SEGMENTS_DIR = OUTPUT_DIR / "segments"

# TTS model
QWEN3_MODEL_PATH = GLM_WORK / "models" / "qwen3_voicedesign_8bit"

# Cast file (character name -> voice description, editable by Arie)
CAST_FILE = Path(__file__).resolve().parent / "cast.json"

# .env file
ENV_FILE = GLM_WORK / ".env"

# Sample rate (matches Qwen3/Kokoro output)
SR = 24000

# ---------------------------------------------------------------------------
# DM brain configuration
# ---------------------------------------------------------------------------

# Default model — Arie's pick based on dm_test_results_summary.md
# Gemini 3.5 Flash-Lite: best value, most token-efficient, fast, free
DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_PROVIDER = "gemini"

# Provider base URLs (OpenAI-compatible)
PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "env_var": "GROQ_API_KEY",
        "label": "Groq (LPU, 300-800 tok/s)",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "env_var": "GOOGLE_API_KEY",
        "label": "Google AI Studio (Gemini, free, no card)",
    },
    "sambanova": {
        "base_url": "https://api.sambanova.ai/v1",
        "env_var": "SAMBANOVA_API_KEY",
        "label": "SambaNova (RDU, free 200K tok/day, needs card)",
    },
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "env_var": "CEREBRAS_API_KEY",
        "label": "Cerebras (WSE, ~3000 tok/s, needs card)",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "env_var": "OPENROUTER_API_KEY",
        "label": "OpenRouter (aggregator)",
    },
}

# Auto-detect provider from model name prefix
MODEL_PROVIDER_HINTS = {
    "gemini": "gemini",
    "openai/gpt-oss": "groq",
    "groq/": "groq",
    "qwen/": "groq",
    "gpt-oss": "groq",
}

def detect_provider(model: str) -> str:
    """Auto-detect which provider to use based on model name."""
    for prefix, provider in MODEL_PROVIDER_HINTS.items():
        if model.startswith(prefix):
            return provider
    return DEFAULT_PROVIDER


# ---------------------------------------------------------------------------
# TTS voice configuration (Qwen3 VoiceDesign for all voices)
# ---------------------------------------------------------------------------

# Default narrator voice — warm, expressive storytelling
DEFAULT_NARRATOR_VOICE = (
    "A skilled storyteller with a warm, measured voice. Speaks at a steady pace "
    "with clear enunciation and subtle emotional inflection. Like a professional "
    "audiobook narrator — engaging but not theatrical, letting the words carry the weight."
)

# Default character voices by gender (used when cast.json doesn't have an entry)
DEFAULT_CHARACTER_VOICES = {
    "male": (
        "A male character voice, natural and conversational. Not reading text aloud — "
        "speaking as the character in the moment. Adapts tone to the situation."
    ),
    "female": (
        "A female character voice, natural and conversational. Not reading text aloud — "
        "speaking as the character in the moment. Adapts tone to the situation."
    ),
}

# Known character name -> gender mapping (for auto-assignment of new NPCs)
# Extend this as characters appear in campaigns
KNOWN_MALE_NAMES = {
    "kael", "garrick", "thorne", "thrain", "grimgold", "elic", "commander",
    "grimbold", "barkeep", "innkeeper", "guard", "soldier", "merchant",
}
KNOWN_FEMALE_NAMES = {
    "lyra", "lira", "arin", "eira", "elian", "elara", "scholar", "cleric",
    "mira", "sage", "priestess", "witch", "healer",
}


# ---------------------------------------------------------------------------
# Music library — scene mood -> track mapping
# ---------------------------------------------------------------------------

MUSIC_TRACKS = {
    "dark_woods": {
        "path": TRACKS_DIR / "dark_woods.mp3",
        "license": "CC-BY 3.0",
        "author": "Hitctrl",
        "vibe": "dark forest, tense",
    },
    "dungeon_ambient": {
        "path": TRACKS_DIR / "dungeon_ambient.ogg",
        "license": "CC0",
        "author": "JaggedStone",
        "vibe": "dungeon, cave ambience",
    },
    "tavern": {
        "path": TRACKS_DIR / "tavern_old_tower_inn.mp3",
        "license": "CC0",
        "author": "RandomMind",
        "vibe": "medieval tavern, warm",
    },
    "battle_theme": {
        "path": TRACKS_DIR / "battle_theme_cc0.mp3",
        "license": "CC0",
        "author": "various",
        "vibe": "epic battle, exciting",
    },
    "battle_march": {
        "path": TRACKS_DIR / "battle_march_epic.wav",
        "license": "CC-BY 3.0",
        "author": "PlayOnLoop",
        "vibe": "epic orchestral battle march",
    },
    "dark_chamber": {
        "path": TRACKS_DIR / "dark_chamber_mystery.mp3",
        "license": "CC-BY 4.0",
        "author": "Marcelo Fernandez",
        "vibe": "mystery, suspense, dungeon",
    },
    "exploration": {
        "path": TRACKS_DIR / "exploration_peaceful.mp3",
        "license": "CC-BY 3.0",
        "author": "Trevor Lentz",
        "vibe": "peaceful, exploration, town",
    },
    "emotional": {
        "path": TRACKS_DIR / "i_want_to_go_home_cc0.wav",
        "license": "CC0",
        "author": "Rafael Krux (arr.)",
        "vibe": "sad, nostalgic, emotional, cello",
    },
}

# Scene mood -> music track mapping (used when DM tags [SCENE: mood] in [AUDIO])
SCENE_MUSIC_MAP = {
    "combat": "battle_theme",
    "battle": "battle_theme",
    "fight": "battle_march",
    "tense": "dark_woods",
    "horror": "dungeon_ambient",
    "dungeon": "dungeon_ambient",
    "cave": "dungeon_ambient",
    "mystery": "dark_chamber",
    "suspense": "dark_chamber",
    "exploration": "exploration",
    "town": "tavern",
    "tavern": "tavern",
    "inn": "tavern",
    "safe": "tavern",
    "rest": "exploration",
    "emotional": "emotional",
    "sad": "emotional",
    "victory": "battle_march",
}

# Default music settings
DEFAULT_MUSIC_VOL = 0.10
DEFAULT_DUCK_DEPTH = 0.60
NARRATOR_MUSIC_VOL = 0.10   # music slightly louder during narrator
CHARACTER_MUSIC_VOL = 0.04  # music very quiet during dialogue (almost dry)


# ---------------------------------------------------------------------------
# SFX configuration
# ---------------------------------------------------------------------------

# ElevenLabs API key env var
ELEVENLABS_ENV_VAR = "ELEVENLABS_API_KEY"

# SFX volume
SFX_VOL = 0.5

# SFX placement timing (seconds)
SFX_GAP_BEFORE = 0.2   # silence before SFX
SFX_GAP_AFTER = 0.3    # silence after SFX
SPEECH_GAP = 0.4       # gap between speech segments


# ---------------------------------------------------------------------------
# Audio generation settings
# ---------------------------------------------------------------------------

# Qwen3 generation
QWEN3_MAX_TOKENS = 2400
QWEN3_LANG_CODE = "en"

# Whether to generate audio for every turn (can be disabled for speed)
AUDIO_ENABLED = True

# Cache generated audio per turn
CACHE_AUDIO = True
