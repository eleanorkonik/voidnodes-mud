"""ASCII map renderer with fog-of-war — Imperian-style [x]-[x] notation."""

from engine import display


# Box rendering constants
BOX_WIDTH = 3      # [x]
H_CONNECTOR = "-"  # between rooms horizontally
H_EMPTY = " "      # no connection
V_CHAR = "|"       # vertical connector


# Zone grid layouts: list of (row, col, room_id)
ZONE_LAYOUTS = {
    "skerry": {
        "name": "The Skerry",
        "grid": [
            (0, 1, "skerry_shelter"),
            (1, 0, "skerry_junkyard"),
            (1, 1, "skerry_central"),
            (1, 2, "skerry_hollow"),
            (2, 1, "skerry_landing"),
        ],
    },
    "debris_field": {
        "name": "The Debris Field",
        "grid": [
            (0, 0, "df_engine_room"),
            (1, 0, "df_cargo_bay"),
            (1, 1, "df_control_room"),
            (2, 0, "df_entrance"),
            (2, 1, "df_hull_breach"),
        ],
    },
    "coral_thicket": {
        "name": "The Coral Thicket",
        "grid": [
            (0, 0, "ct_heart"),
            (1, 0, "ct_grove"),
            (1, 1, "ct_spore_chamber"),
            (2, 0, "ct_entrance"),
            (2, 1, "ct_tunnel"),
        ],
    },
    "frozen_wreck": {
        "name": "The Frozen Wreck",
        "grid": [
            (0, 0, "fw_armory"),
            (0, 1, "fw_vault"),
            (1, 0, "fw_corridor"),
            (1, 1, "fw_quarters"),
            (2, 0, "fw_entrance"),
            (2, 1, "fw_observation"),
        ],
    },
    "verdant_wreck": {
        "name": "The Verdant Wreck",
        "grid": [
            (0, 0, "vw_observation"),
            (0, 1, "vw_heart"),
            (1, 0, "vw_control"),
            (1, 1, "vw_root_wall"),
            (1, 2, "vw_canopy"),
            (2, 1, "vw_greenhouse"),
            (3, 0, "vw_tanks"),
            (3, 1, "vw_promenade"),
            (3, 2, "vw_nursery"),
            (4, 1, "vw_airlock"),
        ],
    },
}


def get_zone_for_room(room_id):
    """Return the zone_id for a given room_id, or None."""
    for zone_id, layout in ZONE_LAYOUTS.items():
        for _, _, rid in layout["grid"]:
            if rid == room_id:
                return zone_id
    return None



def _room_box(room_id, rooms, current_room_id, zone_id):
    """Render a single room box as an ANSI-colored string (fixed width)."""
    room = rooms.get(room_id)

    if not room or not room.discovered:
        # Hidden or undiscovered — no box (connectors still hint at exits)
        return " " * BOX_WIDTH

    if room_id == current_room_id:
        return f"{display.BRIGHT_YELLOW}[*]{display.RESET}"
    elif room.has_enemies():
        return f"{display.BRIGHT_RED}[!]{display.RESET}"
    elif zone_id == "skerry":
        return f"{display.GREEN}[ ]{display.RESET}"
    else:
        return f"{display.CYAN}[ ]{display.RESET}"


def _are_connected(room_id_a, room_id_b, rooms):
    """Check if two rooms are directly connected via exits."""
    room_a = rooms.get(room_id_a)
    if room_a and room_id_b in room_a.exits.values():
        return True
    room_b = rooms.get(room_id_b)
    if room_b and room_id_a in room_b.exits.values():
        return True
    return False


def _either_discovered(room_a, room_b, rooms):
    """Check if at least one room is discovered (for drawing connectors)."""
    a = rooms.get(room_a)
    b = rooms.get(room_b)
    return (a and a.discovered) or (b and b.discovered)


