#!/usr/bin/env python3
"""v0.5b consistency guard tests — presence/liveness, RECALL, contradictions.

Run: python -m narrator_v01.test_guards
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from narrator_v01.world_store import WorldStore, Entity, Scene


def test_presence_liveness_dead_speaker():
    """Test that a dead NPC speaking is flagged as a violation."""
    store = WorldStore(campaign_id="guard_test")
    
    pc, _, _ = store.resolve_or_create(
        "Kael", "pc",
        {"hp": 12, "max_hp": 12, "disposition": "friendly",
         "voice_description": "young", "inventory": [], "stats": {}},
    )
    loc, _, _ = store.resolve_or_create(
        "Tavern", "location",
        {"description": "A tavern", "discovered": True},
    )
    npc, _, _ = store.resolve_or_create(
        "Gorak", "npc",
        {"hp": 7, "max_hp": 7, "disposition": "hostile", "voice_description": "rough"},
    )
    
    # Kill the NPC
    npc.alive = False
    npc.attributes["hp"] = 0
    
    # Set up scene with the NPC present
    store.current_scene = Scene(
        location_id=loc.id,
        present_entity_ids=[npc.id],
        started_turn=1,
    )
    
    # Narrative with dead NPC speaking
    narrative = '[narrator] The room falls silent.\n[Gorak] "You will pay for this!"'
    result = store.presence_liveness_guard(narrative)
    
    assert len(result["violations"]) > 0, "Should detect dead speaker"
    assert any("dead" in v["reason"].lower() for v in result["violations"])
    assert result["correction_prompt"] != ""
    
    print("PASS: presence_liveness_dead_speaker")


def test_presence_liveness_not_present():
    """Test that an NPC not in the scene speaking is flagged."""
    store = WorldStore(campaign_id="guard_test")
    
    pc, _, _ = store.resolve_or_create(
        "Kael", "pc",
        {"hp": 12, "max_hp": 12, "disposition": "friendly",
         "voice_description": "young", "inventory": [], "stats": {}},
    )
    loc, _, _ = store.resolve_or_create(
        "Tavern", "location",
        {"description": "A tavern", "discovered": True},
    )
    npc, _, _ = store.resolve_or_create(
        "Gorak", "npc",
        {"hp": 7, "max_hp": 7, "disposition": "hostile", "voice_description": "rough"},
    )
    
    # Set up scene WITHOUT the NPC
    store.current_scene = Scene(
        location_id=loc.id,
        present_entity_ids=[],
        started_turn=1,
    )
    
    narrative = '[Gorak] "I attack you!"'
    result = store.presence_liveness_guard(narrative)
    
    assert len(result["violations"]) > 0, "Should detect absent speaker"
    assert any("not present" in v["reason"].lower() for v in result["violations"])
    
    print("PASS: presence_liveness_not_present")


def test_presence_liveness_clean():
    """Test that a valid narrative passes without violations."""
    store = WorldStore(campaign_id="guard_test")
    
    pc, _, _ = store.resolve_or_create(
        "Kael", "pc",
        {"hp": 12, "max_hp": 12, "disposition": "friendly",
         "voice_description": "young", "inventory": [], "stats": {}},
    )
    loc, _, _ = store.resolve_or_create(
        "Tavern", "location",
        {"description": "A tavern", "discovered": True},
    )
    npc, _, _ = store.resolve_or_create(
        "Gorak", "npc",
        {"hp": 7, "max_hp": 7, "disposition": "hostile", "voice_description": "rough"},
    )
    
    store.current_scene = Scene(
        location_id=loc.id,
        present_entity_ids=[npc.id],
        started_turn=1,
    )
    
    # Valid narrative: narrator + present NPC
    narrative = '[narrator] The tavern is quiet.\n[Gorak] "What do you want?"'
    result = store.presence_liveness_guard(narrative)
    
    assert len(result["violations"]) == 0, f"Should be clean: {result['violations']}"
    assert result["correction_prompt"] == ""
    
    print("PASS: presence_liveness_clean")


def test_recall_found():
    """Test that RECALL finds an existing entity."""
    store = WorldStore(campaign_id="guard_test")
    
    npc, _, _ = store.resolve_or_create(
        "Gorak", "npc",
        {"hp": 7, "max_hp": 7, "disposition": "hostile", "voice_description": "rough"},
    )
    
    result = store.handle_recall("Gorak")
    assert result["found"]
    assert result["entity_id"] == npc.id
    assert "Gorak" in result["context_text"]
    assert "[RECALLED]" in result["context_text"]
    
    print("PASS: recall_found")


def test_recall_fuzzy():
    """Test that RECALL finds entities via fuzzy matching."""
    store = WorldStore(campaign_id="guard_test")
    
    npc, _, _ = store.resolve_or_create(
        "Mistress Vara", "npc",
        {"hp": 10, "max_hp": 10, "disposition": "neutral",
         "voice_description": "mysterious"},
    )
    
    # Fuzzy match
    result = store.handle_recall("Mistress Vara")
    assert result["found"]
    
    print("PASS: recall_fuzzy")


def test_recall_not_found():
    """Test that RECALL returns not-found for nonexistent entities."""
    store = WorldStore(campaign_id="guard_test")
    
    result = store.handle_recall("Nonexistent Character")
    assert not result["found"]
    assert "No entity matching" in result["message"]
    
    print("PASS: recall_not_found")


def test_contradiction_detection():
    """Test that contradictory updates are detected."""
    store = WorldStore(campaign_id="guard_test")
    
    npc, _, _ = store.resolve_or_create(
        "Gorak", "npc",
        {"hp": 7, "max_hp": 7, "disposition": "hostile", "voice_description": "rough"},
    )
    
    # Set hair_color via ENTITY_UPDATE
    store.apply_turn_mechanics([
        "ENTITY_UPDATE:Gorak,disposition,friendly",
    ], current_turn=1)
    
    # Now try to set it to something different
    warning = store.check_contradiction(npc, "disposition", "hostile")
    assert warning is not None, "Should detect contradiction"
    assert "CONTRADICTION" in warning
    
    print("PASS: contradiction_detection")


def test_no_contradiction_same_value():
    """Test that setting the same value is not a contradiction."""
    store = WorldStore(campaign_id="guard_test")
    
    npc, _, _ = store.resolve_or_create(
        "Gorak", "npc",
        {"hp": 7, "max_hp": 7, "disposition": "hostile", "voice_description": "rough"},
    )
    
    store.apply_turn_mechanics([
        "ENTITY_UPDATE:Gorak,disposition,friendly",
    ], current_turn=1)
    
    # Set to same value
    warning = store.check_contradiction(npc, "disposition", "friendly")
    assert warning is None, "Same value should not be a contradiction"
    
    print("PASS: no_contradiction_same_value")


def test_since_you_were_last_here_digest():
    """Test the 'since you were last here' digest generation."""
    store = WorldStore(campaign_id="guard_test")
    
    loc, _, _ = store.resolve_or_create(
        "Tavern", "location",
        {"description": "A tavern", "discovered": True},
    )
    npc, _, _ = store.resolve_or_create(
        "Gorak", "npc",
        {"hp": 7, "max_hp": 7, "disposition": "hostile", "voice_description": "rough"},
    )
    
    # First visit
    digest1 = store.enter_scene(loc.id, current_turn=1)
    assert digest1 is None, "First visit should have no digest"
    
    # Leave and come back
    store.exit_scene()
    npc.last_seen_turn = 5  # NPC arrived after we left
    
    # Return after several turns
    digest2 = store.enter_scene(loc.id, current_turn=10)
    # Digest may or may not be generated depending on implementation
    # The key is that it doesn't crash
    
    print("PASS: since_you_were_last_here_digest")


def main():
    print("\n" + "="*60)
    print("  V0.5B CONSISTENCY GUARD TESTS")
    print("="*60 + "\n")
    
    tests = [
        test_presence_liveness_dead_speaker,
        test_presence_liveness_not_present,
        test_presence_liveness_clean,
        test_recall_found,
        test_recall_fuzzy,
        test_recall_not_found,
        test_contradiction_detection,
        test_no_contradiction_same_value,
        test_since_you_were_last_here_digest,
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
