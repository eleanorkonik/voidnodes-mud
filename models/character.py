"""Character model — skills, aspects, stress, consequences, fate points."""

BODY_SLOTS = ["head", "torso", "legs", "feet", "hands"]


class Character:
    def __init__(self, data):
        self.name = data["name"]
        self.aspects = data["aspects"]  # {high_concept, trouble, other: []}
        self.skills = dict(data["skills"])  # {skill_name: value}
        self.stress = list(data["stress"])  # [False, False, False]
        # Consequences: lists of {text, greyed} dicts per severity
        raw_cons = data["consequences"]
        self.consequences = {}
        for sev in ("mild", "moderate", "severe"):
            val = raw_cons.get(sev)
            if val is None:
                self.consequences[sev] = []
            elif isinstance(val, str):
                self.consequences[sev] = [{"text": val, "greyed": False}]
            else:
                self.consequences[sev] = list(val)
        self.fate_points = data["fate_points"]
        self.refresh = data["refresh"]
        self.inventory = list(data.get("inventory", []))
        self.worn = dict(data.get("worn", {}))
        self.slot_capacity = dict(data.get("slot_capacity", {"large": 1, "medium": 2, "small": 20}))

    def get_skill(self, skill_name):
        """Get skill value by name (case-insensitive). Returns 0 if not found."""
        for name, value in self.skills.items():
            if name.lower() == skill_name.lower():
                return value
        return 0

    def get_skill_name(self, skill_name):
        """Get the canonical skill name (case-insensitive). Returns None if not found."""
        for name in self.skills:
            if name.lower() == skill_name.lower():
                return name
        return None

    def take_stress(self, shifts):
        """Try to absorb stress. Returns remaining shifts that weren't absorbed.

        Stress boxes absorb exactly their value (box 0 = 1 shift, box 1 = 2, box 2 = 3).
        Pick the lowest box that can absorb the remaining shifts.
        """
        if shifts <= 0:
            return 0

        for i in range(len(self.stress)):
            box_value = i + 1
            if not self.stress[i] and box_value >= shifts:
                self.stress[i] = True
                return 0

        # No single box can absorb it — check if we can use one + consequence
        # Actually in FATE, you use ONE stress box + consequences, not multiple boxes
        # Try each box and see if consequence can cover the rest
        best_option = None
        for i in range(len(self.stress)):
            box_value = i + 1
            if not self.stress[i]:
                remaining = shifts - box_value
                if remaining >= 0 and (best_option is None or box_value < best_option[1]):
                    best_option = (i, box_value, remaining)

        if best_option:
            self.stress[best_option[0]] = True
            return best_option[2]

        # No stress boxes available
        return shifts

    def take_consequence(self, shifts):
        """Try to absorb shifts with a consequence. Returns (remaining_shifts, severity_used).

        Consequences: mild (-2), moderate (-4), severe (-6).
        Wounds stack at natural severity — no slot cap, no overflow cascade.
        """
        consequence_values = {"mild": 2, "moderate": 4, "severe": 6}
        severities = ["mild", "moderate", "severe"]

        # Find the natural severity (lowest that can absorb all shifts)
        for sev in severities:
            if consequence_values[sev] >= shifts:
                self.consequences[sev].append({"text": "Pending", "greyed": False})
                return (0, sev)

        # Shifts exceed even severe — take severe for partial absorption
        self.consequences["severe"].append({"text": "Pending", "greyed": False})
        return (max(0, shifts - consequence_values["severe"]), "severe")

    def apply_damage(self, shifts):
        """Apply damage: try stress first, then consequences.

        Returns (taken_out: bool, severity_used: str|None).
        severity_used is the consequence tier taken (if any), for extraction checks.
        """
        if shifts <= 0:
            return False, None

        remaining = self.take_stress(shifts)
        if remaining > 0:
            remaining, severity_used = self.take_consequence(remaining)
            return remaining > 0, severity_used
        return False, None

    def is_taken_out(self):
        """Check if all stress boxes are full (consequences always have room now)."""
        return all(self.stress)

    def clear_stress(self):
        """Clear all stress boxes (happens after a conflict ends)."""
        self.stress = [False] * len(self.stress)

    def heal_consequence(self, severity, index=0):
        """Remove a consequence entry at the given index from the severity list."""
        entries = self.consequences.get(severity, [])
        if 0 <= index < len(entries):
            entries.pop(index)

    def spend_fate_point(self):
        """Spend a fate point. Returns True if successful."""
        if self.fate_points > 0:
            self.fate_points -= 1
            return True
        return False

    def gain_fate_point(self):
        """Gain a fate point (from compels, conceding, etc.)."""
        self.fate_points += 1

    def refresh_fate_points(self):
        """Reset fate points to refresh value at start of session (if below refresh)."""
        self.fate_points = max(self.fate_points, self.refresh)

    def get_all_aspects(self):
        """Return all character aspects as a flat list (including greyed wounds)."""
        aspects = [self.aspects["high_concept"], self.aspects["trouble"]]
        aspects.extend(self.aspects.get("other", []))
        for severity, entries in self.consequences.items():
            for entry in entries:
                aspects.append(f"{entry['text']} ({severity})")
        return aspects

    def add_to_inventory(self, item_id):
        """Add an item to inventory."""
        self.inventory.append(item_id)

    def remove_from_inventory(self, item_id):
        """Remove an item from inventory. Returns True if found and removed."""
        if item_id in self.inventory:
            self.inventory.remove(item_id)
            return True
        return False

    def has_item(self, item_id):
        """Check if character has an item."""
        return item_id in self.inventory

    def wear_item(self, item_id, slot):
        """Equip an item from inventory to a body slot. Returns False if slot occupied or item not in inventory."""
        if item_id not in self.inventory:
            return False
        if self.worn.get(slot):
            return False
        self.inventory.remove(item_id)
        self.worn[slot] = item_id
        return True

    def remove_worn(self, slot):
        """Unequip an item from a body slot, returning it to inventory. Returns item_id or None."""
        item_id = self.worn.get(slot)
        if not item_id:
            return None
        self.worn[slot] = None
        self.inventory.append(item_id)
        return item_id

    def get_worn_item(self, slot):
        """Return item_id worn in a slot, or None."""
        return self.worn.get(slot)

    def get_all_worn(self):
        """Return {slot: item_id} for occupied slots only."""
        return {slot: item_id for slot, item_id in self.worn.items() if item_id}

    def find_worn_by_item(self, item_id):
        """Return the slot name an item is worn in, or None."""
        for slot, worn_id in self.worn.items():
            if worn_id == item_id:
                return slot
        return None

    def to_dict(self):
        """Serialize to dict for saving."""
        return {
            "name": self.name,
            "aspects": self.aspects,
            "skills": self.skills,
            "stress": self.stress,
            "consequences": self.consequences,
            "fate_points": self.fate_points,
            "refresh": self.refresh,
            "inventory": self.inventory,
            "worn": self.worn,
            "slot_capacity": self.slot_capacity,
        }
