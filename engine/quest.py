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
            "active": "Lira mentioned two ways through: repair the Growth Controller (west of the root wall), or coat the roots with resin and burn through.",
            "roots_weakened": "The roots are coated with resin. A torch should catch now.",
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

def handle_quest_use(item_id, target, room_id, game_state, character, rooms=None):
    """Handle targeted item USE for quests (USE <item> ON <target>).

    Returns (handled: bool, consumed: bool) — caller handles inventory
    removal if consumed.
    """
    quest = game_state.get("quests", {}).get("verdant_bloom", {})

    # PATH B (forceful) — resin + torch on roots at root wall
    # Auto-starts quest if player figures out the solution without talking to Lira
    if room_id == "vw_root_wall" and target in ("roots", "root", "root wall"):
        if item_id == "resin" and not quest.get("roots_weakened"):
            # Auto-start quest if player figured this out on their own
            if quest.get("status") != "active":
                _auto_start_quest(game_state, rooms)
                quest = game_state["quests"]["verdant_bloom"]
            display.narrate("You smear the resin across the thick roots, working it into")
            display.narrate("the bark. The sticky coating soaks into every crack and fiber,")
            display.narrate("turning the damp surface dark and glossy.")
            display.info("  The roots are coated. A flame should catch now.")
            quest["roots_weakened"] = True
            return True, True  # consume resin

        if item_id == "torch" and quest.get("roots_weakened") and not quest.get("roots_cleared"):
            if quest.get("status") != "active":
                _auto_start_quest(game_state, rooms)
                quest = game_state["quests"]["verdant_bloom"]
            display.narrate("You hold the torch to the resin-coated roots. They catch")
            display.narrate("instantly, curling and blackening. In moments, a narrow")
            display.narrate("passage opens to the north, revealing a green glow beyond.")
            print()
            display.warning("The fire doesn't stop. It leaps to the canopy overhead,")
            display.warning("racing along dry vines. Smoke billows through the corridor.")
            display.warning("You need to get the bloom and get out. Fast.")
            quest["roots_cleared"] = True
            quest["path"] = "forceful"
            quest["biodome_burning"] = True
            _set_fire_aspects(game_state, rooms)
            return True, False  # torch not consumed

        if item_id == "torch" and not quest.get("roots_weakened"):
            display.narrate("You hold the torch to the roots, but they're too thick")
            display.narrate("and damp to catch. The flame licks the bark and dies.")
            display.info("  You'd need something flammable to coat them first.")
            return True, False

    # PATH A (careful) — basic_tools on console at control room
    if room_id == "vw_control" and target in ("console", "controller", "growth controller", "panel"):
        if item_id == "basic_tools" and not quest.get("roots_cleared"):
            if quest.get("status") != "active":
                _auto_start_quest(game_state, rooms)
                quest = game_state["quests"]["verdant_bloom"]
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


def _auto_start_quest(game_state, rooms):
    """Silently activate the verdant_bloom quest when the player solves it without talking to Lira."""
    game_state.setdefault("quests", {})["verdant_bloom"] = {
        "status": "active",
        "roots_weakened": False,
        "roots_cleared": False,
        "path": None,
        "control_revealed": False,
    }
    # Also reveal the control room exit since Lira won't get to
    if rooms:
        root_wall = rooms.get("vw_root_wall")
        if root_wall and "west" not in root_wall.exits:
            root_wall.exits["west"] = "vw_control"
            game_state["quests"]["verdant_bloom"]["control_revealed"] = True


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
            if quest.get("lira_witnessed_fire"):
                return {"lines": [dialogue.get("quest_forceful_done_witnessed", dialogue.get("quest_forceful_done", "..."))]}
            return {"lines": [dialogue.get("quest_forceful_done", "...")]}
        return {"lines": [dialogue.get("quest_complete", "...")]}

    # Quest not started — ask tools question, don't start quest yet
    if quest.get("status") != "active":
        already_asked = game_state.get("lira_tools_asked")
        if already_asked:
            # Re-talk after walking away — just the question, no greeting
            lines = [dialogue.get("quest_intro", "...")]
        else:
            # First time — greeting + question
            lines = [
                dialogue.get("greeting", "..."),
                dialogue.get("quest_intro", "..."),
            ]
            game_state["lira_tools_asked"] = True
        # Set pending question for SAY response
        game_state["pending_npc_question"] = {
            "npc_id": "lira",
            "key": "tools_question",
            "room_id": "vw_greenhouse",
        }
        return {"lines": lines, "say_hint": True}

    # Quest active, roots cleared — show completion dialogue
    if quest.get("roots_cleared"):
        return {"lines": [dialogue.get("quest_complete", "...")]}

    # Quest active, in progress — repeat options
    return {"lines": [dialogue.get("quest_options", "...")]}


def handle_lira_say(answer, npc, game_state, rooms):
    """Handle the player's SAY response to Lira's tools question.

    Returns dict with lines + effects, or None if answer not recognized.
    """
    dialogue = npc.get("dialogue", {})
    yes_words = {"yes", "y", "yeah", "yep", "yea", "sure", "aye"}
    no_words = {"no", "n", "nope", "nah", "nay"}

    if answer in yes_words:
        line = dialogue.get("quest_reply_yes", "...")
    elif answer in no_words:
        line = dialogue.get("quest_reply_no", "...")
    else:
        return None  # unrecognized answer

    return {
        "lines": [line],
        "quest_started": True,
        "reveal_exit": ("vw_root_wall", "west", "vw_control"),
    }


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


# ── Biodome Fire ─────────────────────────────────────────────

FIRE_ASPECTS = {
    "vw_root_wall": ["Charred Passage", "Smoke Pouring Through the Gap"],
    "vw_greenhouse": ["The Canopy Is on Fire", "Burning Debris Falling From Above"],
    "vw_promenade": ["Choking Smoke Fills the Corridor"],
    "vw_airlock": ["Heat at Your Back"],
}

FIRE_COMPELS = {
    "vw_root_wall": {
        "aspect": "Smoke Pouring Through the Gap",
        "text": "Thick smoke rolls through the passage. Every breath burns.",
        "accept_text": "You push through the smoke, lungs screaming. The heat sears your arms as you stumble past the charred roots.",
        "accept_effect": "take_stress",
        "stress": 1,
    },
    "vw_greenhouse": {
        "aspect": "The Canopy Is on Fire",
        "text": "Burning branches crash down around you. The greenhouse is an inferno.",
        "accept_text": "A flaming branch clips your shoulder. You stagger but keep moving, sparks in your hair.",
        "accept_effect": "take_stress",
        "stress": 1,
    },
    "vw_promenade": {
        "aspect": "Choking Smoke Fills the Corridor",
        "text": "You can barely see the floor. The smoke is so thick your eyes stream.",
        "accept_text": "You drop low and crawl, but the heat blisters your hands on the tiles. You make it through, coughing.",
        "accept_effect": "take_stress",
        "stress": 1,
    },
}


def _set_fire_aspects(game_state, rooms=None):
    """Set fire aspects on multiple rooms after burning the roots."""
    for room_id, new_aspects in FIRE_ASPECTS.items():
        _update_room_aspect(game_state, room_id, new_aspects, rooms)


def check_fire_compel(game):
    """Check if the current room has a fire hazard compel.

    Returns compel data dict (same shape as character compels) or None.
    """
    quest = game.state.get("quests", {}).get("verdant_bloom", {})
    if not quest.get("biodome_burning"):
        return None

    room = game.current_room()
    if not room:
        return None

    compel = FIRE_COMPELS.get(room.id)
    if not compel:
        return None

    return dict(compel)


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
