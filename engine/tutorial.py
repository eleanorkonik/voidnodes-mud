"""Interactive tutorial — Tuft guides new players through the prologue."""

import random
from engine import display


STEPS = [
    "awakening",         # tendril reaches out, prompt to BOND
    "naming",            # seed asks for a name (input captured in game loop)
    "first_look",        # prompt to LOOK — first perception of the skerry
    "movement",          # prompt to GO somewhere
    "exploring",         # free exploration, encounter explorer at shelter
    "artifact_ih",       # IH to see artifact in room
    "artifact_examine",  # EXAMINE/PROBE the artifact
    "artifact_use",      # TAKE then WEAR the artifact
    "artifact_choice",   # KEEP or OFFER the artifact
    "handoff",           # handoff — switch focus to explorer
    "complete",          # done
]


def _step_index(step):
    try:
        return STEPS.index(step)
    except ValueError:
        return len(STEPS) - 1


def show_prologue_intro():
    """Show the atmospheric opening — void, then the tendril arrives.

    The player starts in darkness. A tendril of green light reaches
    toward them. The first action is to BOND — accepting the connection
    is what gives them perception and grounds them on the skerry.
    """
    print()
    print(f"  {display.DIM}{'─' * 48}{display.RESET}")
    print()
    display.info("  You come to awareness in a sea of emptiness,")
    display.info("  sensing nothing but still sensing.")
    print()
    display.info("  Between the worlds that were and the worlds that might be,")
    display.info("  there is a space — vast, dark, full of drifting wreckage.")
    display.info("  Shattered ships and uprooted earth, all dissolving slowly")
    display.info("  into nothing.")
    print()
    print(f"  {display.DIM}{'─' * 48}{display.RESET}")
    print()

    # The tendril arrives
    display.narrate("Something reaches toward you through the dark — a thread")
    display.narrate("of green light, thin and fragile. It pulses like a heartbeat.")
    print()
    display.narrate("It hesitates at the edge of your awareness, then presses")
    display.narrate("gently against your thoughts. A warmth. An invitation.")
    print()

    # First contact — barely verbal
    display.tuft_speak("... you. I can feel you.")
    print()
    display.tuft_speak("I've been alone so long. Please — let me in.")
    print()

    _tutorial_prompt(f"Try {display.BOLD}BOND{display.BRIGHT_YELLOW} to accept the connection.")


def show_skip_message():
    """Message when the player skips the tutorial."""
    display.tuft_speak("Fine, fine. You know what you're doing. I hope.")
    print()
    display.info("  Tutorial skipped. Jumping to Day 1.")
    display.info("  HELP is always available if you need it.")
    print()


