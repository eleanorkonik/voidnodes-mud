"""Items domain — take, drop, wear, remove, use, give, inventory."""

from engine import display, dice, masterwork
from models.character import BODY_SLOTS

STACK_SIZE = 5
SKERRY_CAPACITY = {"large": 5, "medium": 50, "small": 500}


class ItemsMixin:
    """Mixin providing item manipulation commands for the Game class."""

    def cmd_inventory(self, args):
        char = self.current_character()
        display.display_inventory(char, self.items_db, self.artifacts_db, self.specimens_db)
        used = self._count_slots_used(char)
        capacity = self._get_effective_capacity(char)
        display.display_slot_usage(used, capacity)

    def cmd_take(self, args):
        if not args:
            display.error("Take what?")
            return

        target = " ".join(args).lower()
        room = self.current_room()

        # GET ALL / TAKE ALL — grab all loose items and specimens (not artifacts/fixtures)
        if target == "all":
            if not room.items:
                display.narrate("There's nothing here to pick up.")
                return
            char = self.current_character()
            picked = []
            skipped = []
            for item_id in list(room.items):
                bid = masterwork.base_id(item_id)
                is_fixture = self.items_db.get(bid, {}).get("type") == "fixture"
                is_takeable = bid in self.items_db or item_id in self.specimens_db
                if is_takeable and not is_fixture:
                    if self._can_take_item(char, item_id, allow_overflow=False):
                        room.remove_item(item_id)
                        char.add_to_inventory(item_id)
                        picked.append(item_id)
                    else:
                        skipped.append(item_id)
            if not picked:
                if skipped:
                    display.narrate("Your inventory is too full to carry anything else.")
                else:
                    display.narrate("There's nothing here to pick up.")
                return
            counts = {}
            for mid in picked:
                spec = self.specimens_db.get(mid)
                name = spec["name"] if spec else masterwork.get_display_name(mid, self.items_db)
                counts[name] = counts.get(name, 0) + 1
            for name, count in counts.items():
                if count > 1:
                    display.success(f"  {display.item_name(name)} x{count}")
                else:
                    display.success(f"  {display.item_name(name)}")
            if skipped:
                display.info(f"  Left behind {len(skipped)} item{'s' if len(skipped) != 1 else ''} (no room).")
            return

        # Check artifacts at this location
        for art_id, art in self._artifacts_in_room(room.id):
            if target in art.get("name", "").lower() or target == art_id:
                char = self.current_character()
                if not self._can_take_item(char, art_id):
                    return
                phase = self.state.get("current_phase", "explorer")
                char_role = "explorer" if phase == "explorer" else "steward"
                char.add_to_inventory(art_id)
                self._move_artifact(art_id, "inventory", char_role)
                display.success(f"You pick up the {art.get('name', art_id)}.")
                self._log_event("artifact_found", comic_weight=5,
                                artifact_id=art_id, artifact_name=art.get("name", art_id))
                if not self.state.get("_artifact_found_hint"):
                    self.state["_artifact_found_hint"] = True
                    print()
                    display.seed_speak("An artifact! You can KEEP it for the stat bonus,")
                    display.seed_speak("or FEED it to me — I'll convert it into motes.")
                # Mark quest complete when the verdant_wreck zone artifact is found
                vw_artifact = self.state.get("zone_artifacts", {}).get("verdant_wreck")
                if art_id == vw_artifact:
                    quest = self.state.get("quests", {}).get("verdant_bloom", {})
                    if quest.get("status") == "active":
                        quest["status"] = "complete"
                return

        # Check for specimen items in room
        for rid in list(room.items):
            spec = self.specimens_db.get(rid)
            if spec and (target in spec["name"].lower() or target == rid):
                char = self.current_character()
                if not self._can_take_item(char, rid):
                    return
                room.remove_item(rid)
                char.add_to_inventory(rid)
                display.success(f"You pick up {spec['name']}. (specimen)")
                return

        item_id, item = self._find_entity(list(room.items), target, self.items_db)
        if item:
            if item.get("type") == "fixture":
                display.narrate(f"The {item.get('name', item_id)} is built into the room. Try PROBE to examine it, or USE an item on it.")
                return
            char = self.current_character()
            if not self._can_take_item(char, item_id):
                return
            room.remove_item(item_id)
            char.add_to_inventory(item_id)
            take_name = masterwork.get_display_name(item_id, self.items_db)
            display.success(f"You pick up {take_name}.")
            self._log_event("item_taken", comic_weight=1,
                            item_id=item_id, item_name=take_name)
            # Tutorial nudge: first time picking up remnants with tools
            if item.get("type") == "remnants" and "basic_tools" in char.inventory:
                if not self.state.get("_process_hint"):
                    display.seed_speak("You have tools — you can PROCESS remnants for materials.")
                    self.state["_process_hint"] = True
            return

        display.narrate(f"There's nothing called '{target}' here to take.")

    def cmd_drop(self, args):
        if not args:
            display.error("Drop what? DROP <item> or DROP ALL.")
            return

        target = " ".join(args).lower()
        char = self.current_character()
        room = self.current_room()

        if target == "materials":
            dropped = []
            for item_id in list(char.inventory):
                bid = masterwork.base_id(item_id)
                if self.items_db.get(bid, {}).get("type") == "material":
                    char.remove_from_inventory(item_id)
                    room.add_item(item_id)
                    dropped.append(item_id)
            if dropped:
                counts = {}
                for mid in dropped:
                    name = masterwork.get_display_name(mid, self.items_db)
                    counts[name] = counts.get(name, 0) + 1
                display.narrate("You pile your salvage on the ground.")
                for name, count in counts.items():
                    if count > 1:
                        display.info(f"  {display.item_name(name)} x{count}")
                    else:
                        display.info(f"  {display.item_name(name)}")
            else:
                display.narrate("You don't have any materials to drop.")
            return

        if target == "specimens":
            dropped = []
            for item_id in list(char.inventory):
                spec = self.specimens_db.get(item_id)
                if spec:
                    char.remove_from_inventory(item_id)
                    room.add_item(item_id)
                    dropped.append(item_id)
            if dropped:
                counts = {}
                for mid in dropped:
                    name = self.specimens_db[mid]["name"]
                    counts[name] = counts.get(name, 0) + 1
                display.narrate("You set your specimens down carefully.")
                for name, count in counts.items():
                    if count > 1:
                        display.info(f"  {display.item_name(name)} x{count}")
                    else:
                        display.info(f"  {display.item_name(name)}")
            else:
                display.narrate("You don't have any specimens to drop.")
            return

        if target == "all":
            kept_artifact = self.state.get("kept_artifact")
            dropped = []
            for item_id in list(char.inventory):
                # Skip explicitly KEPT artifact
                if item_id == kept_artifact:
                    continue
                char.remove_from_inventory(item_id)
                room.add_item(item_id)
                # Track artifact status if dropping an artifact
                if item_id in self.artifacts_db:
                    self.state.setdefault("artifacts_status", {})[item_id] = "stored"
                    self._on_artifact_resolved(item_id)
                dropped.append(item_id)
            if dropped:
                counts = {}
                for mid in dropped:
                    spec = self.specimens_db.get(mid)
                    art = self.artifacts_db.get(mid)
                    if spec:
                        name = spec["name"]
                    elif art:
                        name = art.get("name", mid)
                    else:
                        name = masterwork.get_display_name(mid, self.items_db)
                    counts[name] = counts.get(name, 0) + 1
                display.narrate("You set everything down.")
                for name, count in counts.items():
                    if count > 1:
                        display.info(f"  {display.item_name(name)} x{count}")
                    else:
                        display.info(f"  {display.item_name(name)}")
                if kept_artifact and kept_artifact in char.inventory:
                    art = self.artifacts_db.get(kept_artifact, {})
                    display.info(f"  (Kept: {art.get('name', kept_artifact)})")
            else:
                display.narrate("You're not carrying anything to drop.")
            return

        # Drop specific item
        item_id, item = self._find_entity(char.inventory, target, self.items_db)
        if item:
            char.remove_from_inventory(item_id)
            room.add_item(item_id)
            drop_name = masterwork.get_display_name(item_id, self.items_db)
            display.success(f"You set down the {drop_name}.")
            self._log_event("item_dropped", comic_weight=1,
                            item_id=item_id, item_name=drop_name)
            return

        # Check specimens
        spec_id, spec = self._find_entity(char.inventory, target, self.specimens_db)
        if spec:
            char.remove_from_inventory(spec_id)
            room.add_item(spec_id)
            display.success(f"You set down the {spec['name']}.")
            return

        # Check artifacts too
        art_id, art = self._find_entity(char.inventory, target, self.artifacts_db)
        if art:
            char.remove_from_inventory(art_id)
            room.add_item(art_id)
            self.state.setdefault("artifacts_status", {})[art_id] = "stored"
            self._on_artifact_resolved(art_id)
            display.success(f"You set down the {art['name']}.")
            if room.zone == "skerry":
                display.narrate("It'll be safe here until you decide what to do with it.")
            return

        display.error(f"You don't have anything called '{target}'.")

    def cmd_wear(self, args):
        if not args:
            display.error("Wear what?")
            return

        target = " ".join(args).lower()
        char = self.current_character()

        # Find item in inventory — check both items_db and artifacts_db
        art_id, art = self._find_entity(char.inventory, target, self.artifacts_db)
        if art:
            slot = art.get("slot")
            if not slot:
                display.narrate("You can't wear that.")
                return
            if char.worn.get(slot):
                current_name = display._lookup_name(char.worn[slot], self.items_db, self.artifacts_db)
                display.narrate(f"You're already wearing {current_name} on your {slot}. REMOVE it first.")
                return
            char.wear_item(art_id, slot)
            display.success(f"You put on the {art['name']}.")
            self._log_event("item_worn", comic_weight=2,
                            item_id=art_id, item_name=art["name"], slot=slot)
            return

        item_id, item = self._find_entity(char.inventory, target, self.items_db)
        if item:
            slot = item.get("slot")
            if not slot:
                display.narrate("You can't wear that.")
                return
            if char.worn.get(slot):
                current_name = display._lookup_name(char.worn[slot], self.items_db, self.artifacts_db)
                display.narrate(f"You're already wearing {current_name} on your {slot}. REMOVE it first.")
                return
            char.wear_item(item_id, slot)
            display.success(f"You put on the {item['name']}.")
            self._log_event("item_worn", comic_weight=2,
                            item_id=item_id, item_name=item["name"], slot=slot)
            return

        display.narrate(f"You don't have '{target}'.")

    def cmd_remove(self, args):
        if not args:
            display.error("Remove what?")
            return

        target = " ".join(args).lower()
        char = self.current_character()

        # Try target as a slot name
        if target in BODY_SLOTS:
            item_id = char.remove_worn(target)
            if item_id:
                name = display._lookup_name(item_id, self.items_db, self.artifacts_db)
                display.success(f"You take off the {name}.")
            else:
                display.narrate(f"You're not wearing anything on your {target}.")
            return

        # Match item name against worn items
        worn_ids = [wid for wid in char.worn.values() if wid is not None]
        art_id, art = self._find_entity(worn_ids, target, self.artifacts_db)
        if art:
            slot = char.find_worn_by_item(art_id)
            if slot:
                char.remove_worn(slot)
                display.success(f"You take off the {art['name']}.")
                return

        item_id, item = self._find_entity(worn_ids, target, self.items_db)
        if item:
            slot = char.find_worn_by_item(item_id)
            if slot:
                char.remove_worn(slot)
                display.success(f"You take off the {item['name']}.")
                return

        display.narrate(f"You're not wearing anything called '{target}'.")

    def cmd_use(self, args):
        if not args:
            display.error("Use what? (USE <item> or USE <item> ON <target>)")
            return

        raw = " ".join(args).lower()
        char = self.current_character()
        room = self.current_room()

        # Parse USE <item> ON <target>
        item_part, use_target = raw, None
        if " on " in raw:
            parts = raw.split(" on ", 1)
            item_part, use_target = parts[0].strip(), parts[1].strip()

        # Targeted use — quest interactions (USE RESIN ON ROOTS, etc.)
        from engine.quest import handle_quest_use
        if use_target and room:
            item_id_q, item_q = self._find_entity(char.inventory, item_part, self.items_db)
            if item_id_q:
                # Lira stops you from burning her biodome if she's still living here
                if self._lira_blocks_torch(item_id_q, room):
                    return
                biodome_was_burning = self.state.get("quests", {}).get("verdant_bloom", {}).get("biodome_burning")
                handled, consumed = handle_quest_use(item_id_q, use_target, room.id, self.state, char, self.rooms)
                if handled:
                    if consumed:
                        char.remove_from_inventory(item_id_q)
                    # Lira reacts to watching her biodome burn
                    if not biodome_was_burning and self.state.get("quests", {}).get("verdant_bloom", {}).get("biodome_burning"):
                        self._lira_fire_reaction()
                    return
            if not item_id_q:
                display.error(f"You don't have '{item_part}'.")
            else:
                display.narrate(f"Using {item_q['name']} on that doesn't do anything.")
            return

        # No target — untargeted item use (artifacts, food, etc.)
        target = item_part

        # Check artifacts in inventory
        art_id, art = self._find_entity(char.inventory, target, self.artifacts_db)
        if art:
            if art_id == "bloom_catalyst":
                uses = art.get("uses_remaining", 0)
                if uses <= 0:
                    display.narrate("The crystal is spent. It crumbles to dust in your hands.")
                    char.remove_from_inventory(art_id)
                    self.state.get("artifacts_status", {})[art_id] = "spent"
                    self._on_artifact_resolved(art_id)
                    return
                art["uses_remaining"] = uses - 1
                char.add_to_inventory("preserved_food")
                char.add_to_inventory("seeds")
                remaining = uses - 1
                display.success("The Bloom Catalyst pulses. Nearby vegetation erupts into")
                display.success("flower and fruit. You gather what you can.")
                display.info(f"  Gained: preserved food, seeds. ({remaining} bloom{'s' if remaining != 1 else ''} remaining)")
                if remaining > 0:
                    words = ["Zero", "One", "Two", "Three", "Four", "Five"]
                    art["aspects"] = ["Instant Harvest", f"{words[remaining]} Bloom{'s' if remaining != 1 else ''} Remain{'s' if remaining == 1 else ''}"]
                else:
                    display.narrate("The crystal dims and crumbles to dust. Its blooms are spent.")
                    char.remove_from_inventory(art_id)
                    self.state.get("artifacts_status", {})[art_id] = "spent"
                    self._on_artifact_resolved(art_id)
                return
            elif art_id == "silver_slippers":
                display.narrate("You slip them on and click the heels together.")
                display.narrate("Once. Twice. Three times.")
                print()
                display.seed_speak("You feel a tug — toward the skerry. Lost in the")
                display.seed_speak("void, click your heels and these will pull you home.")
            elif art_id == "red_clown_nose":
                display.narrate("You put on the nose. It's squishy. Ridiculous.")
                display.narrate("But something shifts — the air around you softens.")
                print()
                display.seed_speak("Less sharp. Less threatening. Less worth envying.")
                display.seed_speak("That could save your life out there.")
            else:
                display.narrate(f"You hold the {art['name']}. It hums faintly.")
            return

        item_id, item = self._find_entity(char.inventory, target, self.items_db)
        if item:
            if item.get("special") == "restore_stress":
                char.clear_stress()
                char.remove_from_inventory(item_id)
                display.success(f"You eat the {item['name']}. All stress cleared.")
                self._log_event("food_consumed", comic_weight=1,
                                item_id=item_id, item_name=item["name"],
                                effect="stress_cleared")
            elif item.get("type") == "crafted" and item.get("stat_bonuses"):
                display.narrate(f"The {item['name']} is already providing its bonus passively.")
            else:
                display.narrate(f"You can't use {item.get('name', target)} right now.")
            return

        display.narrate(f"You don't have '{target}'.")

    def cmd_give(self, args):
        """GIVE <item> TO <target> — unified give/feed command.

        Target can be the world seed (feeds for motes), an NPC (gift/transfer),
        or the other player agent (inventory transfer).
        """
        if not args:
            display.error(f"Give what to whom? Usage: GIVE <item> TO <name>")
            return

        raw = " ".join(args)
        parts = raw.split(" to ", 1)
        if len(parts) < 2:
            display.error(f"Give what to whom? Usage: GIVE <item> TO <name>")
            return

        item_part = parts[0].strip().lower()
        target_name = parts[1].strip().lower()
        room = self.current_room()
        char = self.current_character()

        if not item_part:
            display.error(f"Give what? Usage: GIVE <item> TO <name>")
            return

        # ── Target: world seed ────────────────────────────────────
        seed_name = self.seed_name.lower()
        if target_name in (seed_name, "seed", "tuft"):
            self._give_to_seed(char, item_part)
            return

        # ── Target: player agent (explorer/steward) ───────────────
        agent_id, agent_data = self._find_agent_in_room(target_name, room.id)
        if agent_data:
            self._give_to_agent(char, item_part, agent_data)
            return

        # ── Target: NPC ───────────────────────────────────────────
        npc_id, npc_data = self._find_entity(room.npcs, target_name, self.npcs_db)
        if npc_data:
            self._give_to_npc(char, item_part, npc_data)
            return

        # Also check followers at this location
        follower_id, follower_data = self._find_follower(target_name, room.id)
        if follower_data:
            self._give_to_npc(char, item_part, follower_data)
            return

        display.error(f"There's nobody called '{target_name}' here to give things to.")

    def _give_to_seed(self, char, item_part):
        """Feed an item to the world seed for motes."""
        # Artifacts first — they have special feed effects
        art_id, art = self._find_in_db(item_part, self.artifacts_db)
        if art and (art_id in char.inventory or self.state.get("artifacts_status", {}).get(art_id) == "discovered"):
            # If worn, unequip first
            worn_slot = char.find_worn_by_item(art_id)
            if worn_slot:
                char.remove_worn(worn_slot)

            motes = art["mote_value"]
            new_total, stage_changed = self.seed.feed(motes)
            char.remove_from_inventory(art_id)
            self.state.setdefault("artifacts_status", {})[art_id] = "fed"
            self._on_artifact_resolved(art_id)
            self._move_artifact(art_id, None, None)

            if art.get("feed_effect"):
                display.narrate(self.sub(art["feed_effect"]))
            else:
                display.success(f"You give the {art['name']} to {self.seed_name}. +{motes} motes!")

            if stage_changed:
                display.success(f"\n  \u2727 {self.seed_name.upper()} GROWS STRONGER! \u2727")
                display.seed_speak(self.seed.communicate(self.seed_name))
                self._log_event("seed_growth", comic_weight=5,
                                new_stage=self.seed.growth_stage,
                                total_motes=new_total)

            self._log_event("artifact_fed", comic_weight=5,
                            artifact_id=art_id, artifact_name=art["name"],
                            motes_gained=motes, total_motes=new_total)
            display.display_seed(self.seed.to_dict(), name=self.seed_name)
            return

        # Regular items (including masterwork) — check inventory + worn
        worn_ids = [wid for wid in char.worn.values() if wid]
        search_ids = list(char.inventory) + worn_ids
        item_id, item = self._find_entity(search_ids, item_part, self.items_db)
        if item:
            motes = item.get("mote_value", 0)
            if motes <= 0:
                feed_name = masterwork.get_display_name(item_id, self.items_db)
                display.seed_speak(f"There's nothing for me in that {feed_name}.")
                return

            # If worn, unequip first
            worn_slot = char.find_worn_by_item(item_id)
            if worn_slot:
                char.remove_worn(worn_slot)

            new_total, stage_changed = self.seed.feed(motes)
            char.remove_from_inventory(item_id)

            feed_name = masterwork.get_display_name(item_id, self.items_db)
            display.success(f"You give {feed_name} to {self.seed_name}. +{motes} motes!")
            self._log_event("item_fed", comic_weight=2,
                            item_id=item_id, item_name=feed_name,
                            motes_gained=motes, total_motes=new_total)
            if stage_changed:
                self._log_event("seed_growth", comic_weight=5,
                                new_stage=self.seed.growth_stage,
                                total_motes=new_total)
                display.success(f"\n  \u2727 {self.seed_name.upper()} GROWS STRONGER! \u2727")
                display.seed_speak(self.seed.communicate(self.seed_name))

            display.display_seed(self.seed.to_dict(), name=self.seed_name)
            return

        display.narrate(f"You don't have '{item_part}' to give.")

    def _give_to_npc(self, char, item_part, npc_data):
        """Give an item to an NPC — artifacts resolve, masterwork gives social bonus."""
        # Artifacts — special handling
        art_id, art = self._find_entity(char.inventory, item_part, self.artifacts_db)
        if art:
            char.remove_from_inventory(art_id)
            self.state.setdefault("artifacts_status", {})[art_id] = "given"
            self._on_artifact_resolved(art_id)
            display.success(f"You give the {art['name']} to {npc_data['name']}.")
            return

        # Regular items (including masterwork) — transfer to NPC's room
        item_id, item = self._find_entity(char.inventory, item_part, self.items_db)
        if item:
            char.remove_from_inventory(item_id)
            # Place in NPC's current room (available for subtask use)
            npc_room = self.rooms.get(npc_data.get("location", ""))
            if npc_room:
                npc_room.add_item(item_id)
            item_name = masterwork.get_display_name(item_id, self.items_db)

            if masterwork.is_masterwork(item_id):
                # Social bonus: mood boost + loyalty
                from commands.skerry_mgmt import MOOD_TIERS
                current_mood = npc_data.get("mood", "content")
                mood_idx = MOOD_TIERS.index(current_mood) if current_mood in MOOD_TIERS else 1
                if mood_idx > 0:
                    npc_data["mood"] = MOOD_TIERS[mood_idx - 1]
                npc_data["loyalty"] = min(10, npc_data.get("loyalty", 0) + 1)
                display.success(f"You give {item_name} to {npc_data['name']}.")
                display.npc_speak(npc_data["name"], "This is... remarkable work. Thank you.")
                display.success(f"  {npc_data['name']}'s mood improves to {npc_data['mood']}. Loyalty +1.")
            else:
                display.success(f"You give {item_name} to {npc_data['name']}.")
                display.npc_speak(npc_data["name"], "Thanks. I'll put this to good use.")

            self._log_event("item_given", comic_weight=3 if masterwork.is_masterwork(item_id) else 2,
                            item_id=item_id, item_name=item_name,
                            recipient=npc_data["name"],
                            masterwork=masterwork.is_masterwork(item_id))
            return

        display.error(f"You don't have anything called '{item_part}'.")

    def _give_to_agent(self, char, item_part, agent_data):
        """Transfer an item to the other player agent (explorer/steward)."""
        target_role = agent_data.get("role")
        target_char = self.steward if target_role == "steward" else self.explorer

        # Check artifacts first, then items
        art_id, art = self._find_entity(char.inventory, item_part, self.artifacts_db)
        if art:
            char.remove_from_inventory(art_id)
            target_char.add_to_inventory(art_id)
            self.state.setdefault("artifacts_status", {})[art_id] = "given"
            self._on_artifact_resolved(art_id)
            display.success(f"You give the {art['name']} to {agent_data['name']}.")
            return

        item_id, item = self._find_entity(char.inventory, item_part, self.items_db)
        if not item:
            display.error(f"You don't have anything called '{item_part}'.")
            return

        char.remove_from_inventory(item_id)
        target_char.add_to_inventory(item_id)
        give_name = masterwork.get_display_name(item_id, self.items_db)
        display.success(f"You give {give_name} to {agent_data['name']}.")
        self._log_event("item_given", comic_weight=2,
                        item_id=item_id, item_name=give_name,
                        recipient=agent_data["name"])

    # ── Inventory Capacity ─────────────────────────────────────────

    def _get_item_size(self, item_id):
        """Get the size of an item ('small', 'medium', or 'large'). Default 'small'."""
        bid = masterwork.base_id(item_id)
        item = self.items_db.get(bid) or self.artifacts_db.get(item_id) or self.specimens_db.get(item_id) or {}
        return item.get("size", "small")

    def _is_item_stackable(self, item_id):
        """Check if an item is stackable. Masterwork items never stack."""
        if masterwork.is_masterwork(item_id):
            return False
        item = self.items_db.get(item_id) or self.artifacts_db.get(item_id) or self.specimens_db.get(item_id) or {}
        return item.get("stackable", False)

    def _count_slots_used(self, char):
        """Count inventory slots used by size. Stacks of STACK_SIZE count as 1 slot."""
        used = {"large": 0, "medium": 0, "small": 0}
        stacks = {}

        for item_id in char.inventory:
            if self._is_item_stackable(item_id):
                stacks[item_id] = stacks.get(item_id, 0) + 1
            else:
                size = self._get_item_size(item_id)
                used[size] += 1

        for item_id, count in stacks.items():
            size = self._get_item_size(item_id)
            slots = (count + STACK_SIZE - 1) // STACK_SIZE
            used[size] += slots

        return used

    def _get_effective_capacity(self, char):
        """Get carrying capacity: generous on skerry, character limits in zones."""
        room = self.current_room()
        if room and room.zone == "skerry":
            return dict(SKERRY_CAPACITY)
        return dict(char.slot_capacity)

    def _can_take_item(self, char, item_id, allow_overflow=True):
        """Check if character can carry an item. May attempt overflow skill check.

        Returns True if the item can be carried.
        allow_overflow=False skips the FP/skill check (used by TAKE ALL, SCAVENGE).
        """
        size = self._get_item_size(item_id)
        used = self._count_slots_used(char)
        capacity = self._get_effective_capacity(char)

        # Stackable: fits in existing partial stack
        if self._is_item_stackable(item_id):
            current_count = sum(1 for iid in char.inventory if iid == item_id)
            if current_count > 0 and current_count % STACK_SIZE != 0:
                return True

        # Under capacity
        if used[size] < capacity[size]:
            return True

        if not allow_overflow:
            return False

        # On skerry — no overflow, just blocked
        room = self.current_room()
        if room and room.zone == "skerry":
            display.narrate(f"No room for more {size} items. Drop something first.")
            return False

        # Zone overflow: skill check + 1 FP
        overflow_count = used[size] - capacity[size]
        dc = 2 + 2 * overflow_count

        if size == "large":
            skill_name = "Physique"
        elif size == "small":
            skill_name = "Athletics"
        else:
            endure_val = char.get_skill("Physique")
            nav_val = char.get_skill("Athletics")
            skill_name = "Physique" if endure_val >= nav_val else "Athletics"

        if char.fate_points < 1:
            display.narrate(f"Your {size} slots are full ({used[size]}/{capacity[size]}) and you're out of fate points.")
            display.info("  Drop something to make room.")
            return False

        # Require confirmation before spending FP
        pending = getattr(self, '_overflow_confirmed', None)
        if pending != item_id:
            display.info(f"  {size.capitalize()} slots full ({used[size]}/{capacity[size]}). Push through? (1 FP + {skill_name} vs DC {dc})")
            display.info(f"  GET it again to push through, or DROP something first.")
            self._overflow_confirmed = item_id
            return False
        self._overflow_confirmed = None

        char.spend_fate_point()
        invoke_bonus = self._consume_invoke_bonus(skill=skill_name)
        skill_val = char.get_skill(skill_name) + invoke_bonus
        total, shifts, dice_result = dice.skill_check(skill_val, dc)

        label = f"{skill_name}+{invoke_bonus}" if invoke_bonus else skill_name
        display.info(f"  Pushing through... (1 FP spent)")
        print(f"  {label}: {dice.roll_description(dice_result, skill_val, label)} vs DC {dc}")

        if shifts >= 0:
            display.success("  You manage to carry it.")
            return True
        else:
            display.narrate("  Too much to carry. It slips from your grip.")
            return False

    # ── PROCESS ───────────────────────────────────────────────────

    def cmd_process(self, args):
        """PROCESS <remnants> — Break down enemy remains into materials."""
        if not args:
            display.error("Process what? PROCESS <remnants> to break them down for materials.")
            return

        target = " ".join(args).lower()
        char = self.current_character()
        room = self.current_room()

        # Find remnants in room items or inventory
        remnant_id = None
        remnant_data = None
        in_room = False

        # Check room first
        for rid in list(room.items):
            item = self.items_db.get(rid, {})
            if item.get("type") == "remnants" and (target in item.get("name", "").lower() or target == rid):
                remnant_id, remnant_data = rid, item
                in_room = True
                break

        # Then inventory
        if not remnant_id:
            for rid in list(char.inventory):
                item = self.items_db.get(rid, {})
                if item.get("type") == "remnants" and (target in item.get("name", "").lower() or target == rid):
                    remnant_id, remnant_data = rid, item
                    break

        if not remnant_id:
            display.error(f"There are no remnants called '{target}' here or in your inventory.")
            return

        # Require basic_tools
        if "basic_tools" not in char.inventory:
            display.error("You need basic tools to process remnants. Find some first.")
            return

        process_dc = remnant_data.get("process_dc", 1)
        process_yields = remnant_data.get("process_yields", [])
        process_verb = remnant_data.get("process_verb", "process")

        # Craft skill check + invoke bonus + workshop bonus
        invoke_bonus = self._consume_invoke_bonus(skill="Crafts")
        skill_val = char.get_skill("Crafts") + invoke_bonus
        workshop_bonus = 0
        if room and room.id == "skerry_workshop":
            workshop_bonus = 1 + room.tool_level
            skill_val += workshop_bonus

        total, shifts, dice_result = dice.skill_check(skill_val, process_dc)

        display.header(f"Processing: {remnant_data['name']}")
        label = f"Craft+{invoke_bonus}" if invoke_bonus else "Crafts"
        print(f"  {label}: {dice.roll_description(dice_result, skill_val, label)}")
        if workshop_bonus:
            print(f"  Workshop bonus: +{workshop_bonus}")
        print(f"  DC: {process_dc:+d}")

        # Remove remnants regardless of outcome
        if in_room:
            room.remove_item(remnant_id)
        else:
            char.remove_from_inventory(remnant_id)

        if shifts >= 0:
            # Success — determine yield multiplier
            masterwork = shifts >= 3
            multiplier = 2 if masterwork else 1

            if masterwork:
                display.success(f"  Masterwork! You {process_verb} the {remnant_data['name']} with expert precision.")
            else:
                display.success(f"  You {process_verb} the {remnant_data['name']}.")

            for yield_id, yield_count in process_yields:
                actual_count = yield_count * multiplier
                for _ in range(actual_count):
                    char.add_to_inventory(yield_id)
                yield_info = self.items_db.get(yield_id) or self.specimens_db.get(yield_id, {})
                yield_name = yield_info.get("name", yield_id)
                display.success(f"    +{actual_count}x {display.item_name(yield_name)}")

            if masterwork:
                display.info("  (Double yield from masterwork!)")
        else:
            # Fail — salvage 1x first yield
            display.warning(f"  You botch the job — the {remnant_data['name']} are ruined.")
            if process_yields:
                salvage_id = process_yields[0][0]
                char.add_to_inventory(salvage_id)
                salvage_info = self.items_db.get(salvage_id) or self.specimens_db.get(salvage_id, {})
                salvage_name = salvage_info.get("name", salvage_id)
                display.narrate(f"  You salvage a few scraps: 1x {display.item_name(salvage_name)}")

        self._log_event("remnants_processed", comic_weight=2,
                        remnant=remnant_data.get("name", remnant_id),
                        verb=process_verb,
                        success=shifts >= 0,
                        masterwork=shifts >= 3)
