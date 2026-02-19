"""Recruit minigame — grid-walking persuasion puzzle.

A colored grid where the player navigates tile to tile using compass directions.
Each color represents a conversational thread; stepping on a color resets its
counter while all other counters tick down. When a counter hits 0, that color's
unvisited tiles are eliminated. Score = steps taken. Reach the threshold to win.
"""

import random
from collections import deque

from engine import display

# ── Colors ────────────────────────────────────────────────────────────

# (char, ANSI code, label, conversational topic)
RECRUIT_COLORS = [
    ("R", "\033[91m", "Red",    "Safety"),
    ("G", "\033[92m", "Green",  "Growth"),
    ("B", "\033[94m", "Blue",   "Community"),
    ("Y", "\033[93m", "Yellow", "Purpose"),
    ("O", "\033[38;5;208m", "Orange", "Stability"),
]

MAX_COUNTER = 7

# ── Difficulty mapping ────────────────────────────────────────────────

# recruit_dc -> (grid_size, num_colors, base_threshold)
RECRUIT_DIFFICULTIES = {
    0: (7, 3, 20),
    1: (6, 3, 20),
    2: (6, 4, 22),
    3: (5, 4, 20),
}

# ── Flavor text ───────────────────────────────────────────────────────

# Generic fallback for NPCs without recruit_flavor data
_GENERIC_FLAVOR = {
    "step_early": [
        "You mention the stable ground. Solid footing, in the void — that's no small thing.",
        "You describe the world seed. Their expression flickers — curiosity, maybe.",
        "You talk about the shelter. Walls. A roof that isn't vacuum.",
        "You bring up the others who've already come. Safety in numbers.",
        "You gesture at the void around you. 'This isn't living. Come see what is.'",
    ],
    "step_mid": [
        "They ask about the others. How many? What skills? A good sign.",
        "You describe what the seed can grow. Real food. Their eyes widen.",
        "They press you on defense. Your answer seems to satisfy.",
        "They lean forward. The skepticism is fading.",
        "You share a specific detail about the skerry. It lands well.",
    ],
    "step_late": [
        "They've stopped arguing and started asking practical questions.",
        "They glance around at their current surroundings with fresh eyes.",
        "The conversation shifts from 'why would I' to 'how would I.'",
        "They're nodding along now. You can feel the resistance breaking.",
        "Something you said really resonated. They're almost there.",
    ],
    "color": {
        "R": "You make a point about safety — shelter, walls, protection from the void.",
        "G": "You talk about the world seed, about growth. Real things, growing here.",
        "B": "You bring up community — other survivors, not being alone anymore.",
        "Y": "You appeal to purpose — meaningful work, building something that matters.",
        "O": "You emphasize stability — pragmatism, durability, things that last.",
    },
    "atmosphere": [
        "They watch you carefully, arms crossed.",
        "They're listening, but haven't committed to anything yet.",
        "They're leaning in, listening closely.",
        "They're nodding slowly. You're getting through.",
    ],
    "warn": [
        "You sense one of your arguments growing stale...",
        "A line of persuasion is losing relevance the longer you ignore it...",
        "You're neglecting a thread of conversation — it's starting to fray...",
    ],
    "eliminate": [
        "That whole line of argument falls flat — you waited too long to follow up.",
        "An entire avenue of persuasion collapses. You let it go cold.",
        "The moment passes. That topic is closed for good.",
    ],
}

# ── Board generation ──────────────────────────────────────────────────


def generate_validated_board(grid_size, num_colors, seed=None):
    """Generate a valid board with structural checks.

    Returns (board, seed) where board is a 2D list of color chars.
    Regenerates up to 20 times if validation fails.
    """
    if seed is None:
        seed = random.randint(0, 0xFFFFFF)

    for attempt in range(20):
        rng = random.Random(seed + attempt)
        colors = [c[0] for c in RECRUIT_COLORS[:num_colors]]
        board = _generate_board(grid_size, num_colors, rng)

        if _validate_board(board, grid_size, num_colors):
            final_seed = seed + attempt
            return board, final_seed

    # Fallback: return last generated board even if imperfect
    return board, seed + 19


def _generate_board(grid_size, num_colors, rng):
    """Generate a random NxN grid of colors."""
    colors = [c[0] for c in RECRUIT_COLORS[:num_colors]]
    board = []
    for r in range(grid_size):
        row = []
        for c in range(grid_size):
            row.append(rng.choice(colors))
        board.append(row)
    return board


