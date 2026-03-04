"""Interactive tutorial — world seed guides new players through Act 1 (prologue).

After the prologue handoff, the tutorial is complete. All further guidance
comes from one-shot contextual hints in command handlers (just-in-time hints).
"""

from engine import display


STEPS = [
    # Act 1 — Miria Prologue
    "awakening",             # tendril reaches out, prompt to BOND
    "naming",                # seed asks for a name (input captured in game loop)
    "first_look",            # prompt to LOOK — teaches aspects + INVOKE
    "invoke_practice",       # player INVOKEs an aspect
    "scavenge_practice",     # player SCAVENGEs the junkyard
    "movement",              # prompt to GO somewhere
    "exploring",             # free exploration, encounter explorer at shelter
    "check_seed",            # CHECK SKERRY — learn about domain overview
    "handoff",               # switch focus to explorer → tutorial complete

    "complete",
]


def _step_index(step):
    try:
        return STEPS.index(step)
    except ValueError:
        return len(STEPS) - 1


def show_prologue_intro():
    """Show the atmospheric opening — void, then the tendril arrives."""
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

    display.narrate("Something reaches toward you through the dark — a thread")
    display.narrate("of green light, thin and fragile. It pulses like a heartbeat.")
    print()
    display.narrate("It hesitates at the edge of your awareness, then presses")
    display.narrate("gently against your thoughts. A warmth. An invitation.")
    print()

    display.seed_speak("... you. I can feel you.")
    print()
    display.seed_speak("I've been alone so long. Please — let me in.")
    print()

    _tutorial_prompt(f"Try {display.BOLD}BOND{display.BRIGHT_YELLOW} to accept the connection.")


def show_skip_message():
    """Message when the player skips the tutorial."""
    display.seed_speak("Fine, fine. You know what you're doing. I hope.")
    print()
    display.info("  Tutorial skipped. Jumping to Day 1.")
    display.info("  HELP is always available if you need it.")
    print()


