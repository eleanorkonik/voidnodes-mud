"""Subtask queue system — structured NPC production per room role."""

import json
import random
from pathlib import Path

from engine import dice, farming

# Crafting material IDs — items that should be hauled to the workshop
CRAFTING_MATERIALS = {
    "metal_scraps", "wire", "torn_fabric", "coral_fragments",
    "crystal_shards", "frozen_water", "ancient_alloys", "rope",
    "hide", "bone", "resin", "luminous_moss",
}

# Healing material IDs — items that should be hauled to the apothecary
HEALING_MATERIALS = {
    "luminous_extract", "tuber_skin_compound", "bandages", "poultice",
}

DATA_DIR = Path(__file__).parent.parent / "data"

_subtask_defs = None


def _load_subtask_defs():
    """Load subtask definitions from data/subtasks.json. Cached."""
    global _subtask_defs
    if _subtask_defs is None:
        with open(DATA_DIR / "subtasks.json") as f:
            _subtask_defs = json.load(f)
    return _subtask_defs


def get_subtasks_for_role(role):
    """Get subtask definitions for a room role, sorted by order."""
    defs = _load_subtask_defs()
    subtasks = defs.get(role, [])
    return sorted(subtasks, key=lambda s: s["order"])


def get_all_subtask_ids():
    """Return a set of all subtask IDs across all roles."""
    defs = _load_subtask_defs()
    ids = set()
    for role_subtasks in defs.values():
        for st in role_subtasks:
            ids.add(st["id"])
    return ids


def find_subtask_role(subtask_id):
    """Find which role a subtask belongs to. Returns (role, subtask_def) or (None, None)."""
    defs = _load_subtask_defs()
    for role, subtasks in defs.items():
        for st in subtasks:
            if st["id"] == subtask_id:
                return role, st
    return None, None


# ── Conditions ───────────────────────────────────────────────

def _check_condition(condition_name, game, room, npc):
    """Evaluate a named condition. None = always true."""
    if condition_name is None:
        return True
    fn = CONDITIONS.get(condition_name)
    if fn is None:
        return True  # unknown condition → allow
    return fn(game, room, npc)


def _has_planted_plots(game, room, npc):
    plots = game.skerry.get_garden_plots()
    return any(p.get("plant") is not None for p in plots)


def _has_harvestable_plots(game, room, npc):
    plots = game.skerry.get_garden_plots()
    return any(farming.is_harvestable(p) for p in plots)


def _has_empty_plots_and_specimens(game, room, npc):
    plots = game.skerry.get_garden_plots()
    has_empty = any(p.get("plant") is None for p in plots)
    if not has_empty:
        return False
    specimen_ids = [item_id for item_id in game.steward.inventory
                    if farming.is_specimen(item_id)]
    return len(specimen_ids) > 0


def _room_has_items(game, room, npc):
    return len(room.items) > 0


def _room_has_materials(game, room, npc):
    """Workshop has materials to craft with — checks room items for raw materials."""
    return any(item_id in CRAFTING_MATERIALS for item_id in room.items)


def _tools_not_maxed(game, room, npc):
    return room.tool_level < 3


def _has_delivery_targets(game, room, npc):
    """At least one delivery target room exists on the skerry."""
    for r in game.skerry.get_all_rooms():
        if r.id == "skerry_workshop" or r.id == "skerry_garden":
            return True
    return False


def _has_wounded(game, room, npc):
    """Any character has a consequence that could benefit from tending."""
    for char_key in ("explorer", "steward"):
        char_data = game.state.get(char_key, {})
        cons = char_data.get("consequences", {})
        if any(v is not None for v in cons.values()):
            return True
    return False


def _room_has_fabric(game, room, npc):
    """Room has torn_fabric for brewing bandages."""
    return "torn_fabric" in room.items


def _healing_level_1(game, room, npc):
    """Apothecary upgraded to infirmary (healing_level >= 1)."""
    return room.healing_level >= 1


