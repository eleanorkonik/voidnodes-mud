"""Display system — ANSI-colored text output for the MUD."""

from models.world_seed import MATURATION_THRESHOLD

# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

WHITE = "\033[37m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"

BRIGHT_WHITE = "\033[97m"
BRIGHT_CYAN = "\033[96m"
BRIGHT_YELLOW = "\033[93m"
BRIGHT_RED = "\033[91m"
BRIGHT_GREEN = "\033[92m"
BRIGHT_MAGENTA = "\033[95m"


def narrate(text):
    """White narration text."""
    print(f"{WHITE}{text}{RESET}")


def room_name(name):
    """Cyan bold room name."""
    print(f"\n{BOLD}{BRIGHT_CYAN}═══ {name} ═══{RESET}")


def room_desc(text):
    """White room description."""
    print(f"{WHITE}{text}{RESET}")


def npc_name(name):
    """Format an NPC name in cyan."""
    return f"{BRIGHT_CYAN}{name}{RESET}"


def npc_speak(name, text):
    """Attributed NPC dialogue."""
    print(f"{BRIGHT_CYAN}{name}:{RESET} {WHITE}'{text}'{RESET}")


def item_name(name):
    """Format an item name in yellow."""
    return f"{BRIGHT_YELLOW}{name}{RESET}"


def enemy_name(name):
    """Format an enemy name in red."""
    return f"{BRIGHT_RED}{name}{RESET}"


def aspect_text(aspect):
    """Format an aspect in magenta."""
    return f"{BRIGHT_MAGENTA}{aspect}{RESET}"


def seed_speak(text):
    """Green text for world seed communication."""
    print(f"{BRIGHT_GREEN}  ✧ {text}{RESET}")


def success(text):
    """Green positive outcome."""
    print(f"{BRIGHT_GREEN}{text}{RESET}")


def warning(text):
    """Red warning text."""
    print(f"{BRIGHT_RED}{text}{RESET}")


def error(text):
    """Red error/damage text."""
    print(f"{RED}{text}{RESET}")


def info(text):
    """Dim info text."""
    print(f"{DIM}{text}{RESET}")


def header(text):
    """Bold header."""
    print(f"\n{BOLD}{text}{RESET}")


def divider():
    """Print a divider line."""
    print(f"{DIM}{'─' * 50}{RESET}")


