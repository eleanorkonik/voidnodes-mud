"""Quest system — locked exits, contextual USE, quest-aware TALK."""

from engine import display


# ── Quest Registry ──────────────────────────────────────────

QUEST_INFO = {
    "verdant_bloom": {
        "name": "The Verdant Heart",
        "giver": "Lira",
        "zone": "The Verdant Wreck",
        "summary": "Massive roots block access to a crystallized bloom at the biodome's heart.",
        "hints": {
            "active": "Lira mentioned two ways through: repair the Growth Controller (west of the root wall), or weaken the roots with solvent and burn through.",
            "roots_weakened": "The roots are weakened. Something hot might finish the job.",
            "roots_cleared": "The way north is open. The bloom awaits.",
        },
    },
}


def get_quest_display(quest_id, quest_state):
    """Return display info for a quest, or None if unknown."""
    info = QUEST_INFO.get(quest_id)
    if not info:
        return None
    status = quest_state.get("status", "inactive")
    hint = None
    if status == "active":
        if quest_state.get("roots_cleared"):
            hint = info["hints"].get("roots_cleared")
        elif quest_state.get("roots_weakened"):
            hint = info["hints"].get("roots_weakened")
        else:
            hint = info["hints"].get("active")
    return {
        "name": info["name"],
        "giver": info["giver"],
        "zone": info["zone"],
        "summary": info["summary"],
        "status": status,
        "hint": hint,
    }


# ── Lock Conditions ──────────────────────────────────────────

CONDITION_MAP = {
    "quest_roots_cleared": lambda s: s.get("quests", {}).get("verdant_bloom", {}).get("roots_cleared", False),
}


def check_lock_condition(condition, game_state):
    """Resolve a locked_exit condition string against game state."""
    resolver = CONDITION_MAP.get(condition)
    return resolver(game_state) if resolver else False


# ── Quest State Helpers ──────────────────────────────────────

def is_quest_active(quest_id, game_state):
    return game_state.get("quests", {}).get(quest_id, {}).get("status") == "active"


def is_quest_complete(quest_id, game_state):
    return game_state.get("quests", {}).get(quest_id, {}).get("status") == "complete"


# ── Contextual USE ───────────────────────────────────────────

def handle_quest_use(item_id, room_id, game_state, character, rooms=None):
    """Handle location-specific item USE for quests.

    Returns (handled: bool, consumed: bool) — caller handles inventory
    removal if consumed.
    """
    quest = game_state.get("quests", {}).get("verdant_bloom", {})
    if quest.get("status") != "active":
        return False, False

    # PATH B (forceful) — resin + torch at root wall
    if room_id == "vw_root_wall":
        if item_id == "resin" and not quest.get("roots_weakened"):
            display.narrate("You spread the resin across the thick roots. The organic")
            display.narrate("solvent soaks in, and you hear faint cracking as the outer")
            display.narrate("layer softens. The roots sag but hold.")
            display.info("  Something hotter might finish the job.")
            quest["roots_weakened"] = True
            return True, True  # consume resin

        if item_id == "torch" and quest.get("roots_weakened") and not quest.get("roots_cleared"):
            display.narrate("You hold the torch to the weakened roots. They catch")
            display.narrate("instantly, curling and blackening. In moments, a narrow")
            display.narrate("passage opens to the north, revealing a green glow beyond.")
            quest["roots_cleared"] = True
            quest["path"] = "forceful"
            _update_room_aspect(game_state, "vw_root_wall", ["Charred Passage"], rooms)
            return True, False  # torch not consumed

        if item_id == "torch" and not quest.get("roots_weakened"):
            display.narrate("You hold the torch to the roots, but they're too thick")
            display.narrate("and damp to catch. The surface barely singes.")
            return True, False

    # PATH A (careful) — basic_tools at control room
    if room_id == "vw_control":
        if item_id == "basic_tools" and not quest.get("roots_cleared"):
            display.narrate("You pry open the console panel and get to work. Corroded")
            display.narrate("connectors, frayed wiring — but the core logic board is intact.")
            display.narrate("You clean the contacts and bridge the broken circuits.")
            print()
            display.success("The Growth Controller hums to life. On the flickering screen,")
            display.success("you see the root network diagram shift — redirecting growth")
            display.success("away from the northern corridor.")
            print()
            display.narrate("Through the wall, you hear the groan of roots retracting.")
            quest["roots_cleared"] = True
            quest["path"] = "careful"
            _update_room_aspect(game_state, "vw_root_wall", ["Roots Retracted"], rooms)
            return True, False  # tools not consumed

    return False, False


# ── Quest-Aware TALK ─────────────────────────────────────────

def get_quest_talk(npc_id, npc, game_state):
    """Get quest-specific dialogue for an NPC.

    Returns dict with lines + effects, or None if no quest dialogue.
    """
    if npc_id != "lira":
        return None

    quest = game_state.get("quests", {}).get("verdant_bloom", {})
    dialogue = npc.get("dialogue", {})

    # Quest complete — react based on path taken
    if quest.get("status") == "complete":
        path = quest.get("path")
        if path == "careful":
            return {"lines": [dialogue.get("quest_careful_done", "...")]}
        elif path == "forceful":
            return {"lines": [dialogue.get("quest_forceful_done", "...")]}
        return {"lines": [dialogue.get("quest_complete", "...")]}

    # Quest not started — activate + show both options + reveal hidden exit
    if quest.get("status") != "active":
        return {
            "lines": [
                dialogue.get("greeting", "..."),
                dialogue.get("quest_intro", "..."),
                dialogue.get("quest_options", "..."),
            ],
            "quest_started": True,
            "reveal_exit": ("vw_root_wall", "west", "vw_control"),
        }

    # Quest active, roots cleared — show completion dialogue
    if quest.get("roots_cleared"):
        return {"lines": [dialogue.get("quest_complete", "...")]}

    # Quest active, in progress — repeat options
    return {"lines": [dialogue.get("quest_options", "...")]}


def apply_quest_talk_effects(result, game_state, rooms, character):
    """Apply side effects from quest dialogue (reveal exits, give items, etc.)."""
    if result.get("quest_started"):
        game_state.setdefault("quests", {})["verdant_bloom"] = {
            "status": "active",
            "roots_weakened": False,
            "roots_cleared": False,
            "path": None,
            "control_revealed": False,
        }

    if result.get("reveal_exit"):
        room_id, direction, target_id = result["reveal_exit"]
        room = rooms.get(room_id)
        if room and direction not in room.exits:
            room.exits[direction] = target_id
            game_state["quests"]["verdant_bloom"]["control_revealed"] = True
            display.info("  [Lira points west — a hidden corridor behind the roots.]")


# ── Internal Helpers ─────────────────────────────────────────

def _update_room_aspect(game_state, room_id, new_aspects, rooms=None):
    """Update a room's aspects in both the zone data and live Room object."""
    # Update zone data (for save persistence)
    for zone_id, zone in game_state.get("zones", {}).items():
        for room_data in zone.get("rooms", []):
            if room_data["id"] == room_id:
                room_data["aspects"] = new_aspects
                break
    # Update live Room object
    if rooms and room_id in rooms:
        rooms[room_id].aspects = list(new_aspects)