def _healing_level_2(game, room, npc):
    """Apothecary upgraded to hospital (healing_level >= 2)."""
    return room.healing_level >= 2


def _has_perishable_food(game, room, npc):
    return any(e.get("shelf_life", -1) > 0 for e in game.skerry.food_stores)


CONDITIONS = {
    "has_planted_plots": _has_planted_plots,
    "has_harvestable_plots": _has_harvestable_plots,
    "has_empty_plots_and_specimens": _has_empty_plots_and_specimens,
    "room_has_items": _room_has_items,
    "room_has_materials": _room_has_materials,
    "tools_not_maxed": _tools_not_maxed,
    "has_perishable_food": _has_perishable_food,
    "has_delivery_targets": _has_delivery_targets,
    "has_wounded": _has_wounded,
    "room_has_fabric": _room_has_fabric,
    "healing_level_1": _healing_level_1,
    "healing_level_2": _healing_level_2,
}


# ── Handlers ─────────────────────────────────────────────────
# Each takes (game, room, npc, shifts) → list of display messages.

def _npc_skill(npc, skill_name):
    """Get an NPC's skill value by name."""
    return npc.get("skills", {}).get(skill_name, 0)


def _handler_water_plants(game, room, npc, shifts):
    """Boost growth on all planted plots."""
    plots = game.skerry.get_garden_plots()
    watered = 0
    for plot in plots:
        if plot.get("plant") and plot["plant"]["growth"] < plot["plant"]["growth_needed"]:
            plot["plant"]["growth"] = min(
                plot["plant"]["growth_needed"],
                plot["plant"]["growth"] + 1
            )
            watered += 1
    if watered:
        return [f"Watered {watered} plot{'s' if watered != 1 else ''}."]
    return []


def _handler_fertilize_soil(game, room, npc, shifts):
    """Improve soil nutrients on planted plots."""
    plots = game.skerry.get_garden_plots()
    fertilized = 0
    boost = max(1, 1 + shifts)
    for plot in plots:
        if plot.get("plant"):
            for nutrient in ("n", "p", "k"):
                plot["soil"][nutrient] = min(20, plot["soil"][nutrient] + boost)
            fertilized += 1
    if fertilized:
        return [f"Fertilized {fertilized} plot{'s' if fertilized != 1 else ''} (+{boost} nutrients)."]
    return []


def _handler_harvest_crops(game, room, npc, shifts):
    """Harvest mature plants."""
    plots = game.skerry.get_garden_plots()
    day = game.state["day"]
    messages = []
    for plot in plots:
        if farming.is_harvestable(plot):
            result = farming.harvest_plot(plot, day)
            if result:
                food, utility = result
                farming.add_to_stores(game.skerry.food_stores, food, day)
                food_name = food.get("name", food["id"])
                qty = food.get("quantity", 1)
                messages.append(f"Harvested {food_name} x{qty} → food stores")
                if utility:
                    util_name = utility.get("name", utility["id"])
                    util_qty = utility.get("quantity", 1)
                    for _ in range(util_qty):
                        game.steward.add_to_inventory(utility["id"])
                    messages.append(f"Byproduct: {util_name} x{util_qty}")
    return messages


def _handler_plant_seeds(game, room, npc, shifts):
    """Plant specimens from steward inventory into empty plots."""
    plots = game.skerry.get_garden_plots()
    day = game.state["day"]
    specimen_ids = [item_id for item_id in game.steward.inventory
                    if farming.is_specimen(item_id)]
    planted = farming.npc_auto_plant(plots, specimen_ids, day)
    messages = []
    for plot_id, spec_id in planted:
        game.steward.remove_from_inventory(spec_id)
        spec = game.specimens_db.get(spec_id, {})
        spec_name = spec.get("name", spec_id)
        messages.append(f"Planted {spec_name} in plot {plot_id}.")
    return messages