def render_zone_map(zone_id, rooms, current_room_id):
    """Render a fog-of-war ASCII map for a single zone.

    Returns a list of strings (lines) to print.
    """
    layout = ZONE_LAYOUTS.get(zone_id)
    if not layout:
        return [f"  Unknown zone: {zone_id}"]

    grid = layout["grid"]
    max_row = max(r for r, c, _ in grid)
    max_col = max(c for r, c, _ in grid)

    # Build lookup: (row, col) -> room_id
    pos_to_room = {}
    for r, c, rid in grid:
        pos_to_room[(r, c)] = rid

    lines = []
    lines.append(f"  {display.BOLD}{layout['name']}{display.RESET}")
    lines.append("")

    for row in range(max_row + 1):
        # ── Room boxes line ──
        box_parts = []
        for col in range(max_col + 1):
            rid = pos_to_room.get((row, col))
            if rid:
                box_parts.append(_room_box(rid, rooms, current_room_id, zone_id))
            else:
                box_parts.append(" " * BOX_WIDTH)

            # Horizontal connector between this col and col+1
            if col < max_col:
                rid_right = pos_to_room.get((row, col + 1))
                if rid and rid_right and _are_connected(rid, rid_right, rooms) and _either_discovered(rid, rid_right, rooms):
                    box_parts.append(f"{display.DIM}{H_CONNECTOR}{display.RESET}")
                else:
                    box_parts.append(H_EMPTY)

        lines.append("  " + "".join(box_parts))

        # ── Vertical connectors line (between this row and next) ──
        if row < max_row:
            vert_parts = []
            for col in range(max_col + 1):
                rid_here = pos_to_room.get((row, col))
                has_vert = False
                rid_below = pos_to_room.get((row + 1, col))
                if rid_below:
                    if rid_here and _are_connected(rid_here, rid_below, rooms) and _either_discovered(rid_here, rid_below, rooms):
                        has_vert = True
                    if not has_vert:
                        for c2 in range(max_col + 1):
                            if c2 == col:
                                continue
                            rid_other = pos_to_room.get((row, c2))
                            if rid_other and _are_connected(rid_other, rid_below, rooms) and _either_discovered(rid_other, rid_below, rooms):
                                has_vert = True
                                break

                if has_vert:
                    # Center | under [x] — 1 space + | + 1 space
                    vert_parts.append(f" {display.DIM}{V_CHAR}{display.RESET} ")
                else:
                    vert_parts.append(" " * BOX_WIDTH)

                if col < max_col:
                    vert_parts.append(H_EMPTY)

            lines.append("  " + "".join(vert_parts))

    lines.append("")

    # Legend
    lines.append(f"  {display.BRIGHT_YELLOW}[*]{display.RESET} You  "
                 f"[ ] Explored  "
                 f"{display.BRIGHT_RED}[!]{display.RESET} Enemies")

    return lines


def render_all_zones_overview(zones_data, rooms, current_room_id):
    """Render a high-level overview of all zones.

    Shows zone names with discovery progress.
    """
    lines = []
    lines.append(f"  {display.BOLD}Zone Overview{display.RESET}")
    lines.append("")

    current_zone = get_zone_for_room(current_room_id)

    for zone_id, layout in ZONE_LAYOUTS.items():
        grid = layout["grid"]
        total = len(grid)
        discovered = sum(1 for _, _, rid in grid
                        if rooms.get(rid) and rooms[rid].discovered)

        marker = " *" if zone_id == current_zone else ""

        if discovered == 0 and zone_id != "skerry":
            # Completely undiscovered non-skerry zone
            lines.append(f"  {display.DIM}??? (undiscovered zone){display.RESET}")
        else:
            # Pick color based on zone type
            if zone_id == "skerry":
                color = display.GREEN
            elif zone_id == current_zone:
                color = display.BRIGHT_YELLOW
            else:
                color = display.CYAN

            bar = "\u2588" * discovered + "\u2591" * (total - discovered)
            lines.append(f"  {color}{layout['name']}{display.RESET} [{bar}] {discovered}/{total}{marker}")

    lines.append("")
    lines.append(f"  Type {display.BOLD}MAP <zone>{display.RESET} for a detailed view.")
    lines.append(f"  Zones: skerry, debris, coral, wreck, verdant")

    return lines


def resolve_zone_name(name):
    """Resolve a user-typed zone name to a zone_id.

    Accepts partial matches like 'debris', 'coral', 'wreck', 'skerry'.
    """
    name = name.lower().strip()
    aliases = {
        "skerry": "skerry",
        "home": "skerry",
        "debris": "debris_field",
        "debris_field": "debris_field",
        "coral": "coral_thicket",
        "coral_thicket": "coral_thicket",
        "thicket": "coral_thicket",
        "wreck": "frozen_wreck",
        "frozen": "frozen_wreck",
        "frozen_wreck": "frozen_wreck",
        "ice": "frozen_wreck",
        "verdant": "verdant_wreck",
        "verdant_wreck": "verdant_wreck",
        "biodome": "verdant_wreck",
        "jungle": "verdant_wreck",
    }
    return aliases.get(name)