def display_room(room, game_state):
    """Display a full room description with contents."""
    room_name(room.name)
    room_desc(room.description)

    if game_state.get("bonded_with_seed", True):
        all_aspects = []
        zone_aspect = _get_zone_aspect(room, game_state)
        if zone_aspect:
            all_aspects.append(zone_aspect)
        all_aspects.extend(room.aspects)
        if all_aspects:
            aspects = ", ".join(aspect_text(a) for a in all_aspects)
            print(f"  Aspects: {aspects}")

    if room.items:
        items = game_state.get("items_db", {})
        artifacts = game_state.get("artifacts_db", {})
        from engine.farming import load_specimens
        specimens = load_specimens()
        from collections import Counter
        # Count items by ID for stacking
        item_counts = Counter(room.items)
        from engine.masterwork import is_masterwork, base_id as mw_base_id
        item_strs = []
        for item_id, count in item_counts.items():
            if item_id in artifacts:
                name = artifacts[item_id]["name"]
                item_strs.append(f"{BRIGHT_WHITE}{BOLD}{name}{RESET} {DIM}(artifact){RESET}")
            elif is_masterwork(item_id):
                bid = mw_base_id(item_id)
                base_data = items.get(bid, {})
                name = f"✦ {base_data.get('name', bid.replace('_', ' ').title())}"
                label = f"{BRIGHT_WHITE}{BOLD}{name}{RESET}"
                item_strs.append(f"{label} x{count}" if count > 1 else label)
            elif item_id in items:
                name = items[item_id]["name"]
                label = item_name(name)
                item_strs.append(f"{label} x{count}" if count > 1 else label)
            elif item_id in specimens:
                name = specimens[item_id]["name"]
                label = f"{BRIGHT_GREEN}{name}{RESET} {DIM}(specimen){RESET}"
                item_strs.append(f"{label} x{count}" if count > 1 else label)
            else:
                name = item_id.replace("_", " ").title()
                label = item_name(name)
                item_strs.append(f"{label} x{count}" if count > 1 else label)
        print(f"  You see: {', '.join(item_strs)}")

    if room.npcs:
        npcs = game_state.get("npcs_db", {})
        for npc_id in room.npcs:
            if npc_id in npcs:
                npc = npcs[npc_id]
                print(f"  {npc_name(npc['name'])} is here.")
            else:
                print(f"  {npc_name(npc_id.replace('_', ' ').title())} is here.")

    # Show followers at this location (only scan recruited NPCs)
    npcs_db = game_state.get("npcs_db", {})
    for fid in game_state.get("recruited_npcs", []):
        fdata = npcs_db.get(fid, {})
        if fdata.get("following") and fdata.get("location") == room.id and fid not in (room.npcs or []):
            print(f"  {npc_name(fdata['name'])} is following you.")

    # Show inactive agents at this location
    agents = game_state.get("agents_db", {})
    for agent_id, agent_data in agents.items():
        if agent_data.get("location") == room.id:
            print(f"  {npc_name(agent_data['name'])} is here.")

    if room.enemies:
        enemies = game_state.get("enemies_db", {})
        for enemy_id in room.enemies:
            if enemy_id in enemies:
                enemy = enemies[enemy_id]
                print(f"  {enemy_name(enemy['name'])} lurks here!")
            else:
                print(f"  {enemy_name(enemy_id.replace('_', ' ').title())} lurks here!")

    exits = room.get_exit_directions()
    locked = getattr(room, 'locked_exits', {}) or {}
    if exits or locked:
        from engine.quest import check_lock_condition
        exit_parts = []
        for e in exits:
            exit_parts.append(f"{BOLD}{e.upper()}{RESET}")
        for e, lock in locked.items():
            if e not in exits:
                if not check_lock_condition(lock["condition"], game_state):
                    exit_parts.append(f"{DIM}{e.upper()} (blocked){RESET}")
                else:
                    exit_parts.append(f"{BOLD}{e.upper()}{RESET}")
        print(f"  Exits: {', '.join(exit_parts)}")


def display_status(character, phase):
    """Display character status bar."""
    stress_str = "".join("[X]" if s else "[ ]" for s in character.stress)
    cons = []
    for severity, aspect in character.consequences.items():
        if aspect:
            cons.append(f"{severity}: {aspect}")
    cons_str = ", ".join(cons) if cons else "none"

    header(f"[{character.name}] — {phase.upper()} PHASE")
    print(f"  Stress: {stress_str}  Fate Points: {BRIGHT_YELLOW}{character.fate_points}{RESET}")
    if cons:
        print(f"  Consequences: {cons_str}")


def display_seed(seed_data, name="Tuft"):
    """Display world seed status."""
    motes = seed_data.get("motes", 0)
    fed = seed_data.get("total_motes_fed", 0)
    remaining = max(0, MATURATION_THRESHOLD - fed)
    if remaining > 0:
        progress = f"  ({remaining} motes to maturation)"
    else:
        progress = f"  (mature)"
    print(f"  {BRIGHT_GREEN}[{name}]{RESET} Motes: {motes}{progress}")


def _get_zone_aspect(room, game_state):
    """Get the zone-level aspect for the room's zone, if any."""
    if room.zone == "skerry":
        return game_state.get("skerry", {}).get("aspect")
    zones = game_state.get("zones", {})
    return zones.get(room.zone, {}).get("aspect")


def _lookup_name(item_id, items_db, artifacts_db):
    """Look up an item name from items_db or artifacts_db, with fallback."""
    from engine.masterwork import is_masterwork, base_id, get_display_name
    if is_masterwork(item_id):
        return get_display_name(item_id, items_db)
    if item_id in items_db:
        return items_db[item_id]["name"]
    if artifacts_db and item_id in artifacts_db:
        return artifacts_db[item_id]["name"]
    return item_id.replace("_", " ").title()


