"""ASCII map renderer with fog-of-war — Imperian-style [x]-[x] notation.

Supports cardinal and diagonal connections (NW/NE/SW/SE shown as \\ and /).
Skerry layout is generated dynamically from room exits (player-placed structures).
Zone layouts remain hardcoded.
"""

from collections import deque
from engine import display


# Box rendering constants
BOX_WIDTH = 3      # [x]
H_CONNECTOR = "-"  # between rooms horizontally
H_EMPTY = " "      # no connection
V_CHAR = "|"       # vertical connector
DIAG_SE = "\\"     # southeast connector
DIAG_SW = "/"      # southwest connector
DIAG_X = "X"       # both diagonals cross

# Direction → grid offset (row_delta, col_delta)
DIR_OFFSETS = {
    "north": (-1, 0), "south": (1, 0),
    "east": (0, 1), "west": (0, -1),
    "northwest": (-1, -1), "northeast": (-1, 1),
    "southwest": (1, -1), "southeast": (1, 1),
}


# Zone grid layouts: list of (row, col, room_id) — for non-skerry zones
ZONE_LAYOUTS = {
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
            (2, 2, "vw_canopy"),
            (2, 1, "vw_greenhouse"),
            (3, 0, "vw_tanks"),
            (3, 1, "vw_promenade"),
            (3, 2, "vw_nursery"),
            (4, 1, "vw_airlock"),
        ],
    },
}


def _build_skerry_grid(rooms):
    """Generate grid positions for skerry rooms via BFS from skerry_central."""
    start = "skerry_central"
    if start not in rooms:
        return []

    placed = {start: (0, 0)}
    queue = deque([start])

    while queue:
        rid = queue.popleft()
        room = rooms.get(rid)
        if not room:
            continue
        row, col = placed[rid]

        for direction, target_id in room.exits.items():
            if target_id in placed:
                continue
            if direction in _VERTICAL_DIRS:
                continue  # UP/DOWN can't be placed on 2D grid
            target_room = rooms.get(target_id)
            if not target_room or target_room.zone != "skerry":
                continue
            offset = DIR_OFFSETS.get(direction)
            if not offset:
                continue
            placed[target_id] = (row + offset[0], col + offset[1])
            queue.append(target_id)

    # Normalize so minimum row/col is 0
    if not placed:
        return []
    min_row = min(r for r, c in placed.values())
    min_col = min(c for r, c in placed.values())
    return [(r - min_row, c - min_col, rid) for rid, (r, c) in placed.items()]


def get_zone_for_room(room_id):
    """Return the zone_id for a given room_id, or None."""
    if room_id and room_id.startswith("skerry_"):
        return "skerry"
    for zone_id, layout in ZONE_LAYOUTS.items():
        for _, _, rid in layout["grid"]:
            if rid == room_id:
                return zone_id
    return None


def _room_box(room_id, rooms, current_room_id, zone_id):
    """Render a single room box as an ANSI-colored string (fixed width)."""
    room = rooms.get(room_id)

    if not room:
        return " " * BOX_WIDTH

    if not room.discovered:
        for rid, r in rooms.items():
            if r.discovered and room_id in r.exits.values():
                return f"{display.DIM}[?]{display.RESET}"
        return " " * BOX_WIDTH

    if room_id == current_room_id:
        return f"{display.BRIGHT_YELLOW}[*]{display.RESET}"
    elif room.has_enemies():
        return f"{display.BRIGHT_RED}[!]{display.RESET}"
    elif zone_id == "skerry":
        return f"{display.GREEN}[ ]{display.RESET}"
    else:
        return f"{display.CYAN}[ ]{display.RESET}"


_VERTICAL_DIRS = {"up", "down"}


def _are_connected(room_id_a, room_id_b, rooms):
    """Check if two rooms are directly connected via planar exits.

    Ignores UP/DOWN exits — those represent vertical layers that can't be
    drawn on a 2D map without creating misleading diagonal lines.
    """
    room_a = rooms.get(room_id_a)
    if room_a:
        for d, target in room_a.exits.items():
            if target == room_id_b and d not in _VERTICAL_DIRS:
                return True
    room_b = rooms.get(room_id_b)
    if room_b:
        for d, target in room_b.exits.items():
            if target == room_id_a and d not in _VERTICAL_DIRS:
                return True
    return False


def _either_discovered(room_a, room_b, rooms):
    """Check if at least one room is discovered (for drawing connectors)."""
    a = rooms.get(room_a)
    b = rooms.get(room_b)
    return (a and a.discovered) or (b and b.discovered)


def _visible_connection(rid_a, rid_b, rooms):
    """True if rooms are connected AND at least one is discovered."""
    return (rid_a and rid_b
            and _are_connected(rid_a, rid_b, rooms)
            and _either_discovered(rid_a, rid_b, rooms))


