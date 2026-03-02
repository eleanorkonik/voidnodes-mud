"""Social encounter system — structured multi-step social interactions.

Encounter types:
  simple   — single skill check, resolves inline
  challenge — multiple independent overcome actions, different skills
  contest  — back-and-forth rounds, first to N victories

Data-driven from data/encounters.json. Rewards and penalties applied via
apply_reward() / apply_penalty().
"""

import json
import random
from pathlib import Path

from engine import dice, display


DATA_DIR = Path(__file__).parent.parent / "data"

_encounters_db = None


def _load_encounters():
    """Load encounter definitions from data/encounters.json. Cached."""
    global _encounters_db
    if _encounters_db is None:
        with open(DATA_DIR / "encounters.json") as f:
            _encounters_db = json.load(f)
    return _encounters_db


# ── Encounter selection ──────────────────────────────────────────

def pick_encounter(game, npc_id, npc):
    """Pick an eligible encounter for this NPC, or None.

    Returns (encounter_id, encounter_def) or (None, None).

    Selection rules:
      - Max 1 encounter trigger per NPC per day (npc.last_encounter_day)
      - NPC's encounter_pool + generic encounters (no npc_specific field)
      - Filter: min_loyalty, min_npcs, cooldown, once-only history
      - 30% base chance + 5% per loyalty above 5 + 10% in steward phase
      - If triggered: random from eligible pool
    """
    day = game.state.get("day", 1)

    # Per-NPC daily gate
    if npc.get("last_encounter_day", 0) == day:
        return None, None

    encounters = _load_encounters()
    npc_pool = set(npc.get("encounter_pool", []))
    loyalty = npc.get("loyalty", 0)
    recruited_count = len(game.state.get("recruited_npcs", []))

    # Cooldowns and history
    cooldowns = game.state.get("encounter_cooldown", {})
    history = npc.get("encounter_history", [])

    eligible = []
    for enc_id, enc in encounters.items():
        # NPC-specific encounters only for the right NPC
        npc_specific = enc.get("npc_specific")
        if npc_specific:
            if npc_id not in npc_specific:
                continue
        else:
            # Generic encounter — eligible for all, OR NPC has it in their pool
            if enc_id not in npc_pool and npc_specific is None:
                pass  # generic, open to all
            elif enc_id not in npc_pool:
                continue

        # NPC pool check — if npc has a pool, non-npc-specific encounters
        # must either be in the pool or be truly generic
        if npc_pool and enc_id not in npc_pool and not npc_specific:
            pass  # generic encounters are always eligible

        # min_loyalty gate
        if loyalty < enc.get("min_loyalty", 0):
            continue

        # min_npcs gate
        if recruited_count < enc.get("min_npcs", 0):
            continue

        # Once-only check
        if enc.get("once") and enc_id in history:
            continue

        # Cooldown check (3 days for repeatable)
        if not enc.get("once"):
            last_trigger = cooldowns.get(enc_id, 0)
            if day - last_trigger < 3:
                continue

        eligible.append((enc_id, enc))

    if not eligible:
        return None, None

    # Trigger chance
    phase = game.state.get("current_phase", "steward")
    chance = 0.30
    if loyalty > 5:
        chance += 0.05 * (loyalty - 5)
    if phase == "steward":
        chance += 0.10
    chance = min(chance, 0.95)

    if random.random() > chance:
        return None, None

    # Pick random from eligible
    enc_id, enc = random.choice(eligible)

    # Mark daily gate
    npc["last_encounter_day"] = day

    return enc_id, enc


# ── State factories ──────────────────────────────────────────────

def create_encounter_state(enc_id, enc, npc_id, npc_name):
    """Create the runtime state dict for an active encounter."""
    enc_type = enc["type"]
    state = {
        "encounter_id": enc_id,
        "encounter_def": enc,
        "npc_id": npc_id,
        "npc_name": npc_name,
        "type": enc_type,
        "resolved": False,
    }

    if enc_type == "challenge":
        state["current_step"] = 0
        state["step_results"] = []  # list of True/False per step
    elif enc_type == "contest":
        state["player_wins"] = 0
        state["npc_wins"] = 0
        state["victories_needed"] = enc.get("victories_needed", 3)
        state["tactic_uses"] = {}  # {tactic_id: count} for stale argument rule
        state["round"] = 1

    return state


