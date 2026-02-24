# Food Stores & Plant Breeding System

## Context

Eleanor wants a farming/food mechanic for Miria's steward phase, inspired by `plant-breeding-design.md`. The colony needs aggregate food tracking (not per-person Rimworld style) with a "are people starving" baseline from a food storage building. Plants are bred over generations with tradeoffs. Food recipes craft buff meals from stores.

## Phasing

### Phase 1: Food Stores + Basic Growing + Food Recipes (core ask)

This is the minimum to make food matter in the game.

#### 1a. Food Item Properties

Add nutrition fields to food items in `data/items.json`:

```json
{
    "colony_grain": {
        "id": "colony_grain",
        "name": "Colony Grain",
        "type": "food",
        "calories": 60,
        "shelf_life": 30,
        "satiation": 4,
        "variety_category": "grain",
        "pleasure": 2,
        "stackable": true,
        "description": "Basic grain harvested from the garden. Filling but bland."
    }
}
```

Properties:
- **calories** — energy per unit (colony needs ~X calories/day based on population)
- **shelf_life** — days before spoilage (-1 = preserved indefinitely)
- **satiation** — how filling (1-10 scale, affects how many units needed)
- **variety_category** — one of: grain, root, leaf, fruit, protein, preserved. Variety score = # of distinct categories in stores
- **pleasure** — enjoyment (1-10). Low pleasure = morale penalty even when not hungry

#### 1b. Food Stores (Skerry-Level Resource)

Tracked in `skerry.food_stores` — a list of food entries with quantities and age:

```python
food_stores = [
    {"item_id": "colony_grain", "quantity": 12, "day_stored": 5},
    {"item_id": "preserved_food", "quantity": 3, "day_stored": 1},
]
```

**Requires storehouse** — without building the storehouse, food sits in inventory (limited, no spoilage tracking, no aggregate stats). Building the storehouse unlocks:
- STORE <item> — move food from inventory to stores
- CHECK STORES — see aggregate food status
- Automatic spoilage tracking
- Day-transition consumption

**CHECK STORES display:**
```
── FOOD STORES ──────────────────────────────────────
  Colony Grain ×12       60 cal each    14 days left
  Preserved Food ×3      40 cal each    stable
  Wild Berries ×5        20 cal each    3 days left

  Total: 920 calories │ ~3.8 days at current population
  Variety: 3/6 categories (grain, preserved, fruit)
  Avg. Pleasure: 3.2 — "Edible, but nobody's excited."

  ⚠ Low variety — people are getting bored of grain.
─────────────────────────────────────────────────────
```

#### 1c. Day Transition: Consumption + Starvation

During day transition (steward→explorer), the colony eats:
- **Daily need** = population × base_calories (e.g., 2 characters + N NPCs × 50 cal each)
- Food consumed oldest-first (uses up short-shelf-life items before they spoil)
- Spoiled food removed automatically

**Starvation tiers** (FATE-aspect based, fits existing compel system):
- **Adequate** (>5 days of food): No effect
- **Lean** (2-5 days): Skerry aspect "Rations Are Getting Thin" — compellable, NPC mood -1
- **Hungry** (1-2 days): Skerry aspect "Hunger Gnaws at Everyone" — NPC loyalty -1/day, both characters gain stress box
- **Starving** (0 days): Skerry aspect "People Are Starving" — NPCs with loyalty <3 leave, both characters take 1 stress/day

**Variety penalty**: If variety score < 3, add aspect "Monotonous Diet" (compellable for morale events)
**Pleasure bonus**: If avg pleasure > 6, add aspect "Well-Fed Colony" (free invoke once per steward phase)

#### 1d. Garden + Planting

The garden buildable room (`skerry_garden`) already exists. Enhance it with:

- **PLANT <seed> [plot]** — plant a seed in the garden (limited plots, start with 4)
- **HARVEST [plot]** — collect grown food, add to inventory (then STORE to storehouse)
- **SURVEY** — see all plots, growth stage, days to harvest, plant health
- **Growing happens during day transitions** — each day, plants advance 1 growth tick
- **Yield determined by seed traits** — how much food per harvest

Garden plots tracked in skerry data:
```python
garden = {
    "plots": [
        {"plot_id": 1, "seed_id": "colony_grain_seed", "planted_day": 3, "growth": 4, "growth_needed": 6, "traits": {...}},
        {"plot_id": 2, "seed_id": None},  # empty
        ...
    ],
    "max_plots": 4,  # expandable with building
}
```

**Seed items** — new item type with plant traits:
```json
{
    "colony_grain_seed": {
        "id": "colony_grain_seed",
        "name": "Colony Grain Seeds",
        "type": "seed",
        "produces": "colony_grain",
        "growth_time": 6,
        "yield_amount": 3,
        "traits": {
            "yield_defense": 7,
            "speed_nutrition": 6,
            "edible_utility": 8
        },
        "stackable": true
    }
}
```

