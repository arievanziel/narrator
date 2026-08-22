#!/usr/bin/env python3
"""Unit tests for world_store.py — tests the World Store in isolation.

Run: python -m narrator_v01.test_world_store
"""
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from narrator_v01.world_store import (
    WorldStore, Entity, Link, Revision, Fact, Scene, Encounter,
    RollRecord, TurnRecord, TokenBudget, ContextBundle,
    normalize_name, REQUIRED_ATTRS, MUTABLE_FIELDS,
)


def test_normalize_name():
    """Test name normalization."""
    assert normalize_name("The Old Innkeeper") == "innkeeper"
    assert normalize_name("Sir Gorak the Brave") == "gorak the brave"
    assert normalize_name("A Health Potion") == "health potion"
    assert normalize_name("Captain Marla") == "marla"
    assert normalize_name("  The  Rusty  Anchor  ") == "rusty anchor"
    print("PASS: normalize_name")


def test_entity_creation():
    """Test basic entity creation and validation."""
    store = WorldStore(campaign_id="test")
    
    # Create an NPC
    entity, created, reason = store.resolve_or_create(
        "Gorak", "npc",
        {"hp": 7, "max_hp": 7, "disposition": "hostile", "voice_description": "gruff"},
        current_turn=1,
    )
    assert created, f"Should create new entity: {reason}"
    assert entity.type == "npc"
    assert entity.name == "Gorak"
    assert entity.attributes["hp"] == 7
    assert entity.id.startswith("npc_")
    print(f"PASS: entity_creation (id={entity.id})")


def test_duplicate_resolution():
    """Test that duplicate entities are resolved, not recreated."""
    store = WorldStore(campaign_id="test")
    
    # First creation
    e1, created1, _ = store.resolve_or_create(
        "Gorak", "npc",
        {"hp": 7, "max_hp": 7, "disposition": "hostile", "voice_description": "gruff"},
    )
    assert created1
    
    # Same name — should match
    e2, created2, reason2 = store.resolve_or_create(
        "Gorak", "npc",
        {"hp": 7, "max_hp": 7, "disposition": "hostile", "voice_description": "gruff"},
    )
    assert not created2, f"Should match existing: {reason2}"
    assert e1.id == e2.id
    
    # Fuzzy match — "Gorak the Goblin" vs "Gorak" should match (ratio >= 0.85)
    e3, created3, reason3 = store.resolve_or_create(
        "Gorak the Goblin", "npc",
        {"hp": 7, "max_hp": 7, "disposition": "hostile", "voice_description": "gruff"},
    )
    assert not created3, f"Should fuzzy match: {reason3}"
    assert e1.id == e3.id
    
    # Alias match
    e4, created4, reason4 = store.resolve_or_create(
        "the goblin", "npc",
        {"hp": 7, "max_hp": 7, "disposition": "hostile", "voice_description": "gruff"},
    )
    # This should create a new entity since "the goblin" normalizes to "goblin"
    # which doesn't match "gorak"
    # But if we create "Gorak" and then try "the gorak", it should match
    e5, created5, reason5 = store.resolve_or_create(
        "the gorak", "npc",
        {"hp": 7, "max_hp": 7, "disposition": "hostile", "voice_description": "gruff"},
    )
    assert not created5, f"Should match via normalization: {reason5}"
    assert e1.id == e5.id
    
    print("PASS: duplicate_resolution")


def test_hp_clamp():
    """Test that HP is clamped to [0, max_hp]."""
    store = WorldStore(campaign_id="test")
    
    # Create PC
    pc, _, _ = store.resolve_or_create(
        "Kael", "pc",
        {"hp": 12, "max_hp": 12, "disposition": "friendly",
         "voice_description": "young male", "inventory": [], "stats": {}},
    )
    
    # Try to set HP above max
    changes = store.apply_turn_mechanics(["HP_CHANGE:+100"], current_turn=1)
    assert pc.attributes["hp"] == 12, f"HP should be clamped at 12, got {pc.attributes['hp']}"
    assert any("12 -> 12" in c for c in changes)
    
    # Damage
    changes = store.apply_turn_mechanics(["HP_CHANGE:-5"], current_turn=2)
    assert pc.attributes["hp"] == 7, f"HP should be 7, got {pc.attributes['hp']}"
    
    # Heal beyond max
    changes = store.apply_turn_mechanics(["HP_CHANGE:+100"], current_turn=3)
    assert pc.attributes["hp"] == 12, f"HP should be clamped at 12, got {pc.attributes['hp']}"
    
    print("PASS: hp_clamp")


