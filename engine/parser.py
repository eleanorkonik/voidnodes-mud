"""Command parser — Lusternia-style VERB [TARGET] [MODIFIER]."""


# Direction aliases
DIRECTION_ALIASES = {
    "n": "north", "s": "south", "e": "east", "w": "west",
    "u": "up", "d": "down",
    "nw": "northwest", "ne": "northeast", "sw": "southwest", "se": "southeast",
    "north": "north", "south": "south", "east": "east", "west": "west",
    "up": "up", "down": "down",
    "northwest": "northwest", "northeast": "northeast",
    "southwest": "southwest", "southeast": "southeast",
}

# Command aliases
COMMAND_ALIASES = {
    "l": "look", "i": "inventory", "inv": "inventory",
    "x": "look", "examine": "look",
    "equip": "wear", "unequip": "remove", "unwear": "remove",
    "get": "take", "grab": "take", "pick": "take",
    "q": "quit", "exit": "quit",
    "?": "help", "h": "help",
    "stat": "status", "stats": "status", "sheet": "status",
    "flee": "retreat",
    "run": "retreat",
    "cross": "enter",
    "launch": "enter",
    "follow": "seek",
    "m": "map",
    "talk": "greet", "hi": "greet",
    "focus": "switch",
    "ca": "exploit", "setup": "exploit",
    "quest": "quests",
    "repair": "fix", "fix": "fix",
    "sow": "plant",
    "dig": "uproot",
    "vault": "bank",
    "sleep": "rest",
    "nap": "rest",
    "butcher": "process",
    "skin": "process",
    "dismantle": "process",
    "salvage": "process",
    "offer": "give",
}

# All recognized commands and which phase they're valid in
COMMANDS = {
    # Universal commands (prologue included for tutorial)
    "look":      {"phases": ["explorer", "steward", "prologue"], "args": "optional"},
    "go":        {"phases": ["explorer", "steward", "prologue"], "args": "required"},
    "inventory": {"phases": ["explorer", "steward", "prologue"], "args": "none"},
    "status":    {"phases": ["explorer", "steward", "prologue"], "args": "none"},
    "check":     {"phases": ["explorer", "steward", "prologue"], "args": "required"},
    "help":      {"phases": ["explorer", "steward", "prologue"], "args": "none"},
    "save":      {"phases": ["explorer", "steward", "prologue"], "args": "none"},
    "done":      {"phases": ["explorer", "steward", "prologue"], "args": "none"},
    "quit":      {"phases": ["explorer", "steward", "prologue"], "args": "none"},
    "greet":     {"phases": ["explorer", "steward", "prologue"], "args": "required"},
    "use":       {"phases": ["explorer", "steward", "prologue"], "args": "required"},
    "wear":      {"phases": ["explorer", "steward", "prologue"], "args": "required"},
    "remove":    {"phases": ["explorer", "steward", "prologue"], "args": "required"},
    "map":       {"phases": ["explorer", "steward", "prologue"], "args": "optional"},
    "quests":    {"phases": ["explorer", "steward", "prologue"], "args": "none"},
    "fix":       {"phases": ["explorer", "steward", "prologue"], "args": "optional"},
    "say":       {"phases": ["explorer", "steward", "prologue"], "args": "required"},
    "skip":      {"phases": ["prologue"], "args": "none"},
    "bond":      {"phases": ["explorer", "steward", "prologue"], "args": "none"},
    "give":      {"phases": ["explorer", "steward", "prologue"], "args": "required"},
    "switch":    {"phases": ["explorer", "steward", "prologue"], "args": "required"},
    # All gameplay commands — narrative guards in handlers replace phase gating
    "attack":    {"args": "required"},
    "defend":    {"args": "none"},
    "invoke":    {"args": "optional"},
    "aspects":   {"args": "none"},
    "exploit":   {"args": "required"},
    "concede":   {"args": "none"},
    "scavenge":  {"args": "none"},
    "investigate": {"args": "none"},
    "probe":     {"args": "required"},
    "feed":      {"args": "required"},
    "keep":      {"args": "required"},
    "recruit":   {"args": "required"},
    "retreat":   {"args": "none"},
    "settle":    {"args": "required"},
    "enter":     {"args": "required"},
    "seek":      {"args": "required"},
    "take":      {"args": "required"},
    "process":   {"args": "required"},
    "ih":        {"args": "optional"},
    "drop":      {"args": "required"},
    "heal":      {"args": "optional"},
    "request":   {"args": "required"},
    "rest":      {"args": "none"},
    "craft":     {"args": "required"},
    "recipes":   {"args": "none"},
    "build":     {"args": "required"},
    "assign":    {"args": "required"},
    "organize":  {"args": "none"},
    "tasks":     {"args": "none"},
    "trade":     {"args": "required"},
    "plant":     {"args": "required"},
    "harvest":   {"args": "optional"},
    "survey":    {"args": "none"},
    "store":     {"args": "required"},
    "uproot":    {"args": "required"},
    "cross-pollinate": {"args": "required"},
    "select":    {"args": "required"},
    "clone":     {"args": "required"},
    "bank":      {"args": "required"},
    "withdraw":  {"args": "required"},
    "queue":     {"args": "optional"},
    "unqueue":   {"args": "required"},
    "upgrade":   {"args": "required"},
    "place":     {"args": "required"},
    "reclaim":   {"args": "required"},
}


def parse(raw_input):
    """Parse raw input into (command, args_list).

    Returns (command, args) where command is lowercase and args is a list of strings.
    Returns (None, []) for empty input.
    Returns ("unknown", [raw]) for unrecognized commands.
    """
    raw = raw_input.strip()
    if not raw:
        return None, []

    # Quote prefix shortcut: "yes → say yes, 'hello → say hello
    if raw[0] in ('"', "'"):
        rest = raw[1:].strip()
        if rest:
            return "say", rest.lower().split()
        return "say", []

    parts = raw.lower().split()
    verb = parts[0]
    args = parts[1:]

    # Handle multi-word commands: "cross pollinate" / "cross-pollinate" → "cross-pollinate"
    if verb == "cross" and args and args[0] == "pollinate":
        return "cross-pollinate", args[1:]
    if verb == "cross-pollinate":
        return "cross-pollinate", args

    # Handle CHECK STORES as a subcommand
    if verb == "check" and args and args[0] == "stores":
        return "check", args  # handled in cmd_check

    # Check direction shortcuts (just typing "north" or "n")
    if verb in DIRECTION_ALIASES:
        return "go", [DIRECTION_ALIASES[verb]]

    # Apply aliases
    verb = COMMAND_ALIASES.get(verb, verb)

    # Normalize direction args for GO
    if verb == "go" and args:
        args[0] = DIRECTION_ALIASES.get(args[0], args[0])

    if verb in COMMANDS:
        return verb, args

    return "unknown", [raw]


def is_valid_for_phase(command, phase):
    """Check if a command is valid for the current phase.

    With unified commands, all commands are valid in all phases —
    narrative guards in handlers provide in-world rejection instead.
    Only 'skip' is prologue-only.
    """
    if command not in COMMANDS:
        return False
    phases = COMMANDS[command].get("phases")
    if phases:
        return phase in phases
    return True
