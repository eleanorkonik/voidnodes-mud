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

# ── Per-NPC flavor text ───────────────────────────────────────────────
#
# Each NPC has: step (early/mid/late), color reactions, atmosphere,
# warn, and eliminate text reflecting their personality.
# Keyed by npc_id. Generic fallback for unknown NPCs.

NPC_FLAVOR = {
    "emmy": {
        "step_early": [
            "'Wait, you have a PLACE? Like, with walls?' She bounces on her heels.",
            "You mention other survivors. Emmy's eyes go wide. 'How many?'",
            "'The void is so quiet,' she says. 'I talk to myself just to hear a voice.'",
            "She fidgets with a strap on her pack. 'I've been here so long. Alone.'",
            "You describe the skerry. She leans forward like you're telling a ghost story.",
        ],
        "step_mid": [
            "'Real food? Not salvage paste?' She actually gasps.",
            "'Other people. Who are they? What are they like? Tell me everything.'",
            "She starts pacing. A good sign — she's thinking it through.",
            "'I know where all the good scrap is around here. I could be useful!'",
            "'You're serious, aren't you?' She searches your face. 'You're really serious.'",
        ],
        "step_late": [
            "She's already mentally packing. You can see it in her eyes.",
            "'When do we leave? Can we leave now? I could leave now.'",
            "'I have a stash. Supplies I've been hoarding. I'll bring everything.'",
            "She laughs — sudden, surprised, like she forgot she could. 'I'm in.'",
            "'Tell me about the others again. I want to know their names.'",
        ],
        "color": {
            "R": "You mention walls and shelter. 'Oh THANK the void. I sleep with one eye open here.'",
            "G": "'A world seed? A real one?' Her voice cracks with something like hope.",
            "B": "'Other people,' she whispers, and you realize she's blinking back tears.",
            "Y": "'I'm good at finding things! Scavenging! I could help, I really could.'",
            "O": "'Something permanent? Something that lasts?' She grabs your arm. 'Promise me.'",
        },
        "atmosphere": [
            "Emmy fidgets, watching you with enormous eyes.",
            "Emmy has stopped fidgeting. She's listening now.",
            "Emmy is bouncing on her heels, barely containing herself.",
            "Emmy looks like she might burst if you don't finish soon.",
        ],
        "warn": [
            "Emmy's attention is drifting — you're losing a thread...",
            "She glances away. Something you were saying is going stale...",
            "'Hm?' Emmy blinks. You've been neglecting something important...",
        ],
        "eliminate": [
            "'Never mind that, I guess,' she says quietly, and that door closes.",
            "Emmy shakes her head. That argument went cold while you weren't looking.",
            "The excitement dims in her eyes. You let that thread go too long.",
        ],
    },
    "chris": {
        "step_early": [
            "Chris peeks out from behind the lean-to. 'You're... not going to hurt me, right?'",
            "You mention shelter. He swallows hard. 'Real shelter?'",
            "'I haven't eaten real food in... I don't know how long.'",
            "He's shaking slightly. Not cold — just afraid. Of everything.",
            "You keep your voice gentle. He looks like he might bolt.",
        ],
        "step_mid": [
            "'There are other people there?' His voice is very small. 'Nice people?'",
            "He uncurls slightly. Still wary, but listening.",
            "'I can work. I'm not useless. I can carry things and — and stuff.'",
            "He takes a half-step closer. Progress.",
            "'Nobody's been nice to me since... before.' He trails off.",
        ],
        "step_late": [
            "'You promise it's safe?' His eyes are huge and desperate.",
            "He's already standing. Ready to go. Just needs the last push.",
            "'I'll do anything. Carry things. Clean. Whatever you need. Just let me come.'",
            "'Please.' One word, barely a whisper. He means it with everything he has.",
            "He wipes his eyes with the back of his hand and tries to look brave.",
        ],
        "color": {
            "R": "'Safe?' He clutches the edge of his lean-to. 'Really safe?'",
            "G": "You describe the world seed. Chris listens like it's a fairy tale.",
            "B": "'Other people...' He shrinks back, then straightens. 'Nice people?'",
            "Y": "'I can help,' he says quickly. 'I'm useful. I promise I'm useful.'",
            "O": "'Something solid. Something that stays.' He sounds like he's praying.",
        },
        "atmosphere": [
            "Chris watches from behind cover, ready to run.",
            "Chris has crept a little closer. Still tense.",
            "Chris is out in the open now, drawn in despite himself.",
            "Chris is standing right in front of you, hope warring with terror.",
        ],
        "warn": [
            "Chris is shrinking back — you're losing him on something...",
            "His eyes go distant. A thread of the conversation is fraying...",
            "He wraps his arms around himself. Something you dropped is fading...",
        ],
        "eliminate": [
            "Chris flinches. Whatever you were building there just collapsed.",
            "'Oh.' His voice goes flat. That line of argument is dead.",
            "He takes a step back. You let something important go cold.",
        ],
    },
    "varis": {
        "step_early": [
            "Varis leans against the crate, arms crossed. 'I'm listening.'",
            "'A world seed.' He doesn't sound impressed. Yet.",
            "He sizes you up. 'I've met plenty of survivors with plans. Most didn't last.'",
            "You describe the skerry. He tilts his head, considering.",
            "'The void takes everything eventually. Why should your place be different?'",
        ],
        "step_mid": [
            "'How long has the seed been rooted?' A practical question. Good sign.",
            "He uncrosses his arms. 'Go on.'",
            "'I've seen nodes collapse overnight. What's your contingency?'",
            "He nods slowly. 'You know more than I expected.'",
            "'The others you've recruited. Are they dead weight or useful?'",
        ],
        "step_late": [
            "'I know the void routes between here and a dozen nodes. That'd be useful to you.'",
            "He's standing straighter now. Already thinking about logistics.",
            "'Fine. You've made your case.' He almost sounds annoyed about it.",
            "'I've got supplies cached in three locations. I'll retrieve them on the way.'",
            "The skepticism is gone. He's planning.",
        ],
        "color": {
            "R": "'Defensible position?' He scans the surroundings. 'Tell me about the perimeter.'",
            "G": "'World seeds need specific conditions. What's your soil composition?'",
            "B": "'Numbers matter. How many hands for watch rotation?'",
            "Y": "'Everyone needs a role. What's your chain of command?'",
            "O": "'Built to last, or built to last the week?' He fixes you with a stare.",
        },
        "atmosphere": [
            "Varis watches you with the flat appraisal of someone who's survived a long time.",
            "Varis is still measuring you, but he hasn't walked away.",
            "Something's shifted. Varis is asking questions, not raising objections.",
            "Varis gives a single, curt nod. He's made up his mind.",
        ],
        "warn": [
            "Varis's expression cools. You're neglecting something he cares about...",
            "'You were saying?' His tone sharpens. A thread is going thin...",
            "He shifts his weight. You're losing credibility on a front...",
        ],
        "eliminate": [
            "'Forget it.' Varis waves a hand. That angle is done.",
            "His jaw tightens. You talked too long without substance and lost him there.",
            "A flat look. That argument died and he's not going to resurrect it for you.",
        ],
    },
    "angya": {
        "step_early": [
            "Angya's hand rests on her blade. She hasn't decided if you're worth listening to.",
            "'Words.' She says it like a curse. 'Everyone has words.'",
            "You press on. She watches with the patience of someone used to waiting for an opening.",
            "'I don't need a speech. I need a reason.' Her eyes are flint.",
            "She shifts her weight. Fighter's habit — always ready to move.",
        ],
        "step_mid": [
            "'How many hostiles have you dealt with?' A real question. She's engaging.",
            "Her grip on the blade relaxes fractionally.",
            "'The skerry. Can it be defended?' She's thinking tactically.",
            "'I've been fighting alone. That gets old.' The closest she'll come to admitting loneliness.",
            "She rolls her shoulders. 'Keep talking.'",
        ],
        "step_late": [
            "'You need someone who can hold a line. I can hold a line.'",
            "She sheathes the blade. The decision is made, even if she hasn't said it.",
            "'I've been wasted out here guarding nothing. Give me something worth defending.'",
            "A dangerous grin. 'Your enemies are my enemies. That's all I needed to hear.'",
            "'Fine. But I fight MY way. We clear on that?'",
        ],
        "color": {
            "R": "'Shelter's no good if you can't defend it.' She tests you.",
            "G": "She eyes you sidelong at the mention of growth. Seeds aren't her language, but survival is.",
            "B": "'More fighters?' Her interest sharpens. 'Or more mouths?'",
            "Y": "'Purpose.' She snorts. 'My purpose is keeping people alive. Works everywhere.'",
            "O": "'Built solid?' She kicks a wall experimentally. 'Good enough.'",
        },
        "atmosphere": [
            "Angya stands ready, hand on blade, judging every word.",
            "Angya is still armed, but she's stopped looking for exits.",
            "Angya's posture has shifted from combat stance to something almost relaxed.",
            "Angya's blade is sheathed. She's already decided.",
        ],
        "warn": [
            "Angya's hand drifts back to her blade. You're boring her...",
            "Her eyes go hard. Talk without substance is losing you ground...",
            "'Get to the point.' She's losing patience with a thread...",
        ],
        "eliminate": [
            "'Done talking about that.' She cuts the air with her hand. Final.",
            "Her lip curls. You let that argument die and she's not sorry to see it go.",
            "A disgusted headshake. Words wasted. That door is shut.",
        ],
    },
    "tilly": {
        "step_early": [
            "Tilly tends her coral garden while she listens. She doesn't look up.",
            "'A world seed, you say.' She brushes soil from her hands. 'I've heard that before.'",
            "'Come back when you have something real.' But she hasn't told you to leave.",
            "She holds up a coral-seed. 'See this? Took me three months to coax it this far.'",
            "You describe the skerry. She pauses mid-work. Brief, but you noticed.",
        ],
        "step_mid": [
            "'What's the soil like? Rocky? Sandy?' She actually looks at you now.",
            "'How much sunlight — or whatever passes for it — does the seed get?'",
            "She plucks a weed with practiced fingers. 'I'm listening.'",
            "'Rain? Wind patterns? Don't tell me you haven't checked.'",
            "'If the seed can grow real food, that changes things.' Her tone is careful, guarded.",
        ],
        "step_late": [
            "'I'd want to see it first. The soil. Before I commit to anything.'",
            "'My coral-seeds would need transplanting carefully. I'd need help with that.'",
            "She stands up, brushing off her knees. That's the first time she's stopped gardening.",
            "'How soon? I'd need to prepare cuttings. Can't leave anything behind that might root.'",
            "'If half of what you're saying is true...' She trails off, but she's convinced.",
        ],
        "color": {
            "R": "'Walls keep the wind off seedlings.' Practical, always practical.",
            "G": "Her head snaps up. 'Describe the growth rate. Exactly.'",
            "B": "'More hands for harvest?' She approves. 'Growing food is labor.'",
            "Y": "'A garden needs a gardener. That's purpose enough for me.'",
            "O": "'Things that last. That's what growing is — building something that outlives you.'",
        },
        "atmosphere": [
            "Tilly tends her garden, occasionally glancing your way.",
            "Tilly's hands have slowed. She's thinking more than gardening.",
            "Tilly has set down her tools. You have her full attention.",
            "Tilly is on her feet, already thinking about logistics.",
        ],
        "warn": [
            "Tilly returns to her weeding. You're losing a thread...",
            "She glances at her garden. Your pitch is going stale on a front...",
            "'Hm.' She's heard prettier words. Something needs reinforcing...",
        ],
        "eliminate": [
            "She shrugs and returns to weeding. That argument's compost now.",
            "'Not convincing.' She pulls a weed. That line of reasoning is done.",
            "Her expression closes off. You let that one wither on the vine.",
        ],
    },
    "callum": {
        "step_early": [
            "Callum adjusts his crystal spectacles. 'Interesting. Go on.'",
            "'A world seed. Fascinating.' He says it the way people say 'fascinating' when they mean 'prove it.'",
            "He traces an inscription on the wall while you talk. Only half-listening.",
            "'The Eliok texts describe world seeds as — but you wouldn't know that. Continue.'",
            "You mention the skerry. He makes a small note on a scrap of metal.",
        ],
        "step_mid": [
            "'The seed responds to proximity? What's the effective radius?'",
            "He's abandoned the inscriptions entirely. All attention on you now.",
            "'If I could study the root structure directly... the implications for Eliok theory...'",
            "'How mature is the seed? Pre-arboreal? Has it produced secondary growths?'",
            "He cleans his spectacles with trembling hands. He's excited and trying not to show it.",
        ],
        "step_late": [
            "'I need to see it. I NEED to see it. Do you understand what this means?'",
            "He's already rolling up his notes. 'The inscriptions can wait. The seed cannot.'",
            "'A living specimen. In the current stage of development. This is unprecedented.'",
            "'Take me there. Immediately. Every hour of data lost is irreplaceable.'",
            "'I'll bring my translation work. The seed and the inscriptions — they're connected. I know it.'",
        ],
        "color": {
            "R": "'Safety. Yes, obviously. A controlled research environment. Essential.'",
            "G": "His spectacles nearly fall off. 'GROWTH data? You have growth data?'",
            "B": "'A research team? Peers to collaborate with?' He's practically salivating.",
            "Y": "'Purpose? My purpose is already clear. Understanding. Knowledge. The seed.'",
            "O": "'Stable conditions for long-term observation. Yes. Yes, that's critical.'",
        },
        "atmosphere": [
            "Callum traces inscriptions absently, half-listening to you.",
            "Callum has stopped tracing. He's staring at you through those crystal spectacles.",
            "Callum is scribbling notes furiously as you talk.",
            "Callum has rolled up his notes and is standing by the door.",
        ],
        "warn": [
            "Callum returns to his inscriptions. You're losing his academic interest...",
            "He polishes his spectacles. Not a good sign — he's disengaging from a thread...",
            "'Yes, yes, but—' He's losing patience with something you haven't followed up on...",
        ],
        "eliminate": [
            "'Insufficient evidence.' He waves dismissively. That angle is closed.",
            "He returns to his inscriptions. That line of argument bored him to death.",
            "'You had something there, but you didn't develop it.' An academic's disappointment.",
        ],
    },
    "dax": {
        "step_early": [
            "Dax doesn't look up from the console. 'Still talking?'",
            "'Yeah, I've heard the pitch before.' A wire sparks. She ignores it.",
            "You mention shelter. She snorts. 'I've GOT shelter.'",
            "'A world seed.' She tightens a bolt. 'Those are supposed to be extinct.'",
            "She holds up a hand. 'If the next thing out of your mouth is a promise, save it.'",
        ],
        "step_mid": [
            "'What's the power situation?' A real question. First one.",
            "She sets down the wrench. 'Okay. You have ten more seconds.'",
            "'The seed generates energy?' She looks at you for the first time. Really looks.",
            "'How's the infrastructure? Plumbing? Ventilation? No? Figures.'",
            "'I could fix that. If I were there. Which I'm not. Yet.' A crack in the armor.",
        ],
        "step_late": [
            "'This console is held together with wire and spite. Fine. I'll look at your skerry.'",
            "She kicks the console. 'This place is falling apart anyway.'",
            "'You need an engineer. Don't pretend you don't.' She's already packing tools.",
            "'I'm not coming because of your speech. I'm coming because this junk heap is dying.'",
            "She sighs — long, theatrical, defeated. 'Lead the way. Don't make me regret it.'",
        ],
        "color": {
            "R": "'Structural integrity?' She raps a knuckle on the wall. 'Better than this?'",
            "G": "'Organic power source.' She's intrigued despite herself. 'What's the output?'",
            "B": "'Great. More people who don't know which end of a wrench to hold.'",
            "Y": "'My purpose is keeping things running. That doesn't change with geography.'",
            "O": "'Durable? Define durable.' She narrows her eyes. 'In engineering terms.'",
        },
        "atmosphere": [
            "Dax tinkers with the console, grunting occasionally in your direction.",
            "Dax has stopped tinkering. She's holding a wrench very still.",
            "Dax is leaning against the console with her arms crossed. Evaluating.",
            "Dax is putting her tools in a bag. She hasn't agreed yet, but her hands have.",
        ],
        "warn": [
            "Dax picks up the wrench again. You're losing her on something...",
            "'Uh huh.' She's not even pretending to listen to a thread...",
            "She rolls her eyes. Something you dropped is dying fast...",
        ],
        "eliminate": [
            "'Nope.' One syllable. Done. That argument is scrap metal.",
            "She snorts derisively. Whatever you were building there just fell apart.",
            "'You lost me.' Back to the console. That thread is welded shut.",
        ],
    },
}

# Generic fallback for unknown NPCs
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
        (1, 0, "SUGGEST"),
        (0, -1, "APPEAL"),
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
    npc_id = state.get("npc_id", "")
    flavor_data = NPC_FLAVOR.get(npc_id, _GENERIC_FLAVOR)

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
                cell = f"{display.DIM} ..  {display.RESET}"
            elif (r, c) in eliminated:
                # Eliminated
                cell = f"\033[2m\033[90m ··  {display.RESET}"
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
        dir_str = ", ".join(f"{display.BOLD}{d}{display.RESET}" for d in dirs)
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


def get_step_flavor(npc_id, progress_ratio, rng=None):
    """Pick a progress-appropriate flavor line for an NPC."""
    flavor_data = NPC_FLAVOR.get(npc_id, _GENERIC_FLAVOR)
    return _pick_step_flavor(flavor_data, progress_ratio, rng)


def get_npc_flavor(npc_id, progress_ratio):
    """Get NPC-specific atmosphere text based on progress."""
    flavor_data = NPC_FLAVOR.get(npc_id, _GENERIC_FLAVOR)
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
