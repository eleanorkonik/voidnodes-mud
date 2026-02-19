"""Aspect system — collection, invocation effects, and compels.

Centralizes aspect gathering from all sources (character, room, enemy, NPC,
followers, world seed, items, artifacts) and provides the compel mechanic
for trouble aspects.
"""

import random

from engine import display


# ── Effect constants ─────────────────────────────────────────────────

COMBAT_EFFECTS = {
    "ATTACK": {
        "label": "+2 Attack",
        "desc": "+2 attack",
    },
    "DEFEND": {
        "label": "+2 Defense",
        "desc": "+2 defense",
    },
    "SETUP": {
        "label": "Free Invoke",
        "desc": "free invoke on enemy aspect",
    },
}

RECRUIT_EFFECTS = {
    "PUSH": {
        "label": "Threshold -4",
        "desc": "threshold -4",
    },
    "COUNTER": {
        "label": "Counter Reset",
        "desc": "reset lowest counter",
    },
    "RESTORE": {
        "label": "Restore 3 Tiles",
        "desc": "un-eliminate 3 tiles",
    },
}

# Flavor text for invoking aspects during recruitment, keyed by source label.
# Falls back to "generic" if source not matched.
# {aspect} = aspect text, {source} = source name, {npc} = NPC being recruited
RECRUIT_INVOKE_FLAVOR = {
    "yours": [
        "You let it show — the part of you that's {aspect}. {npc} sees it and goes quiet.",
        "Your voice changes when you talk about being {aspect}. {npc} notices.",
        "You stop performing and let {aspect} speak for itself. {npc} listens differently after that.",
    ],
    "room": [
        "You point at the world around you. {aspect} — and {npc} can see it with their own eyes.",
        "You don't have to argue this one. {aspect} is right here. {npc} looks around and gets it.",
    ],
    "seed": [
        "You invoke {source}'s nature — {aspect} — and {source} obliges, showing off for {npc}.",
        "{source} pulses with warmth on cue. {aspect}. {npc} stares.",
        "You call on {source}, and the little seed rises to the occasion. {npc} watches, fascinated.",
    ],
    "npc": [
        "You turn {npc}'s own words back on them — {aspect}. They can't argue with themselves.",
        "You point out that {npc} is {aspect}. They pause, caught off guard by their own truth.",
    ],
    "generic": [
        "You invoke {source}'s {aspect}. {npc} hadn't considered that angle.",
        "You bring up {aspect} — {source}. {npc} goes quiet, thinking it over.",
        "{source}. {aspect}. You let it hang in the air and {npc} does the rest.",
    ],
}


def get_recruit_invoke_flavor(aspect, source, npc_name, source_type=None):
    """Pick a flavor line for a recruitment invoke.

    source_type: overrides the pool lookup. Auto-detected for NPC sources.
    """
    key = source_type or source
    # NPC target's own aspects
    if key == npc_name:
        key = "npc"
    pool = RECRUIT_INVOKE_FLAVOR.get(key, RECRUIT_INVOKE_FLAVOR["generic"])
    line = random.choice(pool)
    return line.format(aspect=aspect, source=source, npc=npc_name)


# ── Aspect gathering ─────────────────────────────────────────────────


def _flatten_npc_aspects(npc_data):
    """Flatten an NPC's aspect dict {high_concept, trouble, other} into a list."""
    aspects_field = npc_data.get("aspects", [])
    if isinstance(aspects_field, dict):
        flat = []
        if aspects_field.get("high_concept"):
            flat.append(aspects_field["high_concept"])
        if aspects_field.get("trouble"):
            flat.append(aspects_field["trouble"])
        flat.extend(aspects_field.get("other", []))
        return flat
    # Already a list (shouldn't happen with current data, but safe)
    return list(aspects_field)


def collect_invokable_aspects(game, context="combat"):
    """Gather all invokable aspects with source labels.

    Args:
        game: Game instance
        context: "combat" or "recruit"

    Returns:
        List of (aspect_text, source_label) tuples.
        Zone aspects are excluded (always present, too broad).
    """
    aspects = []
    char = game.current_character()

    # Character aspects (high_concept, trouble, other, consequences)
    for a in char.get_all_aspects():
        aspects.append((a, "yours"))

    # Room aspects
    room = game.current_room()
    if room:
        for a in room.aspects:
            aspects.append((a, "room"))

    # Context-specific sources
    if context == "combat":
        # Enemy aspects
        if game.combat_target:
            enemy = game.enemies_db.get(game.combat_target, {})
            for a in enemy.get("aspects", []):
                aspects.append((a, "enemy"))

        # Following NPC aspects (recruited NPCs at same location)
        explorer_loc = game.state.get("explorer_location")
        for npc_id, npc in game.npcs_db.items():
            if npc.get("following") and npc.get("location") == explorer_loc:
                for a in _flatten_npc_aspects(npc):
                    aspects.append((a, npc.get("name", npc_id)))

    elif context == "recruit":
        # NPC target aspects
        if game.recruit_state:
            npc_data = game.recruit_state.get("npc_data", {})
            for a in _flatten_npc_aspects(npc_data):
                aspects.append((a, npc_data.get("name", "NPC")))

    # World seed aspects
    if game.seed:
        for a in game.seed.aspects:
            aspects.append((a, game.seed_name))

    # Inventory item aspects
    for item_id in char.inventory:
        item = game.items_db.get(item_id, {})
        for a in item.get("aspects", []):
            aspects.append((a, item.get("name", item_id)))

    # Kept artifact aspects
    kept = game.state.get("kept_artifact")
    if kept:
        artifact = game.artifacts_db.get(kept, {})
        for a in artifact.get("aspects", []):
            aspects.append((a, artifact.get("name", kept)))

    return aspects


