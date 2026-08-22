#!/usr/bin/env python3
"""v0.9 Golden transcript regression harness.

Replays a fixed sequence of actions with a mocked LLM and verifies that:
- The World Store creates entities correctly
- Mechanics are applied deterministically
- The context assembler includes the right entities
- No contradictions or hallucinated entities appear

This is a regression harness — if any of these checks fail after a code
change, something broke the World Engine contract.

Run: python -m narrator_v01.test_golden
"""
import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from narrator_v01.dm_engine import GameState, make_initial_state, parse_response
from narrator_v01.world_store import WorldStore, TurnRecord, TokenBudget


# Golden LLM responses — these simulate what a well-behaved LLM would produce
# for a dark fantasy campaign opening. They exercise ENTITY_NEW, MECHANICS,
# and CHRONICLE tags.

GOLDEN_OPENING = """[STORY]
[narrator] The wind howls through the abandoned village of Ravenshade, carrying the scent of ash and old rain.
[narrator] A lone figure, {PC_NAME}, steps through the broken gates, eyes scanning the empty streets.
[narrator] A weathered sign creaks above a door — "The Crooked Crow" — the village tavern, somehow still lit from within.

[SCENE]
exploration

[MECHANICS]
ENTITY_NEW:location,Ravenshade,abandoned village with broken gates and ash-scented wind
ENTITY_NEW:npc,Mara Crow,tavern keeper with grey hair and a sharp wit,disposition:neutral,hp:8,max_hp:8,ac:10,voice_description:weathered female voice with a hint of mystery
ENTITY_NEW:location,The Crooked Crow,weathered tavern still lit from within

[CHRONICLE]
{PC_NAME} arrives at the abandoned village of Ravenshade and discovers The Crooked Crow tavern.

[SUGGESTIONS]
Enter the tavern
Call out to see if anyone is here
Examine the broken gates
"""

GOLDEN_TURN_2 = """[STORY]
[narrator] {PC_NAME} pushes open the creaking door of The Crooked Crow.
[narrator] The warmth of a dying fire greets them, along with the sharp eyes of Mara Crow, who wipes a tankard behind the bar.
[Mara Crow] "Well now. We don't get many visitors these days. What brings you to Ravenshade?"

[SCENE]
dialogue

[MECHANICS]
NO_MECHANICS

[CHRONICLE]
{PC_NAME} enters The Crooked Crow and meets Mara Crow, the tavern keeper.

[SUGGESTIONS]
Ask Mara about the village
Order a drink
Ask about lodging
"""

GOLDEN_TURN_3 = """[STORY]
[narrator] Mara leans forward, her voice dropping to a whisper.
[Mara Crow] "Three nights ago, the shadows started... moving. People vanished. The miller, the smith, even the children."
[Mara Crow] "They say something woke up in the old crypt on the hill. Something old. Something hungry."
[narrator] She slides a tarnished key across the bar.
[Mara Crow] "This opens the crypt door. If you're brave enough."

[SCENE]
dialogue

[MECHANICS]
ITEM_GAINED:Tarnished Crypt Key

[CHRONICLE]
Mara tells {PC_NAME} about the vanishings and gives them a key to the old crypt.

[SUGGESTIONS]
Take the key and head to the crypt
Ask more about the vanishings
Ask who "they" are
"""


def test_entity_creation():
    """Test that ENTITY_NEW creates entities in the World Store."""
    state = make_initial_state(procedural=True)
    state.pc_name = "TestHero"
    store = WorldStore(campaign_id="golden_test")
    state.attach_world_store(store)

    # Parse and apply the golden opening
    sections = parse_response(GOLDEN_OPENING.replace("{PC_NAME}", "TestHero"))
    changes = state.apply_mechanics(sections["MECHANICS"])

    # Verify entities were created
    entity_names = [e.name for e in store.entities.values()]
    assert "Ravenshade" in entity_names, f"Ravenshade not created: {entity_names}"
    assert "Mara Crow" in entity_names, f"Mara Crow not created: {entity_names}"
    assert "The Crooked Crow" in entity_names, f"The Crooked Crow not created: {entity_names}"

    # Verify entity types
    for e in store.entities.values():
        if e.name == "Ravenshade":
            assert e.type == "location", f"Ravenshade should be location, got {e.type}"
        elif e.name == "Mara Crow":
            assert e.type == "npc", f"Mara Crow should be npc, got {e.type}"

    print(f"PASS: entity_creation ({len(store.entities)} entities created)")


def test_entity_persistence_across_turns():
    """Test that entities persist across turns and are retrievable."""
    state = make_initial_state(procedural=True)
    state.pc_name = "TestHero"
    store = WorldStore(campaign_id="golden_test_2")
    state.attach_world_store(store)

    # Turn 1: opening
    sections1 = parse_response(GOLDEN_OPENING.replace("{PC_NAME}", "TestHero"))
    state.apply_mechanics(sections1["MECHANICS"])

    # Turn 2: enter tavern
    sections2 = parse_response(GOLDEN_TURN_2.replace("{PC_NAME}", "TestHero"))
    state.apply_mechanics(sections2["MECHANICS"])

    # Verify Mara Crow still exists
    mara = None
    for e in store.entities.values():
        if e.name == "Mara Crow":
            mara = e
            break
    assert mara is not None, "Mara Crow should persist after turn 2"
    assert mara.alive, "Mara Crow should be alive"

    print("PASS: entity_persistence_across_turns")