# ── Resolution helpers ───────────────────────────────────────────

def resolve_simple(game, enc, npc_id, npc):
    """Resolve a simple encounter inline. Returns (success, messages)."""
    char = game.current_character()
    skill_name = enc["skill"]
    dc = enc.get("dc", 2)

    invoke_bonus = game._consume_invoke_bonus()
    skill_val = char.get_skill(skill_name) + invoke_bonus
    skill_label = f"{skill_name}+{invoke_bonus}" if invoke_bonus else skill_name

    total, shifts, dice_result = dice.skill_check(skill_val, dc)

    messages = []
    messages.append(f"  {char.name}: {dice.roll_description(dice_result, skill_val, skill_label)}")
    messages.append(f"  DC: +{dc} | Shifts: {shifts:+d}")

    if shifts >= 0:
        messages.append("")
        text = enc.get("success_text", "Success.")
        messages.append(f"  {_sub_encounter_text(text, npc.get('name', npc_id))}")
        return True, messages
    else:
        messages.append("")
        text = enc.get("failure_text", "Failure.")
        messages.append(f"  {_sub_encounter_text(text, npc.get('name', npc_id))}")
        return False, messages


def resolve_challenge_step(game, enc_state, action):
    """Resolve one step of a challenge encounter.

    action: "attempt", "invoke", or "concede"
    Returns (step_done, encounter_done, messages)
    """
    enc = enc_state["encounter_def"]
    step_idx = enc_state["current_step"]
    steps = enc["steps"]
    step = steps[step_idx]
    npc_name = enc_state["npc_name"]
    char = game.current_character()
    messages = []

    if action == "concede":
        enc_state["step_results"].append(False)
        messages.append("  You step back from this one.")
        enc_state["current_step"] += 1
        step_done = True
        encounter_done = enc_state["current_step"] >= len(steps)
        return step_done, encounter_done, messages

    # "attempt" or "invoke" (invoke bonus already pending from cmd_invoke)
    skill_name = step["skill"]
    dc = step.get("dc", 2)

    invoke_bonus = game._consume_invoke_bonus()
    skill_val = char.get_skill(skill_name) + invoke_bonus
    skill_label = f"{skill_name}+{invoke_bonus}" if invoke_bonus else skill_name

    total, shifts, dice_result = dice.skill_check(skill_val, dc)

    messages.append(f"  {char.name}: {dice.roll_description(dice_result, skill_val, skill_label)}")
    messages.append(f"  DC: +{dc} | Shifts: {shifts:+d}")
    messages.append("")

    if shifts >= 0:
        enc_state["step_results"].append(True)
        text = step.get("success_text", "Success.")
        messages.append(f"  {_sub_encounter_text(text, npc_name)}")
    else:
        enc_state["step_results"].append(False)
        text = step.get("failure_text", "Failed.")
        messages.append(f"  {_sub_encounter_text(text, npc_name)}")

    enc_state["current_step"] += 1
    step_done = True
    encounter_done = enc_state["current_step"] >= len(steps)
    return step_done, encounter_done, messages


def get_challenge_resolution(enc_state):
    """Get the resolution text and success level for a completed challenge.

    Returns (level, text) where level is "full_success", "partial_success", or "failure".
    """
    enc = enc_state["encounter_def"]
    results = enc_state["step_results"]
    successes = sum(1 for r in results if r)
    total = len(results)

    resolution = enc.get("resolution", {})
    if successes == total:
        return "full_success", resolution.get("full_success", "Complete success.")
    elif successes > 0:
        return "partial_success", resolution.get("partial_success", "Partial success.")
    else:
        return "failure", resolution.get("failure", "Total failure.")


