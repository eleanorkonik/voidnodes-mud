"""Farming domain — plant, harvest, survey, uproot, select, clone, cross-pollinate, bank, withdraw."""

from engine import display, farming


class FarmingMixin:
    """Mixin providing farming and garden commands for the Game class."""

    def cmd_plant(self, args):
        """Manually plant a specimen in a garden plot."""
        if not self.skerry.has_structure("garden"):
            display.error("No garden built. Build one first.")
            return
        if not args:
            display.error("Plant what? PLANT <specimen> [plot number]")
            return

        # Parse: PLANT <specimen> [plot_number]
        plot_id = None
        specimen_target = " ".join(args).lower()

        # Check if last arg is a number (plot ID)
        if len(args) > 1 and args[-1].isdigit():
            plot_id = int(args[-1])
            specimen_target = " ".join(args[:-1]).lower()

        # Find specimen in inventory
        char = self.current_character()
        found_id = None
        for item_id in char.inventory:
            spec = self.specimens_db.get(item_id)
            if spec and (specimen_target in spec["name"].lower() or specimen_target == item_id):
                found_id = item_id
                break

        if not found_id:
            display.error(f"No specimen '{specimen_target}' in your inventory.")
            return

        plots = self.skerry.get_garden_plots()
        if not plots:
            display.error("No garden plots available.")
            return

        # Find target plot (specified or first empty)
        target_plot = None
        if plot_id:
            target_plot = self.skerry.get_plot(plot_id)
            if not target_plot:
                display.error(f"No plot {plot_id}.")
                return
            if target_plot.get("plant"):
                display.error(f"Plot {plot_id} is already occupied. UPROOT it first.")
                return
        else:
            for p in plots:
                if p.get("plant") is None:
                    target_plot = p
                    break
            if not target_plot:
                display.error("All plots are occupied. UPROOT one first.")
                return

        if farming.plant_specimen(target_plot, found_id, self.state["day"]):
            char.remove_from_inventory(found_id)
            spec = self.specimens_db.get(found_id, {})
            display.success(f"Planted {spec.get('name', found_id)} in plot {target_plot['id']}.")
            self._log_event("specimen_planted", comic_weight=2,
                            specimen=spec.get("name", found_id),
                            plot=target_plot["id"])
        else:
            display.error("Couldn't plant that specimen.")

    def cmd_harvest(self, args):
        """Manually harvest a ready garden plot."""
        if not self.skerry.has_structure("garden"):
            display.error("No garden built.")
            return

        plots = self.skerry.get_garden_plots()

        # If no args, harvest all ready plots
        if not args:
            harvested_any = False
            for plot in plots:
                if farming.is_harvestable(plot):
                    result = farming.harvest_plot(plot, self.state["day"])
                    if result:
                        food, utility = result
                        farming.add_to_stores(self.skerry.food_stores, food, self.state["day"])
                        display.success(f"  Plot {plot['id']}: Harvested {food['name']} x{food.get('quantity', 1)}")
                        if utility:
                            for _ in range(utility.get("quantity", 1)):
                                self.steward.add_to_inventory(utility["id"])
                            display.success(f"  Byproduct: {utility['name']} x{utility.get('quantity', 1)}")
                        harvested_any = True
            if not harvested_any:
                display.narrate("Nothing ready to harvest.")
            return

        # Harvest specific plot
        plot_num = " ".join(args).strip()
        try:
            plot_id = int(plot_num)
        except ValueError:
            display.error("HARVEST [plot number] — specify which plot, or just HARVEST for all.")
            return

        plot = self.skerry.get_plot(plot_id)
        if not plot:
            display.error(f"No plot {plot_id}.")
            return
        if not farming.is_harvestable(plot):
            if plot.get("plant"):
                plant = plot["plant"]
                display.narrate(f"Plot {plot_id}: {plant['name']} — {plant['growth']}/{plant['growth_needed']} growth. Not ready.")
            else:
                display.narrate(f"Plot {plot_id} is empty.")
            return

        result = farming.harvest_plot(plot, self.state["day"])
        if result:
            food, utility = result
            farming.add_to_stores(self.skerry.food_stores, food, self.state["day"])
            display.success(f"Harvested {food['name']} x{food.get('quantity', 1)} → food stores")
            self._log_event("harvest", comic_weight=2,
                            plot=plot_id, food=food["name"],
                            quantity=food.get("quantity", 1))
            if utility:
                for _ in range(utility.get("quantity", 1)):
                    self.steward.add_to_inventory(utility["id"])
                display.success(f"Byproduct: {utility['name']} x{utility.get('quantity', 1)}")

    def cmd_survey(self, args):
        """Survey all garden plots."""
        if not self.skerry.has_structure("garden"):
            display.error("No garden built. Build one first.")
            return
        plots = self.skerry.get_garden_plots()
        display.display_plot_survey(plots, self.state["day"])

    def cmd_uproot(self, args):
        """Remove a plant from a garden plot."""
        if not self.skerry.has_structure("garden"):
            display.error("No garden built.")
            return
        if not args:
            display.error("Uproot what? UPROOT <plot number>")
            return
        try:
            plot_id = int(args[0])
        except ValueError:
            display.error("UPROOT <plot number>")
            return

        plot = self.skerry.get_plot(plot_id)
        if not plot:
            display.error(f"No plot {plot_id}.")
            return
        if not plot.get("plant"):
            display.narrate(f"Plot {plot_id} is already empty.")
            return

        plant_name = plot["plant"].get("name", "the plant")
        plot["plant"] = None
        display.narrate(f"Uprooted {plant_name} from plot {plot_id}.")
        self._log_event("plant_uprooted", comic_weight=1,
                        specimen=plant_name, plot=plot_id)

    def cmd_select(self, args):
        """Selective breeding: shift a trait on a planted specimen."""
        if not self.skerry.has_structure("garden"):
            display.error("No garden built.")
            return
        if len(args) < 3:
            display.error("SELECT <plot> FOR <trait>  (e.g., SELECT 1 FOR yield)")
            return

        # Parse: SELECT <plot_num> FOR <trait>
        try:
            plot_id = int(args[0])
        except ValueError:
            display.error("SELECT <plot number> FOR <trait>")
            return

        # Skip "for" keyword if present
        trait_args = args[1:]
        if trait_args and trait_args[0] == "for":
            trait_args = trait_args[1:]
        if not trait_args:
            display.error("SELECT <plot> FOR <trait>")
            return
        trait_name = trait_args[0].lower()

        plot = self.skerry.get_plot(plot_id)
        if not plot or not plot.get("plant"):
            display.error(f"Nothing planted in plot {plot_id}.")
            return

        plant = plot["plant"]
        allowed = farming.get_allowed_breeding(plant["specimen_type"])
        if "select" not in allowed:
            display.error(f"{plant['name']} ({plant['specimen_type']}) doesn't support SELECT.")
            return

        if farming.select_for_trait(plant, trait_name):
            pair = farming.get_trait_pair(trait_name)
            new_val = plant["traits"][pair[0]]
            opp_val = plant["traits"][pair[1]]
            display.success(f"Selected {plant['name']} for {trait_name}.")
            display.info(f"  {pair[0]}: {new_val}  |  {pair[1]}: {opp_val}")
            display.info("  Effect applies at next harvest.")
            self._log_event("selective_breed", comic_weight=2,
                            specimen=plant["name"], trait=trait_name,
                            plot=plot_id)
        else:
            display.error(f"Unknown trait '{trait_name}' or already maxed. Valid: yield, defense, speed, nutrition, specialist, generalist, uniformity, diversity, edible, utility")

    def cmd_clone(self, args):
        """Clone a cutting or transplant specimen."""
        if not self.skerry.has_structure("garden"):
            display.error("No garden built.")
            return
        if not args:
            display.error("CLONE <plot number>")
            return
        try:
            plot_id = int(args[0])
        except ValueError:
            display.error("CLONE <plot number>")
            return

        plot = self.skerry.get_plot(plot_id)
        if not plot or not plot.get("plant"):
            display.error(f"Nothing planted in plot {plot_id}.")
            return

        plant = plot["plant"]
        allowed = farming.get_allowed_breeding(plant["specimen_type"])
        if "clone" not in allowed:
            display.error(f"{plant['name']} ({plant['specimen_type']}) doesn't support CLONE.")
            return

        clone = farming.clone_plant(plant)
        # Store the clone as a specimen in inventory (plantable later)
        self.steward.add_to_inventory(plant["specimen_id"])
        display.success(f"Cloned {plant['name']}. Specimen added to inventory.")
        if plant["traits"].get("uniformity", 5) >= 7:
            display.warning("  Warning: High uniformity — clones share all vulnerabilities.")

    def _handle_cross_pollinate(self, args):
        """Handle CROSS-POLLINATE command."""
        if not self.skerry.has_structure("garden"):
            display.error("No garden built.")
            return
        if len(args) < 3:
            display.error("CROSS-POLLINATE <plot> WITH <plot>  (e.g., CROSS 1 WITH 3)")
            return

        try:
            plot_a_id = int(args[0])
        except ValueError:
            display.error("CROSS-POLLINATE <plot number> WITH <plot number>")
            return

        # Skip "with" keyword
        remaining = args[1:]
        if remaining and remaining[0] == "with":
            remaining = remaining[1:]
        if not remaining:
            display.error("CROSS-POLLINATE <plot> WITH <plot>")
            return

        try:
            plot_b_id = int(remaining[0])
        except ValueError:
            display.error("CROSS-POLLINATE <plot number> WITH <plot number>")
            return

        plot_a = self.skerry.get_plot(plot_a_id)
        plot_b = self.skerry.get_plot(plot_b_id)

        if not plot_a or not plot_a.get("plant"):
            display.error(f"Nothing planted in plot {plot_a_id}.")
            return
        if not plot_b or not plot_b.get("plant"):
            display.error(f"Nothing planted in plot {plot_b_id}.")
            return

        plant_a = plot_a["plant"]
        plant_b = plot_b["plant"]

        can, reason = farming.can_cross_pollinate(plant_a, plant_b)
        if not can:
            display.error(reason)
            return

        # Cross-pollinate: sacrifice both harvests, produce offspring seeds
        offspring = farming.cross_pollinate(plant_a, plant_b)

        # Clear both plots
        plot_a["plant"] = None
        plot_b["plant"] = None

        display.success(f"Cross-pollinated {plant_a['name']} with {plant_b['name']}.")
        display.narrate(f"  Both plants sacrificed. Produced {len(offspring)} new seed{'s' if len(offspring) != 1 else ''}.")
        self._log_event("cross_pollinate", comic_weight=3,
                        parent_a=plant_a["name"], parent_b=plant_b["name"],
                        offspring_count=len(offspring))

        # Add offspring to seed vault or inventory
        for child in offspring:
            # Store as their parent specimen_id (plantable)
            self.steward.add_to_inventory(child["specimen_id"])
            display.info(f"  New seed: {child['name']} (Gen {child['generation']})")

        if reason and "reduced fertility" in reason.lower():
            display.warning(f"  {reason}")

    def cmd_bank(self, args):
        """Store a specimen in the seed vault for safekeeping."""
        if not self.skerry.has_structure("storehouse"):
            display.error("No storehouse built — need a seed vault to bank specimens.")
            return
        if not args:
            display.error("BANK <plot number> — store that plant's genetics in the vault.")
            return

        try:
            plot_id = int(args[0])
        except ValueError:
            display.error("BANK <plot number>")
            return

        plot = self.skerry.get_plot(plot_id)
        if not plot or not plot.get("plant"):
            display.error(f"Nothing planted in plot {plot_id}.")
            return

        plant = plot["plant"]
        entry = farming.bank_specimen(self.skerry.seed_vault, plant)
        display.success(f"Banked {entry['name']} (Gen {entry['generation']}) in the seed vault.")
        self._log_event("specimen_banked", comic_weight=1,
                        specimen=entry["name"], generation=entry["generation"])
        display.info("  The plant remains in the plot. Use WITHDRAW to retrieve banked specimens.")

    def cmd_withdraw(self, args):
        """Retrieve a specimen from the seed vault."""
        if not self.skerry.has_structure("storehouse"):
            display.error("No storehouse built.")
            return
        if not args:
            display.display_seed_vault(self.skerry.seed_vault)
            display.info("  WITHDRAW <number> to retrieve a specimen.")
            return

        try:
            index = int(args[0]) - 1  # 1-indexed display
        except ValueError:
            display.error("WITHDRAW <number> from the vault list.")
            return

        entry = farming.withdraw_specimen(self.skerry.seed_vault, index)
        if entry:
            self.steward.add_to_inventory(entry["specimen_id"])
            display.success(f"Withdrew {entry['name']} from the seed vault. Added to inventory.")
            self._log_event("specimen_withdrawn", comic_weight=1,
                            specimen=entry["name"])
        else:
            display.error("Invalid vault entry number. CHECK VAULT to see available specimens.")
