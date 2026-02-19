"""Interactive tutorial — world seed guides new players through all three acts."""

from engine import display


STEPS = [
    # Act 1 — Miria Prologue
    "awakening",             # tendril reaches out, prompt to BOND
    "naming",                # seed asks for a name (input captured in game loop)
    "first_look",            # prompt to LOOK — first perception of the skerry
    "movement",              # prompt to GO somewhere
    "exploring",             # free exploration, encounter explorer at shelter
    "check_seed",            # CHECK SEED — learn about motes
    "handoff",               # switch focus to explorer

    # Act 2 — Sevarik Explorer
    "explorer_navigate",     # guide to landing pad
    "explorer_void_cross",   # SEEK — first void crossing
    "explorer_free",         # flexible exploration: combat, invoke, artifact, recruit
    "explorer_return",       # SEEK HOME back to skerry
    "explorer_artifact",     # resolve artifact: KEEP, OFFER, or GIVE
    "explorer_stash",        # go to junkyard, DROP materials
    "explorer_handoff",      # SWITCH FOCUS TO MIRIA

    # Act 3 — Miria Steward
    "steward_arrive",        # orientation narration
    "steward_recipes",       # RECIPES
    "steward_craft",         # CRAFT basic_tools
    "steward_assign",        # ASSIGN recruited NPC
    "steward_complete",      # tutorial done

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

    The world seed guides the player through each step, advancing when
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
            display.narrate("Solid ground. Rough soil under your feet, a few")
            display.narrate("scraggly plants, the faint hum of something alive")
            display.narrate("beneath the surface.")
        print()
        display.seed_speak("I hold this ground together — without me, it's all")
        display.seed_speak("just dust in the void. But I can't do it alone anymore.")
        print()
        display.seed_speak("I don't have a name. Not one anyone's given me.")
        display.seed_speak("What would you call me?")
        game.state["awaiting_world_seed_name"] = True
        return False

    if step == "first_look" and cmd == "look":
        game.state["tutorial_step"] = "movement"
        seed_name = game.state.get("world_seed_name", "Tuft")
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
                display.seed_speak("Thanks to our connection, you can INVOKE them. But let's talk about that later.")
            print()
        display.seed_speak("For now, survey our domain. Try walking.")
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
        display.seed_speak("See? I have motes. That's what keeps us alive here.")
        display.seed_speak("Feed me artifacts and materials, and I grow stronger.")
        display.seed_speak("The more motes I have, the more I can do for all of us.")
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
            game.state["tutorial_step"] = "explorer_navigate"
            game._transition_to_day1()
            print()
            _tutorial_prompt("Head south to the landing pad.")
        return False

    # ── Act 2: Sevarik Explorer ──

    if step == "explorer_navigate" and cmd == "go":
        loc = game.state.get("explorer_location")
        if loc == "skerry_landing":
            print()
            game._show_sensed_nodes(game.current_room())
            game.state["tutorial_step"] = "explorer_void_cross"
        else:
            # Not there yet — nudge toward landing pad
            print()
            display.seed_speak("Keep heading south. The landing pad is at the edge.")
        return False

    if step == "explorer_void_cross" and cmd == "seek":
        room = game.current_room()
        if room and room.zone != "skerry":
            print()
            zone = room.zone
            if zone == "verdant_wreck":
                display.seed_speak("A biodome. Life everywhere. Let's see what grew here.")
            elif zone == "frozen_wreck":
                display.seed_speak("Cold. Everything preserved. Be careful what you thaw.")
            elif zone == "coral_thicket":
                display.seed_speak("The coral hums. Something hungry grew here.")
            else:
                display.seed_speak("The debris field. Stay sharp.")
            display.seed_speak("Explore carefully, and watch for danger.")
            game.state["tutorial_step"] = "explorer_free"
        return False

    if step == "explorer_free":
        _explorer_free_hints(cmd, args, game)
        # Check if all seven objectives are done
        if (game.state.get("tutorial_combat_done") and
                game.state.get("tutorial_exploit_done") and
                game.state.get("tutorial_invoke_done") and
                game.state.get("tutorial_scavenge_done") and
                game.state.get("tutorial_artifact_found") and
                game.state.get("tutorial_recruit_done") and
                game.state.get("tutorial_quest_done")):
            print()
            display.seed_speak("You've done well. Head back to the skerry.")
            display.seed_speak("Head south to the entry room, then SEEK home.")
            _tutorial_prompt("Head south, then SEEK HOME to return.")
            game.state["tutorial_step"] = "explorer_return"
        return False

    if step == "explorer_return" and cmd in ("seek", "enter"):
        room = game.current_room()
        if room and room.zone == "skerry":
            # Move Miria to landing pad to greet Sevarik
            miria_id = game.steward_name.lower()
            if miria_id in game.agents_db:
                game.agents_db[miria_id]["location"] = "skerry_landing"
            print()
            display.narrate(f"{game.steward_name} hurries out to the landing pad as you arrive.")
            print()
            # Check if player has an unresolved artifact
            _has_artifact = _player_has_unresolved_artifact(game)
            if _has_artifact:
                seed_name = game.state.get("world_seed_name", "Tuft")
                steward_name = game.state.get("steward_name", "Miria")
                display.seed_speak("Now, what about that artifact you brought back?")
                display.seed_speak(f"You have three choices: KEEP it for the stat bonus.")
                display.seed_speak(f"OFFER it TO {seed_name.upper()} for motes.")
                display.seed_speak(f"Or GIVE it TO {steward_name.upper()}.")
                game.state["tutorial_step"] = "explorer_artifact"
            else:
                _advance_to_stash(game)
        return False

    if step == "explorer_artifact":
        if game.state.get("tutorial_artifact_resolved"):
            _advance_to_stash(game)
        return False

    if step == "explorer_stash":
        if cmd == "drop":
            char = game.current_character()
            has_materials = any(
                game.items_db.get(i, {}).get("type") == "material"
                for i in char.inventory
            )
            if not has_materials:
                # Already dropped everything or had nothing
                print()
                steward_name = game.state.get("steward_name", "Miria")
                display.seed_speak(f"Good. Now let {steward_name} take over.")
                _tutorial_prompt(f"SWITCH FOCUS TO {steward_name.upper()}.")
                game.state["tutorial_step"] = "explorer_handoff"
        elif cmd == "go":
            loc = game.state.get("explorer_location")
            if loc == "skerry_junkyard":
                print()
                display.seed_speak("Drop your salvage here. DROP MATERIALS to pile it all.")
                _tutorial_prompt("DROP MATERIALS to store your salvage.")
        return False

    if step == "explorer_handoff" and cmd == "switch":
        # _switch_focus already handled the phase change
        phase = game.state.get("current_phase")
        if phase == "steward":
            game.state["tutorial_step"] = "steward_arrive"
            _steward_arrive(game)
        return False

    # ── Act 3: Miria Steward ──

    if step == "steward_recipes" and cmd == "recipes":
        print()
        display.seed_speak("See anything you can make? Head to the junkyard —")
        display.seed_speak("GO WEST — and try CRAFT BASIC TOOLS.")
        _tutorial_prompt("GO WEST to the junkyard, then CRAFT BASIC_TOOLS.")
        game.state["tutorial_step"] = "steward_craft"
        return False

    if step == "steward_craft" and cmd == "craft":
        # Check if crafting succeeded (character should have basic_tools)
        char = game.current_character()
        if "basic_tools" in char.inventory:
            print()
            recruited = game.state.get("recruited_npcs", [])
            if recruited:
                npc_id = recruited[0]
                npc_name = game.npcs_db.get(npc_id, {}).get("name", npc_id)
                display.seed_speak(f"Well done. Now put your recruit to work.")
                display.seed_speak(f"ASSIGN {npc_name.upper()} SALVAGE — she can sort what comes in.")
                _tutorial_prompt(f"ASSIGN {npc_name.upper()} SALVAGE.")
            else:
                display.seed_speak("Well done. You'll need help eventually —")
                display.seed_speak("Sevarik can recruit survivors on his next expedition.")
            game.state["tutorial_step"] = "steward_assign"
        else:
            print()
            display.seed_speak("That didn't work. Make sure you're in the junkyard")
            display.seed_speak("with the materials.")
        return False

    if step == "steward_assign" and cmd == "assign":
        # Check if any NPC has a non-idle assignment
        npcs = game.state.get("npcs", {})
        any_assigned = any(
            npc.get("assignment") not in (None, "idle")
            for npc in npcs.values()
        )
        if any_assigned:
            print()
            display.seed_speak("Perfect. They'll process salvage while you focus")
            display.seed_speak("on other things.")
            print()
            display.divider()
            print()
            display.seed_speak("That's the rhythm. Explorer gathers, steward builds.")
            display.seed_speak("Keep going — you know what to do now.")
            display.seed_speak("HELP is always there if you need it.")
            print()
            display.divider()
            game.state["tutorial_step"] = "complete"
            game.state["tutorial_complete"] = True
            return True
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
    display.seed_speak("But I need more motes before I can grow. I'm limited")
    display.seed_speak("in what I can protect, for now.")
    print()

    display.seed_speak(f"Before we go further — CHECK me. See how I'm doing.")
    _tutorial_prompt(f"CHECK {seed_name.upper()} to see the seed's status.")

    game.state["tutorial_step"] = "check_seed"


def _player_has_unresolved_artifact(game):
    """Check if the current character has an unresolved artifact in inventory."""
    char = game.current_character()
    for item_id in char.inventory:
        if item_id in game.artifacts_db:
            status = game.state.get("artifacts_status", {}).get(item_id)
            if status not in ("kept", "fed", "given"):
                return True
    return False


def _advance_to_stash(game):
    """Move tutorial to the explorer_stash step."""
    char = game.current_character()
    has_materials = any(
        game.items_db.get(i, {}).get("type") == "material"
        for i in char.inventory
    )
    if has_materials:
        print()
        display.seed_speak("Drop your salvage at the junkyard — Miria will know")
        display.seed_speak("where to find it. Head west from the clearing.")
        _tutorial_prompt("GO to the junkyard and DROP MATERIALS.")
        game.state["tutorial_step"] = "explorer_stash"
    else:
        # Nothing to stash — skip to handoff
        print()
        steward_name = game.state.get("steward_name", "Miria")
        display.seed_speak(f"Nothing to stash. Let {steward_name} take over.")
        _tutorial_prompt(f"SWITCH FOCUS TO {steward_name.upper()}.")
        game.state["tutorial_step"] = "explorer_handoff"


def _steward_arrive(game):
    """Steward orientation — immediately advance to steward_recipes."""
    print()
    display.seed_speak("Good haul. Head to the junkyard and see what you can make.")
    display.seed_speak("Type RECIPES to check what's available.")
    _tutorial_prompt("RECIPES to see what you can craft.")
    game.state["tutorial_step"] = "steward_recipes"


def _explorer_free_hints(cmd, args, game):
    """Contextual hints during the explorer_free step.

    Teaching order: ATTACK → EXPLOIT → free invocation on ATTACK → INVOKE (paid).
    """
    room = game.current_room()
    if not room:
        return

    combat_done = game.state.get("tutorial_combat_done")
    exploit_done = game.state.get("tutorial_exploit_done")
    invoke_done = game.state.get("tutorial_invoke_done")
    scavenge_done = game.state.get("tutorial_scavenge_done")
    artifact_found = game.state.get("tutorial_artifact_found")
    recruit_done = game.state.get("tutorial_recruit_done")

    # Room has enemies, not in combat, combat not done — prompt ATTACK
    if room.has_enemies() and not game.in_combat and not combat_done:
        print()
        display.seed_speak("Those creatures! ATTACK them before they swarm you.")
        _tutorial_prompt("ATTACK to engage the enemy.")
        return

    # Just attacked, enemy survived, exploit not yet taught
    if cmd == "attack" and game.in_combat and not exploit_done:
        enemy_data = game.enemies_db.get(game.combat_target, {})
        enemy_aspects = enemy_data.get("aspects", [])
        if enemy_aspects:
            first_aspect = enemy_aspects[0]
            short = first_aspect.split()[0] if first_aspect else "aspect"
            print()
            display.seed_speak("They're tough. But every creature has weaknesses.")
            display.seed_speak(f"See '{display.aspect_text(first_aspect)}'?")
            display.seed_speak(f"EXPLOIT {short.upper()} to set up a tactical advantage.")
            display.seed_speak("It won't cost anything — just your ability to NOTICE things versus theirs.")
            _tutorial_prompt(f"EXPLOIT {short.upper()} to create a free invocation.")
        return

    # Just exploited successfully — teach that ATTACK will auto-use it
    if cmd == "exploit" and exploit_done and not game.state.get("_exploit_celebrated"):
        game.state["_exploit_celebrated"] = True
        print()
        display.seed_speak("Now ATTACK — your free invocation will fire automatically.")
        display.seed_speak("+2 to your strike, no fate point spent.")
        _tutorial_prompt("ATTACK to use your free invocation.")
        return

    # Attack consumed a free invocation — celebrate, then teach INVOKE
    if cmd == "attack" and exploit_done and not invoke_done:
        if not game.state.get("_free_invoke_celebrated") and combat_done:
            # Enemy was defeated by the free-invocation attack
            game.state["_free_invoke_celebrated"] = True
            print()
            display.seed_speak("EXPLOIT sets up free hits. INVOKE costs a fate point")
            display.seed_speak("but works instantly, no setup needed.")
            display.seed_speak("Save INVOKE for when you need a guaranteed edge.")
        elif not game.state.get("_free_invoke_celebrated") and game.in_combat:
            # Enemy survived — show the payoff, mention INVOKE
            game.state["_free_invoke_celebrated"] = True
            print()
            display.seed_speak("See? That free invocation hit hard.")
            display.seed_speak("For tougher enemies, you can also INVOKE an aspect —")
            display.seed_speak("costs a fate point, but gives +2 immediately.")
            _tutorial_prompt("INVOKE <aspect> to spend a fate point for +2.")
        return

    # Just invoked successfully
    if cmd == "invoke" and invoke_done and not game.state.get("_invoke_celebrated"):
        game.state["_invoke_celebrated"] = True
        print()
        display.seed_speak("EXPLOIT for free advantages. INVOKE when you need power now.")
        display.seed_speak("That's the rhythm of combat.")
        return

    # Enemy defeated — prompt to take loot and scavenge
    if cmd in ("attack", "invoke") and combat_done and not game.in_combat:
        if room.items and not scavenge_done:
            print()
            display.seed_speak("Don't leave that behind — TAKE it.")
            display.seed_speak("And SCAVENGE this area — Miria needs materials.")
        elif not scavenge_done:
            print()
            display.seed_speak("Good fighting. Now SCAVENGE this area —")
            display.seed_speak("Miria needs materials to work with.")
            _tutorial_prompt("SCAVENGE to search for materials.")
        return

    # Just scavenged successfully (first time only)
    if cmd == "scavenge" and scavenge_done and not game.state.get("tutorial_scavenge_hinted"):
        game.state["tutorial_scavenge_hinted"] = True
        print()
        display.seed_speak("Good haul. You can make things with what you find —")
        display.seed_speak("type RECIPES to see what you know, then CRAFT to build.")
        if not artifact_found:
            display.seed_speak("Keep an eye out for artifacts and survivors too.")
        return

    # Room has undiscovered artifact
    if not artifact_found:
        for art_id, art in game._artifacts_in_room(room.id):
            if cmd == "ih" or cmd == "look":
                print()
                display.seed_speak("I sense something powerful here.")
                display.seed_speak("PROBE it to learn more.")
                _tutorial_prompt(f"PROBE {art.get('name', 'artifact').upper()} to examine it.")
            return

    # Just probed an artifact — check if one was actually discovered here
    if cmd == "probe" and not artifact_found:
        for art_id, art in game._artifacts_in_room(room.id):
            if game.state.get("artifacts_status", {}).get(art_id) == "discovered":
                print()
                display.seed_speak("Take it with you. TAKE it.")
                display.seed_speak("We'll decide what to do with it back home.")
                return
        return

    # Just took an artifact
    if cmd == "take" and artifact_found:
        if not game.state.get("_artifact_take_celebrated"):
            game.state["_artifact_take_celebrated"] = True
            print()
            display.seed_speak("Good. Carry it home. You can decide its fate")
            display.seed_speak("on the skerry.")
        return

    # Room has NPCs, recruit not done — prompt on any command
    if not recruit_done and combat_done:
        npc_ids = room.npcs if hasattr(room, 'npcs') else []
        if npc_ids:
            npc_name = None
            for npc_id in npc_ids:
                npc = game.npcs_db.get(npc_id)
                if npc and not npc.get("recruited"):
                    npc_name = npc.get("name", npc_id)
                    break
            if npc_name:
                print()
                display.seed_speak("Survivors! They could use a safe place.")
                _tutorial_prompt(f"RECRUIT {npc_name.upper()} to bring them to the skerry.")
                return

    # Just recruited
    if cmd == "recruit" and recruit_done:
        if not game.state.get("_recruit_celebrated"):
            game.state["_recruit_celebrated"] = True
            print()
            display.seed_speak("Good. We could use the help.")
        return

    # Combat+exploit done but scavenge not done
    if combat_done and exploit_done and not scavenge_done:
        if cmd == "go":
            print()
            display.seed_speak("SCAVENGE to search for materials.")
            _tutorial_prompt("SCAVENGE to search for materials.")
        return

    # After combat+scavenge done, not yet quested — hint about verdant wreck
    quest_done = game.state.get("tutorial_quest_done")
    if combat_done and scavenge_done and not quest_done:
        quest_status = game.state.get("quests", {}).get("verdant_bloom", {}).get("status", "inactive")
        if quest_status == "inactive" and room.zone == "skerry":
            if cmd in ("go", "look", "ih"):
                print()
                display.seed_speak("I sense life — real life — somewhere in the void.")
                display.seed_speak("Not like the debris. Something growing.")
                display.info("  SEEK LIFE from the landing pad to follow it.")
        elif quest_status == "active":
            quest = game.state.get("quests", {}).get("verdant_bloom", {})
            if not quest.get("roots_cleared") and not game.state.get("_quest_hint_shown") and cmd in ("go", "look"):
                if room.zone == "verdant_wreck":
                    game.state["_quest_hint_shown"] = True
                    print()
                    display.seed_speak("Lira mentioned two ways through the roots.")
                    display.seed_speak("Repair the Growth Controller, or weaken and burn.")
        return


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
    elif step == "movement":
        display.seed_speak("There are paths here. Pick a direction.")
        _tutorial_prompt("Pick a direction — N, S, E, or W.")
    elif step == "exploring":
        display.seed_speak("Keep looking around. There's someone here you need to meet.")
    elif step == "check_seed":
        display.seed_speak(f"CHECK {seed_name.upper()} to see the seed's status.")
        _tutorial_prompt(f"CHECK {seed_name.upper()}.")
    elif step == "handoff":
        display.seed_speak(f"Is it OK if I switch my focus to {explorer_name}?")
        _tutorial_prompt(f"SWITCH FOCUS TO {explorer_name.upper()} when you're ready.")
    elif step == "explorer_navigate":
        _tutorial_prompt("Head south to the landing pad.")
    elif step == "explorer_void_cross":
        game._show_sensed_nodes(game.current_room())
    elif step == "explorer_free":
        _explorer_free_resume_hint(gs)
    elif step == "explorer_return":
        display.seed_speak("Head south to the entry room, then SEEK home.")
        _tutorial_prompt("SEEK HOME to return to the skerry.")
    elif step == "explorer_artifact":
        display.seed_speak(f"What will you do with the artifact?")
        display.seed_speak(f"KEEP it, OFFER it TO {seed_name.upper()},")
        display.seed_speak(f"or GIVE it TO {steward_name.upper()}.")
    elif step == "explorer_stash":
        display.seed_speak("Drop your salvage at the junkyard.")
        _tutorial_prompt("GO WEST from the clearing, then DROP MATERIALS.")
    elif step == "explorer_handoff":
        display.seed_speak(f"Let {steward_name} take over.")
        _tutorial_prompt(f"SWITCH FOCUS TO {steward_name.upper()}.")
    elif step == "steward_arrive":
        _tutorial_prompt("RECIPES to see what you can craft.")
    elif step == "steward_recipes":
        display.seed_speak("Type RECIPES to see what you can make.")
        _tutorial_prompt("RECIPES.")
    elif step == "steward_craft":
        display.seed_speak("Head to the junkyard and try CRAFT BASIC TOOLS.")
        _tutorial_prompt("GO WEST, then CRAFT BASIC_TOOLS.")
    elif step == "steward_assign":
        recruited = gs.get("recruited_npcs", [])
        if recruited:
            npc_name = recruited[0].replace("_", " ").title()
            display.seed_speak(f"ASSIGN {npc_name.upper()} SALVAGE.")
            _tutorial_prompt(f"ASSIGN {npc_name.upper()} SALVAGE.")
        else:
            display.seed_speak("You'll need recruits to assign tasks.")


def _explorer_free_resume_hint(gs):
    """Show a contextual hint for explorer_free when resuming a save."""
    combat_done = gs.get("tutorial_combat_done")
    exploit_done = gs.get("tutorial_exploit_done")
    invoke_done = gs.get("tutorial_invoke_done")
    scavenge_done = gs.get("tutorial_scavenge_done")
    artifact_found = gs.get("tutorial_artifact_found")
    recruit_done = gs.get("tutorial_recruit_done")
    quest_done = gs.get("tutorial_quest_done")

    if not combat_done:
        display.seed_speak("Find enemies and ATTACK them.")
    elif not exploit_done:
        display.seed_speak("Find an enemy and try EXPLOIT [aspect] during combat.")
        display.seed_speak("It sets up free invocations — tactical advantage, no cost.")
    elif not invoke_done:
        display.seed_speak("Try INVOKE [aspect] during combat — costs a fate point for +2.")
    elif not scavenge_done:
        display.seed_speak("SCAVENGE to search for materials.")
    elif not artifact_found:
        display.seed_speak("Look for artifacts. Try IH in each room.")
    elif not recruit_done:
        display.seed_speak("Find survivors and RECRUIT them.")
    elif not quest_done:
        quest_status = gs.get("quests", {}).get("verdant_bloom", {}).get("status", "inactive")
        if quest_status == "inactive":
            display.seed_speak("I sense life in the void. SEEK LIFE from the landing pad.")
        else:
            display.seed_speak("Find a way past the root wall in the verdant wreck.")
    else:
        display.seed_speak("Head south to the entry room, then SEEK HOME.")


def _tutorial_prompt(text):
    """Display a styled game instruction hint (yellow with arrow)."""
    lines = text.split("\n")
    print(f"  {display.BRIGHT_YELLOW}\u25b6 {lines[0]}{display.RESET}")
    for line in lines[1:]:
        print(f"  {display.BRIGHT_YELLOW}  {line}{display.RESET}")