def _handler_sort_salvage(game, room, npc, shifts):
    """Process remnants in the room first; fall back to random scrap generation."""
    # Check for remnants to process
    for item_id in list(room.items):
        item = game.items_db.get(item_id, {})
        if item.get("type") == "remnants":
            process_dc = item.get("process_dc", 1)
            skill_val = _npc_skill(npc, "Crafts")
            total, proc_shifts, dice_result = dice.skill_check(skill_val, process_dc)
            room.remove_item(item_id)
            remnant_name = item.get("name", item_id)
            verb = item.get("process_verb", "processed")
            if proc_shifts >= 0:
                messages = [f"{verb.capitalize()} {remnant_name}:"]
                for yield_id, yield_count in item.get("process_yields", []):
                    for _ in range(yield_count):
                        room.add_item(yield_id)
                    yield_name = game.items_db.get(yield_id, {}).get("name", yield_id)
                    messages.append(f"  +{yield_count}x {yield_name}")
                return messages
            else:
                # Failed — salvage first yield only
                process_yields = item.get("process_yields", [])
                if process_yields:
                    salvage_id = process_yields[0][0]
                    room.add_item(salvage_id)
                    salvage_name = game.items_db.get(salvage_id, {}).get("name", salvage_id)
                    return [f"Botched {verb} on {remnant_name} — salvaged 1x {salvage_name}"]
                return [f"Botched {verb} on {remnant_name} — nothing salvaged."]
    # No remnants — generate random scrap
    loot = random.choice(["metal_scraps", "wire", "torn_fabric", "coral_fragments"])
    room.add_item(loot)
    loot_name = game.items_db.get(loot, {}).get("name", loot)
    return [f"Processed: {loot_name}"]


def _handler_strip_components(game, room, npc, shifts):
    """Break down room items into rarer parts."""
    if not room.items:
        return []
    # Strip one basic material into a rarer component
    strippable = {"metal_scraps": "ancient_alloys", "coral_fragments": "crystal_shards",
                  "wire": "crystal_shards", "torn_fabric": "rope"}
    for item_id in list(room.items):
        if item_id in strippable:
            room.remove_item(item_id)
            result = strippable[item_id]
            room.add_item(result)
            source_name = game.items_db.get(item_id, {}).get("name", item_id)
            result_name = game.items_db.get(result, {}).get("name", result)
            return [f"Stripped {source_name} → {result_name}"]
    return []


def _handler_haul_materials(game, room, npc, shifts):
    """Move processed materials from junkyard to destination rooms based on type."""
    # Build routing: item type → destination room
    routes = []
    workshop = game.skerry.get_room("skerry_workshop")
    garden = game.skerry.get_room("skerry_garden")

    apothecary = game.skerry.get_room("skerry_apothecary")

    if workshop:
        routes.append((CRAFTING_MATERIALS, workshop))
    if apothecary:
        routes.append((HEALING_MATERIALS, apothecary))
    if garden:
        specimens_set = set(game.specimens_db.keys()) if hasattr(game, 'specimens_db') else set()
        if specimens_set:
            routes.append((specimens_set, garden))

    if not routes:
        return []

    hauled = []
    for item_id in list(room.items):
        for valid_ids, dest_room in routes:
            if item_id in valid_ids:
                room.remove_item(item_id)
                dest_room.add_item(item_id)
                item_name = game.items_db.get(item_id, {}).get("name", item_id)
                dest_name = dest_room.name
                hauled.append(f"{item_name} → {dest_name}")
                break

    if hauled:
        summary = ', '.join(hauled[:3])
        if len(hauled) > 3:
            summary += f" (+{len(hauled) - 3} more)"
        return [f"Hauled: {summary}"]
    return []


def _load_recipes():
    """Load recipes from data/recipes.json. Cached."""
    with open(DATA_DIR / "recipes.json") as f:
        return json.load(f)