def _render_grid(grid, zone_name, zone_id, rooms, current_room_id):
    """Render a grid layout with cardinal and diagonal connectors."""
    if not grid:
        return [f"  No rooms to display."]

    max_row = max(r for r, c, _ in grid)
    max_col = max(c for r, c, _ in grid)

    pos_to_room = {}
    for r, c, rid in grid:
        pos_to_room[(r, c)] = rid

    lines = []
    lines.append(f"  {display.BOLD}{zone_name}{display.RESET}")
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
                if _visible_connection(rid, rid_right, rooms):
                    box_parts.append(f"{display.DIM}{H_CONNECTOR}{display.RESET}")
                else:
                    box_parts.append(H_EMPTY)

        lines.append("  " + "".join(box_parts))

        # ── Connector line between this row and next ──
        if row < max_row:
            # Build as a character list, then join
            line_width = (max_col + 1) * BOX_WIDTH + max_col  # cells + gaps
            conn = [" "] * line_width

            for col in range(max_col + 1):
                rid_here = pos_to_room.get((row, col))
                rid_below = pos_to_room.get((row + 1, col))
                center = col * (BOX_WIDTH + 1) + 1  # center of cell

                # Vertical connection
                if _visible_connection(rid_here, rid_below, rooms):
                    if 0 <= center < line_width:
                        conn[center] = V_CHAR

                # Diagonal SE: (row, col) → (row+1, col+1)
                if col < max_col:
                    gap_pos = col * (BOX_WIDTH + 1) + BOX_WIDTH  # gap after cell
                    rid_se = pos_to_room.get((row + 1, col + 1))
                    rid_sw_src = pos_to_room.get((row, col + 1))
                    rid_sw_dst = pos_to_room.get((row + 1, col))

                    has_se = _visible_connection(rid_here, rid_se, rooms)
                    has_sw = _visible_connection(rid_sw_src, rid_sw_dst, rooms)

                    if 0 <= gap_pos < line_width:
                        if has_se and has_sw:
                            conn[gap_pos] = DIAG_X
                        elif has_se:
                            conn[gap_pos] = DIAG_SE
                        elif has_sw:
                            conn[gap_pos] = DIAG_SW

            # Apply dim styling to connector characters
            styled = []
            for ch in conn:
                if ch in (V_CHAR, DIAG_SE, DIAG_SW, DIAG_X):
                    styled.append(f"{display.DIM}{ch}{display.RESET}")
                else:
                    styled.append(ch)
            lines.append("  " + "".join(styled))

    lines.append("")

    # Legend
    lines.append(f"  {display.BRIGHT_YELLOW}[*]{display.RESET} You  "
                 f"[ ] Explored  "
                 f"{display.DIM}[?]{display.RESET} Unknown  "
                 f"{display.BRIGHT_RED}[!]{display.RESET} Enemies")

    return lines


def render_zone_map(zone_id, rooms, current_room_id):
    """Render a fog-of-war ASCII map for a single zone."""
    if zone_id == "skerry":
        grid = _build_skerry_grid(rooms)
        return _render_grid(grid, "The Skerry", "skerry", rooms, current_room_id)

    layout = ZONE_LAYOUTS.get(zone_id)
    if not layout:
        return [f"  Unknown zone: {zone_id}"]

    return _render_grid(layout["grid"], layout["name"], zone_id, rooms, current_room_id)


def render_all_zones_overview(zones_data, rooms, current_room_id):
    """Render a high-level overview of all zones."""
    lines = []
    lines.append(f"  {display.BOLD}Zone Overview{display.RESET}")
    lines.append("")

    current_zone = get_zone_for_room(current_room_id)

    # Skerry (dynamic)
    skerry_grid = _build_skerry_grid(rooms)
    skerry_total = len(skerry_grid)
    skerry_discovered = sum(1 for _, _, rid in skerry_grid
                            if rooms.get(rid) and rooms[rid].discovered)
    marker = " *" if current_zone == "skerry" else ""
    bar = "\u2588" * skerry_discovered + "\u2591" * (skerry_total - skerry_discovered)
    lines.append(f"  {display.GREEN}The Skerry{display.RESET} [{bar}] {skerry_discovered}/{skerry_total}{marker}")

    # Other zones (hardcoded)
    for zone_id, layout in ZONE_LAYOUTS.items():
        grid = layout["grid"]
        total = len(grid)
        discovered = sum(1 for _, _, rid in grid
                        if rooms.get(rid) and rooms[rid].discovered)

        zone_marker = " *" if zone_id == current_zone else ""

        if discovered == 0:
            lines.append(f"  {display.DIM}??? (undiscovered zone){display.RESET}")
        else:
            if zone_id == current_zone:
                color = display.BRIGHT_YELLOW
            else:
                color = display.CYAN
            bar = "\u2588" * discovered + "\u2591" * (total - discovered)
            lines.append(f"  {color}{layout['name']}{display.RESET} [{bar}] {discovered}/{total}{zone_marker}")

    lines.append("")
    lines.append(f"  Type {display.BOLD}MAP <zone>{display.RESET} for a detailed view.")
    lines.append(f"  Zones: skerry, debris, coral, wreck, verdant")

    return lines


def resolve_zone_name(name):
    """Resolve a user-typed zone name to a zone_id."""
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