def after_command(cmd, args, game):
    """Called after each command during the tutorial.

    The world seed guides the player through the prologue, advancing when
    appropriate. Returns True if the tutorial is complete.
    """
    # Don't show tutorial hints while player is responding to a compel
    if getattr(game, "in_compel", False):
        return False

    step = game.state.get("tutorial_step", "awakening")

    if step == "complete" or game.state.get("tutorial_complete"):
        return True

    # ── Act 1: Miria Prologue ──

    if step == "awakening" and cmd == "bond":
        game.state["tutorial_step"] = "naming"
        print()
        room = game.current_room()
        if room:
            room.discover()
            display.room_name(room.name)
            display.room_desc(room.description)
            exits = room.get_exit_directions()
            if exits:
                exit_parts = [f"{display.BOLD}{e.upper()}{display.RESET}" for e in exits]
                print(f"  Exits: {', '.join(exit_parts)}")
        print()
        display.seed_speak("I hold this ground together — without me, it's all")
        display.seed_speak("just dust in the void. But I can't do it alone anymore.")
        print()
        display.seed_speak("I don't have a name. Not one anyone's given me.")
        display.seed_speak("What would you call me?")
        game.state["awaiting_world_seed_name"] = True
        return False

    if step == "first_look" and cmd == "look":
        game.state["tutorial_step"] = "invoke_practice"
        print()
        display.seed_speak("Good. The clearing, the paths, the edges of things?")
        display.seed_speak("You see that with your eyes.")
        print()
        room = game.current_room()
        if room:
            all_aspects = []
            zone_aspect = game._get_zone_aspect(room)
            if zone_aspect:
                all_aspects.append(zone_aspect)
            all_aspects.extend(room.aspects)
            if all_aspects:
                aspect_list = ". ".join(display.aspect_text(a) for a in all_aspects)
                display.seed_speak(f"See those? {aspect_list}.")
                display.seed_speak("Those are aspects — the deeper nature of things.")
                display.seed_speak("The big one covers this whole zone. The others are specific to where you're standing.")
            print()
        display.seed_speak("Thanks to our connection, you can INVOKE them.")
        display.seed_speak("It costs a fate point, but it sharpens your next action —")
        display.seed_speak("a bonus that stacks on whatever you do next.")
        display.seed_speak("You have three fate points. They refresh each day.")
        print()
        display.seed_speak("There's salvage worth picking through here. Try invoking")
        display.seed_speak("an aspect before you dig in.")
        _tutorial_prompt("INVOKE <aspect> to call on it, then SCAVENGE.")
        return False

    if step == "invoke_practice" and cmd == "invoke":
        game.state["tutorial_step"] = "scavenge_practice"
        print()
        display.seed_speak("Good. That bonus is floating now — it'll attach to your")
        display.seed_speak("next skill check, whatever it is.")
        print()
        _tutorial_prompt("Now SCAVENGE to search for useful materials.")
        return False

    if step == "scavenge_practice" and cmd == "scavenge":
        game.state["tutorial_step"] = "movement"
        print()
        display.seed_speak("Each time you search the same spot, the easy pickings thin out.")
        display.seed_speak("Come back the next day and you'll spot things you missed.")
        print()
        display.seed_speak("Now — let's have a look around. Survey our domain.")
        _tutorial_prompt("Pick a direction — N, S, E, or W.")
        return False

    if step == "movement" and cmd == "go":
        pre_loc = game.state.pop("_pre_cmd_location", None)
        if pre_loc is not None and pre_loc == game.state.get("prologue_location"):
            return False
        room = game.current_room()
        if room and "sevarik" in room.npcs:
            _show_sevarik_encounter(game)
        else:
            print()
            display.seed_speak("That's it. One step, then another. The skerry isn't")
            display.seed_speak("big, but it's yours.")
            print()
            display.seed_speak("There's someone here you should find.")
            game.state["tutorial_step"] = "exploring"
        return False

    if step == "exploring" and cmd == "go":
        room = game.current_room()
        if room and "sevarik" in room.npcs:
            _show_sevarik_encounter(game)
        return False

    if step == "check_seed" and cmd == "check":
        seed_name = game.state.get("world_seed_name", "Tuft")
        explorer_name = game.state.get("explorer_name", "Sevarik")
        print()
        display.seed_speak("See? Through our bond, you can sense the whole skerry.")
        display.seed_speak("Who's here, what's built, what we can still build.")
        print()
        display.seed_speak(f"Now... is it OK if I switch my focus to {explorer_name}?")
        display.seed_speak("Now that you're here, it's safe to let him explore.")
        _tutorial_prompt(f"SWITCH FOCUS TO {explorer_name.upper()} when you're ready.")
        game.state["tutorial_step"] = "handoff"
        return False

    if step == "handoff" and cmd == "switch":
        words = [w for w in args if w not in ("focus", "to")]
        target = " ".join(words).lower() if words else ""
        explorer_name = game.state.get("explorer_name", "Sevarik").lower()
        if target in (explorer_name, "explorer"):
            # Prologue complete — tutorial is done
            game.state["tutorial_step"] = "complete"
            game.state["tutorial_complete"] = True
            game._transition_to_day1()
            print()
            display.seed_speak("Head south to the landing pad. I can feel nodes")
            display.seed_speak("of wreckage in the void — there's salvage out there.")
            display.seed_speak("SEEK to follow them.")
        return False

    return False


# ── Helper functions ──

def _show_sevarik_encounter(game):
    """Player meets the explorer at the shelter. Triggers the split explanation."""
    seed_name = game.state.get("world_seed_name", "the seed")
    explorer_name = game.state.get("explorer_name", "Sevarik")
    print()
    display.narrate("A scarred man sits in the shelter's entrance, sharpening")
    display.narrate("a makeshift blade on a chunk of salvaged stone. He rises")
    display.narrate("as you approach — watchful, tense, but not hostile.")
    print()
    print(f"  {display.npc_name(explorer_name)}: \"You bonded with the world seed?\"")
    print(f"  {display.npc_name(explorer_name)}: \"And named it... {seed_name}?\"")
    print(f"  {display.npc_name(explorer_name)}: \"Good. I've been waiting.\"")
    print()
    _show_the_split(game)


def _show_the_split(game):
    """World seed explains the dual-role system. No starter artifact — CHECK SEED instead."""
    seed_name = game.state.get("world_seed_name", "Tuft")
    explorer_name = game.state.get("explorer_name", "Sevarik")
    steward_name = game.state.get("steward_name", "Miria")
    display.divider()
    print()
    display.seed_speak("Listen. There's something you need to understand.")
    print()

    display.seed_speak("We can't survive here alone. Not for long. It takes")
    display.seed_speak("a team.")
    print()

    display.narrate(f"You are {display.GREEN}{steward_name}{display.RESET} — a healer, an organizer, the one who")
    display.narrate("keeps broken things alive. You tend the skerry: crafting,")
    display.narrate("building, managing whoever else washes up here.")
    print()

    display.narrate(f"{display.CYAN}{explorer_name}{display.RESET} — the man before you — is a fighter, a scout.")
    display.narrate("He steps off the edge into the void to scavenge resources,")
    display.narrate("fight threats, and find survivors.")
    print()

    display.seed_speak("I can only focus on one of you at a time, though.")
    display.seed_speak("Perhaps that will change later, as we expand the skerry.")
    display.seed_speak("I'm limited in what I can protect, for now.")
    print()

    display.seed_speak("Before we go further — CHECK the skerry. See how we're doing.")
    _tutorial_prompt("CHECK SKERRY to see an overview of our domain.")

    game.state["tutorial_step"] = "check_seed"