def _handler_craft_supplies(game, room, npc, shifts):
    """Auto-craft from the workshop queue, falling back to random scrap crafting."""
    # Check for a player-set queue
    queue = game.state.get("workshop_queue", [])
    recipes = game.recipes_db if hasattr(game, 'recipes_db') else _load_recipes()

    # Tool level bonus for workshop
    tool_bonus = 0
    if room.id == "skerry_workshop":
        tool_bonus = 1 + room.tool_level

    # Try each queued recipe in order
    for recipe_id in queue:
        recipe = recipes.get(recipe_id)
        if not recipe:
            continue
        # Check if all materials are in the room
        materials = recipe.get("materials", {})
        has_all = all(
            sum(1 for i in room.items if i == mat) >= needed
            for mat, needed in materials.items()
        )
        if not has_all:
            continue

        # Skill check with tool bonus
        dc = recipe.get("difficulty", 1)
        skill_name = recipe.get("skill", "Crafts")
        skill_val = _npc_skill(npc, skill_name) + tool_bonus
        total, craft_shifts, dice_result = dice.skill_check(skill_val, dc)

        if craft_shifts >= 0:
            # Consume materials
            for mat, needed in materials.items():
                for _ in range(needed):
                    room.remove_item(mat)
            result_id = recipe["result"]
            room.add_item(result_id)
            result_name = game.items_db.get(result_id, {}).get("name", result_id)
            return [f"Crafted: {result_name} (from queue)"]
        else:
            recipe_name = recipe.get("name", recipe_id)
            return [f"Failed to craft {recipe_name} (DC {dc})."]

    # Fallback: random scrap crafting (original behavior)
    craftable = {
        "metal_scraps": ["basic_tools", "shelter_patch"],
        "rope": ["shelter_patch"],
        "wire": ["basic_tools"],
    }
    for item_id in list(room.items):
        if item_id in craftable:
            room.remove_item(item_id)
            product = random.choice(craftable[item_id])
            room.add_item(product)
            product_name = game.items_db.get(product, {}).get("name", product)
            return [f"Crafted: {product_name}"]
    return []


def _handler_improve_tools(game, room, npc, shifts):
    """Upgrade the workshop's tool level."""
    if room.tool_level >= 3:
        return []
    room.tool_level += 1
    return [f"Workshop tools improved! Tool level: {room.tool_level}"]


def _handler_collect_water(game, room, npc, shifts):
    """Collect frozen water."""
    room.add_item("frozen_water")
    return ["Gathered: Frozen Water"]


def _handler_align_crystals(game, room, npc, shifts):
    """Improve collection — bonus water on success."""
    bonus = max(1, 1 + shifts)
    for _ in range(bonus):
        room.add_item("frozen_water")
    return [f"Crystal alignment improved — {bonus} bonus Frozen Water."]


def _handler_organize_stores(game, room, npc, shifts):
    """Extend shelf life of stored food."""
    extended = 0
    for entry in game.skerry.food_stores:
        sl = entry.get("shelf_life", -1)
        if sl > 0:
            entry["shelf_life"] += 1
            extended += 1
    if extended:
        return [f"Extended shelf life on {extended} food item{'s' if extended != 1 else ''}."]
    return ["Storehouse is in good order."]


def _handler_preserve_food(game, room, npc, shifts):
    """Treat perishable food to extend shelf life further."""
    preserved = 0
    bonus = max(2, 2 + shifts)
    for entry in game.skerry.food_stores:
        sl = entry.get("shelf_life", -1)
        if sl > 0:
            entry["shelf_life"] += bonus
            preserved += 1
    if preserved:
        return [f"Preserved {preserved} item{'s' if preserved != 1 else ''} (+{bonus} days shelf life)."]
    return []


def _handler_scan_horizon(game, room, npc, shifts):
    """Detect events early."""
    if shifts >= 1:
        return ["Spotted something interesting on the horizon — the colony is forewarned."]
    return ["Kept watch. Nothing unusual spotted."]


def _handler_maintain_post(game, room, npc, shifts):
    """Reinforce the lookout."""
    return ["Lookout post maintained and reinforced."]