#### 1e. Food Recipes (extend existing CRAFT system)

New recipes in `data/recipes.json` that consume food items (from inventory, pulled from stores):

```json
{
    "hearty_stew": {
        "id": "hearty_stew",
        "name": "Hearty Stew",
        "materials": {"colony_grain": 2, "wild_berries": 1},
        "result": "hearty_stew_meal",
        "difficulty": 1,
        "skill": "Craft",
        "recipe_type": "food",
        "description": "A filling stew that warms the bones and lifts spirits."
    }
}
```

Food recipe results are **consumable meals** with buff effects:
```json
{
    "hearty_stew_meal": {
        "type": "consumable",
        "special": "restore_stress",
        "buff": {"mood_bonus": 1, "duration": 2},
        "calories": 120,
        "pleasure": 6,
        "description": "A bowl of thick, warming stew."
    }
}
```

Buff types: stress restoration, temporary skill bonuses, NPC mood boost, free invocations on food-related aspects.

### Phase 2: Plant Breeding

Layer breeding mechanics onto the garden system.

#### 2a. Trait Axes on Seeds (from design doc)

Each seed carries 5 trait axes as integer pairs (total = 10 for each axis):
1. **Yield / Defense** (yield + defense = 10)
2. **Speed / Nutrition** (growth_rate + nutrient_density = 10)
3. **Specialist / Generalist** (specialist + generalist = 10)
4. **Uniformity / Diversity** (uniformity + diversity = 10)
5. **Edible / Utility** (edible + utility = 10)

Simplified from the design doc's full genetics into paired integer scales that determine harvest output.

#### 2b. Breeding Commands

- **CROSS-POLLINATE <plant A> <plant B>** — sexual reproduction, sacrifices one harvest from both, produces new seeds with blended + random-shifted traits. Takes 1 season.
- **SELECT <plot> <trait>** — mass selection for a trait. Slow (+1 to chosen axis over multiple harvests) but preserves diversity score.
- **BANK <seeds>** — store in seed bank (storehouse sub-feature). Protected from spoilage, available for future planting.

#### 2c. PROBE / SURVEY Display

```
── PLOT 3: Colony Grain (Gen 2) ─────────────────
  Growth: ████████░░ 8/10 — harvest in 2 days

    YIELD ■■■■■■■░░░ DEFENSE     High yield, low defense
    SPEED ■■■■■░░░░░ NUTRIENT    Fast but starchy
   EDIBLE ■■■■■■■■░░ UTILITY     Food crop, weak fiber

  Health: Good │ No interactions detected
──────────────────────────────────────────────────
```

### Phase 3: Environmental Complexity (future)

- Companion planting adjacency bonuses
- Allelopathy (negative adjacency, discovered through play)
- Soil depletion per plot (N/P/K simplified to 3 nutrient levels)
- Rotation mechanics
- Blight events (target genetic lineages — uniformity risk)
- Pest invasions
- CLONE, GRAFT, BACKCROSS commands

---

## Files to Modify

| File | Changes |
|------|---------|
| `data/items.json` | Add food items, seed items, meal items |
| `data/recipes.json` | Add food recipes |
| `data/skerry.json` | Add garden plot data to garden room template |
| `models/skerry.py` | Add food_stores tracking, garden plots, spoilage, consumption |
| `engine/parser.py` | Add new commands: PLANT, HARVEST, SURVEY, STORE, COOK (or extend CRAFT) |
| `main.py` | Add cmd_plant, cmd_harvest, cmd_survey, cmd_store handlers; modify day transition for food consumption; modify CHECK for stores |
| `engine/display.py` | Food store display helpers, plant survey formatting |

## Existing Code to Reuse

- `Skerry.can_build()` / `build_room()` — garden already buildable
- `cmd_craft()` pattern for food recipes (same materials + skill check flow)
- `_day_transition()` — hook food consumption here
- `_inventory_counts()` — for material checking
- FATE aspect system — starvation aspects fit existing compel mechanics
- NPC mood/loyalty system — starvation consequences slot right in

## Verification

1. Build storehouse → CHECK STORES shows empty
2. Build garden → PLANT seeds → wait days → HARVEST → STORE food
3. CHECK STORES shows calories, days, variety, pleasure
4. Day transition consumes food, old food spoils
5. Let food run low → starvation aspects appear → NPC mood drops
6. CRAFT food recipe → produces buff meal → USE meal → buff applied
7. (Phase 2) CROSS-POLLINATE two plants → new seeds with blended traits
8. (Phase 2) SELECT for yield → gradual trait improvement over generations