def get_current_hint(step, game_state=None):
    """Show a world-seed-voiced hint for the current step (on resume)."""
    gs = game_state or {}
    seed_name = gs.get("world_seed_name", "the seed")
    explorer_name = gs.get("explorer_name", "Sevarik")
    steward_name = gs.get("steward_name", "Miria")

    if step == "awakening":
        display.narrate("A thread of green light pulses before you, waiting.")
        _tutorial_prompt("Try BOND to accept the connection.")
    elif step == "naming":
        display.seed_speak("I don't have a name. Not one anyone's given me.")
        display.seed_speak("What would you call me?")
        if game_state:
            game_state["awaiting_world_seed_name"] = True
    elif step == "first_look":
        display.seed_speak("Now, let me help you perceive.")
        _tutorial_prompt("Go ahead and LOOK to see your surroundings.")
    elif step == "invoke_practice":
        display.seed_speak("Try calling on one of those aspects.")
        _tutorial_prompt("INVOKE <aspect> to call on it, then SCAVENGE.")
    elif step == "scavenge_practice":
        display.seed_speak("You've got a bonus waiting. Put it to use.")
        _tutorial_prompt("SCAVENGE to search for useful materials.")
    elif step == "movement":
        display.seed_speak("There are paths here. Pick a direction.")
        _tutorial_prompt("Pick a direction — N, S, E, or W.")
    elif step == "exploring":
        display.seed_speak("Keep looking around. There's someone here you need to meet.")
    elif step == "check_seed":
        display.seed_speak("CHECK the skerry — you can see our whole domain through our bond.")
        _tutorial_prompt("CHECK SKERRY.")
    elif step == "handoff":
        display.seed_speak(f"Is it OK if I switch my focus to {explorer_name}?")
        _tutorial_prompt(f"SWITCH FOCUS TO {explorer_name.upper()} when you're ready.")


def garden_walkthrough(game):
    """One-time walkthrough when the garden is first built. Not gated — just informational."""
    if game.state.get("garden_walkthrough_done"):
        return
    game.state["garden_walkthrough_done"] = True

    seed_name = game.state.get("world_seed_name", "Tuft")
    print()
    display.seed_speak("A garden! I can feel the soil already.")
    display.seed_speak("Let me show you how this works.")
    print()

    display.seed_speak("You brought specimens back from the void — alien plants")
    display.seed_speak("that grow in my light. Each one is different.")
    print()

    display.seed_speak("PLANT <specimen> <plot#> puts a specimen in a plot.")
    display.seed_speak("SURVEY shows all your plots and what's growing.")
    display.seed_speak("HARVEST <plot#> collects food when a plant is ready.")
    display.seed_speak("STORE <item> moves harvested food into long-term storage.")
    print()

    display.seed_speak("Assigned NPCs will plant and harvest automatically,")
    display.seed_speak("but breeding is your job.")
    print()

    display.seed_speak("CROSS-POLLINATE <plot> <plot> mixes two plants' traits.")
    display.seed_speak("SELECT <plot> <trait> pushes a trait in one direction.")
    display.seed_speak("Each specimen type has its own tricks — PROBE a specimen")
    display.seed_speak("to see what's possible.")
    print()

    display.seed_speak("CHECK STORES to see your food supply.")
    display.seed_speak("CHECK VAULT for banked specimens.")
    display.seed_speak("Keep the colony fed, and they'll be happy. Let them starve...")
    display.seed_speak("well. Don't.")


def _tutorial_prompt(text):
    """Display a styled game instruction hint (yellow with arrow)."""
    lines = text.split("\n")
    print(f"  {display.BRIGHT_YELLOW}\u25b6 {lines[0]}{display.RESET}")
    for line in lines[1:]:
        print(f"  {display.BRIGHT_YELLOW}  {line}{display.RESET}")