def display_self(character, items_db, artifacts_db=None):
    """Display the character's appearance: worn items and aspects."""
    from models.character import BODY_SLOTS
    artifacts_db = artifacts_db or {}

    header(f"═══ {character.name} ═══")
    print(f"  {character.aspects['high_concept']}")

    print()
    print(f"  {BOLD}Wearing:{RESET}")
    for slot in BODY_SLOTS:
        worn_id = character.worn.get(slot) if hasattr(character, 'worn') else None
        if worn_id:
            name = _lookup_name(worn_id, items_db, artifacts_db)
            print(f"    {slot.capitalize():<8} {item_name(name)}")
        else:
            print(f"    {slot.capitalize():<8} {DIM}(nothing){RESET}")

    print()
    print(f"  {BOLD}Aspects:{RESET}")
    print(f"    {aspect_text(character.aspects['high_concept'])}")
    print(f"    {aspect_text(character.aspects['trouble'])}")
    for a in character.aspects.get("other", []):
        print(f"    {aspect_text(a)}")


def display_inventory(character, items_db, artifacts_db=None, specimens_db=None):
    """Display character inventory."""
    header(f"{character.name}'s Inventory")
    if not character.inventory:
        print("  (empty)")
        return

    artifacts_db = artifacts_db or {}
    specimens_db = specimens_db or {}

    # Count stackable items
    counts = {}
    for item_id in character.inventory:
        counts[item_id] = counts.get(item_id, 0) + 1

    from engine.masterwork import is_masterwork, base_id as mw_base_id

    for item_id, count in counts.items():
        if item_id in artifacts_db:
            art = artifacts_db[item_id]
            motes = art.get("mote_value", 0)
            print(f"  {BRIGHT_WHITE}{BOLD}{art['name']}{RESET} {DIM}({motes} motes){RESET}")
        elif is_masterwork(item_id):
            bid = mw_base_id(item_id)
            base_data = items_db.get(bid, {})
            name = f"✦ {base_data.get('name', bid.replace('_', ' ').title())}"
            if count > 1:
                print(f"  {BRIGHT_WHITE}{BOLD}{name}{RESET} x{count}")
            else:
                print(f"  {BRIGHT_WHITE}{BOLD}{name}{RESET}")
        elif item_id in specimens_db:
            spec = specimens_db[item_id]
            if count > 1:
                print(f"  {BRIGHT_GREEN}{spec['name']}{RESET} x{count} {DIM}(specimen){RESET}")
            else:
                print(f"  {BRIGHT_GREEN}{spec['name']}{RESET} {DIM}(specimen){RESET}")
        elif item_id in items_db:
            name = items_db[item_id]["name"]
            if count > 1:
                print(f"  {item_name(name)} x{count}")
            else:
                print(f"  {item_name(name)}")
        else:
            name = item_id.replace("_", " ").title()
            if count > 1:
                print(f"  {item_name(name)} x{count}")
            else:
                print(f"  {item_name(name)}")

    worn = {s: i for s, i in character.worn.items() if i} if hasattr(character, 'worn') else {}
    if worn:
        print(f"  {BOLD}Wearing:{RESET}")
        for slot, wid in worn.items():
            name = _lookup_name(wid, items_db, artifacts_db)
            print(f"    {slot.capitalize()}: {item_name(name)}")


def display_character_sheet(character):
    """Display full character sheet."""
    header(f"═══ {character.name} ═══")
    print(f"  {BOLD}High Concept:{RESET} {character.aspects['high_concept']}")
    print(f"  {BOLD}Trouble:{RESET} {character.aspects['trouble']}")
    for a in character.aspects.get("other", []):
        print(f"  {BOLD}Aspect:{RESET} {a}")

    print()
    print(f"  {BOLD}Skills:{RESET}")
    # Sort by value descending
    for skill, value in sorted(character.skills.items(), key=lambda x: -x[1]):
        bar = "█" * value + "░" * (4 - value)
        print(f"    {skill:<12} [{bar}] +{value}")

    print()
    stress_str = "".join("[X]" if s else "[ ]" for s in character.stress)
    print(f"  {BOLD}Stress:{RESET} {stress_str}")
    print(f"  {BOLD}Consequences:{RESET}")
    for severity, aspect in character.consequences.items():
        status = aspect if aspect else "(none)"
        print(f"    {severity.capitalize()}: {status}")
    print(f"  {BOLD}Fate Points:{RESET} {character.fate_points} (Refresh: {character.refresh})")


