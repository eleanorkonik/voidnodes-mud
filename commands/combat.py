"""Combat domain — attack, defend, exploit, invoke (combat), concede, retreat, enemy turns, compels."""

import random

from engine import display, dice, aspects


class CombatMixin:
    """Mixin providing combat commands and helpers for the Game class."""

    def cmd_attack(self, args):
        if self.state["current_phase"] == "steward":
            self._wrong_phase_narrate("explorer", "combat")
            return
        if not args and not self.in_combat:
            display.error("Attack what?")
            return

        room = self.current_room()

        if not self.in_combat:
            target = " ".join(args).lower()
            enemy_id, enemy_data = self._find_entity(room.enemies, target, self.enemies_db)
            if not enemy_data:
                # Check if attacking Lira after she warned you
                quest = self.state.get("quests", {}).get("verdant_bloom", {})
                if target == "lira" and quest.get("lira_warned") and not quest.get("lira_defeated"):
                    lira = self.npcs_db.get("lira")
                    if lira and not lira.get("recruited"):
                        self._lira_attacks(room)
                        return  # combat started — player acts next turn
                display.error(f"There's nothing called '{target}' to attack here.")
                return
            self._start_combat(enemy_id)
        elif args:
            # Already in combat — check if re-targeting
            target = " ".join(args).lower()
            enemy_id, enemy_data = self._find_entity(room.enemies, target, self.enemies_db)
            if enemy_data:
                self.combat_target = enemy_id

        enemy_data = self.enemies_db.get(self.combat_target)
        if not enemy_data:
            return

        # Calculate bonus from pending invoke, exploit advantages, and boost
        bonus = self._consume_invoke_bonus()
        used_aspect = None
        if self.exploit_advantages:
            # Auto-consume one exploit advantage
            aspect_name = next(iter(self.exploit_advantages))
            self.exploit_advantages[aspect_name] -= 1
            if self.exploit_advantages[aspect_name] <= 0:
                del self.exploit_advantages[aspect_name]
            bonus += 2
            used_aspect = aspect_name

        if self.combat_boost > 0:
            bonus += self.combat_boost
            self.combat_boost = 0

        atk_skill_val = self.explorer.get_skill("Fight") + bonus
        def_skill_val = enemy_data["skills"].get("Fight", 1)

        atk_total, def_total, shifts, atk_dice, def_dice = dice.opposed_roll(atk_skill_val, def_skill_val)

        display.header(f"Combat: {self.explorer.name} vs {enemy_data['name']}")
        if used_aspect:
            print(f"  {display.DIM}(Exploit advantage: {display.aspect_text(used_aspect)}){display.RESET}")
        skill_label = f"Fight+{bonus}" if bonus else "Fight"
        base_fight = self.explorer.get_skill("Fight")
        print(f"  {self.explorer.name}: {dice.roll_description(atk_dice, base_fight + bonus, skill_label)}")
        print(f"  {enemy_data['name']}: {dice.roll_description(def_dice, def_skill_val, 'Fight')}")

        if shifts > 0:
            display.success(f"  You hit for {shifts} shifts!")
            if self._apply_enemy_damage(enemy_data, self.combat_target, shifts, room):
                return
        elif shifts == 0:
            display.narrate(f"  A draw — neither side gains ground.")
        else:
            display.narrate(f"  You miss. {enemy_data['name']} deflects your strike.")

        # Enemy turn
        self._enemy_turn()

    def cmd_defend(self, args):
        if not self.in_combat:
            display.error("You're not in combat.")
            return

        self.defending = True
        display.narrate("You brace yourself, watching for openings. (+2 defense this exchange)")

        # Enemy turn (with the +2 defense active)
        self._enemy_turn()
        self.defending = False

    def cmd_exploit(self, args):
        """EXPLOIT <aspect> — Create an Advantage by exploiting an aspect.

        Roll Notice vs difficulty to set up a tactical advantage on the aspect.
        Success: 1 advantage. Success with style (3+): 2 advantages.
        Tie: boost (+2 one-use). Fail: wasted turn, enemy still attacks.
        """
        if not args:
            display.error("Exploit what? EXPLOIT <aspect> to create a tactical advantage.")
            return

        if not self.in_combat:
            display.error("You can only exploit aspects during combat.")
            return

        aspect_name = " ".join(args)
        enemy_data = self.enemies_db.get(self.combat_target, {})

        # Gather all available aspects
        all_aspects = []
        room = self.current_room()
        if room:
            all_aspects.extend(room.aspects)
            zone_aspect = self._get_zone_aspect(room)
            if zone_aspect:
                all_aspects.append(zone_aspect)
        all_aspects.extend(enemy_data.get("aspects", []))
        char = self.current_character()
        all_aspects.extend(char.get_all_aspects())

        # Fuzzy match
        found = None
        for a in all_aspects:
            if aspect_name.lower() in a.lower():
                found = a
                break

        if not found:
            display.error(f"No matching aspect found for '{aspect_name}'.")
            display.info("Available aspects:")
            for a in all_aspects:
                print(f"  {display.aspect_text(a)}")
            return

        # Determine difficulty: enemy aspects use enemy Notice, room aspects use flat 1
        is_enemy_aspect = found in enemy_data.get("aspects", [])
        if is_enemy_aspect:
            difficulty = enemy_data["skills"].get("Notice", 1)
        else:
            difficulty = 1

        notice_val = self.explorer.get_skill("Notice")
        total, shifts, dice_result = dice.skill_check(notice_val, difficulty)

        display.header(f"Exploit: {found}")
        diff_label = f"vs {enemy_data['name']} Notice" if is_enemy_aspect else "vs difficulty 1"
        print(f"  {self.explorer.name}: {dice.roll_description(dice_result, notice_val, 'Notice')} ({diff_label})")

        if shifts >= 3:
            # Success with style — 2 advantages
            self.exploit_advantages[found] = self.exploit_advantages.get(found, 0) + 2
            display.success(f"  Brilliant! You spot exactly how to use {display.aspect_text(found)}.")
            display.info(f"  (2 exploit advantages on {found} — free +2 each on your next attacks)")
            if not self.state.get("tutorial_complete"):
                self.state["tutorial_exploit_done"] = True
        elif shifts >= 0:
            # Success — 1 advantage
            self.exploit_advantages[found] = self.exploit_advantages.get(found, 0) + 1
            display.success(f"  You find a way to use {display.aspect_text(found)} to your advantage.")
            display.info(f"  (Exploit advantage on {found} — free +2 on your next attack)")
            if not self.state.get("tutorial_complete"):
                self.state["tutorial_exploit_done"] = True
        elif shifts == -1:
            # Tie — boost
            self.combat_boost += 2
            display.narrate(f"  Not quite — but you gain a momentary edge.")
            display.info(f"  (Boost: +2 on your next action)")
        else:
            # Fail
            display.narrate(f"  You try to exploit {display.aspect_text(found)} but can't find an opening.")

        # Enemy turn
        self._enemy_turn()

    def cmd_invoke(self, args):
        """INVOKE [aspect] [ATTACK|DEFEND|SETUP] — Spend a fate point to invoke an aspect."""
        # In combat — full combat invoke with effects
        if self.in_combat:
            self._combat_invoke(args)
            return

        # Outside combat/recruitment — floating invoke for next skill check
        self._general_invoke(args)

    def _general_invoke(self, args):
        """Invoke an aspect outside combat/recruitment. Stores a floating +2 for the next roll."""
        char = self.current_character()
        all_aspects = aspects.collect_invokable_aspects(self, context="combat")

        if not args:
            # Show available aspects with used ones dimmed
            print(f"\n{display.BOLD}{display.BRIGHT_CYAN}═══ Invoke an Aspect ═══{display.RESET}  (1 FP — you have {char.fate_points})")
            print()
            available = [(a, s) for a, s in all_aspects if a not in self.scene_invoked_aspects]
            used = [(a, s) for a, s in all_aspects if a in self.scene_invoked_aspects]
            if available:
                print("  Available:")
                for a, source in available:
                    print(f"    {display.aspect_text(a)} {display.DIM}({source}){display.RESET}")
            else:
                print(f"  {display.DIM}No aspects remaining to invoke.{display.RESET}")
            if used:
                print()
                print("  Already invoked:")
                for a, source in used:
                    print(f"    {display.DIM}\u2717 {a} ({source}){display.RESET}")
            print()
            display.info("  INVOKE <aspect> to gain +2 on your next skill check.")
            if self.pending_invoke_bonus > 0:
                display.info(f"  (Already invoking: {display.aspect_text(self.pending_invoke_aspect)})")
            return

        raw = " ".join(args)
        found = None
        for a, source in all_aspects:
            if raw.lower() in a.lower():
                found = a
                break

        if not found:
            display.error(f"No matching aspect for '{raw}'.")
            display.info("Available aspects:")
            for a, source in all_aspects:
                if a not in self.scene_invoked_aspects:
                    print(f"  {display.aspect_text(a)} {display.DIM}({source}){display.RESET}")
            return

        # Scene-used check
        if found in self.scene_invoked_aspects:
            display.error(f"You've already invoked {display.aspect_text(found)} this scene.")
            remaining = [(a, s) for a, s in all_aspects if a not in self.scene_invoked_aspects]
            if remaining:
                display.info("  Still available:")
                for a, source in remaining:
                    print(f"    {display.aspect_text(a)} {display.DIM}({source}){display.RESET}")
            return

        if not char.spend_fate_point():
            display.error("No fate points to spend!")
            return

        self.scene_invoked_aspects.add(found)
        self.pending_invoke_bonus = 2
        self.pending_invoke_aspect = found
        if not self.state.get("tutorial_complete"):
            self.state["tutorial_invoke_done"] = True

        display.success(f"You invoke {display.aspect_text(found)} — +2 on your next action.")
        self._log_event("aspect_invoked", comic_weight=2,
                        aspect=found, effect="general", context="exploration")
        display.info(f"  (Fate Points remaining: {char.fate_points})")

    def _combat_invoke(self, args):
        """Handle INVOKE during combat — choose-your-effect system."""
        char = self.current_character()
        all_aspects = aspects.collect_invokable_aspects(self, context="combat")

        # No args — show the invoke menu
        if not args:
            self._display_invoke_menu(char, all_aspects, "combat")
            return

        # Parse args: last word might be an effect keyword
        raw = " ".join(args)
        effect = None
        for keyword in aspects.COMBAT_EFFECTS:
            if raw.upper().endswith(" " + keyword):
                effect = keyword
                raw = raw[:-(len(keyword) + 1)].strip()
                break

        # Fuzzy-match the aspect
        aspect_name = raw
        found = None
        for a, source in all_aspects:
            if aspect_name.lower() in a.lower():
                found = a
                break

        if not found:
            display.error(f"No matching aspect found for '{aspect_name}'.")
            display.info("Available aspects:")
            for a, source in all_aspects:
                if a not in self.scene_invoked_aspects:
                    print(f"  {display.aspect_text(a)} {display.DIM}({source}){display.RESET}")
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
            effect = "ATTACK"

        # Spend fate point
        if not char.spend_fate_point():
            display.error("No fate points to spend!")
            return

        self.scene_invoked_aspects.add(found)
        if not self.state.get("tutorial_complete"):
            self.state["tutorial_invoke_done"] = True

        display.success(f"You invoke {display.aspect_text(found)} — {aspects.COMBAT_EFFECTS[effect]['desc']}!")
        display.info(f"  (Fate Points remaining: {char.fate_points})")
        self._log_event("aspect_invoked", comic_weight=2,
                        aspect=found, effect=effect, context="combat")

        # Branch on effect
        if effect == "ATTACK":
            self._invoke_attack(found)
        elif effect == "DEFEND":
            self._invoke_defend(found)
        elif effect == "SETUP":
            self._invoke_setup(found)

    def _display_invoke_menu(self, char, all_aspects, context):
        """Show available aspects and effects for invocation."""
        print(f"\n{display.BOLD}{display.BRIGHT_CYAN}═══ Invoke an Aspect ═══{display.RESET}  (1 FP each — you have {char.fate_points})")
        print()

        invoked = self.scene_invoked_aspects

        available = [(a, s) for a, s in all_aspects if a not in invoked]
        spent = [(a, s) for a, s in all_aspects if a in invoked]

        if available:
            print("  Available:")
            for a, source in available:
                print(f"    {display.aspect_text(a)} {display.DIM}({source}){display.RESET}")
        else:
            print(f"  {display.DIM}No aspects remaining to invoke.{display.RESET}")

        if spent:
            print()
            print("  Already invoked:")
            for a, source in spent:
                print(f"    {display.DIM}\u2717 {a} ({source}){display.RESET}")

        print()
        if context == "combat":
            effect_parts = []
            for keyword, info in aspects.COMBAT_EFFECTS.items():
                effect_parts.append(f"{display.BOLD}{keyword}{display.RESET} ({info['desc']})")
            print(f"  Effects:  {'  \u00b7  '.join(effect_parts)}")
            print()
            print(f"  {display.DIM}INVOKE <aspect> [ATTACK|DEFEND|SETUP]{display.RESET}")
        elif context == "recruit":
            effect_parts = []
            for keyword, info in aspects.RECRUIT_EFFECTS.items():
                effect_parts.append(f"{display.BOLD}{keyword}{display.RESET} ({info['desc']})")
            print(f"  Effects:  {'  \u00b7  '.join(effect_parts)}")
            print()
            print(f"  {display.DIM}INVOKE <aspect> [PUSH|COUNTER|RESTORE]{display.RESET}")
        else:
            # Social encounters (challenge/contest): invoke is just +2 to next roll
            print(f"  Effect: {display.BOLD}+2{display.RESET} on your next roll")
            print()
            print(f"  {display.DIM}INVOKE <aspect>{display.RESET}")
        print()

    def _invoke_attack(self, invoked_aspect):
        """INVOKE for +2 attack — roll attack with bonus."""
        enemy_data = self.enemies_db.get(self.combat_target, {})
        if not enemy_data:
            return
        room = self.current_room()

        bonus = 2  # invoke bonus
        used_free = None
        if self.exploit_advantages:
            free_aspect = next(iter(self.exploit_advantages))
            self.exploit_advantages[free_aspect] -= 1
            if self.exploit_advantages[free_aspect] <= 0:
                del self.exploit_advantages[free_aspect]
            bonus += 2
            used_free = free_aspect

        if self.combat_boost > 0:
            bonus += self.combat_boost
            self.combat_boost = 0

        atk_skill_val = self.explorer.get_skill("Fight") + bonus
        def_skill_val = enemy_data["skills"].get("Fight", 1)

        atk_total, def_total, shifts, atk_dice, def_dice = dice.opposed_roll(atk_skill_val, def_skill_val)

        base_fight = self.explorer.get_skill("Fight")
        skill_label = f"Fight+{bonus}"
        if used_free:
            print(f"  {display.DIM}(Also using exploit advantage: {display.aspect_text(used_free)}){display.RESET}")
        print(f"  {self.explorer.name}: {dice.roll_description(atk_dice, base_fight + bonus, skill_label)}")
        print(f"  {enemy_data['name']}: {dice.roll_description(def_dice, def_skill_val, 'Fight')}")

        if shifts > 0:
            display.success(f"  Empowered strike for {shifts} shifts!")
            if self._apply_enemy_damage(enemy_data, self.combat_target, shifts, room):
                return
        elif shifts == 0:
            display.narrate("  A draw despite the invocation — neither side gains ground.")
        else:
            display.narrate(f"  Even with the invoke, {enemy_data['name']} deflects your strike.")

        # Enemy turn
        self._enemy_turn()

    def _invoke_defend(self, invoked_aspect):
        """INVOKE for +2 defense — set defending and pass to enemy turn."""
        self.defending = True
        display.narrate(f"  You brace yourself, drawing on {display.aspect_text(invoked_aspect)}.")
        display.info(f"  (+2 defense until your next action)")
        self._enemy_turn()

    def _invoke_setup(self, invoked_aspect):
        """INVOKE SETUP — gain an exploit advantage on a random enemy aspect."""
        enemy_data = self.enemies_db.get(self.combat_target, {})
        enemy_aspects = enemy_data.get("aspects", [])
        if enemy_aspects:
            target_aspect = random.choice(enemy_aspects)
            self.exploit_advantages[target_aspect] = self.exploit_advantages.get(target_aspect, 0) + 1
            display.narrate(f"  You spot an opening in {display.aspect_text(target_aspect)}.")
            display.info(f"  (Exploit advantage gained — free +2 on your next attack)")
        else:
            # No enemy aspects — grant a generic boost instead
            self.combat_boost += 2
            display.narrate(f"  You study your opponent and find an opening.")
            display.info(f"  (Boost: +2 on your next action)")
        self._enemy_turn()

    def cmd_concede(self, args):
        """CONCEDE — Surrender combat. Gain 1 FP + 1 per consequence taken this fight."""
        if not self.in_combat:
            display.error("You're not in combat.")
            return

        enemy = self.enemies_db.get(self.combat_target, {})
        cons_taken = self.combat_consequences_taken
        fp_gain = 1 + cons_taken
        self._end_combat()

        for _ in range(fp_gain):
            self.explorer.gain_fate_point()

        display.narrate(f"You concede the fight against {enemy.get('name', 'the enemy')}.")
        display.narrate("You back away carefully, ceding ground.")
        display.success(f"+{fp_gain} Fate Point{'s' if fp_gain > 1 else ''} for conceding.")
        self._log_event("combat_concede", comic_weight=3,
                        target=enemy.get("name", "unknown"),
                        fp_gained=fp_gain)
        if cons_taken > 0:
            display.info(f"  (1 base + {cons_taken} for consequences taken)")
        display.narrate("The enemy lets you go — for now.")

    def cmd_retreat(self, args):
        if self.state["current_phase"] == "steward":
            self._wrong_phase_narrate("explorer", "void")
            return
        if self.in_combat:
            display.warning(f"Emergency retreat! {self.seed_name} pulls you back to safety.")
            self._seed_extraction()
        else:
            # FWOOM back to skerry
            from_room = self.current_room()
            to_room = self.rooms.get("skerry_landing")
            self.state["explorer_location"] = "skerry_landing"
            self._move_followers("skerry_landing")
            if from_room and to_room and from_room.zone != "skerry":
                self._narrate_void_crossing(from_room, to_room)
            display.display_room(to_room, self.game_context())

    def _start_combat(self, enemy_id):
        """Initialize combat state for a new encounter."""
        self.in_combat = True
        self.combat_target = enemy_id
        self.defending = False
        self.exploit_advantages = {}
        self.combat_boost = 0
        self.combat_consequences_taken = 0
        self.enemy_compel_boost = 0
        self.compel_triggered = False
        self.in_compel = False
        self.compel_data = None
        enemy_data = self.enemies_db.get(enemy_id, {})
        self._log_event("combat_start", comic_weight=2,
                        target=enemy_data.get("name", enemy_id),
                        target_id=enemy_id)

    def _end_combat(self):
        """Clean up after combat ends (victory, concede, or extraction)."""
        self.in_combat = False
        self.combat_target = None
        self.defending = False
        self.exploit_advantages = {}
        self.combat_boost = 0
        self.combat_consequences_taken = 0
        self.enemy_compel_boost = 0
        self.compel_triggered = False
        self.in_compel = False
        self.compel_data = None
        self.explorer.clear_stress()

    def _enemy_turn(self):
        """Enemy takes an independent attack action."""
        if not self.in_combat or not self.combat_target:
            return

        enemy_data = self.enemies_db.get(self.combat_target)
        if not enemy_data:
            return

        # Enemy attacks with Fight vs player Fight (+2 if defending)
        enemy_fight = enemy_data["skills"].get("Fight", 1)
        # Apply compel boost if enemy earned one
        if self.enemy_compel_boost > 0:
            enemy_fight += self.enemy_compel_boost
            self.enemy_compel_boost = 0
        player_fight = self.explorer.get_skill("Fight")
        defend_bonus = 2 if self.defending else 0
        player_defense = player_fight + defend_bonus

        atk_total, def_total, shifts, atk_dice, def_dice = dice.opposed_roll(enemy_fight, player_defense)

        print()
        defense_label = f"Fight+2" if self.defending else "Fight"
        print(f"  {display.DIM}{enemy_data['name']} strikes back!{display.RESET}")
        print(f"  {enemy_data['name']}: {dice.roll_description(atk_dice, enemy_fight, 'Fight')}")
        print(f"  {self.explorer.name}: {dice.roll_description(def_dice, player_defense, defense_label)}")

        if shifts > 0:
            display.warning(f"  {enemy_data['name']} hits you for {shifts} shifts!")
            taken_out = self.explorer.apply_damage(shifts)
            if taken_out:
                display.error(f"\n  ═══ {self.explorer.name.upper()} IS TAKEN OUT! ═══")
                display.narrate(f"  {self.seed_name} reaches across the void...")
                self._log_event("combat_defeat", comic_weight=4,
                                target=enemy_data.get("name", "unknown"),
                                details="Taken out by enemy attack")
                self._seed_extraction()
                return
            # Track and display consequences
            took_consequence = False
            for sev in ["mild", "moderate", "severe"]:
                if self.explorer.consequences.get(sev) == "Pending":
                    self.combat_consequences_taken += 1
                    took_consequence = True
                    # Name the consequence based on enemy
                    con_text = f"Wounded by {enemy_data['name']}"
                    self.explorer.consequences[sev] = con_text
                    display.warning(f"  You take a {sev} consequence: {con_text}")
                    self._record_consequence("explorer", sev, con_text)
                    self._log_event("consequence_taken", comic_weight=4,
                                    severity=sev, description=con_text,
                                    source=enemy_data.get("name", "unknown"))
            if took_consequence and not self.state.get("tutorial_consequence_done"):
                self.state["tutorial_consequence_done"] = True
                print()
                display.seed_speak("That's a consequence — a wound that lasts beyond this fight.")
                display.seed_speak("Stress clears when combat ends, but consequences stay.")
                display.seed_speak("Mild heals on its own after a few zone clears.")
                display.seed_speak("Moderate and severe need a cure item (like bandages) and a")
                display.seed_speak("Lore check — type REQUEST TREATMENT when you have one.")
                display.seed_speak("Building an apothecary later will make treatment easier.")
                display.seed_speak("You can also CONCEDE to end a fight on your terms — you'll")
                display.seed_speak("get a Fate Point for each consequence you took.")
            # Show current stress
            stress_str = "".join("[X]" if s else "[ ]" for s in self.explorer.stress)
            display.info(f"  Stress: {stress_str}")
            if not self.state.get("tutorial_stress_done"):
                self.state["tutorial_stress_done"] = True
                print()
                display.seed_speak("You've been hit. Those boxes are stress — they absorb damage.")
                display.seed_speak("A 1-shift hit fills the first box, 2-shift the second, etc.")
                display.seed_speak("Stress clears automatically when combat ends — no treatment needed.")
                display.seed_speak("If you can't absorb a hit with stress, you take a consequence")
                display.seed_speak("instead — a lasting wound. DEFEND to brace for incoming hits,")
                display.seed_speak("EXPLOIT to find weaknesses, or CONCEDE to leave on your terms.")
        elif shifts == 0:
            display.narrate(f"  {enemy_data['name']} lunges but you deflect it perfectly.")
        else:
            display.narrate(f"  {enemy_data['name']} swings wide. You sidestep easily.")

        # Reset defending after enemy attack resolves
        self.defending = False

        # Check for compel after enemy turn
        self._check_compel()

    def _check_compel(self):
        """Maybe trigger a compel after an enemy turn. At most once per combat."""
        if self.compel_triggered or not self.in_combat:
            return
        if random.random() >= 0.25:
            return
        compel = aspects.check_compel(self)
        if not compel:
            return
        self.compel_triggered = True
        self._present_compel(compel)

    def _present_compel(self, compel, environmental=False):
        """Display a compel prompt to the player."""
        char = self.current_character()
        self.in_compel = True
        self.compel_data = compel
        self.compel_data["_environmental"] = environmental
        print()
        if environmental:
            print(f"{display.BOLD}{display.BRIGHT_RED}═══ Hazard ═══{display.RESET}")
            print(f"  {display.aspect_text(compel['aspect'])} —")
        else:
            print(f"{display.BOLD}{display.BRIGHT_YELLOW}═══ Compel ═══{display.RESET}")
            print(f"  Your {display.aspect_text(compel['aspect'])} —")
        print(f"  {compel['text']}")
        print()
        if environmental:
            print(f"  {display.BRIGHT_GREEN}ACCEPT{display.RESET}: Push through. Take {compel.get('stress', 1)} stress.")
            if char.fate_points > 0:
                print(f"  {display.BRIGHT_RED}REFUSE{display.RESET}: Spend 1 FP to find a safer path. (You have {char.fate_points} FP)")
            else:
                print(f"  {display.DIM}REFUSE: Not available — no fate points.{display.RESET}")
        else:
            print(f"  {display.BRIGHT_GREEN}ACCEPT{display.RESET}: Suffer the effect. Gain 1 FP.")
            if char.fate_points > 0:
                print(f"  {display.BRIGHT_RED}REFUSE{display.RESET}: Spend 1 FP to resist. (You have {char.fate_points} FP)")
            else:
                print(f"  {display.DIM}REFUSE: Not available — no fate points to resist.{display.RESET}")
        print()

    def _handle_compel_input(self, raw):
        """Handle ACCEPT/REFUSE input during a compel."""
        cmd = raw.lower().strip()
        char = self.current_character()
        environmental = self.compel_data.get("_environmental", False)

        if cmd in ("accept", "a", "yes"):
            self.in_compel = False
            compel = self.compel_data
            self.compel_data = None

            # Mark the compelled aspect as used for the scene
            self.scene_invoked_aspects.add(compel["aspect"])

            if environmental:
                # Environmental: take stress, no FP gain
                display.narrate(compel["accept_text"])
                stress_amount = compel.get("stress", 1)
                taken_out = char.apply_damage(stress_amount)
                stress_str = "".join("[X]" if s else "[ ]" for s in char.stress)
                display.info(f"  ({stress_amount} stress — {stress_str})")
                if taken_out:
                    display.error(f"\n  ═══ {self.explorer.name.upper()} IS TAKEN OUT! ═══")
                    display.narrate(f"  {self.seed_name} reaches across the void...")
                    self._seed_extraction()
                    return
            else:
                # Character compel: suffer effect, gain FP
                effect = compel["accept_effect"]
                messages = aspects.resolve_compel_accept(self, compel)
                for msg in messages:
                    if msg == "TAKEN_OUT":
                        display.error(f"\n  ═══ {self.explorer.name.upper()} IS TAKEN OUT! ═══")
                        display.narrate(f"  {self.seed_name} reaches across the void...")
                        self._seed_extraction()
                        return
                    else:
                        display.narrate(msg)
                # Lose turn — enemy gets a free attack
                if effect == "lose_turn":
                    self._enemy_turn()

        elif cmd in ("refuse", "r", "no"):
            if char.fate_points <= 0:
                display.error("You can't refuse — no fate points.")
                display.info("  Type ACCEPT.")
                return

            self.in_compel = False
            compel = self.compel_data
            self.compel_data = None

            # Mark the compelled aspect as used for the scene
            self.scene_invoked_aspects.add(compel["aspect"])

            if environmental:
                # Environmental: spend FP, find a safer path
                char.spend_fate_point()
                display.narrate("You spot a safer route and duck through, avoiding the worst of it.")
                display.info(f"  (-1 Fate Point — you now have {char.fate_points})")
            else:
                messages = aspects.resolve_compel_refuse(self, compel)
                for msg in messages:
                    display.narrate(msg)

        else:
            display.error("Type ACCEPT or REFUSE.")

    def _apply_enemy_damage(self, enemy_data, enemy_id, shifts, room):
        """Apply damage to an enemy. Returns True if enemy was defeated."""
        enemy_stress = enemy_data.get("stress", [False, False])
        enemy_cons = enemy_data.get("consequences", {"mild": None})

        absorbed = False
        for i in range(len(enemy_stress)):
            if not enemy_stress[i] and (i + 1) >= shifts:
                enemy_stress[i] = True
                absorbed = True
                display.narrate(f"  {enemy_data['name']} absorbs the hit.")
                break

        if not absorbed:
            con_values = {"mild": 2, "moderate": 4, "severe": 6}
            for sev in ["mild", "moderate", "severe"]:
                if sev in enemy_cons and enemy_cons[sev] is None and con_values.get(sev, 0) >= shifts:
                    enemy_cons[sev] = "Wounded"
                    absorbed = True
                    display.warning(f"  {enemy_data['name']} takes a {sev} consequence!")
                    break

        if not absorbed:
            # Enemy defeated!
            room.remove_enemy(enemy_id)
            self._end_combat()

            # Special handling for NPC combatants
            if enemy_data.get("_is_npc"):
                if enemy_id == "lira_hostile":
                    self._handle_lira_defeat()
                return True

            display.success(f"\n  {enemy_data['name']} is defeated!")
            loot = enemy_data.get("loot", [])
            dropped = None
            if loot:
                dropped = random.choice(loot)
                room.add_item(dropped)
                item_info = self.items_db.get(dropped, {})
                display.success(f"  It drops: {item_info.get('name', dropped)}")
            # Drop remnants if this enemy has them
            remnants_id = f"{enemy_id}_remnants"
            if remnants_id in self.items_db:
                room.add_item(remnants_id)
                remnants_info = self.items_db[remnants_id]
                display.narrate(f"  {remnants_info.get('name', 'Remains')} left behind.")

            self.explorer.gain_fate_point()
            display.info(f"  (+1 Fate Point for victory)")
            self._log_event("combat_victory", comic_weight=3,
                            target=enemy_data.get("name", enemy_id),
                            target_id=enemy_id,
                            loot=dropped)
            if not self.state.get("tutorial_complete"):
                self.state["tutorial_combat_done"] = True
            return True

        enemy_data["stress"] = enemy_stress
        enemy_data["consequences"] = enemy_cons
        return False

    def _seed_extraction(self):
        """Handle world seed emergency extraction."""
        cost = self.seed.extraction_cost(self.state["extractions"])

        if self.seed.spend_motes(cost):
            self.state["extractions"] += 1
            self._end_combat()
            # Reset consequences to None only if pending
            for sev in list(self.explorer.consequences.keys()):
                if self.explorer.consequences[sev] == "Pending":
                    self.explorer.consequences[sev] = None

            self.state["explorer_location"] = "skerry_landing"
            self._move_followers("skerry_landing")

            # Extraction is a scene boundary — new day begins
            self.state["day"] += 1
            self._day_transition()

            display.warning(f"\n  {self.seed_name} spends {cost} motes to yank you back to the skerry!")
            display.display_seed(self.seed.to_dict(), name=self.seed_name)
            self._log_event("seed_extraction", comic_weight=4,
                            motes_spent=cost, motes_remaining=self.seed.motes)

            if not self.seed.alive:
                display.error(f"\n  ═══ {self.seed_name.upper()}'S MOTES ARE DEPLETED ═══")
                display.error("  The world seed flickers and goes dark.")
                display.error(f"  Without {self.seed_name}, the skerry crumbles into the void.")
                display.error("  ═══ GAME OVER ═══\n")
                self.running = False
            else:
                display.narrate(f"You collapse on the landing pad, gasping. {self.seed_name} saved you — but at a cost.")
                display.seed_speak(self.seed.communicate(self.seed_name))
        else:
            display.error(f"  {self.seed_name} doesn't have enough motes ({cost} needed, {self.seed.motes} available)!")
            display.error(f"\n  ═══ {self.seed_name.upper()} CANNOT SAVE YOU ═══")
            display.error("  ═══ GAME OVER ═══\n")
            self.running = False