def after_command(cmd, args, game):
    """Called after each command during the prologue.

    Tuft guides the player through each step, advancing when
    appropriate. Returns True if the tutorial is complete.
    """
    step = game.state.get("tutorial_step", "awakening")

    if step == "complete" or game.state.get("tutorial_complete"):
        return True

    # ── Step transitions ──

    if step == "awakening" and cmd == "bond":
        game.state["tutorial_step"] = "naming"
        print()
        # Discover the room but DON'T show the full display yet —
        # just an atmospheric arrival. The full room (aspects, exits)
        # comes when the player LOOKs at the first_look step.
        room = game.current_room()
        if room:
            room.discover()
            display.room_name(room.name)
            display.narrate("Solid ground. Rough soil under your feet, a few")
            display.narrate("scraggly plants, the faint hum of something alive")
            display.narrate("beneath the surface.")
        print()
        display.tuft_speak("I hold this ground together — without me, it's all")
        display.tuft_speak("just dust in the void. But I can't do it alone anymore.")
        print()
        display.tuft_speak("I don't have a name. Not one anyone's given me.")
        display.tuft_speak("What would you call me?")
        game.state["awaiting_world_seed_name"] = True
        return False

    if step == "first_look" and cmd == "look":
        game.state["tutorial_step"] = "movement"
        seed_name = game.state.get("world_seed_name", "Tuft")
        print()
        display.tuft_speak("Good. The clearing, the paths, the edges of things?")
        display.tuft_speak("You see that with your eyes.")
        print()
        # Explain aspects
        room = game.current_room()
        if room and room.aspects:
            aspect_list = ". ".join(room.aspects)
            display.tuft_speak(f"See those? {aspect_list}.")
            display.tuft_speak("Those are aspects — the deeper nature of things.")
            display.tuft_speak("Thanks to our connection, you can INVOKE them. But let's talk about that later.")
            print()
        display.tuft_speak("For now, survey our domain. Try walking.")
        _tutorial_prompt("Pick a direction — N, S, E, or W.")
        return False

    if step == "movement" and cmd == "go":
        # Only advance if the player actually moved (not blocked by invalid direction).
        # _pre_cmd_location is stashed by the game loop before dispatching.
        pre_loc = game.state.pop("_pre_cmd_location", None)
        if pre_loc is not None and pre_loc == game.state.get("prologue_location"):
            return False
        room = game.current_room()
        if room and "sevarik" in room.npcs:
            # Found explorer on the first move — go straight to encounter
            _show_sevarik_encounter(game)
        else:
            print()
            display.tuft_speak("That's it. One step, then another. The skerry isn't")
            display.tuft_speak("big, but it's yours.")
            print()
            display.tuft_speak("Out there in the void, there are things I can sense —")
            display.tuft_speak("artifacts, echoes of meaning. Bring them to me.")
            display.tuft_speak("Feed me what has weight, and the skerry grows.")
            print()
            display.tuft_speak("Keep looking around. There's someone here you should find.")
            game.state["tutorial_step"] = "exploring"
        return False

    if step == "exploring" and cmd == "go":
        room = game.current_room()
        if room and "sevarik" in room.npcs:
            _show_sevarik_encounter(game)
        return False

    if step == "artifact_ih" and cmd == "ih":
        artifact_id = game.state.get("starter_artifact")
        art = game.artifacts_db.get(artifact_id, {})
        art_name = art.get("name", "something")
        print()
        display.tuft_speak(f"See that? {art_name}. Look more closely.")
        _tutorial_prompt(f"EXAMINE {art_name.upper()} to get a closer look.")
        game.state["tutorial_step"] = "artifact_examine"
        return False

    if step == "artifact_examine" and cmd == "probe":
        artifact_id = game.state.get("starter_artifact")
        art = game.artifacts_db.get(artifact_id, {})
        aspects = art.get("aspects", [])
        if aspects:
            aspect_str = display.aspect_text(aspects[0])
            print()
            display.tuft_speak(f"See that shimmer? That's an aspect — {aspect_str}.")
            display.tuft_speak("Aspects are the deeper nature of things. When you need")
            display.tuft_speak("strength, you can INVOKE an aspect for a bonus.")
        print()
        display.tuft_speak("Take it. It shouldn't just sit on the ground.")
        art_name = art.get("name", "it")
        _tutorial_prompt(f"TAKE {art_name.upper()} to pick it up.")
        game.state["tutorial_step"] = "artifact_use"
        game.state["artifact_taken"] = False
        return False

    if step == "artifact_use":
        artifact_id = game.state.get("starter_artifact")
        art = game.artifacts_db.get(artifact_id, {})
        art_name = art.get("name", "it")

        if cmd == "take" and not game.state.get("artifact_taken"):
            game.state["artifact_taken"] = True
            print()
            display.tuft_speak("Good. Now try it on.")
            _tutorial_prompt(f"Go ahead and WEAR {art_name.upper()}.")
            return False

        if cmd in ("use", "wear") and game.state.get("artifact_taken"):
            # cmd_use already showed the artifact effect narration
            print()
            seed_name = game.state.get("world_seed_name", "Tuft")
            display.tuft_speak("Now. A choice. You can KEEP it — carry it, use its")
            display.tuft_speak(f"power. Or you can OFFER it TO me. I'll break it down")
            display.tuft_speak("into motes and grow stronger. Your power or mine.")
            display.tuft_speak("There's always a trade.")
            _tutorial_prompt(f"KEEP it, or OFFER {art_name.upper()} TO {seed_name.upper()}.")
            game.state["tutorial_step"] = "artifact_choice"
            return False

        return False

    if step == "artifact_choice" and cmd in ("keep", "offer"):
        explorer_name = game.state.get("explorer_name", "Sevarik")
        print()
        if cmd == "keep":
            display.tuft_speak("Your call. Carry it well.")
        else:
            display.tuft_speak("Mmm. I can feel that. Thank you.")
        print()
        display.tuft_speak(f"Now. {explorer_name} is waiting. Time to see the void")
        display.tuft_speak("through his eyes.")
        _tutorial_prompt(f"SWITCH FOCUS TO {explorer_name.upper()} when you're ready.")
        game.state["tutorial_step"] = "handoff"
        return False

    if step == "handoff" and cmd == "switch":
        # cmd_switch already handled the narration; just complete the tutorial
        words = [w for w in args if w not in ("focus", "to")]
        target = " ".join(words).lower() if words else ""
        explorer_name = game.state.get("explorer_name", "Sevarik").lower()
        if target in (explorer_name, "explorer"):
            game.state["tutorial_step"] = "complete"
            game.state["tutorial_complete"] = True
            return True

    return False