def display_help(phase, seed_name="Tuft"):
    """Display available commands for current phase."""
    header("Available Commands")
    general = [
        ("LOOK [thing]", "Examine surroundings or a specific thing"),
        ("IH [thing]", "List objects here, or examine something"),
        ("GO <direction>", "Move (NORTH/SOUTH/EAST/WEST/UP/DOWN, or N/S/E/W)"),
        ("TALK / HI <npc>", "Talk to an NPC"),
        (f"CHECK <target>", f"Check NPC, {seed_name}, skerry, stores, or vault"),
        ("INVENTORY", "Show your inventory"),
        ("STATUS", "Show your character sheet"),
        ("MAP [zone/ALL]", "Show the zone map"),
        ("SWITCH FOCUS TO <name>", "Switch active agent"),
        ("SAVE", "Save the game"),
        ("QUIT", "Save and exit"),
        ("HELP", "Show this help"),
    ]

    if phase == "prologue":
        for cmd, desc in general:
            print(f"  {BOLD}{cmd:<28}{RESET} {desc}")
        divider()
        print(f"  {BOLD}{'SKIP':<28}{RESET} Skip the tutorial")
        return

    exploration = [
        ("SCAVENGE", "Search the room for materials"),
        ("INVESTIGATE", "Search for hidden artifacts (Notice check)"),
        ("PROBE <thing>", "Examine a discovered artifact or item"),
        ("SEEK [aspect]", f"Cross the void to a node (costs 1 {seed_name} mote)"),
        ("RETREAT", f"Emergency retreat (costs {seed_name} motes)"),
        ("RECRUIT <npc>", "Try to recruit an NPC"),
    ]
    combat = [
        ("ATTACK <target>", "Attack an enemy"),
        ("EXPLOIT <aspect>", "Set up a tactical advantage (free +2)"),
        ("DEFEND", "Take a defensive stance (+2 defense)"),
        ("CONCEDE", "Surrender combat (gain fate points)"),
    ]
    items = [
        ("TAKE <item>", "Pick up an item"),
        ("DROP <item>", "Put down an item (or DROP ALL for materials)"),
        ("GIVE <item> TO <target>", f"Give to NPC, agent, or {seed_name}"),
        (f"FEED <item>", f"Shorthand for GIVE <item> TO {seed_name}"),
        ("USE <item>", "Use an item"),
        ("WEAR <item>", "Equip clothing or artifact"),
        ("REMOVE <item>", "Unequip something"),
        ("KEEP <item>", "Keep an artifact for its stat bonus"),
        ("INVOKE <aspect>", "Spend a fate point for +2 on next action"),
        ("ASPECTS", "Show your aspects"),
        ("CRAFT <recipe>", "Craft an item from materials"),
        ("RECIPES", "List known recipes"),
        ("REQUEST TREATMENT", "Treat injuries (needs cure item + Lore)"),
    ]
    settlement = [
        ("BUILD <structure>", "Build a skerry structure"),
        ("SETTLE <npc> [IN room]", "Settle an NPC on the skerry"),
        ("ASSIGN <npc> <task>", "Assign an NPC to a task"),
        ("ORGANIZE", "View all NPC assignments"),
        ("TASKS", "Show subtask queues"),
        ("REST", "Advance the day"),
    ]
    farming = [
        ("PLANT <specimen> [plot]", "Plant a specimen in a garden plot"),
        ("HARVEST [plot]", "Harvest ready crops"),
        ("SURVEY", "View all garden plots and growth"),
        ("UPROOT <plot>", "Remove a plant from a plot"),
        ("STORE <food>", "Move food to stores"),
        ("SELECT <plot> FOR <trait>", "Selective breed for a trait"),
        ("CROSS <plot> WITH <plot>", "Cross-pollinate two plants"),
        ("CLONE <plot>", "Clone a cutting/transplant"),
        ("BANK <plot>", "Store plant genetics in vault"),
        ("WITHDRAW <#>", "Retrieve specimen from vault"),
    ]

    for cmd, desc in general:
        print(f"  {BOLD}{cmd:<28}{RESET} {desc}")

    sections = [
        ("Exploration", exploration),
        ("Combat", combat),
        ("Items & Skills", items),
        ("Settlement", settlement),
        ("Farming", farming),
    ]
    for section_name, cmds in sections:
        divider()
        print(f"  {BOLD}{section_name:^40}{RESET}")
        for cmd, desc in cmds:
            print(f"  {BOLD}{cmd:<28}{RESET} {desc}")


