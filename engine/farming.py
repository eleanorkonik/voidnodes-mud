"""Farming system — specimens, planting, growth, harvest, breeding, food stores."""

import json
import random
import copy
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

# ── Specimen Loading ──────────────────────────────────────────

_specimens_db = None


def load_specimens():
    """Load specimen data from data/specimens.json. Cached after first call."""
    global _specimens_db
    if _specimens_db is None:
        filepath = DATA_DIR / "specimens.json"
        with open(filepath) as f:
            _specimens_db = json.load(f)
    return _specimens_db


def get_specimen(specimen_id):
    """Get a single specimen definition by ID."""
    db = load_specimens()
    return db.get(specimen_id)


def is_specimen(item_id):
    """Check if an item ID is a known specimen."""
    db = load_specimens()
    return item_id in db


# ── Trait Axis Pairs ──────────────────────────────────────────

TRAIT_AXES = [
    ("yield", "defense"),
    ("speed", "nutrition"),
    ("specialist", "generalist"),
    ("uniformity", "diversity"),
    ("edible", "utility"),
]


def get_trait_pair(trait_name):
    """Given a trait name, return (trait, opposite) or None."""
    for a, b in TRAIT_AXES:
        if trait_name == a:
            return (a, b)
        if trait_name == b:
            return (b, a)
    return None


# ── Growth Calculations ──────────────────────────────────────

def effective_growth_time(specimen):
    """Calculate growth time adjusted by speed trait. speed 10 = halved."""
    base = specimen["growth_time"]
    speed = specimen["traits"]["speed"]
    # speed 5 = normal, speed 10 = halved, speed 1 = 1.4x
    modifier = 1.0 - (speed - 5) * 0.1
    return max(1, round(base * modifier))


def growth_per_day(npc_count):
    """Growth ticks per day: 1 base + 1 per gardening NPC."""
    return 1 + npc_count


# ── Harvest → Food Conversion ────────────────────────────────

FAMILY_TO_CATEGORY = {
    "grain": "grain",
    "rootcrop": "root",
    "vine": "fruit",
    "leafy": "leaf",
    "fungal": "fungal",
    "unknown": "preserved",
}


