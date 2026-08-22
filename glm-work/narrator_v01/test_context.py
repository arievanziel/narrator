#!/usr/bin/env python3
"""v0.5a context assembler tests — verify layered assembly and scoring.

Run: python -m narrator_v01.test_context
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from narrator_v01.world_store import (
    WorldStore, Entity, Scene, TokenBudget, ContextBundle,
)


def test_basic_context_assembly():
    """Test that context assembly produces stable + volatile split."""
    store = WorldStore(campaign_id="ctx_test")
    
    # Create PC
    pc, _, _ = store.resolve_or_create(
        "Kael", "pc",
        {"hp": 12, "max_hp": 12, "disposition": "friendly",
         "voice_description": "young", "inventory": [], "stats": {}},
    )
    
    # Create location
    loc, _, _ = store.resolve_or_create(
        "Darkwood Tavern", "location",
        {"description": "A dim tavern", "discovered": True},
    )
    
    # Create NPC
    npc, _, _ = store.resolve_or_create(
        "Gorak", "npc",
        {"hp": 7, "max_hp": 7, "disposition": "hostile", "voice_description": "rough"},
    )
    
    store.enter_scene(loc.id, current_turn=1)
    
    bundle = store.get_context_for_turn(
        player_input="I attack Gorak!",
        system_prompt="You are a DM.",
    )
    
    assert isinstance(bundle, ContextBundle)
    assert "Kael" in bundle.stable_prefix
    assert "I attack Gorak!" in bundle.volatile_suffix
    assert pc.id in bundle.included_entity_ids
    
    print("PASS: basic_context_assembly")


def test_stable_vs_volatile_split():
    """Test that stable prefix contains system prompt + directory, volatile has action."""
    store = WorldStore(campaign_id="ctx_test")
    
    pc, _, _ = store.resolve_or_create(
        "Kael", "pc",
        {"hp": 12, "max_hp": 12, "disposition": "friendly",
         "voice_description": "young", "inventory": [], "stats": {}},
    )
    
    bundle = store.get_context_for_turn(
        player_input="I look around",
        system_prompt="SYSTEM: You are a DM.",
    )
    
    # System prompt should be in stable prefix
    assert "SYSTEM" in bundle.stable_prefix
    # Player action should be in volatile suffix
    assert "I look around" in bundle.volatile_suffix
    
    print("PASS: stable_vs_volatile_split")


def test_scoring_pinned():
    """Test that pinned entities (PC, active quest, current location) score highest."""
    store = WorldStore(campaign_id="ctx_test")
    
    pc, _, _ = store.resolve_or_create(
        "Kael", "pc",
        {"hp": 12, "max_hp": 12, "disposition": "friendly",
         "voice_description": "young", "inventory": [], "stats": {}},
    )
    loc, _, _ = store.resolve_or_create(
        "Tavern", "location",
        {"description": "A tavern", "discovered": True},
    )
    quest, _, _ = store.resolve_or_create(
        "Save the Village", "quest",
        {"description": "Save the village", "status": "active", "objectives": []},
    )
    
    store.enter_scene(loc.id, current_turn=1)
    
    # Score the PC
    pinned_ids = {pc.id, loc.id, quest.id}
    score = store._score_entity(pc, "I attack", "", 1, pinned_ids)
    assert score >= 100, f"PC should be pinned (score >= 100), got {score}"
    
    # Score the location
    score = store._score_entity(loc, "I attack", "", 1, pinned_ids)
    assert score >= 100, f"Location should be pinned, got {score}"
    
    # Score the quest
    score = store._score_entity(quest, "I attack", "", 1, pinned_ids)
    assert score >= 100, f"Active quest should be pinned, got {score}"
    
    print("PASS: scoring_pinned")


def test_scoring_named_in_input():
    """Test that entities named in player input get scored higher."""
    store = WorldStore(campaign_id="ctx_test")
    
    pc, _, _ = store.resolve_or_create(
        "Kael", "pc",
        {"hp": 12, "max_hp": 12, "disposition": "friendly",
         "voice_description": "young", "inventory": [], "stats": {}},
    )
    npc, _, _ = store.resolve_or_create(
        "Gorak", "npc",
        {"hp": 7, "max_hp": 7, "disposition": "hostile", "voice_description": "rough"},
    )
    
    # Score with "Gorak" in input
    score_with = store._score_entity(npc, "I attack Gorak", "", 1, {pc.id})
    # Score without "Gorak" in input
    score_without = store._score_entity(npc, "I look around", "", 1, {pc.id})
    
    assert score_with > score_without, \
        f"Named in input should score higher: {score_with} > {score_without}"
    assert score_with >= 40, f"Named in input bonus should apply, got {score_with}"
    
    print(f"PASS: scoring_named_in_input (with={score_with}, without={score_without})")


def test_scoring_recency_decay():
    """Test that recency score decays with turns away."""
    store = WorldStore(campaign_id="ctx_test")
    
    pc, _, _ = store.resolve_or_create(
        "Kael", "pc",
        {"hp": 12, "max_hp": 12, "disposition": "friendly",
         "voice_description": "young", "inventory": [], "stats": {}},
    )
    npc, _, _ = store.resolve_or_create(
        "Old Man", "npc",
        {"hp": 5, "max_hp": 5, "disposition": "neutral", "voice_description": "old"},
    )
    
    # Score at turn 1 (just seen)
    score_recent = store._score_entity(npc, "", "", 1, {pc.id})
    
    # Score at turn 20 (19 turns away)
    npc.last_seen_turn = 1
    score_old = store._score_entity(npc, "", "", 20, {pc.id})
    
    assert score_recent > score_old, \
        f"Recent entity should score higher: {score_recent} > {score_old}"
    
    print(f"PASS: scoring_recency_decay (recent={score_recent}, old={score_old})")


def test_token_budget_respected():
    """Test that token budgets are roughly respected."""
    store = WorldStore(campaign_id="ctx_test")
    
    pc, _, _ = store.resolve_or_create(
        "Kael", "pc",
        {"hp": 12, "max_hp": 12, "disposition": "friendly",
         "voice_description": "young", "inventory": [], "stats": {}},
    )
    
    # Use a very small budget
    small_budget = TokenBudget(
        l0_system=50, l1_campaign_meta=50, l2_directory=50,
        l3_pinned=50, l4_working_set=50, l5_scene=50,
        l6_digest=50, l7_recent_turns=50, l8_rules=50, l9_input=50,
    )
    
    bundle = store.get_context_for_turn(
        player_input="I attack the goblin with my sword",
        system_prompt="You are a Dungeon Master running a solo campaign.",
        budget=small_budget,
    )
    
    # Each layer should be truncated
    assert len(bundle.stable_prefix) < 200  # rough check
    assert len(bundle.volatile_suffix) < 200
    
    print("PASS: token_budget_respected")


def test_dropped_entities_tracked():
    """Test that entities dropped due to budget are tracked."""
    store = WorldStore(campaign_id="ctx_test")
    
    pc, _, _ = store.resolve_or_create(
        "Kael", "pc",
        {"hp": 12, "max_hp": 12, "disposition": "friendly",
         "voice_description": "young", "inventory": [], "stats": {}},
    )
    
    # Create many NPCs to exceed budget
    for i in range(20):
        store.resolve_or_create(
            f"NPC_{i}", "npc",
            {"hp": 10, "max_hp": 10, "disposition": "neutral",
             "voice_description": "generic"},
        )
    
    # Use a tiny working set budget
    small_budget = TokenBudget(l4_working_set=100)
    
    bundle = store.get_context_for_turn(
        player_input="I look around",
        budget=small_budget,
    )
    
    # Some entities should be dropped
    assert len(bundle.dropped_entity_ids) > 0, "Should have dropped some entities"
    
    print(f"PASS: dropped_entities_tracked ({len(bundle.dropped_entity_ids)} dropped)")


def test_known_new_markers():
    """Test that entities are marked [KNOWN] or [NEW]."""
    store = WorldStore(campaign_id="ctx_test")
    
    pc, _, _ = store.resolve_or_create(
        "Kael", "pc",
        {"hp": 12, "max_hp": 12, "disposition": "friendly",
         "voice_description": "young", "inventory": [], "stats": {}},
    )
    
    # Create an NPC seen recently (should be KNOWN)
    npc1, _, _ = store.resolve_or_create(
        "Gorak", "npc",
        {"hp": 7, "max_hp": 7, "disposition": "hostile", "voice_description": "rough"},
        current_turn=1,
    )
    npc1.last_seen_turn = 1
    
    # Create an NPC seen long ago (should be NEW or dropped)
    npc2, _, _ = store.resolve_or_create(
        "Stranger", "npc",
        {"hp": 7, "max_hp": 7, "disposition": "neutral", "voice_description": "quiet"},
        current_turn=1,
    )
    npc2.last_seen_turn = -100  # very old
    
    store._turn_count = 5
    
    bundle = store.get_context_for_turn(
        player_input="I talk to Gorak",
    )
    
    # Check that context has KNOWN markers
    assert "[KNOWN]" in bundle.stable_prefix or "[KNOWN]" in bundle.volatile_suffix
    
    print("PASS: known_new_markers")


def test_cache_stability():
    """Test that stable prefix is byte-identical when content doesn't change."""
    store = WorldStore(campaign_id="ctx_test")
    
    pc, _, _ = store.resolve_or_create(
        "Kael", "pc",
        {"hp": 12, "max_hp": 12, "disposition": "friendly",
         "voice_description": "young", "inventory": [], "stats": {}},
    )
    loc, _, _ = store.resolve_or_create(
        "Tavern", "location",
        {"description": "A tavern", "discovered": True},
    )
    
    store.enter_scene(loc.id, current_turn=1)
    
    # Two calls with same stable content but different volatile content
    bundle1 = store.get_context_for_turn(
        player_input="I look around",
        system_prompt="You are a DM.",
    )
    bundle2 = store.get_context_for_turn(
        player_input="I attack the goblin!",
        system_prompt="You are a DM.",
    )
    
    # Stable prefix should be identical (same system prompt, same entities)
    assert bundle1.stable_prefix == bundle2.stable_prefix, \
        "Stable prefix should be byte-identical when content doesn't change"
    
    # Volatile suffix should differ (different player input)
    assert bundle1.volatile_suffix != bundle2.volatile_suffix
    
    print("PASS: cache_stability")


def main():
    print("\n" + "="*60)
    print("  V0.5A CONTEXT ASSEMBLER TESTS")
    print("="*60 + "\n")
    
    tests = [
        test_basic_context_assembly,
        test_stable_vs_volatile_split,
        test_scoring_pinned,
        test_scoring_named_in_input,
        test_scoring_recency_decay,
        test_token_budget_respected,
        test_dropped_entities_tracked,
        test_known_new_markers,
        test_cache_stability,
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
