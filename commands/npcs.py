"""NPC domain — talk, say, recruit, follower management."""

from engine import display, dice, aspects, recruit


class NpcsMixin:
    """Mixin providing NPC interaction commands for the Game class."""

    def cmd_talk(self, args):
        if not args:
            display.error("Talk to whom?")
            return

        target = " ".join(args).lower()
        room = self.current_room()

        npc_id, npc = self._find_entity(room.npcs, target, self.npcs_db)
        # Also check followers at this location
        if not npc:
            npc_id, npc = self._find_follower(target, room.id)
        if npc:
            # Check for quest-specific dialogue first
            from engine.quest import get_quest_talk, apply_quest_talk_effects
            quest_result = get_quest_talk(npc_id, npc, self.state)
            if quest_result:
                for line in quest_result["lines"]:
                    display.npc_speak(npc["name"], self._sub_dialogue(line))
                if quest_result.get("say_hint"):
                    print()
                    display.info("  (SAY YES or SAY NO to answer her)")
                if quest_result.get("quest_started"):
                    display.info("  [Quest started: The Verdant Heart]")
                apply_quest_talk_effects(quest_result, self.state, self.rooms, self.current_character())
                return

            dialogue = npc.get("dialogue", {})
            if npc.get("recruited"):
                mood = npc.get("mood", "content")
                if mood == "content" or mood == "happy":
                    msg = dialogue.get("happy", dialogue.get("idle", "..."))
                else:
                    msg = dialogue.get("idle", "...")
                display.npc_speak(npc["name"], self._sub_dialogue(msg))
                # Talking to recruited NPCs boosts loyalty slightly
                if npc.get("loyalty", 0) < 10:
                    old_loyalty = npc.get("loyalty", 0)
                    npc["loyalty"] = min(10, old_loyalty + 1)
                    display.success(f"  {npc['name']}'s loyalty increases to {npc['loyalty']}.")
                    self._log_event("npc_talked", comic_weight=1,
                                    npc_name=npc["name"], npc_id=npc_id,
                                    loyalty_change=f"{old_loyalty}->{npc['loyalty']}")
            else:
                msg = dialogue.get("greeting", "They look at you warily.")
                display.npc_speak(npc["name"], self._sub_dialogue(msg))
            return

        # Talk to inactive agent
        agent_id, agent = self._find_agent_in_room(target, room.id)
        if agent:
            dialogue = agent.get("dialogue", {})
            msg = dialogue.get("idle", f"{agent['name']} nods quietly.")
            display.npc_speak(agent["name"], self._sub_dialogue(msg))
            return

        display.narrate(f"There's nobody called '{target}' here to talk to.")

    def cmd_say(self, args):
        if not args:
            display.error("Say what? (SAY <words> or \"<words>)")
            return

        char = self.current_character()
        words = " ".join(args).lower()
        pending = self.state.get("pending_npc_question")

        if pending:
            room = self.current_room()
            # Player is in the right room for the pending question
            if room and room.id == pending.get("room_id"):
                if pending["key"] == "tools_question" and pending["npc_id"] == "lira":
                    from engine.quest import handle_lira_say, apply_quest_talk_effects
                    npc = self.npcs_db.get("lira")
                    if npc:
                        result = handle_lira_say(words, npc, self.state, self.rooms)
                        if result:
                            for line in result["lines"]:
                                display.npc_speak(npc["name"], self._sub_dialogue(line))
                            if result.get("quest_started"):
                                print()
                                display.info("  [Quest started: The Verdant Heart]")
                            apply_quest_talk_effects(result, self.state, self.rooms, self.current_character())
                            # Clear the pending question
                            self.state.pop("pending_npc_question", None)
                            # Seed RECRUIT hint
                            self._seed_recruit_hint()
                            return
                        else:
                            # Unrecognized answer
                            display.info("  (SAY YES or SAY NO to answer her)")
                            return
            else:
                # Wrong room — generic speech, pending question stays
                display.narrate(f'{char.name} says: "{" ".join(args)}"')
                return

        # No pending question — generic speech
        display.narrate(f'{char.name} says: "{" ".join(args)}"')

    def _seed_recruit_hint(self):
        """World seed hints about RECRUIT after Lira conversation."""
        cap = self.skerry.population_cap()
        current = 2 + len(self.state.get("recruited_npcs", []))
        remaining = cap - current
        print()
        display.seed_speak(f"We have space for {remaining} more at the skerry.")
        display.seed_speak("RECRUIT her, and I can bring her safely home with you.")

    def cmd_recruit(self, args):
        if not args:
            display.error("Recruit whom?")
            return

        target = " ".join(args).lower()
        room = self.current_room()

        npc_id, npc = self._find_entity(room.npcs, target, self.npcs_db)
        if not npc:
            display.narrate(f"There's nobody called '{target}' here to recruit.")
            return

        if npc.get("recruited"):
            display.narrate(f"{npc['name']} is already with you.")
            return

        dc = npc.get("recruit_dc", 2)
        if dc is None:
            display.narrate(f"{npc['name']} can't be recruited.")
            return

        # Population cap check
        cap = self.skerry.population_cap()
        current = 2 + len(self.state.get("recruited_npcs", []))
        if current >= cap:
            display.seed_speak("We can't support any more people yet.")
            display.info(f"  Population: {current}/{cap}. Build more rooms.")
            return

        # Special conditions
        condition = npc.get("recruit_condition")
        if condition == "combat_demo":
            display.narrate(self._sub_dialogue(npc["dialogue"].get("recruit_fail", "They want proof of your strength.")))
            display.info("  (Defeat an enemy in this room first, then try again.)")
            if room.has_enemies():
                return
            dc = 0

        # Check fate point cost for retries
        attempts = npc.get("recruit_attempts", 0)
        if attempts > 0:
            if not self.explorer.spend_fate_point():
                display.error(f"You need 1 fate point to try recruiting {npc['name']} again. (You have {self.explorer.fate_points} FP.)")
                return
            display.info(f"  Spent 1 fate point to retry. (Fate Points remaining: {self.explorer.fate_points})")

        # FATE roll — sets puzzle difficulty
        invoke_bonus = self._consume_invoke_bonus()
        rapport_val = self.explorer.get_skill("Rapport") + invoke_bonus
        rapport_label = f"Rapport+{invoke_bonus}" if invoke_bonus else "Rapport"
        total, shifts, dice_result = dice.skill_check(rapport_val, dc)
        print(f"  Rapport check: {dice.roll_description(dice_result, rapport_val, rapport_label)}")
        print(f"  DC: +{dc}")
        print(f"  Shifts: {shifts:+d}")

        # Look up puzzle parameters
        grid_size, num_colors, base_threshold = recruit.RECRUIT_DIFFICULTIES.get(dc, (6, 3, 20))
        threshold = recruit.calculate_threshold(base_threshold, shifts, grid_size)

        if shifts >= 0:
            display.success(f"  Your pitch is strong. Threshold: {threshold} steps.")
        elif shifts >= -2:
            display.narrate(f"  A lukewarm start. Threshold: {threshold} steps.")
        else:
            display.warning(f"  Tough crowd. Threshold: {threshold} steps.")
        print()

        # Show NPC greeting for context
        greeting = npc.get("dialogue", {}).get("greeting", "")
        if greeting:
            display.npc_speak(npc["name"], self._sub_dialogue(greeting))
            print()

        # Generate board and start minigame
        origin_zone = room.zone if room else None
        state = recruit.create_recruit_state(npc_id, npc, grid_size, num_colors, threshold)
        state["origin_zone"] = origin_zone
        self.recruit_state = state
        self.in_recruit = True

        seed_hex = f"{state['seed']:06X}"
        display.info(f"  Conversation variant: {seed_hex}")
        print()

        # Show initial board
        recruit.display_board(state, npc["name"])
        flavor = recruit.get_npc_flavor(state, state["score"] / threshold)
        if flavor:
            display.narrate(f"  {flavor}")

        # Tutorial hint: INVOKE works in recruitment too
        if not self.state.get("tutorial_complete") and not self.state.get("_recruit_invoke_hint"):
            self.state["_recruit_invoke_hint"] = True
            print()
            display.seed_speak("Your aspects have power here too.")
            display.seed_speak("INVOKE <aspect> to tip the conversation — PUSH lowers")
            display.seed_speak("the threshold, COUNTER resets a fading topic, RESTORE")
            display.seed_speak("reopens closed lines of argument.")
            display.seed_speak("Type INVOKE with no arguments to see your options.")

        print()

    def _handle_recruit_input(self, raw):
        """Handle player input during the recruit minigame."""
        state = self.recruit_state
        npc_name = state["npc_name"]
        npc = state["npc_data"]

        # Empty input — redisplay
        if not raw:
            recruit.display_board(state, npc_name)
            flavor = recruit.get_npc_flavor(state, state["score"] / state["threshold"])
            if flavor:
                display.narrate(f"  {flavor}")
            return

        cmd = raw.lower().strip()

        # Help
        if cmd in ("help", "?"):
            recruit.display_help_text()
            return

        # Quit/abandon
        if cmd in ("quit", "abandon"):
            self._resolve_recruit(won=False)
            return

        # Invoke aspect
        if cmd.startswith("invoke "):
            self._recruit_invoke(cmd[7:].strip(), state, npc_name)
            return
        if cmd == "invoke":
            char = self.current_character()
            all_aspects = aspects.collect_invokable_aspects(self, context="recruit")
            self._display_invoke_menu(char, all_aspects, "recruit")
            return

        # Parse direction
        direction_map = {
            "w": "WHEEDLE", "wheedle": "WHEEDLE",
            "a": "APPEAL", "appeal": "APPEAL",
            "s": "SUGGEST", "suggest": "SUGGEST",
            "d": "DESCRIBE", "describe": "DESCRIBE",
        }
        direction = direction_map.get(cmd)
        if not direction:
            display.error("Type a tactic (W/A/S/D), INVOKE <aspect>, QUIT, or HELP.")
            return

        # Apply move
        success, messages = recruit.apply_move(state, direction)
        if not success:
            for msg in messages:
                display.error(msg)
            return

        # Show messages (flavor, warnings, eliminations)
        for msg in messages:
            display.narrate(f"  {msg}")

        # Threshold crossed — notify once, but keep going
        if state["score"] >= state["threshold"] and not state.get("threshold_reached"):
            state["threshold_reached"] = True
            print()
            display.success(f"  {npc_name} is convinced! But the conversation is flowing — keep going for bonuses.")

        # Check game over (no valid moves)
        if not recruit.has_valid_moves(state):
            print()
            won = state["score"] >= state["threshold"]
            if won:
                over = state["score"] - state["threshold"]
                display.success(f"  Conversation complete. {state['score']}/{state['threshold']} steps (+{over} over par).")
            else:
                display.warning(f"  No more moves. You reached {state['score']}/{state['threshold']} steps.")
            self._resolve_recruit(won=won)
            return

        # Redisplay board
        recruit.display_board(state, npc_name)
        flavor = recruit.get_npc_flavor(state, state["score"] / state["threshold"])
        if flavor:
            display.narrate(f"  {flavor}")

    def _recruit_invoke(self, raw_query, state, npc_name):
        """INVOKE an aspect during recruitment — choose effect (PUSH/COUNTER/RESTORE)."""
        char = self.current_character()

        all_aspects = aspects.collect_invokable_aspects(self, context="recruit")

        # Parse effect keyword from end of args
        effect = None
        query = raw_query
        for keyword in aspects.RECRUIT_EFFECTS:
            if query.upper().endswith(" " + keyword):
                effect = keyword
                query = query[:-(len(keyword) + 1)].strip()
                break

        # Fuzzy-match the aspect
        found = None
        found_source = None
        for a, source in all_aspects:
            if query.lower() in a.lower():
                found = a
                found_source = source
                break

        if not found:
            display.error(f"No matching aspect for '{query}'.")
            display.info("  Available aspects:")
            for a, source in all_aspects:
                if a not in self.scene_invoked_aspects:
                    print(f"    {display.aspect_text(a)} {display.DIM}({source}){display.RESET}")
            return

        # Check if already invoked this scene
        if found in self.scene_invoked_aspects:
            display.error(f"You've already invoked {display.aspect_text(found)} this scene.")
            remaining = [(a, s) for a, s in all_aspects if a not in self.scene_invoked_aspects]
            if remaining:
                display.info("  Still available:")
                for a, source in remaining:
                    print(f"    {display.aspect_text(a)} {display.DIM}({source}){display.RESET}")
            return

        # Default effect
        if effect is None:
            effect = "PUSH"

        # Spend fate point
        if not char.spend_fate_point():
            display.error(f"No fate points to spend! (You have {char.fate_points} FP.)")
            return

        self.scene_invoked_aspects.add(found)
        if not self.state.get("tutorial_complete"):
            self.state["tutorial_invoke_done"] = True

        source_type = "seed" if found_source == self.seed_name else None
        flavor = aspects.get_recruit_invoke_flavor(found, found_source, npc_name, source_type=source_type)
        display.narrate(f"  {flavor}")
        display.info(f"  (Fate Points remaining: {char.fate_points})")

        # Branch on effect
        if effect == "PUSH":
            old_threshold = state["threshold"]
            total_tiles = state["grid_size"] ** 2
            floor = int(total_tiles * 0.4)
            state["threshold"] = max(floor, old_threshold - 4)
            display.info(f"  Threshold: {old_threshold} → {state['threshold']}")
        elif effect == "COUNTER":
            recruit.reset_lowest_counter(state)
        elif effect == "RESTORE":
            recruit.restore_tiles(state, count=3)

        # Check if threshold now crossed
        if state["score"] >= state["threshold"] and not state.get("threshold_reached"):
            state["threshold_reached"] = True
            print()
            display.success(f"  {npc_name} is convinced! But the conversation is flowing — keep going for bonuses.")

        recruit.display_board(state, npc_name)

    def _resolve_recruit(self, won):
        """Handle the end of a recruit minigame."""
        state = self.recruit_state
        npc_id = state["npc_id"]
        npc = state["npc_data"]
        npc_name = state["npc_name"]
        seed_hex = f"{state['seed']:06X}"

        print()
        if won:
            npc["recruited"] = True
            npc["following"] = True
            npc["location"] = self.state.get("explorer_location", "skerry_central")
            self.state.setdefault("recruited_npcs", []).append(npc_id)

            room = self.current_room()
            if room:
                room.remove_npc(npc_id)

            display.success(self._sub_dialogue(npc["dialogue"].get("recruit_success", f"{npc_name} joins you!")))
            display.info(f"  {npc_name} falls into step behind you.")

            # Bonus tiers for going over par
            over = max(0, state["score"] - state["threshold"])
            bonus_tiers = over // 5
            base_loyalty = 3
            # Zone the NPC knows about (from where they were when recruited)
            npc_zone = state.get("origin_zone")

            if bonus_tiers >= 1:
                # Tier 1: extra loyalty
                base_loyalty += 2
                display.success(f"  Bonus: {npc_name} is impressed. (+2 loyalty)")

            if bonus_tiers >= 2:
                # Tier 2: artifact hint from what they've seen in their zone
                hint = self._get_artifact_hint(npc_zone)
                if hint:
                    print()
                    display.npc_speak(npc_name, hint)
                else:
                    # Already found the artifact — extra loyalty instead
                    base_loyalty += 2
                    display.success(f"  Bonus: {npc_name} shares everything they know. (+2 loyalty)")

            if bonus_tiers >= 3 and not state["eliminated"]:
                # Tier 3: exceptional rapport — happy mood + high loyalty
                # Requires no tiles eliminated (no conversational threads lost)
                base_loyalty = max(base_loyalty, 7)
                npc["mood"] = "happy"
                display.success(f"  Bonus: A perfect conversation. {npc_name} is genuinely fired up.")

            npc["loyalty"] = base_loyalty
            display.info(f"  Score: {state['score']}/{state['threshold']} (+{over} over par, variant: {seed_hex})")

            self._log_event("recruit_success", comic_weight=5,
                            npc_name=npc_name, npc_id=npc_id,
                            loyalty=npc["loyalty"], score=state["score"],
                            threshold=state["threshold"], over_par=over,
                            variant=seed_hex.lower())

            if not self.state.get("tutorial_complete"):
                self.state["tutorial_recruit_done"] = True
        else:
            npc["recruit_attempts"] = npc.get("recruit_attempts", 0) + 1
            display.narrate(self._sub_dialogue(npc["dialogue"].get("recruit_fail", f"{npc_name} isn't convinced yet.")))
            display.info(f"  Score: {state['score']}/{state['threshold']} (variant: {seed_hex})")
            display.info(f"  You can try again (costs 1 fate point).")
            self._log_event("recruit_failed", comic_weight=3,
                            npc_name=npc_name, npc_id=npc_id,
                            score=state["score"], threshold=state["threshold"],
                            variant=seed_hex.lower())

        self.in_recruit = False
        self.recruit_state = None

    def _move_followers(self, target_room_id):
        """Move all following NPCs to the explorer's new location."""
        for npc_id in self.state.get("recruited_npcs", []):
            npc = self.npcs_db.get(npc_id, {})
            if npc.get("following"):
                npc["location"] = target_room_id

    def _followers_to_skerry(self):
        """Move all followers to the skerry when the explorer comes home."""
        for npc_id in self.state.get("recruited_npcs", []):
            npc = self.npcs_db.get(npc_id, {})
            if npc.get("following"):
                npc["following"] = False
                npc["location"] = "skerry_central"
                skerry_central = self.rooms.get("skerry_central")
                if skerry_central and npc_id not in skerry_central.npcs:
                    skerry_central.add_npc(npc_id)

    def _followers_rejoin_explorer(self):
        """Followers leave the skerry and rejoin the explorer.
        Settled NPCs and NPCs with a work assignment stay on the skerry."""
        explorer_loc = self.state.get("explorer_location", "skerry_central")
        for npc_id in self.state.get("recruited_npcs", []):
            npc = self.npcs_db.get(npc_id, {})
            if npc_id == "sevarik":
                continue
            # Settled NPCs have a home — they stay
            if npc.get("settled_room"):
                continue
            # NPCs with a job stay working on the skerry
            if npc.get("assignment", "idle") != "idle":
                continue
            npc["following"] = True
            npc["location"] = explorer_loc
            # Remove from skerry room
            skerry_central = self.rooms.get("skerry_central")
            if skerry_central and npc_id in skerry_central.npcs:
                skerry_central.remove_npc(npc_id)

    def cmd_request(self, args):
        """REQUEST TREATMENT [FROM <name>] — treat a consequence with Lore + cure item."""
        if not args:
            display.error("Request what? Usage: REQUEST TREATMENT [FROM <name>]")
            return

        raw = " ".join(args).lower()

        # Must start with "treatment"
        if not raw.startswith("treatment"):
            display.error("Request what? Usage: REQUEST TREATMENT [FROM <name>]")
            return

        char = self.current_character()
        phase = self.state.get("current_phase", "explorer")
        char_key = "explorer" if phase == "explorer" else "steward"

        # Figure out the treater
        treater_name = None
        treater_lore = None
        remainder = raw[len("treatment"):].strip()
        if remainder.startswith("from "):
            treater_name = remainder[5:].strip()

        if treater_name:
            # Check if it's the other player character
            other_key = "steward" if char_key == "explorer" else "explorer"
            other_name = self.state.get(f"{other_key}_name", "").lower()
            if treater_name == other_name:
                other_char_data = self.state.get(other_key, {})
                treater_lore = other_char_data.get("skills", {}).get("Lore", 0)
                treater_name = self.state.get(f"{other_key}_name")
            else:
                # Check NPCs at this location
                room = self.current_room()
                npc_pool = list(room.npcs or [])
                # Also check followers
                for npc_id, npc in self.npcs_db.items():
                    if npc.get("following") and npc.get("location") == room.id and npc_id not in npc_pool:
                        npc_pool.append(npc_id)
                npc_id, npc_data = self._find_entity(npc_pool, treater_name, self.npcs_db)
                if npc_data:
                    treater_lore = npc_data.get("skills", {}).get("Lore", 0)
                    treater_name = npc_data.get("name", npc_id)
                else:
                    display.error(f"There's nobody called '{treater_name}' here to treat you.")
                    return
        else:
            # Self-treatment — use own Lore
            treater_lore = char.get_skill("Lore")
            treater_name = char.name

        # Check what consequences need treatment
        consequences = []
        for sev in ["severe", "moderate", "mild"]:
            con = char.consequences.get(sev)
            if con:
                consequences.append((sev, con))

        if not consequences:
            display.narrate(f"{char.name} has no injuries to treat.")
            return

        # Show status and find treatable consequences
        display.header("Injuries")
        treatable = []
        for sev, con in consequences:
            eligible, reason = aspects.can_treat_consequence(self, char_key, sev)
            cure = aspects.get_cure_for_consequence(con)
            cure_name = self.items_db.get(cure, {}).get("name", cure) if cure else "unknown"

            if sev == "mild":
                zones_cleared = self.state.get("zones_cleared", 0)
                meta = self.state.get("consequence_meta", {})
                taken_at = meta.get(f"{char_key}_mild", {}).get("taken_at", 0)
                remaining = max(0, aspects.ZONE_CLEARS_REQUIRED["mild"] - (zones_cleared - taken_at))
                print(f"  {display.BOLD}Mild:{display.RESET} {con}")
                display.info(f"    Heals on its own. {remaining} zone clear{'s' if remaining != 1 else ''} remaining.")
            elif eligible:
                has_cure = cure in char.inventory
                difficulty = aspects.TREATMENT_DIFFICULTY[sev]
                ladder = {0: "Mediocre", 1: "Average", 2: "Fair", 3: "Good", 4: "Great"}
                diff_label = ladder.get(difficulty, f"+{difficulty}")
                print(f"  {display.BOLD}{sev.capitalize()}:{display.RESET} {con}")
                if has_cure:
                    print(f"    Needs: {display.item_name(cure_name)} {display.BRIGHT_GREEN}(have){display.RESET} + Lore check ({diff_label})")
                    if sev == "severe":
                        display.info(f"    Treatment will downgrade to moderate, not fully heal.")
                    treatable.append((sev, con, cure, difficulty))
                else:
                    print(f"    Needs: {display.item_name(cure_name)} {display.BRIGHT_RED}(missing){display.RESET} + Lore check ({diff_label})")
            else:
                print(f"  {display.BOLD}{sev.capitalize()}:{display.RESET} {con}")
                display.info(f"    {reason}")

        if not treatable:
            if any(sev != "mild" for sev, _ in consequences):
                display.narrate("No consequences are ready for treatment right now.")
            return

        # Treat the most severe treatable consequence
        sev, con, cure, difficulty = treatable[0]

        # Consume cure item
        char.remove_from_inventory(cure)
        cure_name = self.items_db.get(cure, {}).get("name", cure)

        # Roll Lore check
        print()
        invoke_bonus = self._consume_invoke_bonus()
        effective_lore = treater_lore + invoke_bonus
        label = f"Lore+{invoke_bonus}" if invoke_bonus else "Lore"
        display.narrate(f"{treater_name} prepares the {cure_name} and gets to work...")
        atk_dice = dice.roll_4df()
        total = sum(atk_dice) + effective_lore

        print(f"  {treater_name}: {dice.roll_description(atk_dice, effective_lore, label)}")
        print(f"  Difficulty: {difficulty} ({['Mediocre', 'Average', 'Fair', 'Good', 'Great'][difficulty]})")

        shifts = total - difficulty

        if shifts >= 0:
            # Success
            self._log_event("treatment_given", comic_weight=3,
                            target=char.name, treater=treater_name,
                            severity=sev, consequence=con, success=True)
            if sev == "severe":
                # Downgrade to moderate
                char.consequences["severe"] = None
                char.consequences["moderate"] = con
                # Update metadata — moderate now tracks from current zone clears
                meta = self.state.setdefault("consequence_meta", {})
                meta.pop(f"{char_key}_severe", None)
                meta[f"{char_key}_moderate"] = {
                    "taken_at": self.state.get("zones_cleared", 0),
                    "cure": cure,
                }
                print()
                display.success(f"The treatment takes hold. The injury stabilizes.")
                display.narrate(f"  {con} downgraded from severe to moderate.")
                display.info(f"  Will need another round of treatment to fully heal.")
            else:
                # Full heal for moderate
                char.consequences[sev] = None
                meta = self.state.setdefault("consequence_meta", {})
                meta.pop(f"{char_key}_{sev}", None)
                print()
                display.success(f"The treatment works. {con} has healed.")
        else:
            # Failure — cure item is still consumed
            print()
            display.warning(f"The treatment doesn't take. The {cure_name} is used up, but the injury persists.")
            display.info(f"  (Failed by {abs(shifts)} — try again with better aspects or a more skilled healer.)")