def _handler_tidy_up(game, room, npc, shifts):
    """Clean the shelter for morale."""
    for nid in game.state.get("recruited_npcs", []):
        n = game.npcs_db.get(nid, {})
        if n.get("mood") == "restless":
            n["mood"] = "content"
    return ["Tidied up the shelter. Everyone feels a bit better."]


def _handler_create_art(game, room, npc, shifts):
    """Create art for bigger morale boost."""
    boosted = 0
    for nid in game.state.get("recruited_npcs", []):
        n = game.npcs_db.get(nid, {})
        if n.get("mood") in ("restless", "content"):
            n["mood"] = "happy"
            boosted += 1
    if boosted:
        return [f"Created something beautiful. {boosted} NPC{'s' if boosted != 1 else ''} feel happier."]
    return ["Created something beautiful, but everyone was already in good spirits."]


def _handler_tend_shelves(game, room, npc, shifts):
    """Organize shared items for loyalty boost."""
    boosted = 0
    for nid in game.state.get("recruited_npcs", []):
        n = game.npcs_db.get(nid, {})
        n["loyalty"] = min(10, n.get("loyalty", 0) + 1)
        boosted += 1
    if boosted:
        return [f"Organized the communal shelves. +1 loyalty for {boosted} NPC{'s' if boosted != 1 else ''}."]
    return []


def _handler_tend_wounds(game, room, npc, shifts):
    """Help mild consequences heal faster — reduces zone-clear requirement by 1."""
    from engine import aspects
    messages = []
    zones_cleared = game.state.get("zones_cleared", 0)
    meta = game.state.get("consequence_meta", {})
    # Check both characters for mild consequences
    for char_key in ("explorer", "steward"):
        char_data = game.state.get(char_key, {})
        cons = char_data.get("consequences", {})
        mild = cons.get("mild")
        if not mild:
            continue
        meta_key = f"{char_key}_mild"
        entry = meta.get(meta_key, {})
        taken_at = entry.get("taken_at", 0)
        required = aspects.ZONE_CLEARS_REQUIRED["mild"]
        # Apothecary tier 1+ reduces requirement by 1
        if room.healing_level >= 1:
            required = max(0, required - 1)
        remaining = max(0, required - (zones_cleared - taken_at))
        char_name = game.state.get(f"{char_key}_name", char_key.capitalize())
        if remaining <= 0:
            # Heal it
            cons["mild"] = None
            meta.pop(meta_key, None)
            messages.append(f"{char_name}'s mild injury ({mild}) has healed.")
        else:
            messages.append(f"Tending {char_name}'s wounds. {remaining} zone clear{'s' if remaining != 1 else ''} until healed.")
    if not messages:
        messages.append("No injuries to tend. Organized supplies instead.")
    return messages


def _handler_brew_remedies(game, room, npc, shifts):
    """Auto-craft bandages from torn_fabric in the room."""
    if "torn_fabric" not in room.items:
        return []
    # Consume 2 fabric → 1 bandage (same as recipe)
    count = sum(1 for i in room.items if i == "torn_fabric")
    if count >= 2:
        room.remove_item("torn_fabric")
        room.remove_item("torn_fabric")
        room.add_item("bandages")
        return ["Brewed: Bandages (from 2x Torn Fabric)"]
    return []


def _handler_prepare_poultice(game, room, npc, shifts):
    """Craft a poultice from plant extracts in the room."""
    # Check for luminous_extract or tuber_skin_compound + torn_fabric
    has_fabric = "torn_fabric" in room.items
    if not has_fabric:
        return []
    for extract in ("luminous_extract", "tuber_skin_compound"):
        if extract in room.items:
            room.remove_item(extract)
            room.remove_item("torn_fabric")
            room.add_item("poultice")
            extract_name = game.items_db.get(extract, {}).get("name", extract)
            return [f"Prepared: Poultice (from {extract_name} + Torn Fabric)"]
    return []


