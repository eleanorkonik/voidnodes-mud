#!/usr/bin/env python3
"""Test the invoke system in combat — exercises all effects + edge cases."""

import sys
import io

from models.character import Character
from models.room import Room
from models.world_seed import WorldSeed
from models.skerry import Skerry
from engine import aspects

# ── Build a minimal Game object without loading save files ──────────

CHAR_DATA = {
    "name": "Sevarik",
    "aspects": {
        "high_concept": "Fae-Lands Warrior Stranded in the Void",
        "trouble": "Honor-Bound to Protect Everyone",
        "other": ["Battle-Scarred Veteran", "Reluctant Leader"],
    },
    "skills": {"Fight": 4, "Navigate": 3, "Endure": 3, "Notice": 2},
    "stress": [False, False, False],
    "consequences": {"mild": None, "moderate": None, "severe": None},
    "fate_points": 5,
    "refresh": 3,
    "inventory": ["lantern"],
    "worn": {},
}

ENEMY_DATA = {
    "id": "void_lurker",
    "name": "Void Lurker",
    "aspects": ["Eyeless and Hunting by Sound", "One Wrong Move Draws Blood"],
    "skills": {"Fight": 2, "Notice": 3},
    "stress": [False, False],
    "consequences": {"mild": None},
    "aggressive": True,
    "loot": [],
}

ROOM_DATA = {
    "id": "test_room",
    "name": "Debris Chamber",
    "description": "A dark room.",
    "zone": "debris_field",
    "exits": {},
    "aspects": ["Unstable Footing"],
    "items": [],
    "npcs": [],
    "enemies": ["void_lurker"],
}

SEED_DATA = {
    "motes": 50,
    "growth_stage": 1,
    "aspects": ["Baby Seed With Perfect Memory", "Hungry for Motes"],
}

SKERRY_DATA = {
    "rooms": [{
        "id": "skerry_central",
        "name": "Central Clearing",
        "description": "The heart of the skerry.",
        "zone": "skerry",
        "aspects": ["The Ground Hums With Something Alive"],
    }],
}

NPC_EMMY = {
    "name": "Emmy",
    "recruited": True,
    "following": True,
    "location": "test_room",
    "aspects": {
        "high_concept": "Enthusiastic Scavenger With an Eye for Value",
        "trouble": "Too Trusting for the Void",
        "other": ["Quick Hands, Quicker Smile"],
    },
}


def _fresh_char_data():
    """Deep-enough copy of CHAR_DATA so tests don't mutate the template."""
    import copy
    return copy.deepcopy(CHAR_DATA)


class FakeGame:
    """Minimal Game-like object for testing invoke/compel logic."""
    def __init__(self):
        self.explorer = Character(_fresh_char_data())
        self.state = {
            "current_phase": "explorer",
            "explorer_location": "test_room",
            "world_seed_name": "Tuft",
        }
        self.seed = WorldSeed(SEED_DATA)
        self.enemies_db = {"void_lurker": dict(ENEMY_DATA)}
        self.npcs_db = {"emmy": dict(NPC_EMMY)}
        self.items_db = {
            "lantern": {"name": "Lantern", "aspects": ["A Light That Won't Go Out"]},
        }
        self.artifacts_db = {}
        self.rooms = {
            "test_room": Room(ROOM_DATA),
            "skerry_central": Room(SKERRY_DATA["rooms"][0]),
        }
        self.in_combat = True
        self.combat_target = "void_lurker"
        self.invoked_aspects = set()
        self.free_invocations = {}
        self.combat_boost = 0
        self.defending = False
        self.enemy_compel_boost = 0
        self.compel_triggered = False
        self.recruit_state = None

    @property
    def seed_name(self):
        return self.state.get("world_seed_name", "Tuft")

    def current_character(self):
        return self.explorer

    def current_room(self):
        loc = self.state.get("explorer_location", "test_room")
        return self.rooms.get(loc)


# ── Tests ────────────────────────────────────────────────────────────

