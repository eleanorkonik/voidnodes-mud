"""Skerry state — the home base, expandable island in the void."""

from models.room import Room
from engine import farming


class Skerry:
    def __init__(self, data):
        self.rooms = {r["id"]: Room(r) for r in data.get("rooms", [])}
        self.expandable = data.get("expandable_rooms", [])
        self.structures = list(data.get("structures_built", []))
        self.npc_houses = dict(data.get("npc_houses", {}))  # {npc_id: house_level}
        self.food_stores = list(data.get("food_stores", []))
        # Gardens: {room_id: {"plots": [...], "max_plots": N}}
        # Migrate legacy single-garden format
        if "gardens" in data:
            self.gardens = dict(data["gardens"])
        elif "garden" in data:
            old = data["garden"]
            if old.get("plots"):
                self.gardens = {"skerry_garden": old}
            else:
                self.gardens = {}
        else:
            self.gardens = {}
        self.seed_vault = list(data.get("seed_vault", []))
        self.dynamic_aspects = list(data.get("dynamic_aspects", []))

    def get_room(self, room_id):
        """Get a skerry room by ID."""
        return self.rooms.get(room_id)

    def get_all_rooms(self):
        """Get all skerry rooms."""
        return list(self.rooms.values())

    def population_cap(self):
        """Total population the skerry can support: room count + barracks spaces."""
        barracks = sum(r.barracks_spaces for r in self.rooms.values())
        return len(self.rooms) + barracks

    def has_structure(self, structure_name):
        """Check if a structure exists — built via build_room() or part of starting rooms."""
        if structure_name in self.structures:
            return True
        return any(structure_name in r.structures for r in self.rooms.values())

    def can_build(self, room_template, inventory_counts, npc_count, seed_stage):
        """Check if an expandable room can be built."""
        requires = room_template.get("requires", {})

        # Check materials
        for mat, needed in requires.get("materials", {}).items():
            if inventory_counts.get(mat, 0) < needed:
                return False, f"Need {needed}x {mat.replace('_', ' ')}"

        # Check NPC count
        if npc_count < requires.get("npcs", 0):
            return False, f"Need at least {requires['npcs']} NPCs on the skerry"

        # Check world seed stage
        if seed_stage < requires.get("seed_stage", 0):
            return False, f"World seed must reach stage {requires['seed_stage']}"

        # Check any_specimen requirement (garden needs at least 1 specimen in inventory)
        if requires.get("any_specimen", 0) > 0:
            specimen_count = sum(1 for item_id in inventory_counts
                                if farming.is_specimen(item_id) and inventory_counts[item_id] > 0)
            if specimen_count < requires["any_specimen"]:
                return False, f"Need at least {requires['any_specimen']} specimen(s) to plant"

        return True, "Can build"

    def build_room(self, room_template):
        """Add an expandable room to the skerry."""
        import copy
        room_data = copy.deepcopy(room_template)
        room_data["discovered"] = True
        room_data["items"] = []
        room_data["npcs"] = []
        room_data["enemies"] = []

        # For additional gardens, generate a unique room ID
        is_garden = "garden" in room_data.get("structures", [])
        if is_garden and room_data["id"] in self.rooms:
            # Building another garden — give it a unique ID
            garden_num = sum(1 for rid in self.rooms if rid.startswith("skerry_garden")) + 1
            room_data["id"] = f"skerry_garden_{garden_num}"
            room_data["name"] = f"Garden ({garden_num})"

        # Set up exits
        exits = dict(room_data.get("exits", {}))
        room_data["exits"] = exits

        room = Room(room_data)
        self.rooms[room.id] = room

        # Connect to existing rooms
        for target_id, direction in room_template.get("connect_to", {}).items():
            if target_id in self.rooms:
                self.rooms[target_id].exits[direction] = room.id

        self.structures.append(room_data.get("structures", [None])[0])

        # Initialize garden plots if this is a garden
        if "garden" in room_data:
            garden_data = room_data["garden"]
            # Assign globally unique plot IDs
            max_plot_id = self._max_plot_id()
            for i, plot in enumerate(garden_data["plots"]):
                plot["id"] = max_plot_id + i + 1
            self.gardens[room.id] = garden_data

        # Remove from expandable list (except garden — allow re-building)
        if not is_garden:
            self.expandable = [r for r in self.expandable if r["id"] != room_data["id"]]

        return room

    def build_npc_house(self, npc_id):
        """Build or upgrade an NPC's house. 0=none, 1=tent, 2=house."""
        current = self.npc_houses.get(npc_id, 0)
        if current < 2:
            self.npc_houses[npc_id] = current + 1
            return self.npc_houses[npc_id]
        return current

    def get_house_level(self, npc_id):
        """Get NPC house level. 0=none, 1=tent, 2=house."""
        return self.npc_houses.get(npc_id, 0)

    def get_garden_plots(self):
        """Get all garden plots across all gardens."""
        all_plots = []
        for garden in self.gardens.values():
            all_plots.extend(garden.get("plots", []))
        return all_plots

    def get_garden_plots_for_room(self, room_id):
        """Get plots for a specific garden room. Returns [] if not a garden."""
        garden = self.gardens.get(room_id)
        if garden:
            return garden.get("plots", [])
        return []

    def get_garden_for_room(self, room_id):
        """Get the garden data dict for a specific room, or None."""
        return self.gardens.get(room_id)

    def get_plot(self, plot_id):
        """Get a specific garden plot by ID, searching all gardens."""
        for garden in self.gardens.values():
            for plot in garden.get("plots", []):
                if plot["id"] == plot_id:
                    return plot
        return None

    def _max_plot_id(self):
        """Return the highest plot ID across all gardens, or 0."""
        max_id = 0
        for garden in self.gardens.values():
            for plot in garden.get("plots", []):
                if plot["id"] > max_id:
                    max_id = plot["id"]
        return max_id

    def garden_at_max(self, room_id):
        """Check if a garden room is at its max plot count (20)."""
        garden = self.gardens.get(room_id)
        if not garden:
            return False
        return len(garden.get("plots", [])) >= 20

    def all_gardens_at_max(self):
        """Check if ALL garden rooms are at 20 plots."""
        if not self.gardens:
            return False
        return all(len(g.get("plots", [])) >= 20 for g in self.gardens.values())

    def to_dict(self):
        """Serialize to dict."""
        return {
            "rooms": [r.to_dict() for r in self.rooms.values()],
            "expandable_rooms": self.expandable,
            "structures_built": self.structures,
            "npc_houses": self.npc_houses,
            "food_stores": self.food_stores,
            "gardens": self.gardens,
            "seed_vault": self.seed_vault,
            "dynamic_aspects": self.dynamic_aspects,
        }