def title_screen():
    """Display the game title screen."""
    print(f"""
{BRIGHT_GREEN}
    ╔══════════════════════════════════════════╗
    ║                                          ║
    ║       ✧  V O I D N O D E S  ✧            ║
    ║                                          ║
    ║          The Skerry Chronicle            ║
    ║                                          ║
    ╚══════════════════════════════════════════╝
{RESET}
{DIM}  A text adventure in the space between worlds.
  Tend your world seed. Explore the void. Survive.{RESET}
""")


def phase_banner(phase, day, explorer_name="Sevarik", steward_name="Miria"):
    """Display phase transition banner."""
    if phase == "prologue":
        print(f"""
{BOLD}{GREEN}
  ╔════════════════════════════════════╗
  ║           THE SKERRY              ║
  ╚════════════════════════════════════╝
{RESET}""")
    elif phase == "explorer":
        print(f"""
{BOLD}{CYAN}
  ╔════════════════════════════════════╗
  ║  DAY {day} — EXPLORER PHASE        ║
  ║  {explorer_name} ventures into the void.{' ' * max(0, 10 - len(explorer_name))}║
  ╚════════════════════════════════════╝
{RESET}""")
    else:
        print(f"""
{BOLD}{GREEN}
  ╔════════════════════════════════════╗
  ║  DAY {day} — STEWARD PHASE         ║
  ║  {steward_name} tends the skerry.{' ' * max(0, 14 - len(steward_name))}║
  ╚════════════════════════════════════╝
{RESET}""")


def prompt(phase):
    """Return the input prompt string."""
    if phase == "prologue":
        return f"{BOLD}{BRIGHT_YELLOW}>{RESET} "
    if phase == "explorer":
        return f"{BOLD}{CYAN}>{RESET} "
    return f"{BOLD}{GREEN}>{RESET} "


# ── Food & Farming Displays ──────────────────────────────────

def trait_bar(value, width=10):
    """Render a trait value as a ■░ bar."""
    filled = min(value, width)
    empty = width - filled
    return "■" * filled + "░" * empty


def display_food_stores(food_stores, population, current_day):
    """Display the food stores status panel."""
    from engine.farming import total_calories, days_of_food, variety_score, avg_pleasure

    header("FOOD STORES")

    if not food_stores:
        print(f"  {DIM}(empty){RESET}")
        print(f"\n  Total: 0 calories | 0 days at current pop ({population})")
        return

    for entry in food_stores:
        name = entry.get("name", entry["item_id"].replace("_", " ").title())
        qty = entry["quantity"]
        cal = entry.get("calories", 40)
        sl = entry.get("shelf_life", -1)
        if sl == -1:
            shelf_str = f"{BRIGHT_GREEN}stable{RESET}"
        else:
            days_left = sl - (current_day - entry["day_stored"])
            if days_left <= 2:
                shelf_str = f"{BRIGHT_RED}{days_left} days left{RESET}"
            else:
                shelf_str = f"{days_left} days left"
        print(f"  {BRIGHT_YELLOW}{name}{RESET} x{qty}       {cal} cal each    {shelf_str}")

    total = total_calories(food_stores)
    dof = days_of_food(food_stores, population)
    var = variety_score(food_stores)
    pleasure = avg_pleasure(food_stores)

    print()
    print(f"  Total: {total} calories | ~{dof:.1f} days at current pop ({population})")
    print(f"  Variety: {var}/6 categories", end="")
    if var > 0:
        cats = set()
        for e in food_stores:
            if e["quantity"] > 0:
                cats.add(e.get("variety_category", "unknown"))
        print(f" ({', '.join(sorted(cats))})")
    else:
        print()

    # Pleasure description
    if pleasure >= 7:
        p_desc = "People are eating well."
    elif pleasure >= 5:
        p_desc = "Decent enough. No complaints."
    elif pleasure >= 3:
        p_desc = "Edible, but nobody's excited."
    else:
        p_desc = "Survival rations. Morale is suffering."
    print(f"  Avg Pleasure: {pleasure:.1f} — \"{p_desc}\"")

    # Warnings
    if var < 3 and var > 0:
        print(f"\n  {BRIGHT_YELLOW}! Low variety — people are getting bored of the same food.{RESET}")
    if dof < 2:
        print(f"\n  {BRIGHT_RED}!! FOOD CRITICAL — less than 2 days of food remaining!{RESET}")