def test_collect_aspects():
    """Test that collect_invokable_aspects gathers from all sources."""
    game = FakeGame()
    result = aspects.collect_invokable_aspects(game, context="combat")
    aspect_texts = [a for a, s in result]
    sources = {a: s for a, s in result}

    print("=== Test: collect_invokable_aspects (combat) ===")

    # Character aspects
    assert "Fae-Lands Warrior Stranded in the Void" in aspect_texts, "Missing high_concept"
    assert "Honor-Bound to Protect Everyone" in aspect_texts, "Missing trouble"
    assert "Battle-Scarred Veteran" in aspect_texts, "Missing other aspect"
    assert sources["Battle-Scarred Veteran"] == "yours", f"Wrong source: {sources['Battle-Scarred Veteran']}"

    # Room aspects
    assert "Unstable Footing" in aspect_texts, "Missing room aspect"
    assert sources["Unstable Footing"] == "room", f"Wrong source: {sources['Unstable Footing']}"

    # Enemy aspects
    assert "Eyeless and Hunting by Sound" in aspect_texts, "Missing enemy aspect"
    assert sources["Eyeless and Hunting by Sound"] == "enemy", f"Wrong source"

    # Follower aspects (Emmy is following at test_room)
    assert "Enthusiastic Scavenger With an Eye for Value" in aspect_texts, "Missing follower high_concept"
    assert sources["Enthusiastic Scavenger With an Eye for Value"] == "Emmy", f"Wrong source"
    assert "Too Trusting for the Void" in aspect_texts, "Missing follower trouble"
    assert "Quick Hands, Quicker Smile" in aspect_texts, "Missing follower other"

    # World seed aspects
    assert "Baby Seed With Perfect Memory" in aspect_texts, "Missing seed aspect"
    assert sources["Baby Seed With Perfect Memory"] == "Tuft", f"Wrong source"

    # Item aspects
    assert "A Light That Won't Go Out" in aspect_texts, "Missing item aspect"
    assert sources["A Light That Won't Go Out"] == "Lantern", f"Wrong source"

    # Zone aspects should NOT be present
    assert "The Ground Hums With Something Alive" not in aspect_texts, "Zone aspect should be excluded"

    print(f"  Found {len(result)} aspects from {len(set(s for _, s in result))} sources")
    for a, s in result:
        print(f"    {a} ({s})")
    print("  PASS\n")


def test_flatten_npc_aspects():
    """Test NPC aspect dict flattening."""
    print("=== Test: _flatten_npc_aspects ===")
    flat = aspects._flatten_npc_aspects(NPC_EMMY)
    assert flat == [
        "Enthusiastic Scavenger With an Eye for Value",
        "Too Trusting for the Void",
        "Quick Hands, Quicker Smile",
    ], f"Got: {flat}"
    print(f"  Flattened {len(flat)} aspects")
    print("  PASS\n")


def test_invoke_once_per_aspect():
    """Test that each aspect can only be invoked once."""
    print("=== Test: once-per-aspect tracking ===")
    game = FakeGame()

    game.invoked_aspects.add("Battle-Scarred Veteran")

    all_aspects = aspects.collect_invokable_aspects(game, context="combat")
    available = [(a, s) for a, s in all_aspects if a not in game.invoked_aspects]
    spent = [(a, s) for a, s in all_aspects if a in game.invoked_aspects]

    assert any(a == "Battle-Scarred Veteran" for a, _ in spent), "Veteran should be spent"
    assert not any(a == "Battle-Scarred Veteran" for a, _ in available), "Veteran should not be available"
    assert any(a == "Reluctant Leader" for a, _ in available), "Leader should still be available"

    print(f"  Available: {len(available)}, Spent: {len(spent)}")
    print("  PASS\n")


def test_effect_constants():
    """Test effect constant dicts exist and have required fields."""
    print("=== Test: effect constants ===")
    for key, info in aspects.COMBAT_EFFECTS.items():
        assert "label" in info, f"Missing label for {key}"
        assert "desc" in info, f"Missing desc for {key}"
        print(f"  Combat: {key} → {info['label']}")

    for key, info in aspects.RECRUIT_EFFECTS.items():
        assert "label" in info, f"Missing label for {key}"
        assert "desc" in info, f"Missing desc for {key}"
        print(f"  Recruit: {key} → {info['label']}")
    print("  PASS\n")


def test_compel_check_with_follower():
    """Test compel triggers for Honor-Bound when follower is present."""
    print("=== Test: compel check (follower present) ===")
    game = FakeGame()

    compel = aspects.check_compel(game)
    assert compel is not None, "Compel should trigger for Honor-Bound with follower"
    assert compel["aspect"] == "Honor-Bound to Protect Everyone", f"Wrong aspect: {compel['aspect']}"
    assert "Emmy" in compel["text"], f"Should mention Emmy: {compel['text']}"
    assert compel["accept_effect"] == "take_stress", f"Wrong effect: {compel['accept_effect']}"
    assert compel["stress"] == 1

    print(f"  Aspect: {compel['aspect']}")
    print(f"  Text: {compel['text']}")
    print(f"  Effect: {compel['accept_effect']} (stress={compel['stress']})")
    print("  PASS\n")


def test_compel_check_no_follower():
    """Test compel falls back when follower_present condition fails."""
    print("=== Test: compel check (no follower — fallback) ===")
    game = FakeGame()
    # Remove follower
    game.npcs_db["emmy"]["following"] = False

    compel = aspects.check_compel(game)
    # Should fall back to "Reluctant Leader" which is in Sevarik's "other" aspects
    assert compel is not None, "Should fall back to Reluctant Leader"
    assert compel["aspect"] == "Reluctant Leader", f"Wrong fallback: {compel['aspect']}"
    assert compel["accept_effect"] == "lose_turn"

    print(f"  Fell back to: {compel['aspect']}")
    print(f"  Effect: {compel['accept_effect']}")
    print("  PASS\n")


