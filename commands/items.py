"""Items domain — take, drop, wear, remove, use, give, inventory."""

from engine import display, dice
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
                is_fixture = self.items_db.get(item_id, {}).get("type") == "fixture"
                is_takeable = item_id in self.items_db or item_id in self.specimens_db
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
                name = spec["name"] if spec else self.items_db.get(mid, {}).get("name", mid)
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
                if not self.state.get("tutorial_complete"):
                    self.state["tutorial_artifact_found"] = True
                # Mark quest complete when bloom_catalyst is found
                if art_id == "bloom_catalyst":
                    self.state["tutorial_quest_done"] = True
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
            display.success(f"You pick up {item.get('name', item_id)}.")
            self._log_event("item_taken", comic_weight=1,
                            item_id=item_id, item_name=item.get("name", item_id))
            # Tutorial nudge: first time picking up remnants with tools
            if item.get("type") == "remnants" and "basic_tools" in char.inventory:
                if not self.state.get("tutorial_process_shown"):
                    display.seed_speak("You have tools — you can PROCESS remnants for materials.")
                    self.state["tutorial_process_shown"] = True
            return

        display.narrate(f"There's nothing called '{target}' here to take.")

    def cmd_drop(self, args):
        if not args:
            display.error("Drop what? DROP <item> or DROP ALL.")
            return

        target = " ".join(args).lower()
        char = self.current_character()
        room = self.current_room()

        if target in ("all", "materials"):
            dropped = []
            for item_id in list(char.inventory):
                if self.items_db.get(item_id, {}).get("type") == "material":
                    char.remove_from_inventory(item_id)
                    room.add_item(item_id)
                    dropped.append(item_id)
            if dropped:
                counts = {}
                for mid in dropped:
                    name = self.items_db.get(mid, {}).get("name", mid)
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

        # Drop specific item
        item_id, item = self._find_entity(char.inventory, target, self.items_db)
        if item:
            char.remove_from_inventory(item_id)
            room.add_item(item_id)
            display.success(f"You set down the {item['name']}.")
            self._log_event("item_dropped", comic_weight=1,
                            item_id=item_id, item_name=item["name"])
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
            if not self.state.get("tutorial_complete"):
                self.state["tutorial_artifact_resolved"] = True
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
        if not args:
            display.error("Give what to whom? Usage: GIVE <item> TO <name>")
            return

        raw = " ".join(args)
        parts = raw.split(" to ", 1)
        if len(parts) < 2:
            display.error("Give what to whom? Usage: GIVE <item> TO <name>")
            return

        item_part = parts[0].strip().lower()
        target_name = parts[1].strip().lower()
        room = self.current_room()
        char = self.current_character()

        if not item_part:
            display.error("Give what? Usage: GIVE <item> TO <name>")
            return

        # Find target agent in room
        agent_id, agent_data = self._find_agent_in_room(target_name, room.id)
        if not agent_data:
            # Also check NPCs
            npc_id, npc_data = self._find_entity(room.npcs, target_name, self.npcs_db)
            if not npc_data:
                display.error(f"There's nobody called '{target_name}' here to give things to.")
                return
            # For NPCs, just accept artifacts for tutorial purposes
            art_id, art = self._find_entity(char.inventory, item_part, self.artifacts_db)
            if art:
                char.remove_from_inventory(art_id)
                self.state.setdefault("artifacts_status", {})[art_id] = "given"
                self._on_artifact_resolved(art_id)
                if not self.state.get("tutorial_complete"):
                    self.state["tutorial_artifact_resolved"] = True
                display.success(f"You give the {art['name']} to {npc_data['name']}.")
                return
            display.error(f"You don't have anything called '{item_part}'.")
            return

        # Determine target character object
        target_role = agent_data.get("role")
        target_char = self.steward if target_role == "steward" else self.explorer

        # Check artifacts first, then items
        art_id, art = self._find_entity(char.inventory, item_part, self.artifacts_db)
        if art:
            char.remove_from_inventory(art_id)
            target_char.add_to_inventory(art_id)
            self.state.setdefault("artifacts_status", {})[art_id] = "given"
            self._on_artifact_resolved(art_id)
            if not self.state.get("tutorial_complete"):
                self.state["tutorial_artifact_resolved"] = True
            display.success(f"You give the {art['name']} to {agent_data['name']}.")
            return

        item_id, item = self._find_entity(char.inventory, item_part, self.items_db)
        if not item:
            display.error(f"You don't have anything called '{item_part}'.")
            return

        char.remove_from_inventory(item_id)
        target_char.add_to_inventory(item_id)
        display.success(f"You give {item['name']} to {agent_data['name']}.")
        self._log_event("item_given", comic_weight=2,
                        item_id=item_id, item_name=item["name"],
                        recipient=agent_data["name"])

    # ── Inventory Capacity ─────────────────────────────────────────

    def _get_item_size(self, item_id):
        """Get the size of an item ('small', 'medium', or 'large'). Default 'small'."""
        item = self.items_db.get(item_id) or self.artifacts_db.get(item_id) or self.specimens_db.get(item_id) or {}
        return item.get("size", "small")

    def _is_item_stackable(self, item_id):
        """Check if an item is stackable."""
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

        char.spend_fate_point()
        invoke_bonus = self._consume_invoke_bonus()
        skill_val = char.get_skill(skill_name) + invoke_bonus
        total, shifts, dice_result = dice.skill_check(skill_val, dc)

        label = f"{skill_name}+{invoke_bonus}" if invoke_bonus else skill_name
        display.info(f"  {size.capitalize()} slots full ({used[size]}/{capacity[size]}). Pushing through... (1 FP spent)")
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
        invoke_bonus = self._consume_invoke_bonus()
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