def _validate_board(board, grid_size, num_colors):
    """Check structural validity of a board.

    1. All tiles reachable from center
    2. No single color exceeds 40% of tiles
    3. Each color appears at least grid_size times
    """
    total_tiles = grid_size * grid_size
    colors_used = [c[0] for c in RECRUIT_COLORS[:num_colors]]

    # Count color distribution
    counts = {}
    for row in board:
        for cell in row:
            counts[cell] = counts.get(cell, 0) + 1

    # Check all colors present with minimum count
    for color in colors_used:
        if counts.get(color, 0) < grid_size:
            return False

    # Check no color exceeds 40%
    max_allowed = int(total_tiles * 0.4)
    for color in colors_used:
        if counts.get(color, 0) > max_allowed:
            return False

    # Check connectivity from center
    center = (grid_size // 2, grid_size // 2)
    visited = set()
    queue = deque([center])
    visited.add(center)
    while queue:
        r, c = queue.popleft()
        for nr, nc in get_adjacent(r, c, grid_size):
            if (nr, nc) not in visited:
                visited.add((nr, nc))
                queue.append((nr, nc))

    if len(visited) != total_tiles:
        return False

    return True


# ── Board state helpers ───────────────────────────────────────────────


def get_adjacent(r, c, grid_size):
    """Return list of (row, col) for NSEW neighbors within bounds."""
    neighbors = []
    if r > 0:
        neighbors.append((r - 1, c))  # North
    if r < grid_size - 1:
        neighbors.append((r + 1, c))  # South
    if c > 0:
        neighbors.append((r, c - 1))  # West
    if c < grid_size - 1:
        neighbors.append((r, c + 1))  # East
    return neighbors


def get_available_directions(state):
    """Return list of direction names the player can move."""
    r, c = state["pos"]
    grid_size = state["grid_size"]
    visited = state["visited"]
    eliminated = state["eliminated"]
    directions = []

    checks = [
        (-1, 0, "WHEEDLE"),
        (0, -1, "APPEAL"),
        (1, 0, "SUGGEST"),
        (0, 1, "DESCRIBE"),
    ]
    for dr, dc, name in checks:
        nr, nc = r + dr, c + dc
        if 0 <= nr < grid_size and 0 <= nc < grid_size:
            if (nr, nc) not in visited and (nr, nc) not in eliminated:
                directions.append(name)
    return directions


def has_valid_moves(state):
    """Check if the player has any valid moves from current position."""
    return len(get_available_directions(state)) > 0


def direction_to_delta(direction):
    """Convert a direction string to (dr, dc)."""
    return {
        "WHEEDLE": (-1, 0),
        "SUGGEST": (1, 0),
        "APPEAL": (0, -1),
        "DESCRIBE": (0, 1),
    }.get(direction.upper())


def apply_move(state, direction):
    """Apply a move and return (success, messages).

    Messages is a list of strings to display (flavor, warnings, eliminations).
    """
    dr, dc = direction_to_delta(direction)
    r, c = state["pos"]
    nr, nc = r + dr, c + dc
    grid_size = state["grid_size"]
    messages = []

    # Bounds check
    if not (0 <= nr < grid_size and 0 <= nc < grid_size):
        return False, ["You can't go that way — edge of the conversation space."]

    # Already visited
    if (nr, nc) in state["visited"]:
        return False, ["You've already made that point. Try a different direction."]

    # Eliminated
    if (nr, nc) in state["eliminated"]:
        return False, ["That line of argument is dead. Pick another direction."]

    # Valid move — update state
    state["pos"] = (nr, nc)
    state["visited"].add((nr, nc))
    state["score"] += 1

    stepped_color = state["board"][nr][nc]

    # Reset stepped color counter, decrement others
    counters = state["counters"]
    counters[stepped_color] = MAX_COUNTER

    newly_eliminated_colors = []
    for color in list(counters.keys()):
        if color != stepped_color:
            counters[color] -= 1
            if counters[color] <= 0:
                newly_eliminated_colors.append(color)

    # Look up NPC-specific flavor, falling back to generic
    flavor_data = state.get("npc_data", {}).get("recruit_flavor", _GENERIC_FLAVOR)

    # Color-specific flavor (occasional, not every step)
    rng = random.Random(state["score"] + hash(direction))
    if rng.random() < 0.4:
        color_flavor = flavor_data.get("color", {}).get(stepped_color)
        if color_flavor:
            messages.append(color_flavor)
    else:
        # Progress-based flavor
        progress = state["score"] / state["threshold"]
        flavor = _pick_step_flavor(flavor_data, progress, rng)
        if flavor:
            messages.append(flavor)

    # Warnings for counters at 2
    warn_lines = flavor_data.get("warn", _GENERIC_FLAVOR["warn"])
    for color in counters:
        if counters[color] == 2 and color not in newly_eliminated_colors:
            messages.append(f"{display.BRIGHT_RED}{rng.choice(warn_lines)}{display.RESET}")

    # Eliminate colors that hit 0
    elim_lines = flavor_data.get("eliminate", _GENERIC_FLAVOR["eliminate"])
    for color in newly_eliminated_colors:
        del counters[color]
        # Remove all unvisited tiles of this color
        for er in range(grid_size):
            for ec in range(grid_size):
                if state["board"][er][ec] == color and (er, ec) not in state["visited"]:
                    state["eliminated"].add((er, ec))
        messages.append(f"{display.RED}{rng.choice(elim_lines)}{display.RESET}")

    return True, messages


# ── Threshold calculation ─────────────────────────────────────────────


def calculate_threshold(base_threshold, shifts, grid_size):
    """Apply FATE roll adjustment to threshold.

    Positive shifts = easier (lower threshold).
    Floor: 40% of total tiles.
    Cap: 85% of total tiles.
    """
    total_tiles = grid_size * grid_size
    adjusted = base_threshold - (shifts * 2)
    floor = int(total_tiles * 0.4)
    cap = int(total_tiles * 0.85)
    return max(floor, min(cap, adjusted))


# ── Display ───────────────────────────────────────────────────────────

# ANSI color map for board tiles
_COLOR_ANSI = {
    "R": "\033[91m",          # bright red
    "G": "\033[92m",          # bright green
    "B": "\033[94m",          # bright blue
    "Y": "\033[93m",          # bright yellow
    "O": "\033[38;5;208m",    # bright orange
}

_COLOR_DIM = {
    "R": "\033[31m",          # dim red
    "G": "\033[32m",          # dim green
    "B": "\033[34m",          # dim blue
    "Y": "\033[33m",          # dim yellow
    "O": "\033[38;5;130m",    # dim orange
}


def display_board(state, npc_name):
    """Render the recruit puzzle board to stdout."""
    grid_size = state["grid_size"]
    board = state["board"]
    pos = state["pos"]
    visited = state["visited"]
    eliminated = state["eliminated"]
    counters = state["counters"]
    score = state["score"]
    threshold = state["threshold"]

    print()
    print(f"{display.BOLD}{display.BRIGHT_CYAN}═══ Recruiting {npc_name} ═══{display.RESET}")
    print()

    # Counter display
    counter_parts = []
    for color_char, ansi, label, topic in RECRUIT_COLORS[:state["num_colors"]]:
        if color_char in counters:
            val = counters[color_char]
            if val <= 2:
                counter_parts.append(f"{display.BRIGHT_RED}{color_char}:{val}{display.RESET}")
            else:
                counter_parts.append(f"{ansi}{color_char}:{val}{display.RESET}")
        else:
            counter_parts.append(f"{display.DIM}{color_char}:X{display.RESET}")
    counter_str = "  ".join(counter_parts)

    pct = int(score / threshold * 100) if threshold > 0 else 0
    progress_str = f"{score}/{threshold}"
    if pct >= 75:
        progress_color = display.BRIGHT_GREEN
    elif pct >= 35:
        progress_color = display.BRIGHT_YELLOW
    else:
        progress_color = display.WHITE
    print(f"  Counters: {counter_str}      Progress: {progress_color}{progress_str}{display.RESET}")
    print()

    # Get valid adjacent cells for highlighting
    valid_adjacent = set()
    if pos:
        for nr, nc in get_adjacent(pos[0], pos[1], grid_size):
            if (nr, nc) not in visited and (nr, nc) not in eliminated:
                valid_adjacent.add((nr, nc))

    # Column headers
    header = "      " + "   ".join(f"{i+1}" for i in range(grid_size))
    print(f"{display.DIM}{header}{display.RESET}")

    # Grid rows
    for r in range(grid_size):
        row_str = f"  {display.DIM}{r+1}{display.RESET}   "
        for c in range(grid_size):
            if (r, c) == pos:
                # Player position
                cell = f"{display.BOLD}\033[97m @  {display.RESET}"
            elif (r, c) in visited:
                # Already visited
                cell = f"{display.DIM}..  {display.RESET}"
            elif (r, c) in eliminated:
                # Eliminated
                cell = f"\033[2m\033[90m··  {display.RESET}"
            else:
                color_char = board[r][c]
                counter_val = counters.get(color_char, 0)
                if (r, c) in valid_adjacent:
                    # Bright — valid move target
                    ansi = _COLOR_ANSI.get(color_char, "")
                    cell = f"{ansi}{color_char}{counter_val}  {display.RESET}"
                else:
                    # Dim — not adjacent
                    ansi = _COLOR_DIM.get(color_char, display.DIM)
                    cell = f"{ansi}{color_char}{counter_val}  {display.RESET}"
            row_str += cell
        print(row_str)

    print()

    # Available moves
    dirs = get_available_directions(state)
    if dirs:
        dir_str = ", ".join(
            f"{display.BRIGHT_WHITE}{d[0]}{display.RESET}{display.BOLD}{d[1:]}{display.RESET}"
            for d in dirs
        )
        print(f"  You could: {dir_str}")
    else:
        print(f"  {display.DIM}No valid moves remain.{display.RESET}")

    print()


def display_help_text():
    """Show minigame rules."""
    print(f"""
{display.BOLD}═══ Recruit Minigame — How It Works ═══{display.RESET}

  You're trying to persuade an NPC to join your skerry by navigating a
  grid of colored tiles. Each color represents a line of argument.

  {display.BOLD}Tactics:{display.RESET} Choose how to steer the conversation:
    {display.BOLD}W{display.RESET} / WHEEDLE     Coax them — nudge upward
    {display.BOLD}A{display.RESET} / APPEAL       Appeal to emotion — press left
    {display.BOLD}S{display.RESET} / SUGGEST      Plant an idea — push downward
    {display.BOLD}D{display.RESET} / DESCRIBE     Paint a picture — reach right

  You can't revisit a point you've already made.

  {display.BOLD}Counters:{display.RESET} Each color has a counter (starts at {MAX_COUNTER}). When you step
  on a color, its counter resets to {MAX_COUNTER}. All OTHER colors lose 1.

  {display.BOLD}Elimination:{display.RESET} When a counter hits 0, all unvisited tiles of that
  color are removed from the board. Balance your approach carefully!

  {display.BOLD}Scoring:{display.RESET} Each move = 1 point. Reach the threshold to succeed.

  {display.BOLD}Game Over:{display.RESET} When you have no valid moves remaining.

  {display.BOLD}Other:{display.RESET}
    QUIT / ABANDON   Give up this attempt
    HELP / ?         Show this help
    (empty)          Redisplay the board
""")


# ── Flavor helpers ────────────────────────────────────────────────────


def _pick_step_flavor(flavor_data, progress_ratio, rng=None):
    """Pick a progress-appropriate flavor line from NPC flavor data."""
    rng = rng or random
    if progress_ratio < 0.35:
        pool = flavor_data.get("step_early", _GENERIC_FLAVOR["step_early"])
    elif progress_ratio < 0.75:
        pool = flavor_data.get("step_mid", _GENERIC_FLAVOR["step_mid"])
    else:
        pool = flavor_data.get("step_late", _GENERIC_FLAVOR["step_late"])
    return rng.choice(pool)


def get_step_flavor(recruit_state, progress_ratio, rng=None):
    """Pick a progress-appropriate flavor line for an NPC."""
    flavor_data = recruit_state.get("npc_data", {}).get("recruit_flavor", _GENERIC_FLAVOR)
    return _pick_step_flavor(flavor_data, progress_ratio, rng)


def get_npc_flavor(recruit_state, progress_ratio):
    """Get NPC-specific atmosphere text based on progress."""
    flavor_data = recruit_state.get("npc_data", {}).get("recruit_flavor", _GENERIC_FLAVOR)
    atmosphere = flavor_data.get("atmosphere", _GENERIC_FLAVOR["atmosphere"])

    # Map progress to atmosphere index (4 entries: 0-25%, 25-50%, 50-75%, 75%+)
    if progress_ratio < 0.25:
        idx = 0
    elif progress_ratio < 0.5:
        idx = 1
    elif progress_ratio < 0.75:
        idx = 2
    else:
        idx = 3

    idx = min(idx, len(atmosphere) - 1)
    return atmosphere[idx]


# ── State factory ─────────────────────────────────────────────────────


def create_recruit_state(npc_id, npc, grid_size, num_colors, threshold, seed=None):
    """Create a fresh recruit_state dict for the minigame."""
    board, final_seed = generate_validated_board(grid_size, num_colors, seed)

    # Start at center
    center = (grid_size // 2, grid_size // 2)

    # Initial counters — all colors start at MAX_COUNTER
    colors_used = [c[0] for c in RECRUIT_COLORS[:num_colors]]
    counters = {c: MAX_COUNTER for c in colors_used}

    # The starting tile counts as visited; reset its color, decrement others
    start_color = board[center[0]][center[1]]
    counters[start_color] = MAX_COUNTER
    for color in counters:
        if color != start_color:
            counters[color] -= 1

    return {
        "board": board,
        "pos": center,
        "visited": {center},
        "eliminated": set(),
        "counters": counters,
        "score": 1,  # starting tile counts as first step
        "threshold": threshold,
        "grid_size": grid_size,
        "num_colors": num_colors,
        "npc_id": npc_id,
        "npc_name": npc.get("name", npc_id),
        "npc_data": npc,
        "seed": final_seed,
    }
