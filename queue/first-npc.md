# First NPC Playtest — Remaining Issues

## UX / Polish

### Redundant GREET + RECRUIT prompts
When meeting an NPC for the first time, both prompts fire simultaneously:
```
✧ GREET them — they might know something useful.
▶ RECRUIT DAX to bring them to the skerry.
```
The recruit prompt should come AFTER Dax replies to the greet, not alongside it.

### Redundant "exceptional" + "flawless" on perfect recruit
A perfect recruit run shows both "exceptional conversation" and "flawless conversation" messages back to back. Feels repetitive. Also need to build in trouble aspects for recruits.

### No first-visit hint for new buildings
Walking into the Workshop for the first time gives no suggestions about what you can do there. Should nudge toward CRAFT or relevant commands.

### Contest doesn't show your skill values
In the Prove Your Worth contest, the tactic menu shows:
```
1. Appeal to Evidence       (Rapport)
2. Appeal to Emotion        (Empathy)
3. Show, Don't Tell         (Crafts)
```
But doesn't show your actual skill values. Should display them so you can make an informed choice. Also can't STAT or PROBE during the contest — should be allowed.

### CHECK SKERRY needs breakdowns
Currently one big dump. Should support subcommands like CHECK SKERRY POPULATION, CHECK SKERRY BUILDINGS, CHECK SKERRY TASKS. Should also show which NPCs aren't settled yet.

## Design Questions

### Tool dispute creates items from nothing
The "Tool Dispute" challenge encounter awards Basic Tools on step 3 success without checking if materials exist in junkyard/inventory/storehouse. Should it require materials? And should the player need to GIVE TOOLS to the NPC afterward?

yes, it should require materials. and the player should get a prompt to do it, and the dispute resolves on ensuring both characters have tools. 

### Craft supplies auto-crafts
NPCs assigned to crafting auto-craft common items without Miria's direction. Should need a manual crafting queue — e.g., "always keep 2 bandages on hand."

yes. and guidance on how to set it up the first time entering the relevant buildings! 

### DROP ALL keeps some items
`drop all` should drop EVERYTHING even if it's an artifact or specimen, unless the artifact has been explicitly KEPT. 

## Bugs (not yet investigated)

### MAP wrong in Coral Thicket
The zone map display doesn't match the actual room layout. Needs investigation.

### Dax not doing junkyard tasks
Dax was assigned to salvage in the junkyard but doesn't seem to be producing anything at day transition. Needs investigation.