def test_enemy_dead_requires_roll():
    """Test that ENEMY_DEAD is rejected without roll evidence."""
    store = WorldStore(campaign_id="test")
    
    # Create enemy
    enemy, _, _ = store.resolve_or_create(
        "Goblin Scout", "npc",
        {"hp": 7, "max_hp": 7, "disposition": "hostile", "voice_description": "rough"},
    )
    
    # Try to kill without roll
    changes = store.apply_turn_mechanics(["ENEMY_DEAD:Goblin Scout"], current_turn=1)
    assert enemy.alive, "Enemy should still be alive"
    assert any("REJECTED" in c for c in changes)
    
    # Kill with roll evidence
    changes = store.apply_turn_mechanics([
        "ROLL_REQUEST:d20+5 for attack",
        "ENEMY_DEAD:Goblin Scout",
    ], current_turn=2)
    assert not enemy.alive, "Enemy should be dead"
    assert any("DEAD" in c for c in changes)
    
    print("PASS: enemy_dead_requires_roll")


def test_enemy_hp_zero_requires_roll():
    """Test that setting enemy HP to 0 is rejected without roll evidence."""
    store = WorldStore(campaign_id="test")
    
    enemy, _, _ = store.resolve_or_create(
        "Goblin", "npc",
        {"hp": 7, "max_hp": 7, "disposition": "hostile", "voice_description": "rough"},
    )
    
    # Try to set HP to 0 without roll
    changes = store.apply_turn_mechanics(["ENEMY_HP:Goblin,0/7"], current_turn=1)
    assert enemy.attributes["hp"] == 7, "HP should still be 7"
    assert any("REJECTED" in c for c in changes)
    
    # With roll evidence
    changes = store.apply_turn_mechanics([
        "ROLL_REQUEST:d20+5 for attack",
        "ENEMY_HP:Goblin,0/7",
    ], current_turn=2)
    assert enemy.attributes["hp"] == 0
    assert any("HP -> 0" in c for c in changes)
    
    print("PASS: enemy_hp_zero_requires_roll")


def test_waste_potion_guard():
    """Test that invalid item usage blocks all item usage that turn."""
    store = WorldStore(campaign_id="test")
    
    # Create PC with a health potion
    pc, _, _ = store.resolve_or_create(
        "Kael", "pc",
        {"hp": 10, "max_hp": 12, "disposition": "friendly",
         "voice_description": "young", "inventory": [], "stats": {}},
    )
    potion, _, _ = store.resolve_or_create(
        "Health Potion", "item",
        {"description": "restores HP", "owner_entity_id": pc.id},
    )
    pc.attributes["inventory"] = [potion.id]
    
    # Try to use a fake potion + real potion
    changes = store.apply_turn_mechanics([
        "ITEM_USED:Fake Potion",
        "ITEM_USED:Health Potion",
    ], current_turn=1)
    
    # Both should be rejected
    assert any("REJECTED" in c for c in changes)
    assert len(pc.attributes["inventory"]) == 1, "Potion should not be consumed"
    
    print("PASS: waste_potion_guard")


def test_item_gained():
    """Test that ITEM_GAINED creates an item entity and adds to inventory."""
    store = WorldStore(campaign_id="test")
    
    pc, _, _ = store.resolve_or_create(
        "Kael", "pc",
        {"hp": 12, "max_hp": 12, "disposition": "friendly",
         "voice_description": "young", "inventory": [], "stats": {}},
    )
    
    changes = store.apply_turn_mechanics(["ITEM_GAINED:Iron Dagger"], current_turn=1)
    assert any("Gained" in c for c in changes)
    assert len(pc.attributes["inventory"]) == 1
    
    # Verify the item entity was created
    item_entities = [e for e in store.entities.values() if e.type == "item"]
    assert any(e.name == "Iron Dagger" for e in item_entities)
    
    print("PASS: item_gained")


def test_entity_new():
    """Test ENTITY_NEW tag creates entities."""
    store = WorldStore(campaign_id="test")
    
    changes = store.apply_turn_mechanics([
        "ENTITY_NEW:npc,Mistress Vara,A mysterious sorceress with silver hair",
    ], current_turn=1)
    
    assert any("Created" in c for c in changes)
    entities = [e for e in store.entities.values() if e.name == "Mistress Vara"]
    assert len(entities) == 1
    assert entities[0].summary == "A mysterious sorceress with silver hair"
    
    print("PASS: entity_new")


def test_entity_update_revision():
    """Test that ENTITY_UPDATE writes a revision."""
    store = WorldStore(campaign_id="test")
    
    # Create NPC
    store.resolve_or_create(
        "Gorak", "npc",
        {"hp": 7, "max_hp": 7, "disposition": "hostile", "voice_description": "gruff"},
    )
    
    # Update disposition
    changes = store.apply_turn_mechanics([
        "ENTITY_UPDATE:Gorak,disposition,friendly",
    ], current_turn=1)
    
    assert any("Updated" in c for c in changes)
    gorak = [e for e in store.entities.values() if e.name == "Gorak"][0]
    assert gorak.attributes["disposition"] == "friendly"
    assert len(gorak.revisions) == 1
    assert gorak.revisions[0].field == "disposition"
    assert gorak.revisions[0].old == "hostile"
    assert gorak.revisions[0].new == "friendly"
    
    print("PASS: entity_update_revision")


