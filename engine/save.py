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
    for f in sorted(SAVE_DIR.glob("*.json")):
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
    # Add worn dict for old saves
    for char_key in ("explorer", "steward"):
        if char_key in state:
            state[char_key].setdefault("worn", {})
    # Tutorial state fields
    state.setdefault("tutorial_combat_done", False)
    state.setdefault("tutorial_invoke_done", False)
    state.setdefault("tutorial_scavenge_done", False)
    state.setdefault("tutorial_artifact_found", False)
    state.setdefault("tutorial_artifact_resolved", False)
    state.setdefault("tutorial_recruit_done", False)
    state.setdefault("tutorial_exploit_done", False)
    # Ensure basic_tools recipe is known
    if "basic_tools" not in state.get("discovered_recipes", []):
        state.setdefault("discovered_recipes", []).append("basic_tools")
    # Rename old "scavenging" task to "salvage" + ensure recruit_attempts exists
    for npc_id, npc in state.get("npcs", {}).items():
        if npc.get("assignment") == "scavenging":
            npc["assignment"] = "salvage"
        npc.setdefault("recruit_attempts", 0)
        npc.setdefault("following", False)
    # Place zone-bound artifacts into room items (old saves stored them separately)
    artifacts = state.get("artifacts", {})
    artifacts_status = state.get("artifacts_status", {})
    all_rooms = state.get("rooms", {})
    for art_id, art in artifacts.items():
        room_id = art.get("room")
        if not room_id:
            continue
        if artifacts_status.get(art_id) in ("kept", "fed"):
            continue  # already picked up
        if room_id in all_rooms:
            room_items = all_rooms[room_id].setdefault("items", [])
            if art_id not in room_items:
                room_items.append(art_id)


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


def new_game_state():
    """Create a fresh game state from data files."""
    characters = load_data_file("characters.json")
    zones = load_data_file("zones.json")
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

    # Place zone-bound artifacts into their rooms
    for art_id, art in artifacts.items():
        room_id = art.get("room")
        if room_id and room_id in all_rooms:
            room = all_rooms[room_id]
            if art_id not in room.get("items", []):
                room.setdefault("items", []).append(art_id)

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
        "event_log": [f"Day 1: You arrived at the skerry, a tiny island of solid ground in the endless void."],
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
        "discovered_recipes": ["rope", "torch", "basic_tools"],  # Start knowing basic recipes
    }
    return state
