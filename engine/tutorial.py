"""Interactive tutorial — world seed guides new players through all three acts."""

from engine import display


STEPS = [
    # Act 1 — Miria Prologue
    "awakening",             # tendril reaches out, prompt to BOND
    "naming",                # seed asks for a name (input captured in game loop)
    "first_look",            # prompt to LOOK — first perception of the skerry
    "movement",              # prompt to GO somewhere
    "exploring",             # free exploration, encounter explorer at shelter
    "check_seed",            # CHECK SKERRY — learn about domain overview
    "handoff",               # switch focus to explorer

    # Act 2 — Sevarik Explorer
    "explorer_navigate",     # guide to landing pad
    "explorer_void_cross",   # SEEK — first void crossing
    "explorer_free",         # flexible exploration: combat, invoke, artifact, recruit
    "explorer_return",       # SEEK HOME back to skerry
    "explorer_settle",       # SETTLE recruited NPC on the skerry
    "explorer_artifact",     # resolve artifact: KEEP, OFFER, or GIVE
    "explorer_stash",        # go to junkyard, DROP materials
    "explorer_handoff",      # SWITCH FOCUS TO MIRIA

    # Act 3 — Miria Steward
    "steward_arrive",        # orientation narration
    "steward_build",         # BUILD whatever's affordable
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
            game.state["tutorial_step"] = "explorer_navigate"
            game._transition_to_day1()
            print()
            _tutorial_prompt("Head south to the landing pad.")
        return False

    # ── Act 2: Sevarik Explorer ──

    # Catch-all: if player is on skerry with a follower, skip ahead to settle
    # regardless of which explorer step they're technically on.
    if step in ("explorer_navigate", "explorer_void_cross", "explorer_free", "explorer_return"):
        room = game.current_room()
        if room and room.zone == "skerry":
            _has_follower = any(
                npc.get("following") for npc in game.npcs_db.values()
                if npc.get("recruited")
            )
            if _has_follower:
                follower_name = next(
                    npc["name"] for npc in game.npcs_db.values()
                    if npc.get("following") and npc.get("recruited")
                )
                print()
                display.seed_speak(f"You brought someone back. SETTLE {follower_name.upper()} so they have a place here.")
                game.state["tutorial_step"] = "explorer_settle"
                return False

    if step == "explorer_navigate" and cmd == "go":
        loc = game.state.get("explorer_location")
        if loc == "skerry_landing":
            print()
            game._show_landing_pad_destinations(game.current_room())
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
            display.seed_speak("And SCAVENGE everything you can. We need materials.")
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

    if step == "explorer_return":
        # Follower case handled by catch-all above; this handles no-follower return
        room = game.current_room()
        if room and room.zone == "skerry":
            _advance_to_artifact_or_stash(game)
        return False

    if step == "explorer_settle":
        if game.state.get("tutorial_settle_done"):
            _advance_to_artifact_or_stash(game)
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

    if step == "steward_build" and cmd == "build":
        # Check if any new expandable room was built
        built = len(game.skerry.structures) > 0
        if built:
            print()
            recruited = game.state.get("recruited_npcs", [])
            if recruited:
                npc_id = recruited[0]
                npc_name = game.npcs_db.get(npc_id, {}).get("name", npc_id)
                display.seed_speak(f"Now put your recruit to work.")
                display.seed_speak(f"ASSIGN {npc_name.upper()} SALVAGE — she can sort what comes in.")
                _tutorial_prompt(f"ASSIGN {npc_name.upper()} SALVAGE.")
            else:
                display.seed_speak("Well done. You'll need help eventually —")
                display.seed_speak("Sevarik can recruit survivors on his next expedition.")
            game.state["tutorial_step"] = "steward_assign"
        else:
            print()
            build_name = _first_buildable_name(game)
            display.seed_speak("Hmm, that didn't work. Make sure you have the materials")
            display.seed_speak("and tell me where to put it.")
            _tutorial_prompt(f"BUILD {build_name.upper()} <direction> OF <room>.")
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
    display.seed_speak("I'm limited in what I can protect, for now.")
    print()

    display.seed_speak("Before we go further — CHECK the skerry. See how we're doing.")
    _tutorial_prompt("CHECK SKERRY to see an overview of our domain.")

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


def _advance_to_artifact_or_stash(game):
    """After settling followers, prompt artifact resolution or skip to stash."""
    if _player_has_unresolved_artifact(game):
        seed_name = game.state.get("world_seed_name", "Tuft")
        steward_name = game.state.get("steward_name", "Miria")
        print()
        display.seed_speak("You brought something back. Something with power.")
        display.seed_speak(f"KEEP it for the stat bonus,")
        display.seed_speak(f"OFFER it TO {seed_name.upper()} for motes,")
        display.seed_speak(f"or take it to the junkyard for {steward_name} to sort through.")
        game.state["tutorial_step"] = "explorer_artifact"
    else:
        _advance_to_stash(game)


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
    """Steward orientation — prompt to build whatever's affordable."""
    build_name = _first_buildable_name(game)
    print()
    display.seed_speak("We need to start building. The salvage won't organize itself.")
    display.seed_speak(f"CHECK SKERRY to see what's possible, then BUILD {build_name.upper()}.")
    display.seed_speak("You'll pick where to put it — just say which direction off an existing room.")
    _tutorial_prompt(f"CHECK SKERRY, then BUILD {build_name.upper()} <direction> OF <room>.")
    game.state["tutorial_step"] = "steward_build"


def _first_buildable_name(game):
    """Return the name of the first structure the steward can afford, or a fallback."""
    inv_counts = {}
    junkyard = game.rooms.get("skerry_junkyard")
    if junkyard:
        for item_id in junkyard.items:
            inv_counts[item_id] = inv_counts.get(item_id, 0) + 1
    for item_id in game.steward.inventory:
        inv_counts[item_id] = inv_counts.get(item_id, 0) + 1
    npc_count = len(game.state.get("recruited_npcs", []))
    for tmpl in game.skerry.expandable:
        can, _ = game.skerry.can_build(tmpl, inv_counts, npc_count, game.seed.growth_stage)
        if can:
            return tmpl["name"]
    # Fallback — shouldn't happen if handoff gate works, but safe
    return game.skerry.expandable[0]["name"] if game.skerry.expandable else "something"


def _explorer_free_hints(cmd, args, game):
    """Contextual hints during the explorer_free step.

    Teaching order: ATTACK → EXPLOIT → exploit advantage on ATTACK → INVOKE (paid).
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
            display.seed_speak(f"EXPLOIT {short.upper()} to set up a tactical advantage, or just ATTACK.")
            _tutorial_prompt(f"EXPLOIT {short.upper()} or ATTACK.")
        return

    # Just exploited successfully — teach that ATTACK will auto-use it
    if cmd == "exploit" and exploit_done and not game.state.get("_exploit_celebrated"):
        game.state["_exploit_celebrated"] = True
        print()
        display.seed_speak("Now ATTACK — your exploit advantage will fire automatically.")
        display.seed_speak("+2 to your strike, no fate point spent.")
        _tutorial_prompt("ATTACK to use your exploit advantage.")
        return

    # Attack consumed an exploit advantage — celebrate, then teach INVOKE
    if cmd == "attack" and exploit_done and not invoke_done:
        if not game.state.get("_free_invoke_celebrated") and combat_done:
            # Enemy was defeated by the exploit-boosted attack
            game.state["_free_invoke_celebrated"] = True
            game.state["tutorial_invoke_done"] = True  # explained = learned
            print()
            display.seed_speak("EXPLOIT is free but takes a turn to set up.")
            display.seed_speak("There's another option: INVOKE spends a fate point")
            display.seed_speak("to get +2 right now, no setup required.")
            display.seed_speak("Type INVOKE with no arguments to see all the ways you can use it.")
        elif not game.state.get("_free_invoke_celebrated") and game.in_combat:
            # Enemy survived — show the payoff, mention INVOKE
            game.state["_free_invoke_celebrated"] = True
            game.state["tutorial_invoke_done"] = True  # explained = learned
            print()
            display.seed_speak("That exploit advantage hit hard.")
            display.seed_speak("There's a faster option too — INVOKE spends a fate")
            display.seed_speak("point to get +2 immediately, no setup turn needed.")
            display.seed_speak("Type INVOKE with no arguments to see all the ways you can use it.")
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

    # Room has NPCs, recruit not done — prompt once (first NPC you find)
    if not recruit_done and not game.state.get("_recruit_prompted"):
        npc_ids = room.npcs if hasattr(room, 'npcs') else []
        for npc_id in npc_ids:
            npc = game.npcs_db.get(npc_id)
            if npc and not npc.get("recruited"):
                npc_name = npc.get("name", npc_id)
                game.state["_recruit_prompted"] = True
                print()
                display.seed_speak("Survivors! They could use a safe place.")
                _tutorial_prompt(f"RECRUIT {npc_name.upper()} to bring them to the skerry.")
                # Teach INVOKE alongside recruit if not yet learned
                if not invoke_done:
                    print()
                    display.seed_speak("Recruiting is a skill check. If you need an edge,")
                    display.seed_speak("INVOKE spends a fate point for +2 on any roll.")
                    game.state["tutorial_invoke_done"] = True  # explained = learned
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
            display.seed_speak("Don't move on yet — there may be materials here.")
            _tutorial_prompt("SCAVENGE to search for materials.")
        return

    # After combat+scavenge done, not yet quested — hint about verdant wreck
    quest_done = game.state.get("tutorial_quest_done")
    if combat_done and scavenge_done and not quest_done:
        quest_status = game.state.get("quests", {}).get("verdant_bloom", {}).get("status", "inactive")
        if quest_status == "inactive" and room.zone == "skerry":
            if cmd in ("go", "look", "ih") and not game.state.get("_life_hint_shown"):
                game.state["_life_hint_shown"] = True
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
        display.seed_speak("CHECK the skerry — you can see our whole domain through our bond.")
        _tutorial_prompt("CHECK SKERRY.")
    elif step == "handoff":
        display.seed_speak(f"Is it OK if I switch my focus to {explorer_name}?")
        _tutorial_prompt(f"SWITCH FOCUS TO {explorer_name.upper()} when you're ready.")
    elif step == "explorer_navigate":
        _tutorial_prompt("Head south to the landing pad.")
    elif step == "explorer_void_cross":
        game._show_landing_pad_destinations(game.current_room())
    elif step == "explorer_free":
        _explorer_free_resume_hint(gs)
    elif step == "explorer_return":
        display.seed_speak("Head south to the entry room, then SEEK home.")
        _tutorial_prompt("SEEK HOME to return to the skerry.")
    elif step == "explorer_settle":
        follower_name = next(
            (npc["name"] for npc in gs.get("npcs", {}).values()
             if npc.get("following") and npc.get("recruited")),
            "your companion"
        )
        display.seed_speak(f"SETTLE {follower_name.upper()} so they have a place here.")
        _tutorial_prompt(f"SETTLE {follower_name.upper()}.")
    elif step == "explorer_artifact":
        display.seed_speak(f"What will you do with the artifact?")
        display.seed_speak(f"KEEP it, OFFER it TO {seed_name.upper()},")
        display.seed_speak(f"or take it to the junkyard for {steward_name} to sort through.")
    elif step == "explorer_stash":
        display.seed_speak("Drop your salvage at the junkyard.")
        _tutorial_prompt("GO WEST from the clearing, then DROP MATERIALS.")
    elif step == "explorer_handoff":
        display.seed_speak(f"Let {steward_name} take over.")
        _tutorial_prompt(f"SWITCH FOCUS TO {steward_name.upper()}.")
    elif step == "steward_arrive":
        build_name = _first_buildable_name(game)
        _tutorial_prompt(f"CHECK SKERRY, then BUILD {build_name.upper()} <direction> OF <room>.")
    elif step == "steward_build":
        build_name = _first_buildable_name(game)
        display.seed_speak(f"CHECK SKERRY to see what you can build.")
        _tutorial_prompt(f"BUILD {build_name.upper()} <direction> OF <room>.")
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
        display.seed_speak("It sets up exploit advantages — free +2 on your next attack, no cost.")
    elif not invoke_done:
        display.seed_speak("You've used EXPLOIT (free setup). Now try INVOKE —")
        display.seed_speak("it spends a fate point for an instant +2, no setup turn.")
        _tutorial_prompt("In combat: INVOKE <aspect> (costs 1 FP, instant +2).")
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
