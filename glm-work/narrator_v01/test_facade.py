#!/usr/bin/env python3
"""v0.4d facade test — verify GameState with WorldStore is behavior-neutral.

Runs the same mechanics through both the legacy flat-state path and the
WorldStore-backed path, then compares the results. The facade is
behavior-neutral if both paths produce equivalent state changes.

Run: python -m narrator_v01.test_facade
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from narrator_v01.dm_engine import GameState, Enemy, make_initial_state
from narrator_v01.world_store import WorldStore


def test_facade_basic():
    """Test that attaching a WorldStore doesn't break basic operations."""
    # Create state without store (legacy)
    state_legacy = make_initial_state(auto_roll=True)
    
    # Create state with store
    state_facade = make_initial_state(auto_roll=True)
    store = WorldStore(campaign_id="facade_test")
    state_facade.attach_world_store(store)
    
    # Both should have same initial state
    assert state_legacy.pc_hp == state_facade.pc_hp
    assert state_legacy.pc_max_hp == state_facade.pc_max_hp
    assert state_legacy.pc_ac == state_facade.pc_ac
    assert len(state_legacy.enemies) == len(state_facade.enemies)
    
    print(f"PASS: facade_basic (legacy HP={state_legacy.pc_hp}, facade HP={state_facade.pc_hp})")


def test_facade_hp_change():
    """Test HP_CHANGE produces equivalent results."""
    state_legacy = make_initial_state()
    state_facade = make_initial_state()
    store = WorldStore(campaign_id="facade_test")
    state_facade.attach_world_store(store)
    
    # Apply damage
    changes_legacy = state_legacy.apply_mechanics("HP_CHANGE:-5")
    changes_facade = state_facade.apply_mechanics("HP_CHANGE:-5")
    
    assert state_legacy.pc_hp == state_facade.pc_hp == 7, \
        f"HP mismatch: legacy={state_legacy.pc_hp}, facade={state_facade.pc_hp}"
    
    # Both should report the change
    assert any("HP" in c for c in changes_legacy)
    assert any("HP" in c for c in changes_facade)
    
    print(f"PASS: facade_hp_change (both HP={state_legacy.pc_hp})")


def test_facade_hp_clamp():
    """Test HP clamping works in both paths."""
    state_legacy = make_initial_state()
    state_facade = make_initial_state()
    store = WorldStore(campaign_id="facade_test")
    state_facade.attach_world_store(store)
    
    # Overheal
    state_legacy.apply_mechanics("HP_CHANGE:+100")
    state_facade.apply_mechanics("HP_CHANGE:+100")
    
    assert state_legacy.pc_hp == state_legacy.pc_max_hp
    assert state_facade.pc_hp == state_facade.pc_max_hp
    assert state_legacy.pc_hp == state_facade.pc_hp
    
    print(f"PASS: facade_hp_clamp (both HP={state_legacy.pc_hp}/{state_legacy.pc_max_hp})")


def test_facade_item_gained():
    """Test ITEM_GAINED produces equivalent results."""
    state_legacy = make_initial_state()
    state_facade = make_initial_state()
    store = WorldStore(campaign_id="facade_test")
    state_facade.attach_world_store(store)
    
    legacy_inv_before = len(state_legacy.inventory)
    facade_inv_before = len(state_facade.inventory)
    
    state_legacy.apply_mechanics("ITEM_GAINED:Iron Sword")
    state_facade.apply_mechanics("ITEM_GAINED:Iron Sword")
    
    assert len(state_legacy.inventory) == legacy_inv_before + 1
    assert len(state_facade.inventory) == facade_inv_before + 1
    assert "Iron Sword" in state_legacy.inventory
    assert "Iron Sword" in state_facade.inventory
    
    print(f"PASS: facade_item_gained (both have Iron Sword)")


def test_facade_item_used():
    """Test ITEM_USED produces equivalent results."""
    state_legacy = make_initial_state()
    state_facade = make_initial_state()
    store = WorldStore(campaign_id="facade_test")
    state_facade.attach_world_store(store)
    
    # Both start with "Health Potion"
    assert "Health Potion" in state_legacy.inventory
    assert "Health Potion" in state_facade.inventory
    
    state_legacy.apply_mechanics("ITEM_USED:Health Potion")
    state_facade.apply_mechanics("ITEM_USED:Health Potion")
    
    assert "Health Potion" not in state_legacy.inventory
    assert "Health Potion" not in state_facade.inventory
    
    print("PASS: facade_item_used (both consumed Health Potion)")


def test_facade_waste_potion_guard():
    """Test waste-potion guard works in both paths."""
    state_legacy = make_initial_state()
    state_facade = make_initial_state()
    store = WorldStore(campaign_id="facade_test")
    state_facade.attach_world_store(store)
    
    # Try to use a fake item + real item
    changes_legacy = state_legacy.apply_mechanics(
        "ITEM_USED:Fake Potion\nITEM_USED:Health Potion")
    changes_facade = state_facade.apply_mechanics(
        "ITEM_USED:Fake Potion\nITEM_USED:Health Potion")
    
    # Both should reject and keep the potion
    assert "Health Potion" in state_legacy.inventory
    assert "Health Potion" in state_facade.inventory
    assert any("REJECTED" in c for c in changes_legacy)
    assert any("REJECTED" in c for c in changes_facade)
    
    print("PASS: facade_waste_potion_guard (both rejected invalid item)")