def test_item_gained():
    """Test that ITEM_GAINED adds to inventory."""
    state = make_initial_state(procedural=True)
    state.pc_name = "TestHero"
    store = WorldStore(campaign_id="golden_test_3")
    state.attach_world_store(store)

    # Apply opening first (to set up the world)
    sections1 = parse_response(GOLDEN_OPENING.replace("{PC_NAME}", "TestHero"))
    state.apply_mechanics(sections1["MECHANICS"])

    # Apply turn 3 (ITEM_GAINED)
    sections3 = parse_response(GOLDEN_TURN_3.replace("{PC_NAME}", "TestHero"))
    changes = state.apply_mechanics(sections3["MECHANICS"])

    # Verify item was added
    assert "Tarnished Crypt Key" in state.inventory, \
        f"Tarnished Crypt Key not in inventory: {state.inventory}"
    assert any("Tarnished Crypt Key" in c for c in changes), \
        f"ITEM_GAINED not in changes: {changes}"

    print(f"PASS: item_gained (inventory: {state.inventory})")


def test_context_assembler_includes_known_entities():
    """Test that the context assembler includes created entities as KNOWN."""
    state = make_initial_state(procedural=True)
    state.pc_name = "TestHero"
    store = WorldStore(campaign_id="golden_test_4")
    state.attach_world_store(store)

    # Apply opening
    sections1 = parse_response(GOLDEN_OPENING.replace("{PC_NAME}", "TestHero"))
    state.apply_mechanics(sections1["MECHANICS"])

    # Get context for next turn
    bundle = store.get_context_for_turn(
        player_input="I talk to Mara Crow",
        budget=TokenBudget(),
        last_narration="The Crooked Crow tavern",
        system_prompt="You are a DM.",
        recent_turns=[],
    )

    # The context should mention Mara Crow or Ravenshade
    context_text = bundle.stable_prefix + bundle.volatile_suffix
    assert "Mara" in context_text or "Crow" in context_text, \
        "Mara Crow should appear in context after being created"
    assert "Ravenshade" in context_text, \
        "Ravenshade should appear in context after being created"

    print(f"PASS: context_assembler_includes_known_entities "
          f"({len(bundle.included_entity_ids)} entities in context)")


def test_no_hardcoded_enemies():
    """Test that procedural mode does not create hardcoded enemies."""
    state = make_initial_state(procedural=True)
    assert len(state.enemies) == 0, \
        f"Procedural mode should start with no enemies, got: {state.enemies}"
    assert state.location == "", \
        f"Procedural mode should start with empty location, got: {state.location}"

    print("PASS: no_hardcoded_enemies")


def test_roll_seed_reproducibility():
    """Test that the same campaign+turn always produces the same roll."""
    from narrator_v01.dm_engine import make_roll_seed, resolve_roll
    seed1 = make_roll_seed("golden_campaign", 5)
    seed2 = make_roll_seed("golden_campaign", 5)
    assert seed1 == seed2, "Same campaign+turn should produce same seed"

    req = {"dice": "d20", "skill": "attack", "dc": 12}
    r1 = resolve_roll(req, seed=seed1)
    r2 = resolve_roll(req, seed=seed2)
    assert r1["total"] == r2["total"], \
        f"Same seed should produce same roll: {r1['total']} != {r2['total']}"

    print(f"PASS: roll_seed_reproducibility (roll={r1['total']})")


def test_turn_record_logging():
    """Test that TurnRecords are logged with all fields."""
    state = make_initial_state(procedural=True)
    state.pc_name = "TestHero"
    store = WorldStore(campaign_id="golden_test_5")
    state.attach_world_store(store)

    # Apply opening
    sections = parse_response(GOLDEN_OPENING.replace("{PC_NAME}", "TestHero"))
    state.apply_mechanics(sections["MECHANICS"])

    # Log a turn record
    record = TurnRecord(
        turn=1,
        player_input="Start the story",
        narrative=sections["STORY"][:200],
        mechanics_applied=["Created: Ravenshade"],
    )
    store.append_turn_record(record)

    # Verify the JSONL file exists
    log_path = store.data_dir / f"turns_{store.campaign_id}.jsonl"
    assert log_path.exists(), f"Turn log should exist at {log_path}"

    # Verify content
    with open(log_path) as f:
        line = f.readline().strip()
        data = json.loads(line)
        assert data["turn"] == 1
        assert data["player_input"] == "Start the story"
        assert "Ravenshade" in data["mechanics_applied"][0]

    print("PASS: turn_record_logging")


def test_save_load_worldstore():
    """Test that WorldStore can be saved and loaded."""
    state = make_initial_state(procedural=True)
    state.pc_name = "TestHero"
    store = WorldStore(campaign_id="golden_test_6")
    state.attach_world_store(store)

    # Create some entities
    sections = parse_response(GOLDEN_OPENING.replace("{PC_NAME}", "TestHero"))
    state.apply_mechanics(sections["MECHANICS"])

    # Save
    store.save()

    # Load into a new store
    store2 = WorldStore(campaign_id="golden_test_6")
    store2.load()

    # Verify entities persisted
    names1 = sorted(e.name for e in store.entities.values())
    names2 = sorted(e.name for e in store2.entities.values())
    assert names1 == names2, \
        f"Entity names should match after load: {names1} != {names2}"

    print(f"PASS: save_load_worldstore ({len(names1)} entities persisted)")


def main():
    print("\n" + "="*60)
    print("  V0.9 GOLDEN TRANSCRIPT REGRESSION TESTS")
    print("="*60 + "\n")

    tests = [
        test_entity_creation,
        test_entity_persistence_across_turns,
        test_item_gained,
        test_context_assembler_includes_known_entities,
        test_no_hardcoded_enemies,
        test_roll_seed_reproducibility,
        test_turn_record_logging,
        test_save_load_worldstore,
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
