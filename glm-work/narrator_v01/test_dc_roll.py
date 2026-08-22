#!/usr/bin/env python3
"""v0.4b DC-then-roll tests — verify seeded dice, two-call flow, roll ledger.

Run: python -m narrator_v01.test_dc_roll
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from narrator_v01.dm_engine import (
    parse_roll_request, resolve_roll, roll_dice, make_roll_seed, set_dice_seed,
)


def test_parse_roll_request_with_dc():
    """Test parsing ROLL_REQUEST with a DC."""
    req = parse_roll_request("ROLL_REQUEST:d20+5 for attack with longsword DC 12")
    assert req is not None
    assert req["dice"] == "d20+5"
    assert "attack" in req["skill"]
    assert req["dc"] == 12
    print("PASS: parse_roll_request_with_dc")


def test_parse_roll_request_without_dc():
    """Test parsing ROLL_REQUEST without a DC."""
    req = parse_roll_request("ROLL_REQUEST:d20 for perception")
    assert req is not None
    assert req["dice"] == "d20"
    assert req["skill"] == "perception"
    assert req["dc"] is None
    print("PASS: parse_roll_request_without_dc")


def test_parse_roll_request_none():
    """Test that no ROLL_REQUEST returns None."""
    req = parse_roll_request("HP_CHANGE:-5\nITEM_USED:Torch")
    assert req is None
    print("PASS: parse_roll_request_none")


def test_roll_dice_basic():
    """Test basic dice rolling."""
    set_dice_seed(42)
    roll = roll_dice("d20")
    assert 1 <= roll <= 20
    print(f"PASS: roll_dice_basic (roll={roll})")


def test_roll_dice_with_modifier():
    """Test dice rolling with modifier."""
    set_dice_seed(42)
    roll = roll_dice("d20+5")
    assert 6 <= roll <= 25
    print(f"PASS: roll_dice_with_modifier (roll={roll})")


def test_roll_dice_multiple():
    """Test rolling multiple dice."""
    set_dice_seed(42)
    roll = roll_dice("2d6")
    assert 2 <= roll <= 12
    print(f"PASS: roll_dice_multiple (roll={roll})")


def test_seeded_roll_reproducible():
    """Test that the same seed produces the same roll."""
    seed = make_roll_seed("campaign_123", turn=5)
    rng1 = __import__("random").Random(seed)
    rng2 = __import__("random").Random(seed)
    roll1 = rng1.randint(1, 20)
    roll2 = rng2.randint(1, 20)
    assert roll1 == roll2, f"Same seed should produce same roll: {roll1} != {roll2}"
    print(f"PASS: seeded_roll_reproducible (roll={roll1})")


def test_different_seeds_different_rolls():
    """Test that different seeds produce different rolls (usually)."""
    seed1 = make_roll_seed("campaign_123", turn=1)
    seed2 = make_roll_seed("campaign_123", turn=2)
    assert seed1 != seed2, "Different turns should have different seeds"
    print("PASS: different_seeds_different_rolls")


def test_make_roll_seed_deterministic():
    """Test that make_roll_seed is deterministic."""
    seed1 = make_roll_seed("my_campaign", 10)
    seed2 = make_roll_seed("my_campaign", 10)
    assert seed1 == seed2, "Same campaign+turn should produce same seed"
    print(f"PASS: make_roll_seed_deterministic (seed={seed1})")


def test_resolve_roll_success():
    """Test roll resolution with success."""
    req = {"dice": "d20+5", "skill": "attack", "dc": 15}
    # Use manual roll to control outcome
    result = resolve_roll(req, manual_roll=18)
    assert result["result"] == "SUCCESS"
    assert result["total"] == 18
    assert result["dc"] == 15
    assert result["margin"] == 3
    print(f"PASS: resolve_roll_success (total={result['total']}, margin={result['margin']})")


def test_resolve_roll_failure():
    """Test roll resolution with failure."""
    req = {"dice": "d20+5", "skill": "attack", "dc": 20}
    result = resolve_roll(req, manual_roll=12)
    assert result["result"] == "FAILURE"
    assert result["margin"] == -8
    print(f"PASS: resolve_roll_failure (total={result['total']}, margin={result['margin']})")


def test_resolve_roll_no_dc():
    """Test roll resolution without a DC."""
    req = {"dice": "d20", "skill": "perception", "dc": None}
    result = resolve_roll(req, manual_roll=15)
    assert result["result"] == "NO_DC"
    print("PASS: resolve_roll_no_dc")


def test_resolve_roll_with_seed():
    """Test that seeded roll is reproducible."""
    req = {"dice": "d20", "skill": "attack", "dc": 10}
    seed = make_roll_seed("test_campaign", 1)
    result1 = resolve_roll(req, seed=seed)
    result2 = resolve_roll(req, seed=seed)
    assert result1["total"] == result2["total"], "Same seed should produce same roll"
    print(f"PASS: resolve_roll_with_seed (total={result1['total']})")


def test_resolve_roll_modifier_parsed():
    """Test that modifier is parsed from dice spec."""
    req = {"dice": "d20+5", "skill": "attack", "dc": 15}
    result = resolve_roll(req, manual_roll=20)
    # manual_roll is the total (including modifier)
    assert result["modifier"] == 5
    assert result["total"] == 20
    assert result["roll"] == 15  # raw roll = total - modifier
    print(f"PASS: resolve_roll_modifier_parsed (modifier={result['modifier']}, raw={result['roll']})")


def test_roll_seed_different_campaigns():
    """Test that different campaigns produce different seeds."""
    seed1 = make_roll_seed("campaign_A", 1)
    seed2 = make_roll_seed("campaign_B", 1)
    assert seed1 != seed2, "Different campaigns should have different seeds"
    print("PASS: roll_seed_different_campaigns")


def main():
    print("\n" + "="*60)
    print("  V0.4B DC-THEN-ROLL TESTS")
    print("="*60 + "\n")

    tests = [
        test_parse_roll_request_with_dc,
        test_parse_roll_request_without_dc,
        test_parse_roll_request_none,
        test_roll_dice_basic,
        test_roll_dice_with_modifier,
        test_roll_dice_multiple,
        test_seeded_roll_reproducible,
        test_different_seeds_different_rolls,
        test_make_roll_seed_deterministic,
        test_resolve_roll_success,
        test_resolve_roll_failure,
        test_resolve_roll_no_dc,
        test_resolve_roll_with_seed,
        test_resolve_roll_modifier_parsed,
        test_roll_seed_different_campaigns,
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