def test_compel_accept():
    """Test accepting a compel."""
    print("=== Test: compel accept ===")
    game = FakeGame()
    game.explorer.fate_points = 2

    compel = aspects.check_compel(game)
    messages = aspects.resolve_compel_accept(game, compel)

    assert game.explorer.fate_points == 3, f"FP should be 3, got {game.explorer.fate_points}"
    assert any("stress" in m.lower() for m in messages), f"Should mention stress: {messages}"
    assert any("3" in m for m in messages), f"Should show new FP count: {messages}"

    print(f"  FP: 2 → {game.explorer.fate_points}")
    print(f"  Messages: {messages}")
    print(f"  Stress taken: {game.explorer.stress}")
    print("  PASS\n")


def test_compel_refuse():
    """Test refusing a compel."""
    print("=== Test: compel refuse ===")
    game = FakeGame()
    game.explorer.fate_points = 2

    compel = aspects.check_compel(game)
    messages = aspects.resolve_compel_refuse(game, compel)

    assert game.explorer.fate_points == 1, f"FP should be 1, got {game.explorer.fate_points}"
    assert any("1" in m for m in messages), f"Should show new FP count: {messages}"

    print(f"  FP: 2 → {game.explorer.fate_points}")
    print(f"  Messages: {messages}")
    print("  PASS\n")


def test_compel_enemy_boost():
    """Test enemy_boost compel effect."""
    print("=== Test: compel enemy_boost effect ===")
    game = FakeGame()
    game.explorer.fate_points = 2
    # Use a character with enemy_boost compel
    game.explorer.aspects["trouble"] = "Won't Move Without Proof"

    compel = aspects.check_compel(game)
    assert compel is not None, "Should trigger for Won't Move Without Proof"
    assert compel["accept_effect"] == "enemy_boost"

    messages = aspects.resolve_compel_accept(game, compel)
    assert game.enemy_compel_boost == 2, f"Enemy boost should be 2, got {game.enemy_compel_boost}"
    assert game.explorer.fate_points == 3

    print(f"  Enemy boost: {game.enemy_compel_boost}")
    print(f"  FP: 2 → {game.explorer.fate_points}")
    print("  PASS\n")


def test_all_compel_troubles():
    """Test that every trouble aspect in COMPELS dict produces a valid compel."""
    print("=== Test: all compel troubles ===")
    for trouble, data in aspects.COMPELS.items():
        game = FakeGame()
        game.explorer.aspects["trouble"] = trouble
        game.explorer.aspects["other"] = []  # clear fallbacks

        if data["condition"] == "follower_present":
            # Ensure follower present
            game.npcs_db["emmy"]["following"] = True
            game.npcs_db["emmy"]["location"] = "test_room"

        compel = aspects.check_compel(game)
        if data["condition"] == "always" or data["condition"] == "follower_present":
            assert compel is not None, f"Compel should trigger for '{trouble}'"
            assert compel["accept_effect"] in ("take_stress", "lose_turn", "enemy_boost"), \
                f"Invalid effect for '{trouble}': {compel['accept_effect']}"
            print(f"  {trouble}: {compel['accept_effect']} ✓")

    print("  PASS\n")


def test_recruit_collect_aspects():
    """Test aspect collection in recruit context."""
    print("=== Test: collect_invokable_aspects (recruit) ===")
    game = FakeGame()
    game.in_combat = False
    game.combat_target = None
    game.recruit_state = {
        "npc_data": NPC_EMMY,
        "invoked_aspects": set(),
    }

    result = aspects.collect_invokable_aspects(game, context="recruit")
    aspect_texts = [a for a, s in result]

    # Should have character aspects
    assert "Battle-Scarred Veteran" in aspect_texts
    # Should have NPC target aspects (not enemy)
    assert "Enthusiastic Scavenger With an Eye for Value" in aspect_texts
    # Should NOT have enemy aspects
    assert "Eyeless and Hunting by Sound" not in aspect_texts

    print(f"  Found {len(result)} aspects for recruitment")
    for a, s in result:
        print(f"    {a} ({s})")
    print("  PASS\n")


if __name__ == "__main__":
    test_collect_aspects()
    test_flatten_npc_aspects()
    test_invoke_once_per_aspect()
    test_effect_constants()
    test_compel_check_with_follower()
    test_compel_check_no_follower()
    test_compel_accept()
    test_compel_refuse()
    test_compel_enemy_boost()
    test_all_compel_troubles()
    test_recruit_collect_aspects()
    print("=" * 50)
    print("ALL TESTS PASSED")
