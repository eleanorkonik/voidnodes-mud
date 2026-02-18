"""WorldSeed model — the baby world seed that anchors the skerry."""

import random


# Internal growth stages drive mechanics (communication, aspects, unlocks)
# but are not exposed to the player — they just see motes toward maturation.
_STAGE_COUNT = 5
MATURATION_THRESHOLD = 300  # total motes fed to reach maturity

# World seed communication flavor by growth stage.
# {seed_name} is substituted at runtime via communicate().
FEELINGS = {
    0: [  # Baby — colors and feelings
        "A warm pulse of golden light.",
        "A faint shiver of pale blue unease.",
        "A soft green contentment radiates from below.",
        "An eager orange flicker, like hunger.",
        "A gentle lavender drowsiness.",
    ],
    1: [  # Tendril — sensations
        "You feel {seed_name} reaching, stretching, testing the edges of the skerry.",
        "A vibration through your feet — {seed_name} is excited.",
        "{seed_name} tugs gently at your awareness, wanting attention.",
        "The ground feels warmer where {seed_name}'s roots spread.",
        "A faint hum rises from {seed_name}'s hollow, almost musical.",
    ],
    2: [  # Aura — images
        "An image flashes in your mind: the skerry seen from above, glowing.",
        "You briefly see through {seed_name}'s awareness — every root, every stone.",
        "A mental picture of a great tree appears, then fades. {seed_name} dreams.",
        "{seed_name} shows you a memory: a void-whale passing far overhead.",
        "A fleeting vision of rain falling on leaves that don't exist yet.",
    ],
    3: [  # Canopy — words
        "A whisper at the edge of thought: 'Safe. Home. Growing.'",
        "{seed_name} murmurs wordlessly — you understand it means 'thank you.'",
        "'More,' {seed_name}'s presence suggests. 'Bring more. We grow.'",
        "A sleepy thought drifts up from below: 'Good day. Rest now.'",
        "{seed_name} thinks at you: 'Others coming. Can feel them. Far away.'",
    ],
    4: [  # Beacon — conversation
        "{seed_name} speaks clearly in your mind: 'I can feel other seeds, far across the void. We are not alone.'",
        "'The skerry strengthens,' {seed_name} says. 'Soon we will be a place worth finding.'",
        "'I remember the ship I came from,' {seed_name} muses. 'It was vast. We will be vast again.'",
        "'Protect the others,' {seed_name} asks gently. 'They are fragile but they matter.'",
        "'When I was small, I only knew light and dark. Now I know names. Yours is my favorite.'",
    ],
}


class WorldSeed:
    def __init__(self, data):
        self.motes = data.get("motes", 15)
        self.growth_stage = data.get("growth_stage", 0)
        self.stage_thresholds = data.get("stage_thresholds", [0, 30, 75, 150, 300])
        self.total_motes_fed = data.get("total_motes_fed", 0)
        self.aspects = list(data.get("aspects", ["Baby Seed With Perfect Memory", "Hungry for Motes"]))
        self.stress = list(data.get("stress", [False, False]))
        self.alive = data.get("alive", True)

    def feed(self, mote_amount):
        """Feed motes to the world seed. Returns (new_total, stage_changed)."""
        self.motes += mote_amount
        self.total_motes_fed += mote_amount

        old_stage = self.growth_stage
        # Check for stage advancement
        while (self.growth_stage < len(self.stage_thresholds) - 1 and
               self.total_motes_fed >= self.stage_thresholds[self.growth_stage + 1]):
            self.growth_stage += 1
            self._apply_stage_growth()

        stage_changed = self.growth_stage > old_stage
        return self.motes, stage_changed

    def spend_motes(self, amount):
        """Spend motes (for extraction, etc). Returns True if enough motes."""
        if self.motes >= amount:
            self.motes -= amount
            if self.motes <= 0:
                self.alive = False
            return True
        return False

    def extraction_cost(self, extraction_count):
        """Calculate extraction cost: 5 base + 2 per previous extraction."""
        return 5 + (2 * extraction_count)

    def communicate(self, name="Tuft"):
        """Get a random world seed communication based on growth stage."""
        messages = FEELINGS.get(self.growth_stage, FEELINGS[0])
        msg = random.choice(messages)
        return msg.format(seed_name=name)

    def _apply_stage_growth(self):
        """Apply changes when the world seed reaches a new growth stage."""
        stage = self.growth_stage
        if stage == 1:  # Tendril
            self.aspects = ["Growing Seed Anchoring the Skerry", "Hungry for Motes"]
            self.stress = [False, False, False]  # +1 stress box
        elif stage == 2:  # Aura
            self.aspects = ["Protective Seed With Growing Awareness", "Connection to the Void"]
        elif stage == 3:  # Voyager
            self.aspects = ["World Seed Shaping the Skerry", "Voice of the Green"]
        elif stage == 4:  # Sun
            self.aspects = ["World Seed With Its Own Magic Field", "Memory of a World"]

    def to_dict(self):
        """Serialize to dict."""
        return {
            "motes": self.motes,
            "growth_stage": self.growth_stage,
            "stage_thresholds": self.stage_thresholds,
            "total_motes_fed": self.total_motes_fed,
            "aspects": self.aspects,
            "stress": self.stress,
            "alive": self.alive,
        }