# ── Compel data ──────────────────────────────────────────────────────

COMPELS = {
    "Honor-Bound to Protect Everyone": {
        "condition": "follower_present",
        "text": "{follower} is in the crossfire. You feel compelled to shield them.",
        "accept_effect": "take_stress",
        "accept_text": "You throw yourself between {follower} and danger. The blow catches your shoulder instead.",
        "stress": 1,
    },
    "Reluctant Leader": {
        "condition": "always",
        "text": "The weight of command hits you. Do you really have the right to risk this?",
        "accept_effect": "lose_turn",
        "accept_text": "You hesitate, second-guessing yourself. The moment passes before you can act.",
    },
    "Secrets That Could Help or Harm": {
        "condition": "always",
        "text": "You know something that could help — but revealing it would expose your secrets.",
        "accept_effect": "enemy_boost",
        "accept_text": "You hold back what you know. The enemy reads your indecision and presses hard.",
    },
    "Too Trusting for the Void": {
        "condition": "always",
        "text": "You lower your guard for just a moment — old habits.",
        "accept_effect": "take_stress",
        "accept_text": "Your guard drops and something gets through. You stagger, clutching your side.",
        "stress": 1,
    },
    "Jumps at Every Shadow": {
        "condition": "always",
        "text": "A flicker of movement in the corner of your eye. Your nerve wavers.",
        "accept_effect": "lose_turn",
        "accept_text": "You flinch hard, spinning toward nothing. By the time you recover, the moment's gone.",
    },
    "Trust Issues (Well-Founded)": {
        "condition": "follower_present",
        "text": "You glance at {follower}. Can you really count on them?",
        "accept_effect": "lose_turn",
        "accept_text": "You split your attention between the enemy and {follower}. Neither gets your best.",
    },
    "Won't Move Without Proof": {
        "condition": "always",
        "text": "You're not sure this fight is worth it. Where's the evidence you should be here?",
        "accept_effect": "enemy_boost",
        "accept_text": "You pull back, unconvinced. The enemy doesn't share your reservations.",
    },
    "Knowledge Above Self-Preservation": {
        "condition": "always",
        "text": "You notice something fascinating about the enemy's anatomy. Mid-fight.",
        "accept_effect": "take_stress",
        "accept_text": "You lean in for a closer look. It costs you — claws rake across your arm. Worth it, probably.",
        "stress": 1,
    },
    "Respects Only Strength": {
        "condition": "always",
        "text": "This enemy is weak. Beneath you. You lower your guard in contempt.",
        "accept_effect": "enemy_boost",
        "accept_text": "You practically yawn at them. They take the opening you handed them.",
    },
    "Patient Observer": {
        "condition": "always",
        "text": "You pause to study your opponent's pattern. Fascinating, but...",
        "accept_effect": "lose_turn",
        "accept_text": "You watch instead of act, cataloguing every movement. Thorough, but not timely.",
    },
}


def _get_follower_name(game):
    """Get the name of a follower at the explorer's current location, or None."""
    explorer_loc = game.state.get("explorer_location")
    for npc_id, npc in game.npcs_db.items():
        if npc.get("following") and npc.get("location") == explorer_loc:
            return npc.get("name", npc_id)
    return None


def check_compel(game):
    """Check if a compel should trigger. Returns compel data dict or None.

    Checks the active character's trouble aspect against COMPELS dict.
    Only triggers if conditions are met.
    """
    char = game.current_character()
    trouble = char.aspects.get("trouble")
    if not trouble:
        return None

    # Try the trouble aspect first
    compel = COMPELS.get(trouble)
    if not compel:
        return None

    # Check condition
    if compel["condition"] == "follower_present":
        follower = _get_follower_name(game)
        if not follower:
            # Try other character aspects for a fallback compel
            for other_aspect in char.aspects.get("other", []):
                alt = COMPELS.get(other_aspect)
                if alt and alt["condition"] == "always":
                    compel = alt
                    trouble = other_aspect
                    break
            else:
                return None

    # Build the compel data with filled-in template
    follower = _get_follower_name(game)
    follower_name = follower or "your ally"

    return {
        "aspect": trouble,
        "text": compel["text"].format(follower=follower_name),
        "accept_effect": compel["accept_effect"],
        "accept_text": compel["accept_text"].format(follower=follower_name),
        "stress": compel.get("stress", 0),
    }


def resolve_compel_accept(game, compel):
    """Apply the accept effect of a compel. Returns message strings."""
    char = game.current_character()
    char.gain_fate_point()
    messages = []

    messages.append(compel["accept_text"])

    effect = compel["accept_effect"]
    if effect == "take_stress":
        stress_amount = compel.get("stress", 1)
        taken_out = char.apply_damage(stress_amount)
        stress_str = "".join("[X]" if s else "[ ]" for s in char.stress)
        messages.append(f"  ({stress_amount} stress — {stress_str})")
        if taken_out:
            messages.append("TAKEN_OUT")
    elif effect == "lose_turn":
        pass  # accept_text covers the narrative; enemy free attack handled by caller
    elif effect == "enemy_boost":
        game.enemy_compel_boost = 2

    messages.append(f"  (+1 Fate Point — you now have {char.fate_points})")
    return messages


def resolve_compel_refuse(game, compel):
    """Spend FP to refuse a compel. Returns message strings."""
    char = game.current_character()
    char.spend_fate_point()
    return [
        "You push through, refusing to let it get to you.",
        f"  (-1 Fate Point — you now have {char.fate_points})",
    ]