def _show_sevarik_encounter(game):
    """Player meets the explorer at the shelter. Triggers the split explanation."""
    seed_name = game.state.get("world_seed_name", "the seed")
    explorer_name = game.state.get("explorer_name", "Sevarik")
    print()
    display.narrate("A scarred man sits in the shelter's entrance, sharpening")
    display.narrate("a makeshift blade on a chunk of salvaged stone. He rises")
    display.narrate("as you approach — watchful, tense, but not hostile.")
    print()
    print(f"  {display.npc_name(explorer_name)}: \"You're the one {seed_name} bonded with.\"")
    print(f"  {display.npc_name(explorer_name)}: \"Good. I've been waiting.\"")
    print()
    _show_the_split(game)


def _show_the_split(game):
    """World seed explains the dual-role system. Player starts as steward."""
    seed_name = game.state.get("world_seed_name", "Tuft")
    explorer_name = game.state.get("explorer_name", "Sevarik")
    steward_name = game.state.get("steward_name", "Miria")
    display.divider()
    print()
    display.tuft_speak("Listen. There's something you need to understand.")
    print()

    display.narrate("The skerry is tiny. The void is vast. To survive here,")
    display.narrate("you need to be in two places at once — someone out there")
    display.narrate("finding what you need, and someone here keeping everything")
    display.narrate("from falling apart.")
    print()

    display.tuft_speak("I can extend tendrils to both of you — but I can only")
    display.tuft_speak("actively focus through one at a time.")
    print()

    display.narrate(f"You are {display.GREEN}{steward_name}{display.RESET} — a healer, an organizer, the one who")
    display.narrate("keeps broken things alive. You tend the skerry: crafting,")
    display.narrate("building, managing whoever else washes up here.")
    print()

    display.narrate(f"{display.CYAN}{explorer_name}{display.RESET} — the man before you — is a fighter, a scout.")
    display.narrate("He steps off the edge into the void to scavenge resources,")
    display.narrate("fight threats, and find survivors.")
    print()

    display.tuft_speak("A world seed needs multiple agents to grow and thrive.")
    display.tuft_speak("Like parents. Someone to explore the void and bring back")
    display.tuft_speak("resources, and someone to tend to hearth and home.")
    print()

    display.tuft_speak("I can only focus on one of you at a time, right now —")
    display.tuft_speak("although perhaps that will change later.")
    print()

    # Quick reference
    display.header("Quick Reference")
    cmds = [
        ("LOOK [thing]", "Examine your surroundings"),
        ("IH [thing]", "List objects here, or examine something"),
        ("GO <direction>", "Move (N/S/E/W or full words)"),
        ("MAP", "Show the zone map"),
        ("TALK / HI <npc>", "Talk to someone"),
        (f"CHECK {seed_name.upper()}", f"Check {seed_name}'s status"),
        ("INVENTORY", "Your items"),
        ("STATUS", "Your character sheet"),
        ("SWITCH FOCUS TO <name>", "Switch active agent"),
        ("HELP", "Full command list"),
        ("SAVE / QUIT", "Save progress"),
    ]
    for cmd, desc in cmds:
        print(f"  {display.BOLD}{cmd:<22}{display.RESET} {desc}")
    print()

    display.divider()
    print()

    display.tuft_speak(f"You're {steward_name} right now.")
    print()

    # Set up starter artifact
    artifact_id = random.choice(["silver_slippers", "red_clown_nose"])
    game.state["starter_artifact"] = artifact_id

    # Place artifact in player's current room
    room = game.current_room()
    if room:
        art = game.artifacts_db.get(artifact_id, {})
        art["room"] = room.id
        if artifact_id not in room.items:
            room.add_item(artifact_id)

    display.tuft_speak("Hold on. I can feel something nearby. Our bond lets you")
    display.tuft_speak("sense objects with substance. Try IH to see what's here.")
    _tutorial_prompt("IH shows what's around you.")

    game.state["tutorial_step"] = "artifact_ih"


