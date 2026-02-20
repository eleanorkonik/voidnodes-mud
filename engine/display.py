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
        item_strs = []
        for item_id in room.items:
            if item_id in items:
                item_strs.append(item_name(items[item_id]["name"]))
            else:
                item_strs.append(item_name(item_id.replace("_", " ").title()))
        print(f"  You see: {', '.join(item_strs)}")

    if room.npcs:
        npcs = game_state.get("npcs_db", {})
        for npc_id in room.npcs:
            if npc_id in npcs:
                npc = npcs[npc_id]
                print(f"  {npc_name(npc['name'])} is here.")
            else:
                print(f"  {npc_name(npc_id.replace('_', ' ').title())} is here.")

    # Show followers at this location
    npcs_db = game_state.get("npcs_db", {})
    for fid, fdata in npcs_db.items():
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


def display_inventory(character, items_db, artifacts_db=None):
    """Display character inventory."""
    header(f"{character.name}'s Inventory")
    if not character.inventory:
        print("  (empty)")
        return

    artifacts_db = artifacts_db or {}

    # Count stackable items
    counts = {}
    for item_id in character.inventory:
        counts[item_id] = counts.get(item_id, 0) + 1

    for item_id, count in counts.items():
        if item_id in artifacts_db:
            art = artifacts_db[item_id]
            motes = art.get("mote_value", 0)
            print(f"  {BRIGHT_WHITE}{BOLD}{art['name']}{RESET} {DIM}({motes} motes){RESET}")
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
        status = aspect if aspect else "(open)"
        print(f"    {severity.capitalize()}: {status}")
    print(f"  {BOLD}Fate Points:{RESET} {character.fate_points} (Refresh: {character.refresh})")


def display_help(phase, seed_name="Tuft"):
    """Display available commands for current phase."""
    header("Available Commands")
    universal = [
        ("LOOK [thing]", "Examine surroundings or a specific thing"),
        ("IH [thing]", "List objects here, or examine something"),
        ("GO <direction>", "Move (NORTH/SOUTH/EAST/WEST/UP/DOWN, or N/S/E/W)"),
        ("TALK / HI <npc>", "Talk to an NPC (also: GREET)"),
        (f"CHECK <npc/{seed_name.lower()}>", f"Check status of NPC or {seed_name}"),
        ("USE <item>", "Use an item"),
        ("WEAR <item>", "Put on a piece of clothing or artifact"),
        ("REMOVE <item>", "Take off something you're wearing"),
        ("EXAMINE SELF", "See your appearance, worn items, and aspects"),
        (f"FEED <item>", f"Feed an item to {seed_name} for motes"),
        ("INVENTORY", "Show your inventory"),
        ("STATUS", "Show your character sheet"),
        ("HELP", "Show this help"),
        ("MAP [zone/ALL]", "Show the zone map"),
        ("SWITCH FOCUS TO <name>", "Switch active agent"),
        ("SAVE", "Save the game"),
        ("QUIT", "Save and exit"),
    ]
    explorer_cmds = [
        ("ATTACK <target>", "Attack an enemy"),
        ("EXPLOIT <aspect>", "Set up a tactical advantage (free +2)"),
        ("DEFEND", "Take a defensive stance (+2 to defense)"),
        ("INVOKE <aspect>", "Spend a fate point for +2 (costs FP)"),
        ("CONCEDE", "Surrender combat (gain fate points)"),
        ("SCAVENGE", "Search the room for materials"),
        ("PROBE <thing>", "Examine an item or artifact closely"),
        ("KEEP <item>", "Keep an artifact for its stat bonus"),
        ("TAKE <item>", "Pick up an item"),
        ("RECRUIT <npc>", "Try to recruit an NPC"),
        ("SEEK <aspect>", "Cross the void to a node by its aspect"),
        ("RETREAT", f"Emergency retreat (costs {seed_name} motes)"),
    ]
    steward_cmds = [
        ("CRAFT <recipe>", "Craft an item from materials"),
        ("RECIPES", "List known recipes"),
        ("BUILD <structure>", "Build a skerry structure"),
        ("ASSIGN <npc> <task>", "Assign an NPC to a task"),
        ("ORGANIZE", "View all NPC assignments"),
        ("TRADE <npc>", "Trade with an NPC"),
    ]

    for cmd, desc in universal:
        print(f"  {BOLD}{cmd:<22}{RESET} {desc}")

    if phase == "prologue":
        divider()
        print(f"  {BOLD}{'Tutorial Commands':^40}{RESET}")
        print(f"  {BOLD}{'MAP':<22}{RESET} Show the zone map")
        print(f"  {BOLD}{'SKIP':<22}{RESET} Skip the tutorial")
        return

    if phase == "explorer":
        divider()
        print(f"  {BOLD}{'Explorer Commands':^40}{RESET}")
        for cmd, desc in explorer_cmds:
            print(f"  {BOLD}{cmd:<22}{RESET} {desc}")
    elif phase == "steward":
        divider()
        print(f"  {BOLD}{'Steward Commands':^40}{RESET}")
        for cmd, desc in steward_cmds:
            print(f"  {BOLD}{cmd:<22}{RESET} {desc}")


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
