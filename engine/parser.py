"""Command parser — Lusternia-style VERB [TARGET] [MODIFIER]."""


# Direction aliases
DIRECTION_ALIASES = {
    "n": "north", "s": "south", "e": "east", "w": "west",
    "u": "up", "d": "down",
    "north": "north", "south": "south", "east": "east", "west": "west",
    "up": "up", "down": "down",
}

# Command aliases
COMMAND_ALIASES = {
    "l": "look", "i": "inventory", "inv": "inventory",
    "x": "look", "examine": "probe",
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
    "hi": "talk", "greet": "talk",
    "focus": "switch",
    "ca": "exploit", "setup": "exploit",
    "quest": "quests",
    "repair": "fix", "fix": "fix",
    "sow": "plant",
    "dig": "uproot",
    "vault": "bank",
    "sleep": "rest",
    "nap": "rest",
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
    "talk":      {"phases": ["explorer", "steward", "prologue"], "args": "required"},
    "use":       {"phases": ["explorer", "steward", "prologue"], "args": "required"},
    "wear":      {"phases": ["explorer", "steward", "prologue"], "args": "required"},
    "remove":    {"phases": ["explorer", "steward", "prologue"], "args": "required"},
    "map":       {"phases": ["explorer", "steward", "prologue"], "args": "optional"},
    "quests":    {"phases": ["explorer", "steward", "prologue"], "args": "none"},
    "fix":       {"phases": ["explorer", "steward", "prologue"], "args": "optional"},
    "skip":      {"phases": ["prologue"], "args": "none"},
    "bond":      {"phases": ["explorer", "steward", "prologue"], "args": "none"},
    "give":      {"phases": ["explorer", "steward", "prologue"], "args": "required"},
    "switch":    {"phases": ["explorer", "steward", "prologue"], "args": "required"},
    # Explorer commands
    "attack":    {"phases": ["explorer"], "args": "required"},
    "defend":    {"phases": ["explorer"], "args": "none"},
    "invoke":    {"phases": ["explorer", "steward"], "args": "optional"},
    "exploit":   {"phases": ["explorer"], "args": "required"},
    "concede":   {"phases": ["explorer"], "args": "none"},
    "scavenge":  {"phases": ["explorer"], "args": "none"},
    "probe":     {"phases": ["explorer", "prologue"], "args": "required"},
    "feed":      {"phases": ["explorer", "steward"], "args": "required"},
    "keep":      {"phases": ["explorer", "prologue"], "args": "required"},
    "recruit":   {"phases": ["explorer"], "args": "required"},
    "retreat":   {"phases": ["explorer"], "args": "none"},
    "settle":    {"phases": ["explorer"], "args": "required"},
    "enter":     {"phases": ["explorer", "steward"], "args": "required"},
    "seek":      {"phases": ["explorer", "steward"], "args": "required"},
    "take":      {"phases": ["explorer", "prologue"], "args": "required"},
    "ih":        {"phases": ["explorer", "steward", "prologue"], "args": "optional"},
    "offer":     {"phases": ["explorer", "steward", "prologue"], "args": "required"},
    "drop":      {"phases": ["explorer", "steward", "prologue"], "args": "required"},
    "request":   {"phases": ["explorer", "steward"], "args": "required"},
    # Steward commands
    "rest":      {"phases": ["steward"], "args": "none"},
    "craft":     {"phases": ["explorer", "steward"], "args": "required"},
    "recipes":   {"phases": ["explorer", "steward"], "args": "none"},
    "build":     {"phases": ["steward"], "args": "required"},
    "assign":    {"phases": ["steward"], "args": "required"},
    "organize":  {"phases": ["steward"], "args": "none"},
    "tasks":     {"phases": ["steward"], "args": "none"},
    "trade":     {"phases": ["steward"], "args": "required"},
    # Farming commands (steward phase)
    "plant":     {"phases": ["steward"], "args": "required"},
    "harvest":   {"phases": ["steward"], "args": "optional"},
    "survey":    {"phases": ["steward"], "args": "none"},
    "store":     {"phases": ["steward"], "args": "required"},
    "uproot":    {"phases": ["steward"], "args": "required"},
    # Breeding commands (steward phase)
    "cross-pollinate": {"phases": ["steward"], "args": "required"},
    "select":    {"phases": ["steward"], "args": "required"},
    "clone":     {"phases": ["steward"], "args": "required"},
    "bank":      {"phases": ["steward"], "args": "required"},
    "withdraw":  {"phases": ["steward"], "args": "required"},
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
    """Check if a command is valid for the current phase."""
    if command not in COMMANDS:
        return False
    return phase in COMMANDS[command]["phases"]


def get_phase_commands(phase):
    """Get list of commands valid for a given phase."""
    return [cmd for cmd, info in COMMANDS.items() if phase in info["phases"]]