def get_current_hint(step, game_state=None):
    """Show a world-seed-voiced hint for the current step (on resume)."""
    seed_name = (game_state or {}).get("world_seed_name", "the seed")
    if step == "awakening":
        display.narrate("A thread of green light pulses before you, waiting.")
        _tutorial_prompt(f"Try BOND to accept the connection.")
    elif step == "naming":
        display.tuft_speak("I don't have a name. Not one anyone's given me.")
        display.tuft_speak("What would you call me?")
        if game_state:
            game_state["awaiting_world_seed_name"] = True
    elif step == "first_look":
        display.tuft_speak("Now, let me help you perceive.")
        _tutorial_prompt("Go ahead and LOOK to see your surroundings.")
    elif step == "movement":
        display.tuft_speak("There are paths here. Pick a direction.")
        _tutorial_prompt("Pick a direction — N, S, E, or W.")
    elif step == "exploring":
        display.tuft_speak("Keep looking around. There's someone here you need to meet.")
    elif step == "artifact_ih":
        display.tuft_speak("I can feel something nearby. Try IH to see what's here.")
        _tutorial_prompt("IH shows what's around you.")
    elif step == "artifact_examine":
        artifact_id = (game_state or {}).get("starter_artifact")
        if artifact_id and game_state:
            art = game_state.get("artifacts", {}).get(artifact_id, {})
            art_name = art.get("name", "the artifact")
        else:
            art_name = "the artifact"
        display.tuft_speak(f"Look more closely at the {art_name}.")
        _tutorial_prompt(f"EXAMINE {art_name.upper()} to get a closer look.")
    elif step == "artifact_use":
        artifact_id = (game_state or {}).get("starter_artifact")
        if artifact_id and game_state:
            art = game_state.get("artifacts", {}).get(artifact_id, {})
            art_name = art.get("name", "the artifact")
        else:
            art_name = "the artifact"
        if (game_state or {}).get("artifact_taken"):
            display.tuft_speak(f"Try it on. WEAR the {art_name}.")
            _tutorial_prompt(f"Go ahead and WEAR {art_name.upper()}.")
        else:
            display.tuft_speak(f"Pick it up first.")
            _tutorial_prompt(f"TAKE {art_name.upper()} to pick it up.")
    elif step == "artifact_choice":
        seed_name = (game_state or {}).get("world_seed_name", "Tuft")
        artifact_id = (game_state or {}).get("starter_artifact")
        if artifact_id and game_state:
            art = game_state.get("artifacts", {}).get(artifact_id, {})
            art_name = art.get("name", "the artifact")
        else:
            art_name = "the artifact"
        display.tuft_speak("Your power or mine. There's always a trade.")
        _tutorial_prompt(f"KEEP it, or OFFER {art_name.upper()} TO {seed_name.upper()}.")
    elif step == "handoff":
        explorer_name = (game_state or {}).get("explorer_name", "Sevarik")
        steward_name = (game_state or {}).get("steward_name", "Miria")
        display.tuft_speak(f"You're {steward_name} right now. Explore the skerry if you like.")
        _tutorial_prompt(f"SWITCH FOCUS TO {explorer_name.upper()} when you're ready.")


def _tutorial_prompt(text):
    """Display a styled game instruction hint (yellow with arrow)."""
    lines = text.split("\n")
    print(f"  {display.BRIGHT_YELLOW}\u25b6 {lines[0]}{display.RESET}")
    for line in lines[1:]:
        print(f"  {display.BRIGHT_YELLOW}  {line}{display.RESET}")