def _handler_surgical_care(game, room, npc, shifts):
    """Auto-treat moderate consequences overnight with a Lore check."""
    from engine import aspects
    # Find a character with a treatable moderate consequence
    for char_key in ("explorer", "steward"):
        char_data = game.state.get(char_key, {})
        cons = char_data.get("consequences", {})
        moderate = cons.get("moderate")
        if not moderate:
            continue
        # Check if eligible for treatment
        eligible, _ = aspects.can_treat_consequence(
            type("FakeGame", (), {"state": game.state})(), char_key, "moderate"
        )
        if not eligible:
            continue
        # Need a cure item in the room
        cure = aspects.get_cure_for_consequence(moderate)
        if cure not in room.items:
            continue
        # Consume the cure item — Lore check already passed via subtask runner
        room.remove_item(cure)
        cons["moderate"] = None
        meta = game.state.setdefault("consequence_meta", {})
        meta.pop(f"{char_key}_moderate", None)
        char_name = game.state.get(f"{char_key}_name", char_key.capitalize())
        return [f"Treated {char_name}'s moderate injury ({moderate}). Fully healed."]
    return ["No moderate injuries to operate on."]


HANDLERS = {
    "water_plants": _handler_water_plants,
    "fertilize_soil": _handler_fertilize_soil,
    "harvest_crops": _handler_harvest_crops,
    "plant_seeds": _handler_plant_seeds,
    "sort_salvage": _handler_sort_salvage,
    "strip_components": _handler_strip_components,
    "haul_materials": _handler_haul_materials,
    "craft_supplies": _handler_craft_supplies,
    "improve_tools": _handler_improve_tools,
    "collect_water": _handler_collect_water,
    "align_crystals": _handler_align_crystals,
    "organize_stores": _handler_organize_stores,
    "preserve_food": _handler_preserve_food,
    "scan_horizon": _handler_scan_horizon,
    "maintain_post": _handler_maintain_post,
    "tidy_up": _handler_tidy_up,
    "create_art": _handler_create_art,
    "tend_shelves": _handler_tend_shelves,
    "tend_wounds": _handler_tend_wounds,
    "brew_remedies": _handler_brew_remedies,
    "prepare_poultice": _handler_prepare_poultice,
    "surgical_care": _handler_surgical_care,
}


# ── Runner ───────────────────────────────────────────────────

def run_room_subtasks(game, room, workers):
    """Run subtask queue for a room.

    Returns [(npc_name, subtask_name, messages)] for display.

    Settled NPCs (settled_room == room.id) run ALL subtasks.
    Floating NPCs run only their assigned_subtask (or first subtask if None).
    """
    subtask_defs = get_subtasks_for_role(room.role)
    if not subtask_defs:
        return []

    results = []

    for npc in workers:
        npc_name = npc.get("name", "Unknown")
        is_settled = npc.get("settled_room") == room.id

        if is_settled:
            # Settled: run all subtasks in order
            run_list = subtask_defs
        else:
            # Floating: run only assigned subtask, or first if none
            assigned = npc.get("assigned_subtask")
            if assigned:
                run_list = [s for s in subtask_defs if s["id"] == assigned]
            else:
                run_list = subtask_defs[:1]

        for st in run_list:
            # Check condition
            if not _check_condition(st.get("condition"), game, room, npc):
                continue

            # Skill check if needed
            shifts = 0
            skill_name = st.get("skill")
            dc = st.get("dc", 0)
            if skill_name:
                skill_val = _npc_skill(npc, skill_name)
                # Masterwork room enhancement: +1 if any masterwork item is in the room
                from engine.masterwork import is_masterwork
                if any(is_masterwork(item_id) for item_id in room.items):
                    skill_val += 1
                total, shifts, dice_result = dice.skill_check(skill_val, dc)
                if shifts < 0:
                    # Failed — skip this subtask, continue to next
                    results.append((npc_name, st["name"],
                                    [f"Failed {skill_name} check (DC {dc})."]
                                    ))
                    continue

            # Execute handler
            handler = HANDLERS.get(st.get("handler"))
            if handler:
                messages = handler(game, room, npc, shifts)
                if messages:
                    results.append((npc_name, st["name"], messages))

    return results
