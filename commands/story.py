"""Story domain — quest hints, Lira interactions, day transitions, phase transitions."""

import random

from engine import display, dice, subtasks, farming


class StoryMixin:
    """Mixin providing story scripting and event methods for the Game class."""

    def _quest_room_hints(self, room):
        """Lira gives contextual advice at quest locations if she's following."""
        lira = self.npcs_db.get("lira")
        if not lira or not lira.get("following"):
            return
        quest = self.state.get("quests", {}).get("verdant_bloom", {})
        if quest.get("status") != "active":
            return

        inv = self.explorer.inventory

        if room.id == "vw_root_wall" and not quest.get("roots_cleared"):
            print()
            if not quest.get("roots_weakened"):
                if "resin" in inv:
                    print(f"  {display.npc_name('Lira')}: \"Those roots are too damp to burn. But resin's")
                    print(f"  flammable — coat them and a torch would catch. USE RESIN ON ROOTS.\"")
                elif "basic_tools" in inv:
                    print(f"  {display.npc_name('Lira')}: \"There's a Growth Controller west of here.")
                    print(f"  Go WEST and USE BASIC TOOLS ON CONSOLE.\"")
                else:
                    print(f"  {display.npc_name('Lira')}: \"We need to get past these roots. The Growth")
                    print(f"  Controller is west of here — GO WEST and USE BASIC TOOLS ON CONSOLE.")
                    print(f"  Or coat these roots with resin — USE RESIN ON ROOTS — and burn through.\"")
            else:
                # Roots weakened, need fire
                if "torch" in inv:
                    print(f"  {display.npc_name('Lira')}: \"The roots are coated — they'll burn now.")
                    print(f"  USE TORCH ON ROOTS to burn through.\" She hesitates.")
                    print(f"  {display.npc_name('Lira')}: \"Be ready to move fast.\"")
                else:
                    print(f"  {display.npc_name('Lira')}: \"The resin's on — they'll catch now, but we need fire.")
                    print(f"  We need a torch. CRAFT TORCH if you have luminous moss and wire.\"")

        elif room.id == "vw_control" and not quest.get("roots_cleared"):
            if "basic_tools" in inv:
                print()
                print(f"  {display.npc_name('Lira')}: \"This is the Growth Controller. USE BASIC TOOLS ON CONSOLE")
                print(f"  — the logic board might still work.\"")

    def _lira_blocks_torch(self, item_id, room):
        """Lira stops you from torching her biodome if she hasn't been recruited.

        First time: warning. Second time: she attacks.
        """
        if item_id != "torch" or room.id != "vw_root_wall":
            return False
        quest = self.state.get("quests", {}).get("verdant_bloom", {})
        if not quest.get("roots_weakened") or quest.get("roots_cleared"):
            return False
        lira = self.npcs_db.get("lira")
        if not lira or lira.get("recruited"):
            return False
        if quest.get("lira_defeated"):
            return False

        if not quest.get("lira_warned"):
            # First attempt — she confronts you
            quest["lira_warned"] = True
            self._log_event("lira_encounter", comic_weight=4,
                            event="torch_warning")
            print()
            display.narrate("You raise the torch toward the resin-coated roots —")
            print()
            display.narrate("A hand grabs your wrist. Hard.")
            print()
            print(f"  {display.npc_name('Lira')}: \"What are you DOING?\"")
            print()
            print(f"  {display.npc_name('Lira')}: \"I live here. This is my home. You set that fire")
            print(f"  {display.npc_name('Lira')}: and everything in this biodome burns — including me.\"")
            print()
            display.narrate("She stands between you and the roots.")
            print()
            print(f"  {display.npc_name('Lira')}: \"Use the Growth Controller. Or take me with you first.\"")
            return True
        else:
            # Second attempt — she attacks
            self._lira_attacks(room)
            return True

    def _lira_attacks(self, room):
        """Lira attacks you to defend her biodome."""
        print()
        display.narrate("You raise the torch again. Lira's eyes go wide.")
        print()
        print(f"  {display.npc_name('Lira')}: \"No!\"")
        print()
        display.narrate("She rips a thorny vine from the wall and swings at you.")
        print()
        # Set up Lira as a temporary enemy
        lira_enemy = {
            "id": "lira_hostile",
            "name": "Lira",
            "aspects": ["Botanist Without a Ship", "Knows Every Root by Name"],
            "skills": {"Fight": 1, "Notice": 2},
            "stress": [False, False],
            "consequences": {"mild": None},
            "aggressive": False,
            "loot": [],
            "_is_npc": True,
        }
        self.enemies_db["lira_hostile"] = lira_enemy
        room.enemies.append("lira_hostile")
        self._start_combat("lira_hostile")
        display.warning(f"  Lira attacks!")

    def _handle_lira_defeat(self):
        """Handle Lira being defeated in combat — she can no longer be recruited."""
        quest = self.state.get("quests", {}).get("verdant_bloom", {})
        quest["lira_defeated"] = True
        self._log_event("lira_encounter", comic_weight=4,
                        event="lira_defeated")
        lira = self.npcs_db.get("lira")
        if lira:
            # Remove her from her room
            greenhouse = self.rooms.get("vw_greenhouse")
            if greenhouse and "lira" in greenhouse.npcs:
                greenhouse.npcs.remove("lira")
        print()
        display.narrate("Lira slumps against the wall, clutching her side.")
        print()
        print(f"  {display.npc_name('Lira')}: \"You... you'd really...\"")
        print()
        display.narrate("She pulls herself up and stumbles south, into the smoke.")
        display.narrate("You hear the airlock cycle. She's gone.")
        print()
        display.warning("  Lira can no longer be recruited.")

    def _lira_fire_reaction(self):
        """Lira reacts to the biodome being set on fire, if she's following."""
        lira = self.npcs_db.get("lira")
        if not lira or not lira.get("following"):
            return
        explorer_loc = self.state.get("explorer_location")
        if lira.get("location") != explorer_loc:
            return
        print()
        display.narrate("Lira watches the fire climb. Her jaw tightens.")
        print()
        print(f"  {display.npc_name('Lira')}: \"I knew it would spread. I told you it would.\"")
        print()
        display.narrate("She's not looking at you. She's watching the canopy catch,")
        display.narrate("weeks of growth curling black in seconds.")
        print()
        print(f"  {display.npc_name('Lira')}: \"Get the bloom. Before we lose that too.\"")
        print()
        # Mood and mechanical impact — she suggested it, but watching still hurts
        lira["mood"] = "grim"
        lira["loyalty"] = max(0, lira.get("loyalty", 0) - 1)
        quest = self.state.get("quests", {}).get("verdant_bloom", {})
        quest["lira_witnessed_fire"] = True
        self._log_event("lira_encounter", comic_weight=4,
                        event="witnessed_fire",
                        mood="grim", loyalty=lira.get("loyalty", 0))

    def _day_transition(self):
        """Handle end-of-day events."""
        self.scene_invoked_aspects = set()

        day = self.state["day"]

        # Refresh fate points for both characters
        self.explorer.refresh_fate_points()
        self.steward.refresh_fate_points()

        # World seed growth check
        display.seed_speak(self.seed.communicate(self.seed_name))

        # NPC mood updates
        for npc_id in self.state.get("recruited_npcs", []):
            npc = self.npcs_db.get(npc_id, {})
            if npc:
                house = npc.get("house_level", 0)
                if house == 0 and npc.get("mood") != "unhappy":
                    if random.random() < 0.3:
                        old_mood = npc.get("mood", "content")
                        npc["mood"] = "restless"
                        display.info(f"  {npc['name']} is getting restless without proper shelter.")
                        self._log_event("npc_mood_change", comic_weight=2,
                                        npc_name=npc["name"], npc_id=npc_id,
                                        old_mood=old_mood, new_mood="restless",
                                        cause="no shelter")

        # Room-driven NPC production via subtask queues
        for room in self.skerry.get_all_rooms():
            if not room.role:
                continue
            task_name = self._role_to_task(room.role)
            workers = [self.npcs_db[nid] for nid in self.state.get("recruited_npcs", [])
                       if self.npcs_db.get(nid, {}).get("assignment") == task_name]
            if not workers:
                continue

            # Garden pre-step: base growth ticks (time passing, not an NPC action)
            if room.role == "garden":
                plots = self.skerry.get_garden_plots()
                newly_ready = farming.advance_growth(plots, len(workers))
                for plot_id in newly_ready:
                    plot = self.skerry.get_plot(plot_id)
                    if plot and plot.get("plant"):
                        display.success(f"  Plot {plot_id}: {plot['plant'].get('name')} is ready!")

            # Run subtask queue
            results = subtasks.run_room_subtasks(self, room, workers)
            for npc_name, subtask_name, messages in results:
                for msg in messages:
                    display.success(f"  {npc_name} ({subtask_name}): {msg}")

        # Random event
        if random.random() < 0.4:
            events = self.events_db.get("steward_events", [])
            if events:
                # Filter by requirements
                eligible = []
                npc_count = len(self.state.get("recruited_npcs", []))
                for evt in events:
                    reqs = evt.get("requires", {})
                    if npc_count >= reqs.get("min_npcs", 0):
                        eligible.append(evt)

                if eligible:
                    weights = [e.get("weight", 1) for e in eligible]
                    event = random.choices(eligible, weights=weights, k=1)[0]
                    display.header(f"Event: {self.sub(event['name'])}")
                    display.narrate(f"  {self.sub(event['description'])}")

                    if event.get("skill_check"):
                        sc = event["skill_check"]
                        total, shifts, dice_result = dice.skill_check(
                            self.steward.get_skill(sc["skill"]), sc["difficulty"])
                        print(f"  {dice.roll_description(dice_result, self.steward.get_skill(sc['skill']), sc['skill'])}")

                        if shifts >= 0:
                            display.success(f"  {self.sub(event['success'])}")
                            effect = event.get("success_effect", {})
                            if effect.get("mote_bonus"):
                                self.seed.feed(effect["mote_bonus"])
                            if effect.get("random_item"):
                                item = random.choice(["metal_scraps", "wire", "torn_fabric"])
                                self.steward.add_to_inventory(item)
                            if effect.get("loyalty_bonus"):
                                for nid in self.state.get("recruited_npcs", []):
                                    n = self.npcs_db.get(nid, {})
                                    n["loyalty"] = min(10, n.get("loyalty", 0) + 1)
                        else:
                            display.warning(f"  {self.sub(event['failure'])}")
                            effect = event.get("failure_effect", {})
                            if effect.get("stress"):
                                self.steward.apply_damage(effect["stress"])
                            if effect.get("mood_penalty"):
                                for nid in self.state.get("recruited_npcs", []):
                                    n = self.npcs_db.get(nid, {})
                                    if n.get("mood") == "content":
                                        n["mood"] = "restless"
                    else:
                        display.success(f"  {self.sub(event['success'])}")
                        effect = event.get("success_effect", {})
                        if effect.get("mote_bonus"):
                            self.seed.feed(effect["mote_bonus"])
                        if effect.get("mood_bonus"):
                            for nid in self.state.get("recruited_npcs", []):
                                n = self.npcs_db.get(nid, {})
                                n["mood"] = "content"

        # ── Food consumption + spoilage ──
        if self.skerry.has_structure("storehouse") and self.skerry.food_stores:
            # Remove spoiled food
            spoiled = farming.remove_spoiled(self.skerry.food_stores, day)
            for name in spoiled:
                display.warning(f"  Spoiled: {name} has gone bad.")

            # Consume food
            population = 2 + len(self.state.get("recruited_npcs", []))
            daily_need = population * 50
            consumed = farming.consume_food(self.skerry.food_stores, daily_need, day)
            if consumed > 0:
                display.info(f"  Colony consumed {consumed} cal ({population} people).")

            # Check starvation tier
            food_days = farming.days_of_food(self.skerry.food_stores, population)
            tier = farming.get_starvation_tier(food_days)
            # Remove old starvation/food aspects and apply new ones
            food_aspects = {"Rations Are Getting Thin", "Hunger Gnaws at Everyone",
                            "People Are Starving", "Monotonous Diet", "Well-Fed Colony"}
            dyn = self.skerry.dynamic_aspects
            dyn[:] = [a for a in dyn if a not in food_aspects]

            if tier["aspect"]:
                dyn.append(tier["aspect"])
                display.warning(f"  Aspect: {tier['aspect']}")

            # Variety check
            var = farming.variety_score(self.skerry.food_stores)
            if 0 < var < 3:
                dyn.append("Monotonous Diet")
                display.warning(f"  Aspect: Monotonous Diet")

            # Pleasure check
            pleasure = farming.avg_pleasure(self.skerry.food_stores)
            if pleasure > 6:
                dyn.append("Well-Fed Colony")
                display.success(f"  Aspect: Well-Fed Colony (free invoke)")

            # Starvation effects on NPCs
            if tier["aspect"] == "Hunger Gnaws at Everyone":
                for nid in self.state.get("recruited_npcs", []):
                    n = self.npcs_db.get(nid, {})
                    n["loyalty"] = max(0, n.get("loyalty", 5) - 1)
                self.steward.apply_damage(1)
                self.explorer.apply_damage(1)
                display.warning("  Hunger takes its toll. Everyone suffers.")
            elif tier["aspect"] == "People Are Starving":
                departed = []
                for nid in list(self.state.get("recruited_npcs", [])):
                    n = self.npcs_db.get(nid, {})
                    if n.get("loyalty", 5) < 3:
                        departed.append(nid)
                for nid in departed:
                    npc = self.npcs_db[nid]
                    display.warning(f"  {npc['name']} has left the colony — too hungry to stay.")
                    self._log_event("npc_departed", comic_weight=4,
                                    npc_name=npc["name"], npc_id=nid,
                                    cause="starvation")
                    npc["recruited"] = False
                    npc["assignment"] = "idle"
                    npc["settled_room"] = None
                    if nid in self.state.get("recruited_npcs", []):
                        self.state["recruited_npcs"].remove(nid)
                self.steward.apply_damage(1)
                self.explorer.apply_damage(1)

        self._log_event("day_transition", comic_weight=1,
                        day_number=day,
                        population=2 + len(self.state.get("recruited_npcs", [])))
        display.display_seed(self.seed.to_dict(), name=self.seed_name)

    def _transition_to_day1(self):
        """Transition from prologue to Day 1 Explorer Phase."""
        self.state["current_phase"] = "explorer"
        day = self.state["day"]
        self._log_event("phase_change", comic_weight=3,
                        from_phase="prologue", to_phase="explorer")

        # Sevarik starts where Miria found him (the prologue location)
        self.state["explorer_location"] = self.state.get("prologue_location", "skerry_central")

        # Remove Sevarik-as-NPC (he's now the active explorer character)
        for room in self.rooms.values():
            if "sevarik" in room.npcs:
                room.remove_npc("sevarik")
        if "sevarik" in self.npcs_db:
            del self.npcs_db["sevarik"]

        # Miria becomes an inactive agent on the skerry
        self._deactivate_agent("steward")

        print()
        display.phase_banner("explorer", day, self.explorer_name, self.steward_name)

        # Show explorer starting location
        room = self.rooms.get(self.state["explorer_location"])
        if room:
            room.discover()
            display.display_room(room, self.game_context())

        print()
        display.display_status(self.explorer, "explorer")
        display.display_seed(self.seed.to_dict(), name=self.seed_name)

        # World seed gives Sevarik direction
        print()
        display.seed_speak("Good. We have a steward. I'm stronger now.")
        display.seed_speak("I can send you beyond the skerry — my tendril will carry you.")
        print()

        self.save_game(silent=True)