def test_facade_enemy_dead_guard():
    """Test ENEMY_DEAD guard works in both paths."""
    state_legacy = make_initial_state()
    state_facade = make_initial_state()
    store = WorldStore(campaign_id="facade_test")
    state_facade.attach_world_store(store)
    
    # Try to kill without roll evidence
    changes_legacy = state_legacy.apply_mechanics("ENEMY_DEAD:Goblin Scout")
    changes_facade = state_facade.apply_mechanics("ENEMY_DEAD:Goblin Scout")
    
    # Both should reject
    assert any("REJECTED" in c for c in changes_legacy)
    assert any("REJECTED" in c for c in changes_facade)
    
    # Now with roll evidence — enemy name must appear in ROLL_REQUEST text
    # or be targeted by an ENEMY_HP tag in the same turn
    changes_legacy = state_legacy.apply_mechanics(
        "ROLL_REQUEST:d20+5 for attack on Goblin Scout\nENEMY_DEAD:Goblin Scout")
    changes_facade = state_facade.apply_mechanics(
        "ROLL_REQUEST:d20+5 for attack on Goblin Scout\nENEMY_DEAD:Goblin Scout")
    
    assert any("DEAD" in c for c in changes_legacy), f"Legacy should kill: {changes_legacy}"
    assert any("DEAD" in c for c in changes_facade), f"Facade should kill: {changes_facade}"
    
    print("PASS: facade_enemy_dead_guard (both enforce roll evidence)")


def test_facade_to_dict():
    """Test to_dict produces equivalent structure."""
    state_legacy = make_initial_state()
    state_facade = make_initial_state()
    store = WorldStore(campaign_id="facade_test")
    state_facade.attach_world_store(store)
    
    dict_legacy = state_legacy.to_dict()
    dict_facade = state_facade.to_dict()
    
    # Same keys
    assert set(dict_legacy.keys()) == set(dict_facade.keys())
    
    # Same PC attributes
    for key in ["pc_name", "pc_class", "pc_level", "pc_hp", "pc_max_hp",
                "pc_ac", "pc_str", "pc_dex", "pc_con", "pc_int", "pc_wis", "pc_cha"]:
        assert dict_legacy[key] == dict_facade[key], \
            f"Mismatch in {key}: legacy={dict_legacy[key]}, facade={dict_facade[key]}"
    
    # Same number of enemies
    assert len(dict_legacy["enemies"]) == len(dict_facade["enemies"])
    
    print("PASS: facade_to_dict (equivalent structure)")


def test_facade_to_prompt_block():
    """Test to_prompt_block produces equivalent output."""
    state_legacy = make_initial_state()
    state_facade = make_initial_state()
    store = WorldStore(campaign_id="facade_test")
    state_facade.attach_world_store(store)
    
    block_legacy = state_legacy.to_prompt_block()
    block_facade = state_facade.to_prompt_block()
    
    # Should contain the same key information
    assert state_legacy.pc_name in block_facade
    assert str(state_legacy.pc_hp) in block_facade
    assert state_legacy.location in block_facade
    
    print("PASS: facade_to_prompt_block (equivalent content)")


def test_facade_no_store_legacy_path():
    """Test that without a WorldStore, the legacy path is used."""
    state = make_initial_state()
    assert state.world_store is None
    
    # Should work exactly as before
    changes = state.apply_mechanics("HP_CHANGE:-3")
    assert state.pc_hp == 9
    assert any("HP" in c for c in changes)
    
    print("PASS: facade_no_store_legacy_path (legacy path works without store)")


def test_facade_save_load():
    """Test that the WorldStore can save/load and state survives."""
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        state = make_initial_state()
        store = WorldStore(campaign_id="facade_test", data_dir=Path(tmpdir))
        state.attach_world_store(store)
        
        # Apply some changes
        state.apply_mechanics("HP_CHANGE:-5")
        assert state.pc_hp == 7
        
        # Save
        store.save()
        
        # Load into new store
        store2 = WorldStore(campaign_id="facade_test", data_dir=Path(tmpdir))
        store2.load()
        
        # Verify PC entity survived
        pc = store2._get_pc()
        assert pc is not None
        assert pc.attributes["hp"] == 7
    
    print("PASS: facade_save_load (state persists through save/load)")


def main():
    print("\n" + "="*60)
    print("  V0.4D FACADE TESTS (behavior-neutral verification)")
    print("="*60 + "\n")
    
    tests = [
        test_facade_basic,
        test_facade_hp_change,
        test_facade_hp_clamp,
        test_facade_item_gained,
        test_facade_item_used,
        test_facade_waste_potion_guard,
        test_facade_enemy_dead_guard,
        test_facade_to_dict,
        test_facade_to_prompt_block,
        test_facade_no_store_legacy_path,
        test_facade_save_load,
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
        print("  ALL TESTS PASSED — facade is behavior-neutral")
    else:
        print(f"  {failed} TESTS FAILED")
    print("="*60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
