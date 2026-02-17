"""ASCII map renderer with fog-of-war."""

from engine import display


# Box rendering constants
BOX_WIDTH = 12     # [xxxxxxxxxx]
LABEL_WIDTH = 10   # inside brackets
H_CONNECTOR = " \u2500 "  # ─
H_EMPTY = "   "
V_CHAR = "\u2502"  # │
CELL_PITCH = BOX_WIDTH + len(H_CONNECTOR)  # 15


# Short labels for each room
ROOM_LABELS = {
    # Skerry
    "skerry_central": "Central",
    "skerry_shelter": "Shelter",
    "skerry_hollow": "Hollow",
    "skerry_landing": "Landing",
    # Debris Field
    "df_entrance": "Entrance",
    "df_cargo_bay": "Cargo Bay",
    "df_hull_breach": "Breach",
    "df_control_room": "Control",
    "df_engine_room": "Engine",
    # Coral Thicket
    "ct_entrance": "Threshold",
    "ct_grove": "Grove",
    "ct_tunnel": "Tunnel",
    "ct_spore_chamber": "Spore Ch.",
    "ct_heart": "Heart",
    # Frozen Wreck
    "fw_entrance": "Bow",
    "fw_corridor": "Corridor",
    "fw_observation": "Observ.",
    "fw_quarters": "Quarters",
    "fw_armory": "Armory",
    "fw_vault": "Vault",
}


# Zone grid layouts: list of (row, col, room_id)
ZONE_LAYOUTS = {
    "skerry": {
        "name": "The Skerry",
        "grid": [
            (0, 0, "skerry_shelter"),
            (1, 0, "skerry_central"),
            (1, 1, "skerry_hollow"),
            (2, 0, "skerry_landing"),
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
}


def get_zone_for_room(room_id):
    """Return the zone_id for a given room_id, or None."""
    for zone_id, layout in ZONE_LAYOUTS.items():
        for _, _, rid in layout["grid"]:
            if rid == room_id:
                return zone_id
    return None


def _is_visible(room_id, rooms):
    """Check if a room should be visible on the map.

    A room is visible if:
    - It has been discovered, OR
    - It is adjacent (connected by exit) to a discovered room
    """
    room = rooms.get(room_id)
    if not room:
        return False
    if room.discovered:
        return True
    # Check if any room that has an exit leading here is discovered
    for rid, r in rooms.items():
        if r.discovered and room_id in r.exits.values():
            return True
    return False


def _room_box(room_id, rooms, current_room_id, zone_id):
    """Render a single room box as an ANSI-colored string (fixed width)."""
    room = rooms.get(room_id)

    if not _is_visible(room_id, rooms):
        # Completely hidden
        return " " * BOX_WIDTH

    if room and not room.discovered:
        # Adjacent to discovered but not yet visited
        padded = "???".center(LABEL_WIDTH)
        return f"{display.DIM}[{padded}]{display.RESET}"

    label = ROOM_LABELS.get(room_id, room_id[:LABEL_WIDTH])

    if room_id == current_room_id:
        padded = f"*{label}"[:LABEL_WIDTH].center(LABEL_WIDTH)
        return f"{display.BRIGHT_YELLOW}[{padded}]{display.RESET}"
    elif room and room.has_enemies():
        padded = label[:LABEL_WIDTH].center(LABEL_WIDTH)
        return f"{display.BRIGHT_RED}[{padded}]{display.RESET}"
    elif zone_id == "skerry":
        padded = label[:LABEL_WIDTH].center(LABEL_WIDTH)
        return f"{display.GREEN}[{padded}]{display.RESET}"
    else:
        padded = label[:LABEL_WIDTH].center(LABEL_WIDTH)
        return f"{display.CYAN}[{padded}]{display.RESET}"


def _are_connected(room_id_a, room_id_b, rooms):
    """Check if two rooms are directly connected via exits."""
    room_a = rooms.get(room_id_a)
    if room_a and room_id_b in room_a.exits.values():
        return True
    room_b = rooms.get(room_id_b)
    if room_b and room_id_a in room_b.exits.values():
        return True
    return False


def _both_visible(room_a, room_b, rooms):
    """Check if both rooms are visible (for drawing connectors)."""
    return _is_visible(room_a, rooms) and _is_visible(room_b, rooms)


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
                if rid and rid_right and _are_connected(rid, rid_right, rooms) and _both_visible(rid, rid_right, rooms):
                    box_parts.append(f"{display.DIM}{H_CONNECTOR}{display.RESET}")
                else:
                    box_parts.append(H_EMPTY)

        lines.append("  " + "".join(box_parts))

        # ── Vertical connectors line (between this row and next) ──
        if row < max_row:
            vert_parts = []
            for col in range(max_col + 1):
                rid_here = pos_to_room.get((row, col))
                # Check for any connection going down from any room in this row
                # to any room in the next row at this column
                has_vert = False
                rid_below = pos_to_room.get((row + 1, col))
                if rid_below:
                    # Check direct vertical: room at (row, col) connects to (row+1, col)
                    if rid_here and _are_connected(rid_here, rid_below, rooms) and _both_visible(rid_here, rid_below, rooms):
                        has_vert = True
                    # Check diagonal: any room in this row connects to (row+1, col)
                    if not has_vert:
                        for c2 in range(max_col + 1):
                            if c2 == col:
                                continue
                            rid_other = pos_to_room.get((row, c2))
                            if rid_other and _are_connected(rid_other, rid_below, rooms) and _both_visible(rid_other, rid_below, rooms):
                                has_vert = True
                                break

                if has_vert:
                    # Center the │ in the box width
                    left_pad = BOX_WIDTH // 2
                    right_pad = BOX_WIDTH - left_pad - 1
                    vert_parts.append(" " * left_pad + f"{display.DIM}{V_CHAR}{display.RESET}" + " " * right_pad)
                else:
                    vert_parts.append(" " * BOX_WIDTH)

                if col < max_col:
                    vert_parts.append(H_EMPTY)

            lines.append("  " + "".join(vert_parts))

    lines.append("")

    # Legend
    lines.append(f"  {display.BRIGHT_YELLOW}*{display.RESET} = You are here  "
                 f"{display.DIM}???{display.RESET} = Unexplored  "
                 f"{display.BRIGHT_RED}Red{display.RESET} = Enemies")

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
    lines.append(f"  Zones: skerry, debris, coral, wreck")

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
    }
    return aliases.get(name)