def resolve_contest_round(game, enc_state, tactic_id):
    """Resolve one round of a contest encounter.

    Returns (round_done, contest_done, messages)
    """
    enc = enc_state["encounter_def"]
    npc_name = enc_state["npc_name"]
    char = game.current_character()
    messages = []

    # Find the chosen tactic
    tactics = enc.get("tactics", [])
    tactic = None
    for t in tactics:
        if t["id"] == tactic_id:
            tactic = t
            break
    if not tactic:
        return False, False, ["  Invalid tactic."]

    # Stale argument penalty
    uses = enc_state["tactic_uses"].get(tactic_id, 0)
    stale_penalty = uses  # -1 per previous use
    enc_state["tactic_uses"][tactic_id] = uses + 1

    # Player roll
    skill_name = tactic["skill"]
    invoke_bonus = game._consume_invoke_bonus()
    skill_val = char.get_skill(skill_name) + invoke_bonus - stale_penalty
    skill_label = skill_name
    if invoke_bonus and stale_penalty:
        skill_label = f"{skill_name}+{invoke_bonus}-{stale_penalty}stale"
    elif invoke_bonus:
        skill_label = f"{skill_name}+{invoke_bonus}"
    elif stale_penalty:
        skill_label = f"{skill_name}-{stale_penalty}stale"

    # Flavor text
    flavor = tactic.get("flavor", "")
    if flavor:
        messages.append(f"  {_sub_encounter_text(flavor, npc_name)}")
        messages.append("")

    if stale_penalty:
        messages.append(f"  {display.DIM}(Stale argument: -{stale_penalty} for reusing this tactic){display.RESET}")

    # NPC roll
    npc_skill_name = enc.get("npc_skill", "Will")
    npc_skill_val = enc.get("npc_skill_value", 2)

    player_dice = dice.roll_4df()
    npc_dice = dice.roll_4df()
    player_total = skill_val + sum(player_dice)
    npc_total = npc_skill_val + sum(npc_dice)
    shifts = player_total - npc_total

    messages.append(f"  {char.name}: {dice.roll_description(player_dice, skill_val, skill_label)}")
    messages.append(f"  {npc_name}: {dice.roll_description(npc_dice, npc_skill_val, npc_skill_name)}")
    messages.append(f"  Shifts: {shifts:+d}", )

    if shifts > 0:
        enc_state["player_wins"] += 1
        messages.append(f"  You win this exchange.")
    elif shifts < 0:
        enc_state["npc_wins"] += 1
        messages.append(f"  {npc_name} wins this exchange.")
    else:
        messages.append(f"  A standoff. Neither side gains ground.")

    enc_state["round"] += 1

    # Check for contest end
    needed = enc_state["victories_needed"]
    contest_done = (enc_state["player_wins"] >= needed or
                    enc_state["npc_wins"] >= needed)

    return True, contest_done, messages


# ── Reward / Penalty system ──────────────────────────────────────

