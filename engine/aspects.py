"""Aspect system — collection, invocation effects, and compels.

Centralizes aspect gathering from all sources (character, room, enemy, NPC,
followers, world seed, items, artifacts) and provides the compel mechanic
for trouble aspects.
"""

import random

from engine import display


# ── Aspect normalization & affinity ──────────────────────────────────


def normalize_aspect(raw):
    """Normalize an aspect entry to (text, affinity_list).

    Aspects can be a bare string (universal) or a dict with affinity:
      "Battle-Scarred Veteran"  →  ("Battle-Scarred Veteran", [])
      {"text": "Battle-Scarred Veteran", "affinity": ["Fight", "Physique"]}
        →  ("Battle-Scarred Veteran", ["Fight", "Physique"])
    """
    if isinstance(raw, dict):
        return raw.get("text", ""), raw.get("affinity", [])
    return str(raw), []


def calc_invoke_bonus(affinity, skill):
    """Calculate invoke bonus based on aspect affinity and skill being checked.

    - Universal aspect (empty affinity): +2
    - Matching affinity (skill in list): +2
    - Non-matching affinity: +1
    """
    if not affinity:
        return 2  # universal
    return 2 if skill in affinity else 1


# ── Effect constants ─────────────────────────────────────────────────

COMBAT_EFFECTS = {
    "ATTACK": {
        "label": "Attack",
        "desc": "attack",
    },
    "DEFEND": {
        "label": "Defense",
        "desc": "defense",
    },
    "SETUP": {
        "label": "Exploit Advantage",
        "desc": "exploit advantage on enemy aspect",
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
    """Flatten an NPC's aspect dict {high_concept, trouble, other} into a raw list.

    Returns raw values which may be strings or affinity dicts — callers should
    use normalize_aspect() to extract text and affinity.
    """
    aspects_field = npc_data.get("aspects", [])
    if isinstance(aspects_field, dict):
        flat = []
        hc = aspects_field.get("high_concept")
        if hc:
            flat.append(hc)
        trouble = aspects_field.get("trouble")
        if trouble:
            flat.append(trouble)
        flat.extend(aspects_field.get("other", []))
        return flat
    # Already a list (shouldn't happen with current data, but safe)
    return list(aspects_field)


def collect_invokable_aspects(game, context="combat"):
    """Gather all invokable aspects with source labels and affinity.

    Args:
        game: Game instance
        context: "combat" or "recruit"

    Returns:
        List of (aspect_text, source_label, affinity_list) tuples.
    """
    aspects = []
    char = game.current_character()

    # Character aspects (high_concept, trouble, other, consequences)
    for a in char.get_all_aspects():
        text, aff = normalize_aspect(a)
        aspects.append((text, "yours", aff))

    # Room aspects
    room = game.current_room()
    if room:
        for a in room.aspects:
            text, aff = normalize_aspect(a)
            aspects.append((text, "room", aff))

        # Zone aspect
        zone_aspect = game._get_zone_aspect(room)
        if zone_aspect:
            text, aff = normalize_aspect(zone_aspect)
            aspects.append((text, "zone", aff))

    # Context-specific sources
    if context == "combat":
        # Enemy aspects
        if game.combat_target:
            enemy = game.enemies_db.get(game.combat_target, {})
            for a in enemy.get("aspects", []):
                text, aff = normalize_aspect(a)
                aspects.append((text, "enemy", aff))

        # Following NPC aspects (recruited NPCs at same location)
        explorer_loc = game.state.get("explorer_location")
        for npc_id in game.state.get("recruited_npcs", []):
            npc = game.npcs_db.get(npc_id, {})
            if npc.get("following") and npc.get("location") == explorer_loc:
                for a in _flatten_npc_aspects(npc):
                    text, aff = normalize_aspect(a)
                    aspects.append((text, npc.get("name", npc_id), aff))

    elif context == "recruit":
        # NPC target aspects
        if game.recruit_state:
            npc_data = game.recruit_state.get("npc_data", {})
            for a in _flatten_npc_aspects(npc_data):
                text, aff = normalize_aspect(a)
                aspects.append((text, npc_data.get("name", "NPC"), aff))

    elif context == "social":
        # Social encounter — NPC aspects from encounter state
        if game.social_encounter_state:
            npc_id = game.social_encounter_state.get("npc_id")
            npc_data = game.npcs_db.get(npc_id, {})
            for a in _flatten_npc_aspects(npc_data):
                text, aff = normalize_aspect(a)
                aspects.append((text, npc_data.get("name", npc_id), aff))

    # World seed aspects — only invokable in its room
    if game.seed and room and room.id == "skerry_hollow":
        for a in game.seed.aspects:
            text, aff = normalize_aspect(a)
            aspects.append((text, game.seed_name, aff))

    # Inventory item aspects
    for item_id in char.inventory:
        item = game.items_db.get(item_id, {})
        for a in item.get("aspects", []):
            text, aff = normalize_aspect(a)
            aspects.append((text, item.get("name", item_id), aff))

    # Kept artifact aspects
    kept = game.state.get("kept_artifact")
    if kept:
        artifact = game.artifacts_db.get(kept, {})
        for a in artifact.get("aspects", []):
            text, aff = normalize_aspect(a)
            aspects.append((text, artifact.get("name", kept), aff))

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
    for npc_id in game.state.get("recruited_npcs", []):
        npc = game.npcs_db.get(npc_id, {})
        if npc.get("following") and npc.get("location") == explorer_loc:
            return npc.get("name", npc_id)
    return None


def check_compel(game):
    """Check if a compel should trigger. Returns compel data dict or None.

    Checks the active character's trouble aspect against COMPELS dict.
    Only triggers if conditions are met.
    """
    char = game.current_character()
    raw_trouble = char.aspects.get("trouble")
    if not raw_trouble:
        return None

    trouble, _ = normalize_aspect(raw_trouble)

    # Try the trouble aspect first
    compel = COMPELS.get(trouble)
    if not compel:
        return None

    # Check condition
    if compel["condition"] == "follower_present":
        follower = _get_follower_name(game)
        if not follower:
            # Try other character aspects for a fallback compel
            for raw_other in char.aspects.get("other", []):
                other_text, _ = normalize_aspect(raw_other)
                alt = COMPELS.get(other_text)
                if alt and alt["condition"] == "always":
                    compel = alt
                    trouble = other_text
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
        taken_out, _ = char.apply_damage(stress_amount)
        stress_str = "".join("[X]" if s else "[ ]" for s in char.stress)
        messages.append(f"  ({stress_amount} stress — {stress_str})")
        if taken_out:
            messages.append("TAKEN_OUT")
    elif effect == "lose_turn":
        messages.append("  (You lose your next action — the enemy strikes.)")
    elif effect == "enemy_boost":
        game.enemy_compel_boost = 2

    messages.append(f"  (+1 Fate Point — you now have {char.fate_points})")
    return messages


# ── Consequence healing ──────────────────────────────────────────────

# Maps consequence text patterns to cure items.
# "Wounded by" and "Ambushed by" are the current combat consequence formats.
# As more consequence types are added, extend this mapping.
CONSEQUENCE_CURES = {
    "Wounded": "bandages",
    "Ambushed": "bandages",
    "Burned": "bandages",
    "Gashed": "bandages",
    "Clawed": "bandages",
    "Bitten": "bandages",
}

# Treatment difficulty by severity (Fate ladder values)
TREATMENT_DIFFICULTY = {
    "mild": 0,       # auto-clears, no check needed
    "moderate": 2,   # Fair (+2)
    "severe": 4,     # Great (+4)
}

# Natural recovery rates: zone clears per severity tier downgrade
NATURAL_HEAL_RATE = 3      # unbandaged: 3 clears per tier
BANDAGED_HEAL_RATE = 1     # bandaged (greyed): 1 clear per tier

# Invoke bonuses when enemies exploit wounds
FRESH_INVOKE_BONUS = {"mild": 1, "moderate": 2}    # severe = extraction, never invoked fresh
GREYED_INVOKE_BONUS = {"mild": 0, "moderate": 1, "severe": 2}

# Severity tiers in order for effective_severity lookup
_SEVERITY_TIERS = ["severe", "moderate", "mild"]


def _effective_severity(original_sev, recovery):
    """Return the effective severity after recovery steps.

    Each recovery step shifts the severity down one tier:
      severe(0) → severe, severe(1) → moderate, severe(2) → mild
      moderate(0) → moderate, moderate(1) → mild
      mild(0) → mild

    Returns None if recovery exceeds the number of possible downgrades (fully healed).
    """
    try:
        idx = _SEVERITY_TIERS.index(original_sev)
    except ValueError:
        return original_sev
    new_idx = idx + recovery
    if new_idx >= len(_SEVERITY_TIERS):
        return None  # fully healed (past mild)
    return _SEVERITY_TIERS[new_idx]


def get_cure_for_consequence(consequence_text):
    """Determine what cure item a consequence requires based on its name.

    Returns the item_id of the cure, or "bandages" as default for unknown types.
    """
    if not consequence_text:
        return None
    for pattern, cure in CONSEQUENCE_CURES.items():
        if pattern.lower() in consequence_text.lower():
            return cure
    # Default: all combat injuries use bandages until more cure types exist
    return "bandages"


def check_auto_heal(game):
    """Natural recovery: all wounds heal over zone clears. Bandaging speeds it up.

    On each zone clear, check each wound. If enough clears have passed for the
    current effective severity tier, increment recovery (downgrade one tier) and
    reset taken_at. When effective severity passes mild → remove the wound.

    Returns list of (character_key, original_severity, consequence_text, event_type)
    where event_type is "cleared" (fully healed) or "downgraded" (tier reduced).
    """
    zones_cleared = game.state.get("zones_cleared", 0)
    meta = game.state.get("consequence_meta", {})
    results = []

    for char_key in ("explorer", "steward"):
        char_data = game.state.get(char_key)
        if not char_data:
            continue
        cons = char_data.get("consequences", {})

        for sev in ["severe", "moderate", "mild"]:
            entries = cons.get(sev, [])
            if not isinstance(entries, list):
                continue
            # Iterate in reverse to safely remove by index
            for i in range(len(entries) - 1, -1, -1):
                entry = entries[i]
                con_text = entry.get("text", "")
                if not con_text:
                    continue

                meta_key = f"{char_key}_{sev}_{i}"
                meta_entry = meta.get(meta_key, {})
                recovery = meta_entry.get("recovery", 0)
                eff_sev = _effective_severity(sev, recovery)

                if eff_sev is None:
                    # Already past mild — clean up stale entry
                    entries.pop(i)
                    meta.pop(meta_key, None)
                    _reindex_meta(meta, char_key, sev, i)
                    results.append((char_key, sev, con_text, "cleared"))
                    continue

                # Determine heal rate based on greyed status
                greyed = entry.get("greyed", False)
                heal_rate = BANDAGED_HEAL_RATE if greyed else NATURAL_HEAL_RATE

                taken_at = meta_entry.get("taken_at", 0)
                if zones_cleared - taken_at >= heal_rate:
                    # Advance recovery one tier
                    new_recovery = recovery + 1
                    new_eff = _effective_severity(sev, new_recovery)

                    if new_eff is None:
                        # Fully healed — remove wound
                        entries.pop(i)
                        meta.pop(meta_key, None)
                        _reindex_meta(meta, char_key, sev, i)
                        results.append((char_key, sev, con_text, "cleared"))
                    else:
                        # Downgraded — update meta, reset timer
                        meta_entry["recovery"] = new_recovery
                        meta_entry["taken_at"] = zones_cleared
                        results.append((char_key, sev, con_text, "downgraded"))

    return results


def _reindex_meta(meta, char_key, severity, removed_index):
    """After removing an entry at removed_index, shift higher-indexed meta keys down."""
    i = removed_index + 1
    while True:
        old_key = f"{char_key}_{severity}_{i}"
        new_key = f"{char_key}_{severity}_{i - 1}"
        if old_key in meta:
            meta[new_key] = meta.pop(old_key)
            i += 1
        else:
            break


# Keep old name as alias for any callers we might miss
check_mild_auto_heal = check_auto_heal


def can_treat_consequence(game, char_key, severity, index=0):
    """Check if a consequence entry is eligible for treatment (bandaging).

    Treatment is optional but strategic: it greys the wound (reducing invoke
    bonus) and switches to faster healing rate. Available for moderate+ wounds.

    Returns (eligible, reason_if_not).
    """
    char_data = game.state.get(char_key)
    if not char_data:
        return False, "Character not found."

    cons = char_data.get("consequences", {})
    entries = cons.get(severity, [])
    if not isinstance(entries, list) or index >= len(entries):
        return False, f"No {severity} consequence to treat."

    entry_data = entries[index]
    if not entry_data.get("text"):
        return False, f"No {severity} consequence to treat."

    # Already greyed (bandaged) — no further treatment needed
    if entry_data.get("greyed"):
        return False, "This injury is already bandaged."

    meta = game.state.get("consequence_meta", {})
    meta_key = f"{char_key}_{severity}_{index}"
    meta_entry = meta.get(meta_key, {})
    recovery = meta_entry.get("recovery", 0)
    eff_sev = _effective_severity(severity, recovery)

    # Already at mild-equivalent — heals on its own quickly enough
    if eff_sev == "mild" or eff_sev is None:
        return False, "This injury is minor — it will heal on its own."

    return True, None


def get_treatment_aspects(game):
    """Gather invokable aspects for a treatment skill check.

    Similar to combat/recruit but for healing context. Includes:
    - Treater's character aspects
    - Patient's consequence aspects
    - Room aspects
    - World seed aspects
    - Inventory item aspects
    - Kept artifact aspects

    Returns:
        List of (aspect_text, source_label, affinity_list) tuples.
    """
    aspects = []
    char = game.current_character()

    # Treater's character aspects
    for a in char.get_all_aspects():
        text, aff = normalize_aspect(a)
        aspects.append((text, "yours", aff))

    # Room aspects
    room = game.current_room()
    if room:
        for a in room.aspects:
            text, aff = normalize_aspect(a)
            aspects.append((text, "room", aff))

    # World seed aspects — only invokable in its room
    if game.seed and room and room.id == "skerry_hollow":
        for a in game.seed.aspects:
            text, aff = normalize_aspect(a)
            aspects.append((text, game.seed_name, aff))

    # Inventory item aspects
    for item_id in char.inventory:
        item = game.items_db.get(item_id, {})
        for a in item.get("aspects", []):
            text, aff = normalize_aspect(a)
            aspects.append((text, item.get("name", item_id), aff))

    # Kept artifact aspects
    kept = game.state.get("kept_artifact")
    if kept:
        artifact = game.artifacts_db.get(kept, {})
        for a in artifact.get("aspects", []):
            text, aff = normalize_aspect(a)
            aspects.append((text, artifact.get("name", kept), aff))

    return aspects


def get_enemy_invoke_target(character):
    """Pick a consequence for enemy invoke, weighted by bonus.

    Fresh wounds: mild +1, moderate +2, severe = extraction (not invoked).
    Greyed wounds: mild +0 (skip), moderate +1, severe +2.

    Returns (severity, index, text, greyed, bonus) or None.
    """
    candidates = []
    for sev in ("mild", "moderate", "severe"):
        for i, entry in enumerate(character.consequences.get(sev, [])):
            greyed = entry.get("greyed", False)
            if greyed:
                bonus = GREYED_INVOKE_BONUS.get(sev, 0)
            else:
                bonus = FRESH_INVOKE_BONUS.get(sev, 0)
            if bonus > 0:
                candidates.append((sev, i, entry["text"], greyed, bonus))
    return random.choice(candidates) if candidates else None


def resolve_compel_refuse(game, compel):
    """Spend FP to refuse a compel. Returns message strings."""
    char = game.current_character()
    char.spend_fate_point()
    return [
        "You push through, refusing to let it get to you.",
        f"  (-1 Fate Point — you now have {char.fate_points})",
    ]