def display_plot_survey(plots, current_day):
    """Display all garden plots in a survey view."""
    header("GARDEN SURVEY")

    if not plots:
        print(f"  {DIM}No garden plots available. Build a garden first.{RESET}")
        return

    for plot in plots:
        plot_id = plot["id"]
        plant = plot.get("plant")
        if not plant:
            print(f"\n  {DIM}Plot {plot_id}: (empty){RESET}")
            continue

        name = plant.get("name", plant["specimen_id"].replace("_", " ").title())
        spec_type = plant.get("specimen_type", "unknown")
        growth = plant["growth"]
        needed = plant["growth_needed"]
        gen = plant.get("generation", 1)

        # Growth bar
        if growth >= needed:
            growth_bar = f"{BRIGHT_GREEN}{'█' * 10} READY — harvest available{RESET}"
        else:
            filled = min(10, round(growth / needed * 10))
            empty = 10 - filled
            days_left = needed - growth
            growth_bar = f"{'█' * filled}{'░' * empty} {growth}/{needed} — ~{days_left} day{'s' if days_left != 1 else ''} left"

        print(f"\n  {BOLD}Plot {plot_id}: {BRIGHT_GREEN}{name}{RESET} {DIM}(Gen {gen}, {spec_type}){RESET}")
        print(f"  Growth: {growth_bar}")

        # Trait axes display
        traits = plant.get("traits", {})
        _print_trait_axis("YIELD", traits.get("yield", 5), "DEFENSE", traits.get("defense", 5))
        _print_trait_axis("SPEED", traits.get("speed", 5), "NUTRIENT", traits.get("nutrition", 5))
        _print_trait_axis("EDIBLE", traits.get("edible", 5), "UTILITY", traits.get("utility", 5))
        _print_trait_axis("UNIFORM", traits.get("uniformity", 5), "DIVERSE", traits.get("diversity", 5))
        _print_trait_axis("SPECIAL", traits.get("specialist", 5), "GENERAL", traits.get("generalist", 5))

        # Breeding options
        from engine.farming import get_allowed_breeding
        allowed = get_allowed_breeding(spec_type)
        print(f"  Breed: {', '.join(a.upper() for a in allowed)}")

        # Hidden traits (if revealed)
        hidden = plant.get("hidden_traits", {})
        revealed = [k for k, v in hidden.items() if v is True or (isinstance(v, str) and v != "unknown")]
        if revealed:
            for h in revealed:
                print(f"  {BRIGHT_YELLOW}! {h.replace('_', ' ').title()}{RESET}")

        # Health
        health = plant.get("health", "good")
        health_color = BRIGHT_GREEN if health == "good" else BRIGHT_YELLOW if health == "fair" else BRIGHT_RED
        print(f"  Health: {health_color}{health.capitalize()}{RESET}")


def _print_trait_axis(name_a, val_a, name_b, val_b):
    """Print a single trait axis line: NAME_A  ■■■■░░░░░░  NAME_B"""
    bar = trait_bar(val_a)
    print(f"    {name_a:<8} {bar} {name_b}")