def test_unknown_tag_rejected():
    """Test that unknown tags are rejected and logged."""
    store = WorldStore(campaign_id="test")
    
    changes = store.apply_turn_mechanics(["UNKNOWN_TAG:foo"], current_turn=1)
    assert any("REJECTED" in c and "unknown" in c for c in changes)
    
    print("PASS: unknown_tag_rejected")


def test_persistence_atomic():
    """Test atomic save/load."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = WorldStore(campaign_id="test", data_dir=Path(tmpdir))
        
        # Create some entities
        store.resolve_or_create(
            "Kael", "pc",
            {"hp": 12, "max_hp": 12, "disposition": "friendly",
             "voice_description": "young", "inventory": [], "stats": {}},
        )
        store.resolve_or_create(
            "Goblin", "npc",
            {"hp": 7, "max_hp": 7, "disposition": "hostile", "voice_description": "rough"},
        )
        
        # Save
        save_path = store.save()
        assert save_path.exists()
        
        # Load into new store
        store2 = WorldStore(campaign_id="test", data_dir=Path(tmpdir))
        store2.load()
        
        assert len(store2.entities) == 2
        assert any(e.name == "Kael" for e in store2.entities.values())
        assert any(e.name == "Goblin" for e in store2.entities.values())
        
    print("PASS: persistence_atomic")


def test_turn_log_append():
    """Test that turn records are appended to the JSONL log."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = WorldStore(campaign_id="test", data_dir=Path(tmpdir))
        
        record1 = TurnRecord(turn=1, player_input="I attack", narrative="...",
                             mechanics_applied=["HP: 12 -> 10"])
        store.append_turn_record(record1)
        
        record2 = TurnRecord(turn=2, player_input="I dodge", narrative="...",
                             mechanics_applied=["HP: 10 -> 10"])
        store.append_turn_record(record2)
        
        log_path = Path(tmpdir) / "turns_test.jsonl"
        assert log_path.exists()
        
        with open(log_path) as f:
            lines = f.readlines()
        assert len(lines) == 2
        
    print("PASS: turn_log_append")


def test_context_assembly():
    """Test basic context assembly."""
    store = WorldStore(campaign_id="test")
    
    pc, _, _ = store.resolve_or_create(
        "Kael", "pc",
        {"hp": 12, "max_hp": 12, "disposition": "friendly",
         "voice_description": "young", "inventory": [], "stats": {}},
    )
    
    loc, _, _ = store.resolve_or_create(
        "The Rusty Anchor", "location",
        {"description": "A dim tavern", "discovered": True},
    )
    
    enemy, _, _ = store.resolve_or_create(
        "Goblin Scout", "npc",
        {"hp": 7, "max_hp": 7, "disposition": "hostile", "voice_description": "rough"},
    )
    
    # Set up scene
    store.enter_scene(loc.id, current_turn=1)
    
    bundle = store.get_context_for_turn("I attack the goblin!")
    
    assert "Kael" in bundle.stable_prefix
    assert "I attack the goblin!" in bundle.volatile_suffix
    assert pc.id in bundle.included_entity_ids
    
    print("PASS: context_assembly")


def test_quest_update():
    """Test QUEST_UPDATE tag."""
    store = WorldStore(campaign_id="test")
    
    changes = store.apply_turn_mechanics([
        "QUEST_UPDATE:Find the Lost Artifact,active",
    ], current_turn=1)
    
    assert any("Quest" in c for c in changes)
    quests = [e for e in store.entities.values() if e.type == "quest"]
    assert len(quests) == 1
    assert quests[0].attributes["status"] == "active"
    
    # Invalid status
    changes = store.apply_turn_mechanics([
        "QUEST_UPDATE:Find the Lost Artifact,in_progress",
    ], current_turn=2)
    assert any("REJECTED" in c for c in changes)
    
    print("PASS: quest_update")


def main():
    print("\n" + "="*60)
    print("  WORLD STORE UNIT TESTS (v0.4c)")
    print("="*60 + "\n")
    
    tests = [
        test_normalize_name,
        test_entity_creation,
        test_duplicate_resolution,
        test_hp_clamp,
        test_enemy_dead_requires_roll,
        test_enemy_hp_zero_requires_roll,
        test_waste_potion_guard,
        test_item_gained,
        test_entity_new,
        test_entity_update_revision,
        test_unknown_tag_rejected,
        test_persistence_atomic,
        test_turn_log_append,
        test_context_assembly,
        test_quest_update,
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