def apply_reward(game, npc, reward_dict):
    """Apply encounter rewards. Returns list of display messages."""
    if not reward_dict:
        return []
    messages = []
    npc_name = npc.get("name", "NPC")

    if "loyalty_bonus" in reward_dict:
        old = npc.get("loyalty", 0)
        npc["loyalty"] = min(10, old + reward_dict["loyalty_bonus"])
        messages.append(f"  {npc_name}'s loyalty increases to {npc['loyalty']}.")

    if "mood_bonus" in reward_dict:
        tiers = ["unhappy", "restless", "content", "happy"]
        current = npc.get("mood", "content")
        idx = tiers.index(current) if current in tiers else 2
        new_idx = min(len(tiers) - 1, idx + reward_dict["mood_bonus"])
        npc["mood"] = tiers[new_idx]
        if npc["mood"] != current:
            messages.append(f"  {npc_name}'s mood improves to {npc['mood']}.")

    if reward_dict.get("backstory_reveal"):
        backstory = npc.get("backstory", {})
        backstory_aspects = backstory.get("aspects", [])
        revealed = npc.get("revealed_backstory", [])
        npc.setdefault("revealed_backstory", [])
        for aspect_text in backstory_aspects:
            if aspect_text not in revealed:
                npc["revealed_backstory"].append(aspect_text)
                npc.setdefault("aspects", {}).setdefault("other", [])
                if aspect_text not in npc["aspects"]["other"]:
                    npc["aspects"]["other"].append(aspect_text)
                messages.append(f"  New aspect revealed: {display.aspect_text(aspect_text)}")
                break

    if "npc_skill_bonus" in reward_dict:
        bonus = reward_dict["npc_skill_bonus"]
        skill = bonus["skill"]
        amount = bonus["amount"]
        npc.setdefault("skills", {})[skill] = npc.get("skills", {}).get(skill, 0) + amount
        messages.append(f"  {npc_name}'s {skill} increases by {amount}.")

    if "item" in reward_dict:
        item_id = reward_dict["item"]
        # Check if materials are required
        consume = reward_dict.get("consume_materials")
        if consume:
            char = game.current_character()
            # Check all sources: inventory, room items, junkyard, storehouse
            available = {}
            for iid in char.inventory:
                available[iid] = available.get(iid, 0) + 1
            room = game.current_room()
            if room:
                for iid in room.items:
                    available[iid] = available.get(iid, 0) + 1
            can_afford = all(available.get(mat, 0) >= qty for mat, qty in consume.items())
            if not can_afford:
                # Can't make the item — show no_materials_text if provided
                no_mat_text = reward_dict.get("no_materials_text")
                if no_mat_text:
                    messages.append(f"  {no_mat_text}")
                else:
                    messages.append("  Not enough materials to craft that.")
            else:
                # Consume materials from inventory first, then room
                for mat, qty in consume.items():
                    remaining = qty
                    for _ in range(remaining):
                        if mat in char.inventory:
                            char.remove_from_inventory(mat)
                        elif room and mat in room.items:
                            room.remove_item(mat)
                        remaining -= 1
                char.add_to_inventory(item_id)
                item_name = game.items_db.get(item_id, {}).get("name", item_id.replace("_", " ").title())
                messages.append(f"  Received: {display.item_name(item_name)}")
        else:
            char = game.current_character()
            char.add_to_inventory(item_id)
            item_name = game.items_db.get(item_id, {}).get("name", item_id.replace("_", " ").title())
            messages.append(f"  Received: {display.item_name(item_name)}")

    if "recipe" in reward_dict:
        recipe_id = reward_dict["recipe"]
        game.state.setdefault("discovered_recipes", [])
        if recipe_id not in game.state["discovered_recipes"]:
            game.state["discovered_recipes"].append(recipe_id)
            messages.append(f"  New recipe discovered: {recipe_id.replace('_', ' ').title()}")

    if "skerry_mood_bonus" in reward_dict:
        boosted = 0
        tiers = ["unhappy", "restless", "content", "happy"]
        for nid in game.state.get("recruited_npcs", []):
            n = game.npcs_db.get(nid, {})
            current = n.get("mood", "content")
            idx = tiers.index(current) if current in tiers else 2
            new_idx = min(len(tiers) - 1, idx + reward_dict["skerry_mood_bonus"])
            if new_idx > idx:
                n["mood"] = tiers[new_idx]
                boosted += 1
        if boosted:
            messages.append(f"  The whole skerry feels better. ({boosted} NPC{'s' if boosted != 1 else ''} mood improved)")

    return messages


def apply_penalty(game, npc, penalty_dict, char=None):
    """Apply encounter penalties. Returns list of display messages."""
    if not penalty_dict:
        return []
    messages = []
    npc_name = npc.get("name", "NPC")
    if char is None:
        char = game.current_character()

    if "mood_penalty" in penalty_dict:
        tiers = ["unhappy", "restless", "content", "happy"]
        current = npc.get("mood", "content")
        idx = tiers.index(current) if current in tiers else 2
        new_idx = max(0, idx - penalty_dict["mood_penalty"])
        npc["mood"] = tiers[new_idx]
        if npc["mood"] != current:
            messages.append(f"  {npc_name}'s mood drops to {npc['mood']}.")

    if "loyalty_penalty" in penalty_dict:
        old = npc.get("loyalty", 0)
        npc["loyalty"] = max(0, old - penalty_dict["loyalty_penalty"])
        if npc["loyalty"] < old:
            messages.append(f"  {npc_name}'s loyalty drops to {npc['loyalty']}.")

    if "miria_stress" in penalty_dict:
        amount = penalty_dict["miria_stress"]
        taken_out = char.apply_damage(amount)
        stress_str = "".join("[X]" if s else "[ ]" for s in char.stress)
        messages.append(f"  {char.name} takes {amount} stress. ({stress_str})")
        if taken_out:
            # Generate a social consequence — find "Pending" entries in list
            for sev in ["mild", "moderate", "severe"]:
                for entry in char.consequences.get(sev, []):
                    if entry.get("text") == "Pending":
                        social_cons = random.choice([
                            "Compassion Fatigue",
                            "Everyone's Disappointed",
                            "Burned Out",
                            "Doubting Herself",
                        ])
                        entry["text"] = social_cons
                        messages.append(f"  {char.name} takes a {sev} consequence: {social_cons}")
                        break
                else:
                    continue
                break

    if "festering_aspect" in penalty_dict:
        aspect_name = penalty_dict["festering_aspect"]
        dyn = game.skerry.dynamic_aspects
        if aspect_name not in dyn:
            dyn.append(aspect_name)
            messages.append(f"  Festering aspect: {display.aspect_text(aspect_name)}")

            # Seed stress
            seed_taken_out = _apply_seed_stress(game, 1)
            messages.append(f"  {game.seed_name} strains under the tension. (1 seed stress)")
            if seed_taken_out:
                messages.append(f"  {game.seed_name} takes a consequence from the strain!")

    return messages