def display_probe_plant(plant, plot_id):
    """Display a detailed PROBE view of a plant in a garden plot."""
    name = plant.get("name", plant["specimen_id"].replace("_", " ").title())
    spec_type = plant.get("specimen_type", "unknown")
    gen = plant.get("generation", 1)
    growth = plant["growth"]
    needed = plant["growth_needed"]

    if growth >= needed:
        growth_bar = f"{BRIGHT_GREEN}{'█' * 10} READY{RESET}"
    else:
        filled = min(10, round(growth / needed * 10))
        empty = 10 - filled
        growth_bar = f"{'█' * filled}{'░' * empty} {growth}/{needed}"

    header(f"PLOT {plot_id}: {name} (Gen {gen}, {spec_type})")
    print(f"  Growth: {growth_bar}")
    print(f"  Compat: {plant.get('compatibility_group', '?')} | Family: {plant.get('family', '?')}")

    traits = plant.get("traits", {})
    print()
    _print_trait_axis("YIELD", traits.get("yield", 5), "DEFENSE", traits.get("defense", 5))
    _print_trait_axis("SPEED", traits.get("speed", 5), "NUTRIENT", traits.get("nutrition", 5))
    _print_trait_axis("EDIBLE", traits.get("edible", 5), "UTILITY", traits.get("utility", 5))
    _print_trait_axis("UNIFORM", traits.get("uniformity", 5), "DIVERSE", traits.get("diversity", 5))
    _print_trait_axis("SPECIAL", traits.get("specialist", 5), "GENERAL", traits.get("generalist", 5))

    from engine.farming import get_allowed_breeding
    allowed = get_allowed_breeding(spec_type)
    print(f"\n  Breed: {', '.join(a.upper() for a in allowed)}")

    hidden = plant.get("hidden_traits", {})
    revealed = [k for k, v in hidden.items() if v is True or (isinstance(v, str) and v != "unknown")]
    unknown = [k for k, v in hidden.items() if v == "unknown"]
    if revealed:
        for h in revealed:
            print(f"  {BRIGHT_YELLOW}! {h.replace('_', ' ').title()}{RESET}")
    if unknown:
        for h in unknown:
            print(f"  {DIM}? {h.replace('_', ' ').title()} (unknown){RESET}")


def display_probe_specimen(specimen):
    """Display a detailed PROBE view of a specimen item."""
    header(specimen["name"])
    print(f"  Type: {specimen['specimen_type']} | Family: {specimen['family']}")
    print(f"  Origin: {specimen['origin'].replace('_', ' ').title()}")
    print(f"  Compat: {specimen['compatibility_group']}")
    if specimen.get("probe_text"):
        print()
        narrate(f"  {specimen['probe_text']}")

    traits = specimen["traits"]
    print()
    _print_trait_axis("YIELD", traits.get("yield", 5), "DEFENSE", traits.get("defense", 5))
    _print_trait_axis("SPEED", traits.get("speed", 5), "NUTRIENT", traits.get("nutrition", 5))
    _print_trait_axis("EDIBLE", traits.get("edible", 5), "UTILITY", traits.get("utility", 5))
    _print_trait_axis("UNIFORM", traits.get("uniformity", 5), "DIVERSE", traits.get("diversity", 5))
    _print_trait_axis("SPECIAL", traits.get("specialist", 5), "GENERAL", traits.get("generalist", 5))

    from engine.farming import get_allowed_breeding
    allowed = get_allowed_breeding(specimen["specimen_type"])
    print(f"\n  Breed: {', '.join(a.upper() for a in allowed)}")
    print(f"  Growth time: {specimen['growth_time']} days | Base yield: {specimen['base_yield']}")


def display_slot_usage(used, capacity):
    """Display inventory slot usage: [Large: 1/1] [Medium: 0/2] [Small: 8/20]"""
    parts = []
    for size in ("large", "medium", "small"):
        u = used.get(size, 0)
        c = capacity.get(size, 0)
        label = f"{size.capitalize()}: {u}/{c}"
        if u > c:
            parts.append(f"{BRIGHT_RED}{label}{RESET}")
        elif u == c:
            parts.append(f"{BRIGHT_YELLOW}{label}{RESET}")
        else:
            parts.append(label)
    print(f"\n  [{'] ['.join(parts)}]")


def display_seed_vault(seed_vault):
    """Display the contents of the seed vault."""
    header("SEED VAULT")
    if not seed_vault:
        print(f"  {DIM}(empty){RESET}")
        return
    for i, entry in enumerate(seed_vault):
        name = entry.get("name", entry["specimen_id"].replace("_", " ").title())
        spec_type = entry.get("specimen_type", "?")
        gen = entry.get("generation", 1)
        print(f"  {i + 1}. {BRIGHT_YELLOW}{name}{RESET} ({spec_type}, Gen {gen})")
