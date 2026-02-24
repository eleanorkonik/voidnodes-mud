"""Save/Load system — JSON serialization for game state."""

import json
import os
from pathlib import Path

SAVE_DIR = Path(__file__).parent.parent / "saves"
DATA_DIR = Path(__file__).parent.parent / "data"


def ensure_save_dir():
    """Create saves directory if it doesn't exist."""
    SAVE_DIR.mkdir(exist_ok=True)


def _migrate_save_filenames():
    """Auto-fix any save files whose filename doesn't match their world_seed_name."""
    ensure_save_dir()
    for f in list(SAVE_DIR.glob("*.json")):
        try:
            with open(f) as fh:
                data = json.load(fh)
            seed_name = data.get("world_seed_name")
            if not seed_name:
                continue
            correct_slug = _slot_name_for(seed_name)
            if f.stem != correct_slug:
                new_path = SAVE_DIR / f"{correct_slug}.json"
                if not new_path.exists():
                    f.rename(new_path)
        except (json.JSONDecodeError, KeyError):
            pass


def list_saves():
    """List available save files. Returns list of (filename, metadata) tuples."""
    _migrate_save_filenames()
    saves = []
    for f in sorted(SAVE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(f) as fh:
                data = json.load(fh)
            saves.append((f.stem, {
                "day": data.get("day", 1),
                "phase": data.get("current_phase", "explorer"),
                "seed_name": data.get("world_seed_name", "Tuft"),
            }))
        except (json.JSONDecodeError, KeyError):
            saves.append((f.stem, {"day": "?", "phase": "?"}))
    return saves


def _slot_name_for(seed_name):
    """Derive a save file slug from the world seed name."""
    return seed_name.lower().replace(" ", "-")


def seed_name_taken(name):
    """Check if a save file already exists for this world seed name."""
    ensure_save_dir()
    filepath = SAVE_DIR / f"{_slot_name_for(name)}.json"
    return filepath.exists()


def save_game(state):
    """Save game state to a JSON file named after the world seed."""
    ensure_save_dir()
    seed_name = state.get("world_seed_name", "Tuft")
    slot = _slot_name_for(seed_name)
    filepath = SAVE_DIR / f"{slot}.json"
    with open(filepath, "w") as f:
        json.dump(state, f, indent=2)
    return filepath


def load_game(slot_name):
    """Load game state from a JSON file. Returns None if not found."""
    filepath = SAVE_DIR / f"{slot_name}.json"
    if not filepath.exists():
        return None
    with open(filepath) as f:
        state = json.load(f)
    _migrate_state(state)
    return state


def _migrate_state(state):
    """Migrate old save data to current format."""
    # Rename homekeeper → steward
    if "homekeeper" in state and "steward" not in state:
        state["steward"] = state.pop("homekeeper")
    if "homekeeper_location" in state:
        state["steward_location"] = state.pop("homekeeper_location")
    if state.get("current_phase") == "homekeeper":
        state["current_phase"] = "steward"
    # Migrate event keys
    events = state.get("events", {})
    if "homekeeper_events" in events and "steward_events" not in events:
        events["steward_events"] = events.pop("homekeeper_events")
    # Rename tuft → seed
    if "tuft" in state and "seed" not in state:
        state["seed"] = state.pop("tuft")
    if "bonded_with_tuft" in state:
        state["bonded_with_seed"] = state.pop("bonded_with_tuft")
    # Add new fields with defaults
    state.setdefault("explorer_name", "Sevarik")
    state.setdefault("steward_name", "Miria")
    state.setdefault("agents", {})
    # Add worn dict and slot capacity for old saves
    for char_key in ("explorer", "steward"):
        if char_key in state:
            state[char_key].setdefault("worn", {})
            state[char_key].setdefault("slot_capacity", {"large": 1, "medium": 2, "small": 20})
    # Tutorial state fields
    state.setdefault("tutorial_combat_done", False)
    state.setdefault("tutorial_invoke_done", False)
    state.setdefault("tutorial_scavenge_done", False)
    state.setdefault("tutorial_artifact_found", False)
    state.setdefault("tutorial_artifact_resolved", False)
    state.setdefault("tutorial_recruit_done", False)
    state.setdefault("tutorial_exploit_done", False)
    state.setdefault("tutorial_quest_done", False)
    state.setdefault("tutorial_settle_done", False)
    state.setdefault("quests", {})
    # Healing system fields
    state.setdefault("zones_cleared", 0)
    state.setdefault("consequence_meta", {})
    # Zone unloading
    state.setdefault("unloaded_zones", [])
    # Ensure basic_tools and bandages recipes are known
    for recipe_id in ("basic_tools", "bandages"):
        if recipe_id not in state.get("discovered_recipes", []):
            state.setdefault("discovered_recipes", []).append(recipe_id)
    # Farming system fields
    skerry_state = state.get("skerry", {})
    skerry_state.setdefault("food_stores", [])
    skerry_state.setdefault("garden", {"plots": [], "max_plots": 4})
    skerry_state.setdefault("seed_vault", [])
    skerry_state.setdefault("dynamic_aspects", [])
    # Rename old task names + ensure NPC fields exist
    for npc_id, npc in state.get("npcs", {}).items():
        if npc.get("assignment") == "scavenging":
            npc["assignment"] = "salvage"
        if npc.get("assignment") == "building":
            npc["assignment"] = "idle"
        if npc.get("assignment") == "resting":
            npc["assignment"] = "communal"
        npc.setdefault("recruit_attempts", 0)
        npc.setdefault("following", False)
        npc.setdefault("settled_room", None)
        npc.setdefault("assigned_subtask", None)
    # Ensure skerry rooms have role/barracks_spaces/tool_level fields
    _room_defaults = {
        "skerry_central": {"role": None},
        "skerry_shelter": {"role": "communal", "barracks_spaces": 2},
        "skerry_hollow": {"role": None},
        "skerry_junkyard": {"role": "salvage"},
        "skerry_landing": {"role": None},
        "skerry_storehouse": {"role": "organize"},
        "skerry_workshop": {"role": "craft", "tool_level": 0},
        "skerry_garden": {"role": "garden"},
        "skerry_water": {"role": "gather"},
        "skerry_lookout": {"role": "guard"},
    }
    skerry_data = state.get("skerry", {})
    for room_data in skerry_data.get("rooms", []):
        rid = room_data.get("id", "")
        defaults = _room_defaults.get(rid, {})
        for key, val in defaults.items():
            room_data.setdefault(key, val)
        room_data.setdefault("role", None)
        room_data.setdefault("barracks_spaces", 0)
        room_data.setdefault("tool_level", 0)
        # Migrate old "rest" role → "communal"
        if room_data.get("role") == "rest":
            room_data["role"] = "communal"
    for tmpl in skerry_data.get("expandable_rooms", []):
        rid = tmpl.get("id", "")
        defaults = _room_defaults.get(rid, {})
        for key, val in defaults.items():
            tmpl.setdefault(key, val)
    # Workshop queue
    state.setdefault("workshop_queue", [])
    # Ensure new workshop recipes are discoverable (added with workshop build)
    # Migrate event_log: convert old string entries to dicts
    event_log = state.get("event_log", [])
    for i, entry in enumerate(event_log):
        if isinstance(entry, str):
            event_log[i] = {
                "day": state.get("day", 1),
                "phase": "unknown",
                "type": "legacy",
                "actor": "unknown",
                "location": "unknown",
                "comic_weight": 1,
                "details": entry,
            }
    # Migrate artifact fields to location dict
    artifacts = state.get("artifacts", {})
    all_rooms = state.get("rooms", {})
    artifacts_status = state.get("artifacts_status", {})
    for art_id, art in artifacts.items():
        # Convert old room/spawn_spot field → location dict
        if "location" not in art:
            room_id = art.get("spawn_spot") or art.get("room")
            if room_id:
                art["location"] = {"type": "room", "id": room_id}
            else:
                art["location"] = None
        art.pop("room", None)
        art.pop("zone", None)
        art.pop("spawn_spot", None)
        # If artifact was resolved, clear its location
        if artifacts_status.get(art_id) in ("kept", "fed", "given"):
            if art_id in (art.get("location") or {}).get("id", ""):
                pass  # leave as-is if in inventory
            # For kept artifacts, location is the character's inventory
            # For fed artifacts, location is null (consumed)
            if artifacts_status.get(art_id) == "fed":
                art["location"] = None
        # Remove artifact from room.items (artifacts are no longer displayed in rooms)
        for room in all_rooms.values():
            room_items = room.get("items", [])
            if art_id in room_items:
                room_items.remove(art_id)


def delete_save(slot_name):
    """Delete a save file."""
    filepath = SAVE_DIR / f"{slot_name}.json"
    if filepath.exists():
        os.remove(filepath)
        return True
    return False


def load_data_file(filename):
    """Load a data file from the data/ directory."""
    filepath = DATA_DIR / filename
    with open(filepath) as f:
        return json.load(f)


def _load_zones():
    """Load all zone files from data/zones/ directory. Returns dict keyed by zone id."""
    zones_dir = DATA_DIR / "zones"
    zones = {}
    for zone_file in sorted(zones_dir.glob("*.json")):
        with open(zone_file) as f:
            zone_data = json.load(f)
        zone_id = zone_data["id"]
        zones[zone_id] = zone_data
    return zones


def new_game_state():
    """Create a fresh game state from data files."""
    characters = load_data_file("characters.json")
    zones = _load_zones()
    skerry = load_data_file("skerry.json")
    npcs = load_data_file("npcs.json")
    items = load_data_file("items.json")
    artifacts = load_data_file("artifacts.json")
    recipes = load_data_file("recipes.json")
    seed_data = load_data_file("tuft.json")  # data file keeps its name
    events = load_data_file("events.json")

    # Build room lookup from zones
    all_rooms = {}
    for zone_id, zone in zones.items():
        for room in zone["rooms"]:
            all_rooms[room["id"]] = room

    # Add skerry rooms
    for room in skerry["rooms"]:
        all_rooms[room["id"]] = room

    # Build enemy lookup from zones
    enemies_db = {}
    for zone_id, zone in zones.items():
        for enemy in zone.get("enemies_data", []):
            enemies_db[enemy["id"]] = enemy

    state = {
        "version": 1,
        "day": 1,
        "current_phase": "prologue",
        "explorer": characters["sevarik"],
        "steward": characters["miria"],
        "seed": seed_data,
        "skerry": skerry,
        "npcs": npcs,
        "zones": zones,
        "rooms": all_rooms,
        "items_db": items,
        "artifacts": artifacts,
        "recipes": recipes,
        "events": events,
        "enemies_db": enemies_db,
        "artifacts_status": {},  # tracks discovered/kept/fed
        "event_log": [{"day": 1, "phase": "prologue", "type": "game_start", "actor": "miria",
                       "location": "skerry_central", "comic_weight": 5,
                       "details": "Arrived at the skerry, a tiny island of solid ground in the endless void."}],
        "extractions": 0,
        "explorer_location": "skerry_shelter",
        "steward_location": "skerry_central",
        "prologue_location": "skerry_central",
        "tutorial_step": "awakening",
        "tutorial_complete": False,
        "bonded_with_seed": False,
        "explorer_name": "Sevarik",
        "steward_name": "Miria",
        "world_seed_name": "Tuft",
        "recruited_npcs": [],
        "discovered_recipes": ["rope", "torch", "basic_tools", "bandages"],  # Start knowing basic recipes
        "zones_cleared": 0,
        "consequence_meta": {},  # {char_severity: {taken_at: N, cure: item_id}}
    }
    return state