def _apply_seed_stress(game, amount):
    """Apply stress to the world seed. Returns True if overflow (consequence needed)."""
    stress = game.seed.stress
    for i in range(len(stress)):
        if not stress[i] and (i + 1) >= amount:
            stress[i] = True
            return False
    # Overflow — seed consequence
    seed_cons = game.state.setdefault("seed_consequences", [])
    con_text = random.choice([
        "Roots Withdrawing",
        "Flickering Glow",
        "Weakened Barrier",
    ])
    if con_text not in seed_cons:
        seed_cons.append(con_text)
    return True


# ── Social compels (festering aspects) ───────────────────────────

# Aspects created by social encounter failures — tracked for compel,
# mote drain, and subtask penalty
SOCIAL_ASPECTS = {
    "Unresolved Dispute",
    "Doubts About Leadership",
    "Neglected Garden",
}


def check_social_compel(game):
    """Check if a social compel should trigger on skerry room entry.

    Returns compel data dict or None.
    Max 1 compel per room entry. Each festering aspect compels once per day.
    """
    dyn = game.skerry.dynamic_aspects
    social = [a for a in dyn if a in SOCIAL_ASPECTS]
    if not social:
        return None

    compelled_today = set(game.state.get("social_compels_today", []))
    char = game.current_character()

    for aspect in social:
        if aspect in compelled_today:
            continue
        # Found one to compel
        return {
            "aspect": aspect,
            "text": _social_compel_text(aspect),
            "accept_effect": "take_stress",
            "accept_text": "The weight settles on your shoulders. You push on.",
            "stress": 1,
        }
    return None


def _social_compel_text(aspect):
    """Get flavor text for a social compel."""
    texts = {
        "Unresolved Dispute": "The \"Unresolved Dispute\" weighs on you. Everyone's tense. It's your problem now.",
        "Doubts About Leadership": "\"Doubts About Leadership\" hangs in the air. People avoid your eyes.",
        "Neglected Garden": "The \"Neglected Garden\" is visible from here. Plants wilting. Nobody's stepped up.",
    }
    return texts.get(aspect, f"The \"{aspect}\" weighs on you as you step inside.")


def mark_social_compel_used(game, aspect):
    """Mark a festering aspect as having compelled today."""
    today = game.state.setdefault("social_compels_today", [])
    if aspect not in today:
        today.append(aspect)


def get_festering_aspects(game):
    """Get all active festering/social aspects on the skerry."""
    dyn = game.skerry.dynamic_aspects
    return [a for a in dyn if a in SOCIAL_ASPECTS]


def get_festering_penalty(game):
    """Count festering aspects for subtask penalty. Returns negative int."""
    return -len(get_festering_aspects(game))


def apply_festering_drain(game):
    """Apply daily mote drain from festering aspects. Returns (drain_amount, messages)."""
    social = get_festering_aspects(game)
    if not social:
        return 0, []
    drain = len(social)
    game.seed.spend_motes(drain)
    messages = [f"  {game.seed_name} strains under unresolved tensions. (-{drain} mote{'s' if drain != 1 else ''})"]
    return drain, messages


