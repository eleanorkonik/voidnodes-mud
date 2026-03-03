"""NPC domain — greet, say, recruit, follower management, social encounters."""

from engine import display, dice, aspects, recruit, social


class NpcsMixin:
    """Mixin providing NPC interaction commands for the Game class."""

    def cmd_greet(self, args):
        if not args:
            display.error("Greet whom?")
            return

        # If we're in a social encounter, route to handler
        if self.in_social_encounter:
            display.error("You're in the middle of something. Finish the encounter first.")
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

            if npc.get("recruited"):
                # Check for eligible encounter
                enc_id, enc = social.pick_encounter(self, npc_id, npc)
                if enc:
                    self._start_encounter(enc_id, enc, npc_id, npc)
                    return

                # No encounter — contextual greeting (no loyalty gain)
                msg = social.get_contextual_greeting(npc, npc_id, self)
                display.npc_speak(npc["name"], self._sub_dialogue(msg))
                self._log_event("npc_greeted", comic_weight=1,
                                npc_name=npc["name"], npc_id=npc_id)
            else:
                dialogue = npc.get("dialogue", {})
                msg = dialogue.get("greeting", "They look at you warily.")
                display.npc_speak(npc["name"], self._sub_dialogue(msg))
                # First time greeting any unrecruited NPC — seed hints about RECRUIT
                if not self.state.get("_recruit_hint_shown"):
                    self.state["_recruit_hint_shown"] = True
                    self._seed_recruit_hint(npc["name"])
            return

        # Greet inactive agent
        agent_id, agent = self._find_agent_in_room(target, room.id)
        if agent:
            dialogue = agent.get("dialogue", {})
            msg = dialogue.get("idle", f"{agent['name']} nods quietly.")
            display.npc_speak(agent["name"], self._sub_dialogue(msg))
            return

        display.narrate(f"There's nobody called '{target}' here to talk to.")

    # ── Social encounter management ──────────────────────────────

    def _start_encounter(self, enc_id, enc, npc_id, npc):
        """Start a social encounter — simple resolves inline, others use intercept."""
        npc_name = npc.get("name", npc_id)

        # Record cooldown/history
        day = self.state.get("day", 1)
        if enc.get("once"):
            npc.setdefault("encounter_history", []).append(enc_id)
        else:
            self.state.setdefault("encounter_cooldown", {})[enc_id] = day

        social.display_encounter_header(enc, npc_name)

        if enc["type"] == "simple":
            success, messages = social.resolve_simple(self, enc, npc_id, npc)
            for msg in messages:
                print(msg)

            # Apply rewards/penalties
            print()
            if success:
                reward_msgs = social.apply_reward(self, npc, enc.get("success_reward"))
                for msg in reward_msgs:
                    display.success(msg)
            else:
                penalty_msgs = social.apply_penalty(self, npc, enc.get("failure_penalty"))
                for msg in penalty_msgs:
                    display.warning(msg)

            # Check if this encounter resolves a festering aspect
            resolves = enc.get("resolves_aspect")
            if resolves and success:
                resolve_msgs = social.resolve_festering_aspect(self, resolves)
                for msg in resolve_msgs:
                    display.success(msg)

            self._log_event("social_encounter", comic_weight=3,
                            encounter_id=enc_id, npc_name=npc_name,
                            encounter_type="simple", success=success)

        elif enc["type"] == "challenge":
            state = social.create_encounter_state(enc_id, enc, npc_id, npc_name)
            self.in_social_encounter = True
            self.social_encounter_state = state
            social.display_challenge_step(enc, 0)

        elif enc["type"] == "contest":
            state = social.create_encounter_state(enc_id, enc, npc_id, npc_name)
            self.in_social_encounter = True
            self.social_encounter_state = state
            social.display_contest_round(state, char=self.current_character())

    def _handle_social_encounter_input(self, raw):
        """Route input during a social encounter to the appropriate handler."""
        state = self.social_encounter_state
        if not state:
            self.in_social_encounter = False
            return

        enc_type = state["type"]
        cmd = raw.lower().strip()

        # Allow info commands during encounters
        if cmd in ("stat", "stats", "status"):
            self.cmd_stat([])
            return
        if cmd.startswith("probe ") or cmd.startswith("check "):
            parts = cmd.split(None, 1)
            handler = getattr(self, f"cmd_{parts[0]}", None)
            if handler:
                handler(parts[1].split() if len(parts) > 1 else [])
            return

        if enc_type == "challenge":
            self._handle_challenge_input(cmd, state)
        elif enc_type == "contest":
            self._handle_contest_input(cmd, state)

    def _handle_challenge_input(self, cmd, state):
        """Handle input during a challenge encounter."""
        enc = state["encounter_def"]

        if cmd in ("attempt", "a", "roll"):
            step_done, enc_done, messages = social.resolve_challenge_step(self, state, "attempt")
            for msg in messages:
                print(msg)

            # Apply per-step rewards
            step_idx = state["current_step"] - 1  # just incremented
            step = enc["steps"][step_idx]
            result = state["step_results"][step_idx]
            if result and step.get("success_reward"):
                npc = self.npcs_db.get(state["npc_id"], {})
                reward_msgs = social.apply_reward(self, npc, step["success_reward"])
                for msg in reward_msgs:
                    display.success(msg)

            if enc_done:
                self._resolve_challenge(state)
            else:
                print()
                social.display_challenge_step(enc, state["current_step"])

        elif cmd.startswith("invoke"):
            # Let the player use INVOKE — it sets pending_invoke_bonus
            # Then they still need to ATTEMPT
            rest = cmd[6:].strip()
            if rest:
                self._general_invoke(rest.split())
            else:
                char = self.current_character()
                all_aspects = aspects.collect_invokable_aspects(self, context="social")
                self._display_invoke_menu(char, all_aspects, "social")

        elif cmd in ("concede", "walk", "leave"):
            step_done, enc_done, messages = social.resolve_challenge_step(self, state, "concede")
            for msg in messages:
                print(msg)
            if enc_done:
                self._resolve_challenge(state)
            else:
                print()
                social.display_challenge_step(enc, state["current_step"])

        else:
            display.error("Type ATTEMPT, INVOKE <aspect>, or CONCEDE.")

    def _resolve_challenge(self, state):
        """Resolve a completed challenge encounter."""
        enc = state["encounter_def"]
        npc_id = state["npc_id"]
        npc_name = state["npc_name"]
        npc = self.npcs_db.get(npc_id, {})

        level, text = social.get_challenge_resolution(state)
        social.display_encounter_resolution(level, text)

        # Apply final rewards/penalties based on outcome
        if level == "full_success":
            # All step rewards already applied; check for encounter-level bonus
            pass
        elif level == "failure":
            penalty_msgs = social.apply_penalty(self, npc, enc.get("failure_penalty"))
            for msg in penalty_msgs:
                display.warning(msg)

        # Check resolves_aspect
        resolves = enc.get("resolves_aspect")
        if resolves and level in ("full_success", "partial_success"):
            resolve_msgs = social.resolve_festering_aspect(self, resolves)
            for msg in resolve_msgs:
                display.success(msg)

        self._log_event("social_encounter", comic_weight=4,
                        encounter_id=state["encounter_id"], npc_name=npc_name,
                        encounter_type="challenge", result=level)

        self.in_social_encounter = False
        self.social_encounter_state = None

    def _handle_contest_input(self, cmd, state):
        """Handle input during a contest encounter."""
        enc = state["encounter_def"]
        tactics = enc.get("tactics", [])

        # Concede
        if cmd in ("concede", "walk", "leave"):
            self._resolve_contest(state, conceded=True)
            return

        # Invoke
        if cmd.startswith("invoke"):
            rest = cmd[6:].strip()
            if rest:
                self._general_invoke(rest.split())
            else:
                char = self.current_character()
                all_aspects = aspects.collect_invokable_aspects(self, context="social")
                self._display_invoke_menu(char, all_aspects, "social")
            return

        # Parse tactic choice (1/2/3 or name)
        tactic_id = None
        if cmd.isdigit():
            idx = int(cmd) - 1
            if 0 <= idx < len(tactics):
                tactic_id = tactics[idx]["id"]
        else:
            for t in tactics:
                if cmd in t["name"].lower() or cmd == t["id"]:
                    tactic_id = t["id"]
                    break

        if not tactic_id:
            display.error("Pick a tactic (1/2/3), INVOKE <aspect>, or CONCEDE.")
            return

        round_done, contest_done, messages = social.resolve_contest_round(self, state, tactic_id)
        for msg in messages:
            print(msg)

        if contest_done:
            self._resolve_contest(state)
        else:
            print()
            social.display_contest_round(state, char=self.current_character())

    def _resolve_contest(self, state, conceded=False):
        """Resolve a completed contest encounter."""
        enc = state["encounter_def"]
        npc_id = state["npc_id"]
        npc_name = state["npc_name"]
        npc = self.npcs_db.get(npc_id, {})

        needed = state["victories_needed"]
        player_won = not conceded and state["player_wins"] >= needed

        print()
        if player_won:
            text = enc.get("win_text", f"{npc_name} is convinced.")
            display.success(f"  {text}")
            reward_msgs = social.apply_reward(self, npc, enc.get("win_reward"))
            for msg in reward_msgs:
                display.success(msg)
            # Check resolves_aspect
            resolves = enc.get("resolves_aspect")
            if resolves:
                resolve_msgs = social.resolve_festering_aspect(self, resolves)
                for msg in resolve_msgs:
                    display.success(msg)
        else:
            if conceded:
                display.narrate("  You step away from the argument.")
            text = enc.get("lose_text", f"{npc_name} isn't convinced.")
            display.warning(f"  {text}")
            penalty_msgs = social.apply_penalty(self, npc, enc.get("lose_penalty"))
            for msg in penalty_msgs:
                display.warning(msg)

        result = "win" if player_won else ("concede" if conceded else "lose")
        self._log_event("social_encounter", comic_weight=4,
                        encounter_id=state["encounter_id"], npc_name=npc_name,
                        encounter_type="contest", result=result,
                        player_wins=state["player_wins"],
                        npc_wins=state["npc_wins"])

        self.in_social_encounter = False
        self.social_encounter_state = None

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
                            # Seed RECRUIT hint (only if not already shown)
                            if not self.state.get("_recruit_hint_shown"):
                                self.state["_recruit_hint_shown"] = True
                                self._seed_recruit_hint(npc.get("name"))
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

    def _seed_recruit_hint(self, npc_name=None):
        """World seed hints about RECRUIT after greeting an unrecruited NPC."""
        cap = self.skerry.population_cap()
        current = 2 + len(self.state.get("recruited_npcs", []))
        remaining = cap - current
        print()
        display.seed_speak(f"We have space for {remaining} more at the skerry.")
        them = npc_name if npc_name else "them"
        display.seed_speak(f"RECRUIT {them}, and I can bring them safely home with you.")

    def cmd_recruit(self, args):
        if self.state["current_phase"] == "steward":
            display.narrate("Everyone here has already chosen to stay.")
            return
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
        char = self.current_character()
        attempts = npc.get("recruit_attempts", 0)
        if attempts > 0:
            if not char.spend_fate_point():
                display.error(f"You need 1 fate point to try recruiting {npc['name']} again. (You have {char.fate_points} FP.)")
                return
            display.info(f"  Spent 1 fate point to retry. (Fate Points remaining: {char.fate_points})")

        # FATE roll — sets puzzle difficulty
        invoke_bonus = self._consume_invoke_bonus(skill="Rapport")
        rapport_val = char.get_skill("Rapport") + invoke_bonus
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
        found_affinity = []
        for a, source, aff in all_aspects:
            if query.lower() in a.lower():
                found = a
                found_source = source
                found_affinity = aff
                break

        if not found:
            display.error(f"No matching aspect for '{query}'.")
            display.info("  Available aspects:")
            for a, source, aff in all_aspects:
                if a not in self.scene_invoked_aspects:
                    print(f"    {display.aspect_text(a)} {display.DIM}({source}){display.RESET}")
            return

        # Check if already invoked this scene
        if found in self.scene_invoked_aspects:
            display.error(f"You've already invoked {display.aspect_text(found)} this scene.")
            remaining = [(a, s, aff) for a, s, aff in all_aspects if a not in self.scene_invoked_aspects]
            if remaining:
                display.info("  Still available:")
                for a, source, aff in remaining:
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
        if not self.state.get("_invoke_hint"):
            self.state["_invoke_hint"] = True

        source_type = "seed" if found_source == self.seed_name else None
        flavor = aspects.get_recruit_invoke_flavor(found, found_source, npc_name, source_type=source_type)
        display.narrate(f"  {flavor}")
        display.info(f"  (Fate Points remaining: {char.fate_points})")

        # Calculate affinity bonus for scaling effects
        bonus = aspects.calc_invoke_bonus(found_affinity, "Rapport")

        # Branch on effect
        if effect == "PUSH":
            old_threshold = state["threshold"]
            total_tiles = state["grid_size"] ** 2
            floor = int(total_tiles * 0.4)
            push_amount = 4 if bonus == 2 else 3
            state["threshold"] = max(floor, old_threshold - push_amount)
            display.info(f"  Threshold: {old_threshold} → {state['threshold']}")
        elif effect == "COUNTER":
            recruit.reset_lowest_counter(state)
        elif effect == "RESTORE":
            restore_count = 3 if bonus == 2 else 2
            recruit.restore_tiles(state, count=restore_count)

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

            # True perfect: every tile visited, zero eliminations
            total_tiles = state["grid_size"] ** 2
            all_visited = len(state["visited"]) == total_tiles
            is_flawless = all_visited and not state["eliminated"]

            if bonus_tiers >= 3 and not state["eliminated"] and not is_flawless:
                # Tier 3: exceptional rapport — happy mood + high loyalty
                # (Only show if NOT flawless — flawless subsumes this)
                base_loyalty = max(base_loyalty, 7)
                npc["mood"] = "happy"
                display.success(f"  Bonus: An exceptional conversation. {npc_name} is genuinely fired up.")

            if is_flawless:
                base_loyalty = min(10, base_loyalty + 3)
                npc["mood"] = "happy"
                backstory = npc.get("backstory", {})
                backstory_aspects = backstory.get("aspects", [])
                backstory_story = backstory.get("story", "")
                if backstory_aspects or backstory_story:
                    print()
                    display.success(f"  A flawless conversation. {npc_name} trusts you completely.")
                    if backstory_story:
                        display.narrate(f"  {npc_name} hesitates, then speaks quietly:")
                        display.npc_speak(npc_name, backstory_story)
                    if backstory_aspects:
                        # Reveal first backstory aspect
                        aspect_text = backstory_aspects[0]
                        npc.setdefault("aspects", {}).setdefault("other", [])
                        if aspect_text not in npc["aspects"]["other"]:
                            npc["aspects"]["other"].append(aspect_text)
                        npc.setdefault("revealed_backstory", [])
                        if aspect_text not in npc["revealed_backstory"]:
                            npc["revealed_backstory"].append(aspect_text)
                        display.success(f"  New aspect revealed: {display.aspect_text(aspect_text)}")
                else:
                    display.success(f"  A flawless conversation. {npc_name} trusts you completely.")

            npc["loyalty"] = base_loyalty
            display.info(f"  Score: {state['score']}/{state['threshold']} (+{over} over par, variant: {seed_hex})")

            flawless = all_visited and not state["eliminated"]
            self._log_event("recruit_success", comic_weight=7 if flawless else 5,
                            npc_name=npc_name, npc_id=npc_id,
                            loyalty=npc["loyalty"], score=state["score"],
                            threshold=state["threshold"], over_par=over,
                            flawless=flawless,
                            variant=seed_hex.lower())

            if not self.state.get("_recruit_settle_hint"):
                self.state["_recruit_settle_hint"] = True
                print()
                display.seed_speak("Good — now SETTLE them at a building to put them to work.")
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

    # ── Healing / Treatment ──────────────────────────────────────

    def _resolve_healer(self, healer_name):
        """Resolve a healer by name. Returns (display_name, lore_skill) or (None, None)."""
        char = self.current_character()
        phase = self.state.get("current_phase", "explorer")
        char_key = "explorer" if phase == "explorer" else "steward"

        # Check if it's the other player character
        other_key = "steward" if char_key == "explorer" else "explorer"
        other_name = self.state.get(f"{other_key}_name", "").lower()
        if healer_name == other_name:
            other_char_data = self.state.get(other_key, {})
            lore = other_char_data.get("skills", {}).get("Lore", 0)
            return self.state.get(f"{other_key}_name"), lore

        # Check NPCs at this location
        room = self.current_room()
        npc_pool = list(room.npcs or [])
        for npc_id, npc in self.npcs_db.items():
            if npc.get("following") and npc.get("location") == room.id and npc_id not in npc_pool:
                npc_pool.append(npc_id)
        npc_id, npc_data = self._find_entity(npc_pool, healer_name, self.npcs_db)
        if npc_data:
            return npc_data.get("name", npc_id), npc_data.get("skills", {}).get("Lore", 0)

        return None, None

    def _perform_treatment(self, patient, patient_key, treater_name, treater_lore):
        """Core healing logic: assess injuries, roll Lore, apply recovery + greying."""
        # Check what consequences need treatment
        consequences = []
        for sev in ["severe", "moderate", "mild"]:
            for i, entry in enumerate(patient.consequences.get(sev, [])):
                if entry.get("text"):
                    consequences.append((sev, i, entry))

        if not consequences:
            display.narrate(f"{patient.name} has no injuries to treat.")
            return

        # Show status and find treatable consequences
        display.header("Injuries")
        treatable = []
        meta = self.state.get("consequence_meta", {})
        zones_cleared = self.state.get("zones_cleared", 0)
        for sev, idx, entry_data in consequences:
            con = entry_data["text"]
            greyed = entry_data.get("greyed", False)
            eligible, reason = aspects.can_treat_consequence(self, patient_key, sev, idx)
            cure = aspects.get_cure_for_consequence(con)
            cure_name = self.items_db.get(cure, {}).get("name", cure) if cure else "unknown"

            meta_key = f"{patient_key}_{sev}_{idx}"
            meta_entry = meta.get(meta_key, {})
            recovery = meta_entry.get("recovery", 0)
            eff_sev = aspects._effective_severity(sev, recovery)
            recovering_suffix = "*" if recovery > 0 else ""
            bandaged_suffix = f" {display.DIM}(bandaged){display.RESET}" if greyed else ""

            # Calculate healing progress
            heal_rate = aspects.BANDAGED_HEAL_RATE if greyed else aspects.NATURAL_HEAL_RATE
            taken_at = meta_entry.get("taken_at", 0)
            clears_to_next = max(0, heal_rate - (zones_cleared - taken_at))

            if eff_sev is None:
                print(f"  {display.BOLD}{sev.capitalize()}{recovering_suffix}:{display.RESET} {con}{bandaged_suffix}")
                display.info(f"    Nearly healed.")
            elif eligible:
                has_cure = cure in patient.inventory
                difficulty = aspects.TREATMENT_DIFFICULTY[eff_sev]
                ladder = {0: "Mediocre", 1: "Average", 2: "Fair", 3: "Good", 4: "Great"}
                diff_label = ladder.get(difficulty, f"+{difficulty}")
                invoke_bonus = aspects.FRESH_INVOKE_BONUS.get(eff_sev, 0)
                print(f"  {display.BOLD}{sev.capitalize()}{recovering_suffix}:{display.RESET} {con}{bandaged_suffix}")
                print(f"    Healing naturally ({clears_to_next} clear{'s' if clears_to_next != 1 else ''} to next tier). Enemies exploit for +{invoke_bonus}.")
                if has_cure:
                    print(f"    Bandage: {display.item_name(cure_name)} {display.BRIGHT_GREEN}(have){display.RESET} + Lore check ({diff_label})")
                    display.info(f"    Bandaging speeds healing 3x and reduces enemy exploit bonus.")
                    treatable.append((sev, idx, con, cure, difficulty))
                else:
                    print(f"    Bandage: {display.item_name(cure_name)} {display.BRIGHT_RED}(missing){display.RESET} + Lore check ({diff_label})")
            else:
                print(f"  {display.BOLD}{sev.capitalize()}{recovering_suffix}:{display.RESET} {con}{bandaged_suffix}")
                if greyed and eff_sev:
                    greyed_bonus = aspects.GREYED_INVOKE_BONUS.get(eff_sev, 0)
                    bonus_str = f" Enemies exploit for +{greyed_bonus}." if greyed_bonus > 0 else ""
                    display.info(f"    Healing ({clears_to_next} clear{'s' if clears_to_next != 1 else ''} to next tier).{bonus_str}")
                elif reason:
                    display.info(f"    {reason}")

        if not treatable:
            if any(not entry_data.get("greyed") for _, _, entry_data in consequences):
                display.narrate("No consequences need bandaging right now.")
            return

        # Treat the most severe treatable consequence
        sev, treat_idx, con, cure, difficulty = treatable[0]

        # Consume cure item from patient's inventory
        patient.remove_from_inventory(cure)
        cure_name = self.items_db.get(cure, {}).get("name", cure)

        # Roll Lore check
        print()
        invoke_bonus = self._consume_invoke_bonus(skill="Lore")
        effective_lore = treater_lore + invoke_bonus

        # Apothecary room bonus
        room = self.current_room()
        apoth_bonus = 0
        if room and room.id == "skerry_apothecary":
            apoth_bonus = room.healing_level
            effective_lore += apoth_bonus

        # Cure item bonus (poultice gives +1)
        cure_item = self.items_db.get(cure, {})
        item_bonus = cure_item.get("treatment_bonus", 0)
        effective_lore += item_bonus

        # Compute effective severity for DC
        meta_key = f"{patient_key}_{sev}_{treat_idx}"
        meta_entry = meta.get(meta_key, {})
        recovery = meta_entry.get("recovery", 0)
        eff_sev = aspects._effective_severity(sev, recovery)

        # Hospital (tier 2) reduces severe-equivalent DC by 1
        effective_dc = difficulty
        if room and room.id == "skerry_apothecary" and room.healing_level >= 2 and eff_sev == "severe":
            effective_dc = max(0, difficulty - 1)

        label = f"Lore+{invoke_bonus}" if invoke_bonus else "Lore"
        display.narrate(f"{treater_name} prepares the {cure_name} and gets to work...")
        atk_dice = dice.roll_4df()
        total = sum(atk_dice) + effective_lore

        print(f"  {treater_name}: {dice.roll_description(atk_dice, effective_lore, label)}")
        if apoth_bonus:
            print(f"  {room.name} bonus: +{apoth_bonus}")
        if item_bonus:
            print(f"  {cure_item.get('name', cure)} bonus: +{item_bonus}")
        ladder = {0: "Mediocre", 1: "Average", 2: "Fair", 3: "Good", 4: "Great"}
        if effective_dc != difficulty:
            print(f"  Difficulty: {effective_dc} ({ladder.get(effective_dc, f'+{effective_dc}')}) (reduced from {difficulty})")
        else:
            print(f"  Difficulty: {effective_dc} ({ladder.get(effective_dc, f'+{effective_dc}')})")

        shifts = total - effective_dc

        if shifts >= 0:
            self._log_event("treatment_given", comic_weight=3,
                            target=patient.name, treater=treater_name,
                            severity=sev, consequence=con, success=True)
            meta = self.state.setdefault("consequence_meta", {})
            meta_entry = meta.setdefault(meta_key, {})
            meta_entry["recovery"] = recovery + 1
            meta_entry["taken_at"] = self.state.get("zones_cleared", 0)
            # Grey the wound so enemies can't exploit it
            patient.consequences[sev][treat_idx]["greyed"] = True
            next_eff = aspects._effective_severity(sev, recovery + 1)
            print()
            if next_eff == "mild":
                display.success(f"The treatment takes hold. The injury is stabilizing.")
                display.narrate(f"  {con} is now healing on its own.")
                display.info(f"  It will clear after a few zone clears.")
            elif next_eff is None:
                patient.heal_consequence(sev, treat_idx)
                meta.pop(meta_key, None)
                aspects._reindex_meta(meta, patient_key, sev, treat_idx)
                display.success(f"The treatment takes hold. {con} has fully healed.")
            else:
                display.success(f"The treatment takes hold. The injury is improving.")
                display.narrate(f"  {con} is recovering (effective severity: {next_eff}).")
                display.info(f"  Will need another round of treatment to heal further.")
        else:
            print()
            display.warning(f"The treatment doesn't take. The {cure_name} is used up, but the injury persists.")
            display.info(f"  (Failed by {abs(shifts)} — try again with better aspects or a more skilled healer.)")

    def cmd_heal(self, args):
        """HEAL [<name>] — treat your own injuries, or heal someone else."""
        char = self.current_character()
        phase = self.state.get("current_phase", "explorer")
        char_key = "explorer" if phase == "explorer" else "steward"

        if not args:
            # HEAL — self-heal
            self._perform_treatment(char, char_key, char.name, char.get_skill("Lore"))
            return

        # HEAL <name> — heal another character
        target_name = " ".join(args).lower()

        # Check if target is the other player character
        other_key = "steward" if char_key == "explorer" else "explorer"
        other_name = self.state.get(f"{other_key}_name", "").lower()
        if target_name == other_name:
            other_char = self.steward if other_key == "steward" else self.explorer
            self._perform_treatment(other_char, other_key, char.name, char.get_skill("Lore"))
            return

        # Check NPCs/followers at this location
        room = self.current_room()
        npc_pool = list(room.npcs or [])
        for npc_id, npc in self.npcs_db.items():
            if npc.get("following") and npc.get("location") == room.id and npc_id not in npc_pool:
                npc_pool.append(npc_id)
        npc_id, npc_data = self._find_entity(npc_pool, target_name, self.npcs_db)
        if npc_data:
            display.narrate(f"NPCs don't take consequences the way you do. {npc_data['name']} appreciates the thought.")
            return

        display.error(f"There's nobody called '{target_name}' here to heal.")

    def cmd_request(self, args):
        """REQUEST HEAL FROM <name> — ask an NPC to treat your injuries.

        Also accepts REQUEST TREATMENT FROM <name> for backward compatibility.
        """
        if not args:
            display.error("Request what? Usage: REQUEST HEAL FROM <name>")
            return

        raw = " ".join(args).lower()

        # Accept both "treatment" and "heal" as the noun
        if raw.startswith("treatment"):
            remainder = raw[len("treatment"):].strip()
        elif raw.startswith("heal"):
            remainder = raw[len("heal"):].strip()
        else:
            display.error("Request what? Usage: REQUEST HEAL FROM <name>")
            return

        # Bare REQUEST TREATMENT / REQUEST HEAL (no FROM) → redirect
        if not remainder.startswith("from "):
            display.narrate("To heal yourself, use HEAL. To ask someone, use REQUEST HEAL FROM <name>.")
            return

        healer_name = remainder[5:].strip()
        if not healer_name:
            display.error("Request healing from whom? Usage: REQUEST HEAL FROM <name>")
            return

        char = self.current_character()
        phase = self.state.get("current_phase", "explorer")
        char_key = "explorer" if phase == "explorer" else "steward"

        resolved_name, treater_lore = self._resolve_healer(healer_name)
        if resolved_name is None:
            display.error(f"There's nobody called '{healer_name}' here to treat you.")
            return

        self._perform_treatment(char, char_key, resolved_name, treater_lore)
