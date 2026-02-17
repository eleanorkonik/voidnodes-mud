"""FATE dice system — 4dF rolls, skill checks, opposed rolls."""

import random


def roll_4df():
    """Roll 4 Fudge dice. Each die is -1, 0, or +1. Returns list of 4 results."""
    return [random.choice([-1, 0, 1]) for _ in range(4)]


def roll_total():
    """Roll 4dF and return the sum (-4 to +4)."""
    return sum(roll_4df())


def skill_check(skill_value, difficulty=0):
    """Roll skill + 4dF against a difficulty.

    Returns (total, shifts, dice) where:
        total = skill + dice roll
        shifts = total - difficulty (positive = success)
        dice = the raw 4dF results
    """
    dice = roll_4df()
    total = skill_value + sum(dice)
    shifts = total - difficulty
    return total, shifts, dice


def opposed_roll(attacker_skill, defender_skill):
    """Two opposed skill rolls. Returns (attacker_total, defender_total, shifts, atk_dice, def_dice).

    Positive shifts = attacker wins. Negative = defender wins. Zero = tie.
    """
    atk_dice = roll_4df()
    def_dice = roll_4df()
    atk_total = attacker_skill + sum(atk_dice)
    def_total = defender_skill + sum(def_dice)
    shifts = atk_total - def_total
    return atk_total, def_total, shifts, atk_dice, def_dice


def dice_to_str(dice):
    """Format dice results as symbols: + 0 - """
    symbols = {-1: "-", 0: "0", 1: "+"}
    return " ".join(symbols[d] for d in dice)


def roll_description(dice, skill_value, skill_name=None):
    """Format a complete roll description for display."""
    total = skill_value + sum(dice)
    dice_str = dice_to_str(dice)
    roll_part = f"[{dice_str}] = {sum(dice):+d}"
    if skill_name:
        return f"{skill_name} ({skill_value:+d}) {roll_part} → Total: {total:+d}"
    return f"Skill ({skill_value:+d}) {roll_part} → Total: {total:+d}"