def harvest_food(specimen, generation=1):
    """Generate a food item dict from a specimen's traits at harvest time.

    Returns (food_item, utility_item_or_None).
    """
    traits = specimen["traits"]
    yield_val = traits["yield"]
    base_yield = specimen["base_yield"]
    nutrition = traits["nutrition"]
    edible = traits["edible"]
    diversity = traits["diversity"]

    # Quantity: yield_trait × base_yield / 5, minimum 1
    quantity = max(1, round(yield_val * base_yield / 5))

    # Calories per unit: nutrition × 10 + 10 (range 20-110)
    calories = nutrition * 10 + 10

    # Pleasure: edible trait (1-10)
    pleasure = edible

    # Shelf life: 5 + diversity variance. High uniformity = consistent, high diversity = variable
    uniformity = traits["uniformity"]
    if uniformity >= 7:
        shelf_life = 10  # consistent, decent shelf life
    elif diversity >= 7:
        shelf_life = random.randint(4, 14)  # variable
    else:
        shelf_life = 8  # middling

    # Variety category from family
    category = FAMILY_TO_CATEGORY.get(specimen["family"], "preserved")

    # Name: specimen name + cultivar suffix if bred
    name = specimen["name"]
    if generation > 1:
        name = f"{specimen['name']} cv.{generation}"

    food_id = specimen["produces"]["food_id"]
    food_item = {
        "id": food_id,
        "name": name,
        "type": "food",
        "calories": calories,
        "shelf_life": shelf_life,
        "pleasure": pleasure,
        "variety_category": category,
        "quantity": quantity,
        "source_specimen": specimen["id"],
        "description": f"Harvested {name}. {calories} cal each, keeps for {shelf_life} days.",
    }

    # Utility byproduct
    utility_item = None
    utility_id = specimen["produces"].get("utility_id")
    if utility_id and traits["utility"] >= 3:
        utility_item = {
            "id": utility_id,
            "name": utility_id.replace("_", " ").title(),
            "type": "material",
            "quantity": max(1, traits["utility"] // 3),
            "description": f"Byproduct from {specimen['name']}.",
        }

    return food_item, utility_item


# ── Food Store Operations ────────────────────────────────────

def add_to_stores(food_stores, food_item, day, quantity=None):
    """Add food to the colony's food stores."""
    qty = quantity if quantity is not None else food_item.get("quantity", 1)
    # Check if we already have this food type stored on same day
    for entry in food_stores:
        if entry["item_id"] == food_item["id"] and entry["day_stored"] == day:
            entry["quantity"] += qty
            return
    food_stores.append({
        "item_id": food_item["id"],
        "name": food_item.get("name", food_item["id"].replace("_", " ").title()),
        "quantity": qty,
        "calories": food_item.get("calories", 40),
        "shelf_life": food_item.get("shelf_life", -1),
        "pleasure": food_item.get("pleasure", 3),
        "variety_category": food_item.get("variety_category", "preserved"),
        "day_stored": day,
    })


def consume_food(food_stores, calories_needed, current_day):
    """Consume calories from stores, oldest and shortest-shelf-life first.

    Returns calories_consumed.
    """
    # Sort: spoiling-soonest first (shelf_life > 0 sorted ascending, then shelf_life == -1 last)
    def sort_key(entry):
        sl = entry.get("shelf_life", -1)
        if sl == -1:
            return (1, 0)  # preserved food last
        days_left = sl - (current_day - entry["day_stored"])
        return (0, days_left)

    food_stores.sort(key=sort_key)

    consumed = 0
    to_remove = []
    for entry in food_stores:
        if consumed >= calories_needed:
            break
        cal_per_unit = entry.get("calories", 40)
        while entry["quantity"] > 0 and consumed < calories_needed:
            entry["quantity"] -= 1
            consumed += cal_per_unit
        if entry["quantity"] <= 0:
            to_remove.append(entry)

    for entry in to_remove:
        food_stores.remove(entry)

    return consumed


def remove_spoiled(food_stores, current_day):
    """Remove food that has exceeded its shelf life. Returns list of spoiled item names."""
    spoiled = []
    remaining = []
    for entry in food_stores:
        sl = entry.get("shelf_life", -1)
        if sl == -1:
            remaining.append(entry)
            continue
        age = current_day - entry["day_stored"]
        if age > sl:
            spoiled.append(entry.get("name", entry["item_id"]))
        else:
            remaining.append(entry)
    food_stores.clear()
    food_stores.extend(remaining)
    return spoiled


def total_calories(food_stores):
    """Sum total calories in stores."""
    return sum(e["quantity"] * e.get("calories", 40) for e in food_stores)


def days_of_food(food_stores, population):
    """Calculate how many days the stores will feed the colony."""
    daily_need = population * 50
    if daily_need <= 0:
        return 99
    total = total_calories(food_stores)
    return total / daily_need


def variety_score(food_stores):
    """Count distinct variety categories in stores."""
    categories = set()
    for entry in food_stores:
        if entry["quantity"] > 0:
            categories.add(entry.get("variety_category", "unknown"))
    return len(categories)


def avg_pleasure(food_stores):
    """Weighted average pleasure of food in stores."""
    total_qty = sum(e["quantity"] for e in food_stores)
    if total_qty == 0:
        return 0
    weighted = sum(e["quantity"] * e.get("pleasure", 3) for e in food_stores)
    return weighted / total_qty


# ── Starvation Tiers ─────────────────────────────────────────

STARVATION_TIERS = [
    {"min_days": 5, "aspect": None, "label": "Well-supplied"},
    {"min_days": 2, "aspect": "Rations Are Getting Thin", "label": "Low rations"},
    {"min_days": 1, "aspect": "Hunger Gnaws at Everyone", "label": "Hungry"},
    {"min_days": 0, "aspect": "People Are Starving", "label": "Starving"},
]


def get_starvation_tier(food_days):
    """Return the starvation tier dict for the given days-of-food."""
    for tier in STARVATION_TIERS:
        if food_days >= tier["min_days"]:
            return tier
    return STARVATION_TIERS[-1]


# ── Garden Plot Operations ───────────────────────────────────

def make_empty_plot(plot_id):
    """Create a new empty garden plot."""
    return {
        "id": plot_id,
        "plant": None,
        "soil": {"n": 10, "p": 10, "k": 10},
    }


def plant_specimen(plot, specimen_id, day):
    """Plant a specimen in a plot. Returns True if successful."""
    if plot["plant"] is not None:
        return False
    specimen = get_specimen(specimen_id)
    if not specimen:
        return False
    plot["plant"] = {
        "specimen_id": specimen_id,
        "planted_day": day,
        "growth": 0,
        "growth_needed": effective_growth_time(specimen),
        "traits": copy.deepcopy(specimen["traits"]),
        "hidden_traits": copy.deepcopy(specimen.get("hidden_traits", {})),
        "generation": 1,
        "name": specimen["name"],
        "specimen_type": specimen["specimen_type"],
        "family": specimen["family"],
        "compatibility_group": specimen["compatibility_group"],
        "health": "good",
    }
    return True


def is_harvestable(plot):
    """Check if a plot's plant is ready for harvest."""
    plant = plot.get("plant")
    if not plant:
        return False
    return plant["growth"] >= plant["growth_needed"]


def harvest_plot(plot, day):
    """Harvest a mature plant. Returns (food_item, utility_item) or None.

    Removes the plant from the plot (except tubers which regrow).
    """
    plant = plot.get("plant")
    if not plant or not is_harvestable(plot):
        return None

    specimen = get_specimen(plant["specimen_id"])
    if not specimen:
        return None

    # Build a modified specimen dict with the plot's current traits
    harvest_spec = copy.deepcopy(specimen)
    harvest_spec["traits"] = plant["traits"]

    food, utility = harvest_food(harvest_spec, plant.get("generation", 1))

    # Tubers regrow from roots; everything else is cleared
    if plant["specimen_type"] == "tuber":
        plant["growth"] = 0
        plant["planted_day"] = day
    else:
        plot["plant"] = None

    return food, utility


def advance_growth(plots, gardening_npc_count):
    """Advance growth on all plots by one day. Returns list of plot IDs that became harvestable."""
    ticks = growth_per_day(gardening_npc_count)
    newly_ready = []
    for plot in plots:
        plant = plot.get("plant")
        if plant and plant["growth"] < plant["growth_needed"]:
            plant["growth"] = min(plant["growth_needed"], plant["growth"] + ticks)
            if plant["growth"] >= plant["growth_needed"]:
                newly_ready.append(plot["id"])
    return newly_ready


# ── NPC Auto-Farming ─────────────────────────────────────────

def npc_auto_plant(plots, available_specimens, day):
    """NPCs plant available specimens in empty plots.

    available_specimens: list of specimen_ids in stores/inventory.
    Returns list of (plot_id, specimen_id) planted.
    """
    planted = []
    specimens_left = list(available_specimens)
    for plot in plots:
        if plot["plant"] is None and specimens_left:
            spec_id = specimens_left.pop(0)
            if plant_specimen(plot, spec_id, day):
                planted.append((plot["id"], spec_id))
    return planted


def npc_auto_harvest(plots, day):
    """NPCs harvest any ready plots. Returns list of (food_item, utility_item)."""
    harvested = []
    for plot in plots:
        if is_harvestable(plot):
            result = harvest_plot(plot, day)
            if result:
                harvested.append(result)
    return harvested


# ── Breeding ─────────────────────────────────────────────────

def _mutate_trait(value, amount=1):
    """Randomly shift a trait value, clamped to 1-9."""
    delta = random.choice([-amount, amount])
    return max(1, min(9, value + delta))


def can_cross_pollinate(plant_a, plant_b):
    """Check if two plants can cross-pollinate."""
    if plant_a["specimen_type"] != "seeds" or plant_b["specimen_type"] != "seeds":
        return False, "Both plants must be seed-type for cross-pollination."
    if plant_a["compatibility_group"] != plant_b["compatibility_group"]:
        # Check for adjacent groups (same prefix)
        group_a = plant_a["compatibility_group"].split("-")[0]
        group_b = plant_b["compatibility_group"].split("-")[0]
        if group_a == group_b:
            return True, "Adjacent compatibility — offspring may have reduced fertility."
        return False, "Incompatible species — only grafting works across distant groups."
    return True, "Compatible."


def cross_pollinate(plant_a, plant_b):
    """Cross two seed-type plants. Returns 1-3 new specimen dicts with blended traits.

    Sacrifices both plants (caller must clear the plots).
    """
    offspring_count = random.randint(1, 3)
    offspring = []
    for _ in range(offspring_count):
        new_traits = {}
        for axis_a, axis_b in TRAIT_AXES:
            # Blend: average of parents ± small random mutation
            avg_a = (plant_a["traits"][axis_a] + plant_b["traits"][axis_a]) // 2
            avg_b = (plant_a["traits"][axis_b] + plant_b["traits"][axis_b]) // 2
            # Mutation: ±1-2 random
            new_a = _mutate_trait(avg_a, random.randint(1, 2))
            # Enforce axis sum = 10
            new_b = max(1, min(9, 10 - new_a))
            new_traits[axis_a] = new_a
            new_traits[axis_b] = new_b

        # Blend hidden traits: each has 50% chance from either parent
        hidden = {}
        for key in set(list(plant_a.get("hidden_traits", {}).keys()) +
                       list(plant_b.get("hidden_traits", {}).keys())):
            val_a = plant_a.get("hidden_traits", {}).get(key)
            val_b = plant_b.get("hidden_traits", {}).get(key)
            if val_a is not None and val_b is not None:
                hidden[key] = random.choice([val_a, val_b])
            elif val_a is not None:
                hidden[key] = val_a if random.random() < 0.5 else None
            elif val_b is not None:
                hidden[key] = val_b if random.random() < 0.5 else None
        hidden = {k: v for k, v in hidden.items() if v is not None}

        gen_a = plant_a.get("generation", 1)
        gen_b = plant_b.get("generation", 1)
        new_gen = max(gen_a, gen_b) + 1

        child = {
            "specimen_id": plant_a["specimen_id"],  # inherits primary parent's ID
            "name": f"{plant_a['name']} cv.{new_gen}",
            "specimen_type": "seeds",
            "family": plant_a["family"],
            "compatibility_group": plant_a["compatibility_group"],
            "traits": new_traits,
            "hidden_traits": hidden,
            "generation": new_gen,
            "health": "good",
        }
        offspring.append(child)

    return offspring


def select_for_trait(plant, trait_name):
    """Apply selective breeding: shift named trait +1, opposite -1.

    Returns True if successful, False if trait unknown.
    """
    pair = get_trait_pair(trait_name)
    if not pair:
        return False
    trait, opposite = pair
    current = plant["traits"][trait]
    opp_current = plant["traits"][opposite]
    if current >= 9:
        return False  # already maxed
    plant["traits"][trait] = min(9, current + 1)
    plant["traits"][opposite] = max(1, opp_current - 1)
    return True


def clone_plant(plant):
    """Clone a cutting or transplant. Returns identical specimen dict."""
    return {
        "specimen_id": plant["specimen_id"],
        "name": plant["name"],
        "specimen_type": plant["specimen_type"],
        "family": plant["family"],
        "compatibility_group": plant["compatibility_group"],
        "traits": copy.deepcopy(plant["traits"]),
        "hidden_traits": copy.deepcopy(plant.get("hidden_traits", {})),
        "generation": plant.get("generation", 1),
        "health": "good",
    }


def get_allowed_breeding(specimen_type):
    """Return list of breeding commands allowed for a specimen type."""
    allowed = {
        "seeds": ["cross-pollinate", "select", "bank"],
        "cutting": ["clone", "graft", "select", "bank"],
        "tuber": ["select", "bank", "backcross"],
        "spore": ["select", "bank"],
        "transplant": ["graft", "clone", "bank"],
    }
    return allowed.get(specimen_type, ["bank"])


# ── Seed Vault ───────────────────────────────────────────────

def bank_specimen(seed_vault, plant_data):
    """Store a plant's genetic data in the seed vault."""
    entry = {
        "specimen_id": plant_data["specimen_id"],
        "name": plant_data["name"],
        "specimen_type": plant_data["specimen_type"],
        "family": plant_data["family"],
        "compatibility_group": plant_data["compatibility_group"],
        "traits": copy.deepcopy(plant_data["traits"]),
        "hidden_traits": copy.deepcopy(plant_data.get("hidden_traits", {})),
        "generation": plant_data.get("generation", 1),
    }
    seed_vault.append(entry)
    return entry


def withdraw_specimen(seed_vault, index):
    """Remove and return a specimen from the seed vault by index."""
    if 0 <= index < len(seed_vault):
        return seed_vault.pop(index)
    return None
