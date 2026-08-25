#!/usr/bin/env python3
"""v0.5c procedural opening tests — verify no hardcoded goblins.

Run: python -m narrator_v01.test_procedural
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from narrator_v01.dm_engine import GameState, Enemy, make_initial_state, PROMPT_VERSION


def test_procedural_no_hardcoded_goblins():
    """Test that procedural mode does not create hardcoded goblins."""
    state = make_initial_state(procedural=True)
    
    assert len(state.enemies) == 0, f"Procedural mode should have no enemies, got {state.enemies}"
    assert state.location == "", f"Procedural mode should have no location, got '{state.location}'"
    
    print("PASS: procedural_no_hardcoded_goblins")


def test_legacy_mode_still_works():
    """Test that legacy mode (procedural=False) still creates goblins."""
    state = make_initial_state(procedural=False)
    
    assert len(state.enemies) == 2, f"Legacy mode should have 2 enemies, got {len(state.enemies)}"
    assert state.enemies[0].name == "Goblin Scout"
    assert state.enemies[1].name == "Goblin Raider"
    
    print("PASS: legacy_mode_still_works")


def test_procedural_with_campaign_meta():
    """Test that procedural mode applies campaign_meta."""
    meta = {
        "style": "dark fantasy",
        "setting": "a cursed kingdom",
        "persona": "a reluctant hero",
        "tone": "ominous",
    }
    state = make_initial_state(procedural=True, campaign_meta=meta)
    
    assert state.story_style == "dark fantasy"
    assert state.setting == "a cursed kingdom"
    assert state.persona == "a reluctant hero"
    assert state.atmosphere == "ominous"
    
    print("PASS: procedural_with_campaign_meta")


def test_procedural_preserves_auto_roll():
    """Test that auto_roll setting is preserved in procedural mode."""
    state_auto = make_initial_state(procedural=True, auto_roll=True)
    state_manual = make_initial_state(procedural=True, auto_roll=False)
    
    assert state_auto.auto_roll == True
    assert state_manual.auto_roll == False
    
    print("PASS: procedural_preserves_auto_roll")


def test_prompt_version():
    """Test that PROMPT_VERSION is set."""
    assert PROMPT_VERSION == "v11"
    print(f"PASS: prompt_version ({PROMPT_VERSION})")


def test_prompt_has_procedural_instructions():
    """Test that the system prompt includes procedural generation instructions."""
    from narrator_v01.dm_engine import SYSTEM_PROMPT
    
    assert "PROCEDURAL WORLD" in SYSTEM_PROMPT
    assert "ENTITY_NEW" in SYSTEM_PROMPT
    assert "never reuse a fixed scenario" in SYSTEM_PROMPT.lower() or \
           "NEVER reuse a fixed scenario" in SYSTEM_PROMPT
    assert "KNOWN" in SYSTEM_PROMPT
    assert "RECALL" in SYSTEM_PROMPT
    
    print("PASS: prompt_has_procedural_instructions")


def test_prompt_has_new_tags():
    """Test that the system prompt documents the new entity tags."""
    from narrator_v01.dm_engine import SYSTEM_PROMPT

    assert "ENTITY_NEW" in SYSTEM_PROMPT
    assert "ENTITY_UPDATE" in SYSTEM_PROMPT
    assert "ALIAS" in SYSTEM_PROMPT
    assert "QUEST_UPDATE" in SYSTEM_PROMPT

    print("PASS: prompt_has_new_tags")


def test_derive_mood_from_scene_setting():
    """v1.0: Test that _derive_mood infers mood from scene-setting prose."""
    from narrator_v01.game_loop import _derive_mood

    # Horror keywords
    assert _derive_mood("The crypt was filled with dread and decay.") == "horror"
    # Mystery keywords
    assert _derive_mood("An ancient, forgotten hall full of secrets.") == "mystery"
    # Combat keywords
    assert _derive_mood("The sound of swords clashing echoed.") == "combat"
    # Tavern keywords
    assert _derive_mood("A warm tavern with laughter and ale.") == "tavern"
    # No match → fallback
    assert _derive_mood("A quiet path through the woods.") == "exploration"
    assert _derive_mood("A quiet path through the woods.", "mystery") == "mystery"

    print("PASS: derive_mood_from_scene_setting")


def main():
    print("\n" + "="*60)
    print("  V0.5C PROCEDURAL OPENING TESTS")
    print("="*60 + "\n")
    
    tests = [
        test_procedural_no_hardcoded_goblins,
        test_legacy_mode_still_works,
        test_procedural_with_campaign_meta,
        test_procedural_preserves_auto_roll,
        test_prompt_version,
        test_prompt_has_procedural_instructions,
        test_prompt_has_new_tags,
        test_derive_mood_from_scene_setting,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL: {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{passed + failed} passed")
    if failed == 0:
        print("  ALL TESTS PASSED")
    else:
        print(f"  {failed} TESTS FAILED")
    print("="*60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