def resolve_festering_aspect(game, aspect_name):
    """Remove a festering aspect and heal associated seed stress.

    Returns list of display messages.
    """
    messages = []
    dyn = game.skerry.dynamic_aspects
    if aspect_name in dyn:
        dyn.remove(aspect_name)
        messages.append(f"  Resolved: {display.aspect_text(aspect_name)}")

        # Heal one seed stress box
        for i in range(len(game.seed.stress) - 1, -1, -1):
            if game.seed.stress[i]:
                game.seed.stress[i] = False
                messages.append(f"  {game.seed_name} relaxes. (1 seed stress healed)")
                break

    return messages


# ── Contextual greeting lines ────────────────────────────────────

def get_contextual_greeting(npc, npc_id, game):
    """Get a mood/context-aware greeting line for an NPC with no encounter.

    Falls back to existing dialogue.idle / dialogue.happy.
    """
    greet_lines = npc.get("greet_lines", {})
    mood = npc.get("mood", "content")
    loyalty = npc.get("loyalty", 0)
    dialogue = npc.get("dialogue", {})

    # Check greet_lines first
    if mood in ("restless", "unhappy") and greet_lines.get("mood_restless"):
        return random.choice(greet_lines["mood_restless"])
    if loyalty >= 6 and greet_lines.get("high_loyalty"):
        return random.choice(greet_lines["high_loyalty"])
    if greet_lines.get("low_loyalty"):
        return random.choice(greet_lines["low_loyalty"])

    # Fall back to existing dialogue
    if mood in ("content", "happy"):
        return dialogue.get("happy", dialogue.get("idle", "..."))
    return dialogue.get("idle", "...")


# ── Display helpers ──────────────────────────────────────────────

def display_encounter_header(enc, npc_name=""):
    """Display the encounter title and description."""
    name = enc.get("name", "Encounter")
    desc = enc.get("description", "")
    print(f"\n{display.BOLD}{display.BRIGHT_CYAN}═══ {name} ═══{display.RESET}")
    if desc:
        print(f"\n  {_sub_encounter_text(desc, npc_name)}")
    print()


def display_challenge_step(enc, step_idx):
    """Display a challenge step prompt with options."""
    steps = enc["steps"]
    step = steps[step_idx]
    total = len(steps)
    print(f"  Step {step_idx + 1} of {total}: {step['prompt']}")
    print(f"  Skill: {step['skill']} (DC +{step.get('dc', 2)})")
    print()
    print(f"  > {display.BOLD}ATTEMPT{display.RESET}    Roll {step['skill']} vs DC {step.get('dc', 2)}")
    print(f"  > {display.BOLD}INVOKE{display.RESET}     Spend FP for +2, then roll")
    print(f"  > {display.BOLD}CONCEDE{display.RESET}    Walk away (minor penalty)")
    print()


def display_contest_round(enc_state, char=None):
    """Display a contest round with tactic options."""
    enc = enc_state["encounter_def"]
    tactics = enc.get("tactics", [])
    char_name = "You"
    npc_name = enc_state["npc_name"]
    p_wins = enc_state["player_wins"]
    n_wins = enc_state["npc_wins"]
    needed = enc_state["victories_needed"]
    rnd = enc_state["round"]

    print(f"  Round {rnd} — {char_name}: {p_wins}  {npc_name}: {n_wins}  (first to {needed})")
    print()
    for i, tactic in enumerate(tactics):
        skill = tactic["skill"]
        skill_val = char.get_skill(skill) if char else None
        skill_str = f" +{skill_val}" if skill_val is not None else ""
        uses = enc_state["tactic_uses"].get(tactic["id"], 0)
        stale = f" {display.DIM}(-{uses} stale){display.RESET}" if uses > 0 else ""
        print(f"  {i + 1}. {tactic['name']:<24} ({skill}{skill_str}){stale}")
    print()
    print(f"  > {display.BOLD}1/2/3{display.RESET}, {display.BOLD}INVOKE{display.RESET} <aspect>, or {display.BOLD}CONCEDE{display.RESET}")
    print()


def display_encounter_resolution(level, text):
    """Display the final resolution of an encounter."""
    print()
    if level == "full_success":
        display.success(f"  {text}")
    elif level == "partial_success":
        display.narrate(f"  {text}")
    else:
        display.warning(f"  {text}")


# ── Text substitution ────────────────────────────────────────────

def _sub_encounter_text(text, npc_name):
    """Substitute {npc_name} in encounter text."""
    return text.replace("{npc_name}", npc_name)
