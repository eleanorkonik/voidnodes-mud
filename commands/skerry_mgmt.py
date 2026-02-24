"""Skerry management domain — settle, assign, organize, tasks, rest, trade, store, agents."""

from engine import display, dice, subtasks


class SkerryMgmtMixin:
    """Mixin providing skerry management commands for the Game class."""

    # Room-name → task aliases so players can say ASSIGN LIRA JUNKYARD or ASSIGN LIRA SALVAGE
    _ROOM_TO_TASK = {
        "junkyard": "salvage", "the junkyard": "salvage",
        "garden": "gardening", "the garden": "gardening",
        "lookout": "guarding", "lookout post": "guarding",
        "workshop": "crafting", "the workshop": "crafting",
        "storehouse": "organizing", "the storehouse": "organizing",
        "water": "gathering", "water collection": "gathering",
        "shelter": "communal", "basic shelter": "communal",
    }
    _VALID_TASKS = {"salvage", "gardening", "guarding", "crafting", "organizing", "gathering", "communal", "idle"}
    # Which task needs which room built to be useful
    _TASK_REQUIRES_ROOM = {
        "salvage": "junkyard",
        "gardening": "garden",
        "guarding": "lookout_post",
        "crafting": "workshop",
        "organizing": "storehouse",
        "gathering": "water_collection",
        "communal": "basic_shelter",
    }
    # Map room role → NPC task name (for counting workers per room)
    _ROLE_TO_TASK = {
        "salvage": "salvage",
        "garden": "gardening",
        "guard": "guarding",
        "craft": "crafting",
        "organize": "organizing",
        "gather": "gathering",
        "communal": "communal",
        "recreation": "recreation",
        "seedcare": "seedcare",
    }

    def _role_to_task(self, role):
        """Map a room role to the corresponding NPC task name."""
        return self._ROLE_TO_TASK.get(role, role)

    def _count_settled_in_room(self, room_id):
        """Count how many NPCs are settled (housed) in a room."""
        return sum(1 for n in self.npcs_db.values()
                   if n.get("recruited") and n.get("settled_room") == room_id)

    def cmd_settle(self, args):
        """SETTLE <npc> — settle on skerry.  SETTLE <npc> IN <room> — house in a specific room."""
        if not args:
            display.error("Settle who? SETTLE <name> or SETTLE <name> IN <room>.")
            return

        room = self.current_room()
        if not room or room.zone != "skerry":
            display.error("You can only settle people on the skerry.")
            return

        # Parse: SETTLE <npc> IN <room>
        words = [w.lower() for w in args]
        if "in" in words:
            in_idx = words.index("in")
            npc_target = " ".join(words[:in_idx])
            room_target = " ".join(words[in_idx + 1:])
        else:
            npc_target = " ".join(words)
            room_target = None

        # Only the steward can assign housing
        if room_target and self.state.get("current_phase") != "steward":
            display.error("Only the steward can assign housing. Use SETTLE <name> to bring them to the skerry.")
            return

        npc_id, npc = self._find_in_db(npc_target, self.npcs_db)
        if not npc or not npc.get("recruited"):
            display.error(f"No recruited companion named '{npc_target}'.")
            return

        # SETTLE <npc> IN <room> — housing assignment
        if room_target:
            # Fuzzy-match room name
            target_room = None
            for r in self.skerry.get_all_rooms():
                if room_target in r.name.lower() or room_target == r.id:
                    target_room = r
                    break
            if not target_room:
                display.error(f"No skerry room matching '{room_target}'.")
                return
            if target_room.role is None:
                display.error(f"{target_room.name} isn't a place anyone can live.")
                return

            # Check bed capacity
            settled_count = self._count_settled_in_room(target_room.id)
            if settled_count >= target_room.max_workers:
                display.error(f"{target_room.name} is full — {settled_count}/{target_room.max_workers} beds taken.")
                return

            # Clear old housing if any
            old_room_id = npc.get("settled_room")

            # House them
            npc["settled_room"] = target_room.id
            npc["following"] = False
            npc["location"] = target_room.id

            # Auto-assign master task from room role
            master_task = self._role_to_task(target_room.role)
            npc["assignment"] = master_task

            if old_room_id and old_room_id != target_room.id:
                old_name = self.skerry.get_room(old_room_id)
                old_label = old_name.name if old_name else old_room_id
                display.success(f"{npc['name']} moves from {old_label} to {target_room.name}.")
            else:
                display.success(f"{npc['name']} settles into {target_room.name}.")
            display.info(f"  Master task: {master_task}")
            self._log_event("npc_settled", comic_weight=3,
                            npc_name=npc["name"], npc_id=npc_id,
                            room=target_room.name, task=master_task)
            self.state["tutorial_settle_done"] = True
            return

        # SETTLE <npc> — original behavior, settle on skerry without room housing
        if not npc.get("following"):
            display.narrate(f"{npc['name']} is already settled here.")
            return

        npc["following"] = False
        npc["location"] = "skerry_central"
        skerry_central = self.rooms.get("skerry_central")
        if skerry_central and npc_id not in skerry_central.npcs:
            skerry_central.add_npc(npc_id)
        display.success(f"{npc['name']} settles in on the skerry.")
        display.narrate(f"{npc['name']} looks around, taking it in. For now, the clearing will do.")
        self._log_event("npc_settled", comic_weight=3,
                        npc_name=npc["name"], npc_id=npc_id,
                        room="skerry_central")
        self.state["tutorial_settle_done"] = True

    def cmd_assign(self, args):
        if len(args) < 2:
            display.error("Usage: ASSIGN <npc> <task>  (tasks: salvage, gardening, guarding, crafting, organizing, gathering, communal, idle)")
            display.info("  You can also assign a specific subtask: ASSIGN <npc> <subtask>  (e.g., ASSIGN LIRA WATER PLANTS)")
            return

        npc_target = args[0].lower()
        task_input = " ".join(args[1:]).lower()

        npc_id, npc = self._find_in_db(npc_target, self.npcs_db)
        if not npc or not npc.get("recruited"):
            display.error(f"No recruited NPC named '{npc_target}'.")
            return

        # Try matching as a subtask ID first (e.g., "water plants" → "water_plants")
        subtask_id = task_input.replace(" ", "_")
        subtask_role, subtask_def = subtasks.find_subtask_role(subtask_id)
        if subtask_role:
            master_task = self._role_to_task(subtask_role)
            # Warn if the required facility isn't built
            required_structure = self._TASK_REQUIRES_ROOM.get(master_task)
            if required_structure and not self.skerry.has_structure(required_structure):
                display.warning(f"The {required_structure.replace('_', ' ')} hasn't been built yet — {npc['name']} won't be able to do this.")

            # Organize skill check (DC 1)
            total, shifts, dice_result = dice.skill_check(self.steward.get_skill("Organize"), 1)
            print(f"  Organize: {dice.roll_description(dice_result, self.steward.get_skill('Organize'), 'Organize')}")

            if shifts >= 0:
                npc["assignment"] = master_task
                npc["assigned_subtask"] = subtask_id
                display.success(f"Assigned {npc['name']} to {subtask_def['name']} ({master_task}).")
                self._log_event("npc_assigned", comic_weight=2,
                                npc_name=npc["name"], npc_id=npc_id,
                                task=master_task, subtask=subtask_id)
            else:
                display.narrate(f"You try to assign {npc['name']}, but the instructions get muddled. Try again.")
            return

        # Resolve room-name aliases to tasks
        task = self._ROOM_TO_TASK.get(task_input, task_input)

        if task not in self._VALID_TASKS:
            display.error(f"Unknown task: '{task_input}'. Valid: {', '.join(sorted(self._VALID_TASKS))}")
            display.info("  Or assign a specific subtask (e.g., ASSIGN LIRA WATER PLANTS). Type TASKS to see options.")
            return

        if task == "idle":
            npc["assignment"] = "idle"
            npc["assigned_subtask"] = None
            display.success(f"{npc['name']} is now idle.")
            return

        # Warn if the required facility isn't built yet
        required_structure = self._TASK_REQUIRES_ROOM.get(task)
        if required_structure and not self.skerry.has_structure(required_structure):
            display.warning(f"The {required_structure.replace('_', ' ')} hasn't been built yet — {npc['name']} won't be able to produce anything.")

        # Organize skill check (DC 1)
        total, shifts, dice_result = dice.skill_check(self.steward.get_skill("Organize"), 1)
        print(f"  Organize: {dice.roll_description(dice_result, self.steward.get_skill('Organize'), 'Organize')}")

        if shifts >= 0:
            npc["assignment"] = task
            npc["assigned_subtask"] = None  # master task, no specific subtask
            display.success(f"Assigned {npc['name']} to {task}.")
            self._log_event("npc_assigned", comic_weight=2,
                            npc_name=npc["name"], npc_id=npc_id, task=task)
        else:
            display.narrate(f"You try to assign {npc['name']}, but the instructions get muddled. Try again.")

    def cmd_organize(self, args):
        display.header("NPC Assignments")
        has_npcs = False
        for npc_id in self.state.get("recruited_npcs", []):
            npc = self.npcs_db.get(npc_id, {})
            if npc:
                has_npcs = True
                mood_colors = {"content": display.GREEN, "happy": display.BRIGHT_GREEN,
                              "restless": display.YELLOW, "grim": display.YELLOW,
                              "unhappy": display.RED, "angry": display.BRIGHT_RED,
                              "crisis": display.BRIGHT_RED}
                mood = npc.get("mood", "content")
                mc = mood_colors.get(mood, display.WHITE)
                print(f"  {display.npc_name(npc['name'])}: {npc.get('assignment', 'idle')} — "
                      f"Loyalty: {npc.get('loyalty', 0)}/10 — {mc}{mood}{display.RESET}")
        if not has_npcs:
            print("  No NPCs recruited yet.")

    def cmd_tasks(self, args):
        """Show subtask queues for all rooms with workers."""
        display.header("Task Queues")
        any_shown = False
        for room in self.skerry.get_all_rooms():
            if not room.role:
                continue
            st_defs = subtasks.get_subtasks_for_role(room.role)
            if not st_defs:
                continue

            task_name = self._role_to_task(room.role)
            workers = [self.npcs_db[nid] for nid in self.state.get("recruited_npcs", [])
                       if self.npcs_db.get(nid, {}).get("assignment") == task_name]

            print(f"\n  {display.BRIGHT_WHITE}{room.name}{display.RESET} ({room.role})")
            for st in st_defs:
                # Find who's working on this subtask
                assigned_names = []
                for w in workers:
                    is_settled = w.get("settled_room") == room.id
                    assigned_sub = w.get("assigned_subtask")
                    if is_settled:
                        assigned_names.append(f"{display.npc_name(w['name'])} [settled]")
                    elif assigned_sub == st["id"]:
                        assigned_names.append(display.npc_name(w['name']))
                    elif assigned_sub is None and st["order"] == 1:
                        # Floating with no specific subtask → defaults to first
                        assigned_names.append(f"{display.npc_name(w['name'])} [default]")

                worker_str = ", ".join(assigned_names) if assigned_names else f"{display.DIM}unassigned{display.RESET}"
                skill_str = f" ({st['skill']} DC {st['dc']})" if st.get("skill") else ""
                print(f"    {st['order']}. {st['name']}{skill_str} — {worker_str}")
                print(f"       {display.DIM}{st['description']}{display.RESET}")
            any_shown = True

        if not any_shown:
            print("  No rooms with task queues yet.")

    def cmd_rest(self, args):
        """Advance the day from steward phase. Time passes on the skerry."""
        self._log_event("rest", comic_weight=1, day=self.state["day"])
        self.state["day"] += 1
        day = self.state["day"]
        print()
        display.narrate("The skerry dims. Something like night settles over the void.")
        display.narrate("You sleep, and the seed keeps watch.")
        print()
        self._day_transition()
        print()
        display.narrate(f"Morning. Day {day}.")
        display.display_status(self.current_character(), "steward")

    def cmd_trade(self, args):
        display.narrate("Trading isn't fully set up yet — NPCs share resources with the community for now.")

    def cmd_store(self, args):
        """Move food from inventory to food stores."""
        if not self.skerry.has_structure("storehouse"):
            display.error("No storehouse built. Build one to store food.")
            return
        if not args:
            display.error("Store what? STORE <food item>")
            return

        target = " ".join(args).lower()
        char = self.current_character()

        # Check for preserved_food in inventory
        for item_id in char.inventory:
            item = self.items_db.get(item_id, {})
            spec = self.specimens_db.get(item_id)
            if item.get("calories") and (target in item.get("name", "").lower() or target == item_id):
                char.remove_from_inventory(item_id)
                food_data = {
                    "id": item_id,
                    "name": item.get("name", item_id),
                    "calories": item.get("calories", 40),
                    "shelf_life": item.get("shelf_life", -1),
                    "pleasure": item.get("pleasure", 3),
                    "variety_category": item.get("variety_category", "preserved"),
                }
                from engine import farming
                farming.add_to_stores(self.skerry.food_stores, food_data, self.state["day"])
                display.success(f"Stored {item['name']} in food stores.")
                self._log_event("food_stored", comic_weight=1,
                                item_id=item_id, item_name=item["name"])
                return

        display.error(f"No storable food item '{target}' in your inventory.")

    def _deactivate_agent(self, role):
        """Mark an agent as inactive — add to agents_db so they appear on the skerry."""
        if role == "explorer":
            agent_id = self.explorer_name.lower()
            location = "skerry_landing"
            agent_data = {
                "name": self.explorer_name,
                "role": "explorer",
                "location": location,
                "dialogue": {
                    "greeting": f"{self.explorer_name} nods. 'Back from the void. What do you need?'",
                    "idle": f"'{self.seed_name} is focused on you right now. I'll wait.'",
                    "happy": "'The skerry. It's not much, but it's worth fighting for.'",
                },
            }
        else:
            agent_id = self.steward_name.lower()
            location = self.state.get("steward_location", "skerry_central")
            agent_data = {
                "name": self.steward_name,
                "role": "steward",
                "location": location,
                "dialogue": {
                    "greeting": f"{self.steward_name} looks up from her work. 'Everything's holding together.'",
                    "idle": f"'{self.seed_name} is focused on you right now. I'll keep busy.'",
                    "happy": "'The skerry feels stronger today. We're getting somewhere.'",
                },
            }
        self.agents_db[agent_id] = agent_data

    def _activate_agent(self, role):
        """Mark an agent as active — remove from agents_db (player controls them directly)."""
        if role == "explorer":
            agent_id = self.explorer_name.lower()
        else:
            agent_id = self.steward_name.lower()
        self.agents_db.pop(agent_id, None)

    def _find_agent_in_room(self, target, room_id):
        """Find an inactive agent in the given room. Returns (agent_id, agent_data) or (None, None)."""
        for agent_id, agent_data in self.agents_db.items():
            if agent_data.get("location") == room_id:
                name = agent_data.get("name", "").lower()
                role = agent_data.get("role", "")
                if target in name or target == agent_id or target == role:
                    return agent_id, agent_data
        return None, None
