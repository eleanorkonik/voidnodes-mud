# Colony Farm Plant Breeding: A MUD Design Document

## The Core Fantasy

You're running a farm for a colony that needs things from plants: food, medicine, fiber, fuel, building material, pest repellent, maybe even defensive compounds. Your seed stock is whatever weird stuff scavengers drag back from abandoned outposts, ruined greenhouses, feral overgrowth, and alien biomes. None of it is optimized for your conditions. Everything is a tradeoff. Your job is to domesticate the alien wilderness into something that keeps people alive — and every generation of selective breeding that makes a plant more *useful* also makes it more *fragile* in ways you didn't anticipate.

---

## Why Plant Breeding Is Fundamentally Different From Animal Breeding

Most game breeding systems are designed around animals, and they miss what makes plants mechanically interesting as a design space:

**Plants don't move.** They compete for light, water, and soil nutrients in place. This means *where you plant something matters as much as what you plant.* Adjacent plants interact — companion planting, allelopathy (chemical warfare between root systems), canopy shading, nitrogen fixing. Animal breeding is about individual specimens; plant breeding is about *populations in spatial relationships.*

**Plants reproduce weirdly.** Self-pollination, cross-pollination, clonal propagation via cuttings, grafting one variety's rootstock onto another's fruiting body, polyploidy (chromosome doubling that creates instant new species). Each method has different genetic consequences. Clones are genetically identical — fast, reliable, but dangerously uniform. Sexual reproduction shuffles genes — slow, unpredictable, but generates the diversity you need to adapt.

**Plants are infrastructure, not companions.** You don't name your wheat. A plant's value is systemic — what it does for the colony's food supply, its pharmacy, its defenses, its trade economy. This means breeding decisions are resource allocation decisions at the colony level, not individual optimization puzzles.

**Domestication has real costs.** This is the big one from real-world plant science, and it's the key to making the whole system work as a game. Every time humans have domesticated a wild plant, we've traded away survival traits for utility traits. Bigger seeds mean plants can't disperse themselves. Higher yield means weaker disease resistance. Better taste means fewer defensive toxins. Reduced seed dormancy means easier planting but catastrophic vulnerability to untimely frost. The domestication syndrome is a Pareto frontier made of thousands of years of tradeoffs — and your colony is trying to compress that process into seasons instead of millennia.

---

## The Domestication Tradeoff Engine

This is the core mechanic. Every plant has traits organized into **opposed axes** where improvement on one side degrades the other. These aren't arbitrary game-balance penalties — they're modeled on real plant biology where the underlying resource allocation is genuinely zero-sum.

### Axis 1: Yield vs. Defense

The most fundamental tradeoff in all of plant biology. Plants allocate finite metabolic resources between growth/reproduction and chemical/physical defenses. Wild plants from scavenging runs are tough, bitter, thorny, low-yield, and resistant to everything. Colony-bred cultivars are tender, nutritious, high-yield, and vulnerable to pests and disease.

**Game mechanic:** Every plant has a YIELD score and a DEFENSE score on opposite ends of a shared resource pool. Breeding for higher yield *necessarily* reduces defense. A plant with YIELD 8 / DEFENSE 2 produces abundant food but is devastated by blight events. A plant with YIELD 2 / DEFENSE 8 barely feeds anyone but survives everything you throw at it.

**The decision:** When raiders are burning your fields, you need fast-growing high-yield crops to rebuild food stores. When a fungal plague sweeps through, you wish you'd kept more wild genetics in your seed bank. You can't prepare for both simultaneously.

### Axis 2: Speed vs. Nutrition

Fast-growing plants produce more harvests per season but with lower nutritional density. Slow-growing plants concentrate more nutrients but tie up field space longer.

**Game mechanic:** GROWTH RATE and NUTRIENT DENSITY are inversely correlated. A fast crop might give you three harvests per season at 40 nutrition each (120 total) while a slow crop gives one harvest at 100 nutrition. The math *seems* to favor the fast crop — until you factor in that each planting cycle costs labor, water, seed stock, and soil nutrients. And the slow crop might produce medicinal compounds the fast one can't.

**The decision:** The colony is starving *right now* and needs calories today, or the colony has enough calories but people are getting scurvy/bone-weak/mentally foggy because their diet lacks specific nutrients only found in slow-growing deep-root plants.

### Axis 3: Specialist vs. Generalist

Plants adapted to specific conditions outperform generalists in those conditions but fail catastrophically outside them.

**Game mechanic:** Environmental adaptation traits (cold tolerance, drought resistance, shade tolerance, salt tolerance, altitude adaptation) each have a cost in the general vigor pool. A plant bred for perfect performance in your colony's current conditions will die if those conditions change. A generalist survives anything but excels at nothing.

**The decision:** Your colony is in a temperate river valley. Do you breed plants perfectly adapted to this specific microclimate (maximum short-term yield), or maintain broad genetic diversity against the possibility of climate shifts, forced relocation, or the need to trade seed stock with colonies in different biomes?

### Axis 4: Uniformity vs. Diversity

Uniform crops are predictable, easy to harvest, and compatible with standardized processing. Diverse populations resist disease, adapt to microclimates, and handle surprise stressors.

**Game mechanic:** You can pursue LANDRACE breeding (maintaining a genetically diverse population that averages lower yield but never catastrophically fails) or CULTIVAR breeding (selecting a single high-performing genotype that you propagate clonally for maximum consistency). Cultivars have higher peak performance. Landraces have higher floor performance.

**The decision:** The colony's food processing relies on uniform crop maturation — everything ripens at once for efficient harvest. But last season a rust pathogen wiped out 90% of your Cultivar-7 monoculture while the old landrace fields lost only 15%. Do you switch back to the messy, labor-intensive landrace system that requires hand-harvesting over weeks, or breed a new cultivar and hope the next pathogen targets something else?

### Axis 5: Edibility vs. Utility

Some plants are most valuable as food. Others produce fibers, building materials, fuel, medicinal compounds, dyes, adhesives, pest repellents, or alchemical reagents. Breeding for one set of outputs reduces the other.

**Game mechanic:** Plants have multiple potential OUTPUT CHANNELS. A wild specimen from an outpost might produce small amounts of food, fiber, and a medicinal sap. Breeding can amplify any one channel, but the plant's total metabolic budget is fixed. Maxing out food production reduces fiber yield to nothing. Maxing medicinal output makes the plant nearly inedible.

**The decision:** The colony needs rope. The colony also needs food. The same plant genus can provide both, but not both at maximum from the same cultivar. Do you dedicate field space to two specialized varieties, or keep one generalist that does both poorly?

---

## The Scavenging Pipeline: Where New Genetics Come From

Scavengers return from outpost runs with **specimens** — seeds, cuttings, tubers, spore samples, entire transplants. Each specimen is a package of unknown genetics from an environment the colony may never have encountered.

### Specimen Properties

Every specimen arrives with:

- **Origin biome** — determines which environmental adaptations it carries (desert outpost plants have drought tolerance but cold vulnerability; deep-cave specimens have shade tolerance but light sensitivity)
- **Domestication level** — how much prior human selection has occurred. Feral crops from abandoned greenhouses are partially domesticated (some yield, some defense). True wild specimens from overgrown ruins are high-defense, low-yield, but carry rare resistances. Lab specimens from research outposts might have exotic engineered traits with unknown side effects.
- **Compatibility group** — which existing colony plants it can cross-breed with. Not everything crosses with everything. Compatibility is tiered: same-group crosses are reliable, adjacent-group crosses are possible but produce sterile hybrids or reduced fertility, distant crosses require grafting instead of sexual reproduction.
- **Hidden traits** — recessive alleles, latent disease susceptibilities, allelopathic properties (suppresses nearby plants), or mutualistic properties (supports nearby plants) that only reveal through growing, breeding, or experimental planting.

### No Skill Gates — Full Information, Hard Choices

Every player can fully examine any specimen from the start. The complexity isn't in *unlocking* information — it's in *acting on it*. A complete trait readout doesn't tell you what to do with a plant any more than a complete stat sheet tells you how to build a baseball roster. The decision space is the game, not the grind to reach the decision space.

Hidden traits still exist — recessive alleles don't surface until offspring express them, allelopathic interactions only manifest when plants are actually grown near each other, and latent disease susceptibilities only appear when the pathogen shows up. But this is *situational* hiddenness (you haven't encountered the right conditions yet), not *skill-gated* hiddenness (you haven't leveled enough). The information is always there for anyone willing to do the experimental planting.

---

## The Breeding Actions

Players interact with the breeding system through a small set of high-consequence, low-frequency actions (as opposed to the fast-twitch combat loop or the daily farming maintenance loop).

### CROSS-POLLINATE [Plant A] [Plant B]

Sexual reproduction. Produces seeds with shuffled genetics from both parents. Outcome is probabilistic, influenced by both parents' genotypes plus random mutation chance. Takes one growing season to see results. 

**Tradeoff:** You sacrifice one harvest from both parent plants (they're spending metabolic energy on seed production instead of yield). The seeds are genetically unpredictable — you might get something great, something terrible, or something that looks great for two generations before a recessive homozygous disease susceptibility surfaces.

### SELECT [Field] [Trait Preference]

Mass selection across a genetically diverse planting. Instead of hand-picking individual parents, you harvest the entire field but save seeds only from plants expressing your desired trait. Gradual, low-risk, low-control.

**Tradeoff:** Slow. Takes many generations to move the population meaningfully. But it preserves genetic diversity within the population, maintaining disease resistance that targeted cross-breeding eliminates.

### CLONE [Plant] → CUTTING/GRAFT

Vegetative propagation. Produces genetically identical copies. Instant, reliable, no genetic surprises.

**Tradeoff:** Monoculture vulnerability. Every clone shares every disease susceptibility. Cloned populations can be wiped out in a single pathogen event. Also, vigor loss over successive clone generations (real phenomenon — accumulated viral load, epigenetic drift) means clones degrade over time and must be periodically refreshed from seed stock.

### GRAFT [Rootstock] [Scion]

Attach one plant's above-ground fruiting body to another plant's root system. The rootstock provides environmental adaptation (drought tolerance, soil pathogen resistance, nutrient access); the scion provides the desired fruit/seed/leaf output.

**Tradeoff:** Grafted plants don't breed true — their seeds carry rootstock genetics, scion genetics, or unpredictable combinations. You get the functional benefits of both plants in one specimen, but you can't propagate the combination sexually. Every grafted plant must be individually assembled. Labor-intensive, doesn't scale, but lets you combine traits that can't be combined through breeding.

### BACKCROSS [Cultivar] [Wild Specimen]

Introduce wild genetics back into a domesticated line. Used when a cultivar has been over-bred and lost disease resistance, environmental tolerance, or genetic diversity.

**Tradeoff:** You *will* lose yield. The wild genetics bring defense and resilience but drag yield and uniformity backward. It takes multiple generations of backcrossing to recover yield while retaining the new resistance — during which time you're feeding the colony from reduced harvests.

### BANK [Seeds/Specimen]

Store genetic material for future use. Requires storage infrastructure (seed vault, cold storage, preservation compounds).

**Tradeoff:** Storage space competes with other colony needs. Banked seeds degrade over time unless storage is maintained. But losing a seed line is permanent — if you don't bank the weird specimens scavengers bring back, and then discover you need that genetic material three seasons later, it's gone.

---

## Field Layout and Plant Interactions

Because plants are sessile, **spatial arrangement matters.** Fields aren't just containers for crops — they're ecosystems.

### Companion Planting

Certain plant combinations benefit each other when grown in adjacent plots:

- **Nitrogen fixers** (legume-analogues) enrich soil for neighboring heavy feeders
- **Pest-repellent aromatics** protect adjacent crops from insect damage
- **Deep-root / shallow-root pairs** access different soil layers without competing
- **Canopy stratification** — tall sun-lovers shade low-growing shade-tolerant crops, maximizing light use per plot

### Allelopathy (Chemical Warfare)

Some plants release compounds through their roots or leaf litter that suppress neighboring plants. This is a *discoverable* property — you only learn about it by observing reduced growth in adjacent plots once you've actually planted them near each other.

**Game application:** Allelopathic plants can be deliberately used as weed suppressors around field margins, but accidentally planting one next to a compatible crop destroys your yield. Wild specimens from outposts are more likely to be allelopathic (it's a survival trait) than domesticated ones.

### Soil Depletion and Rotation

Monoculture depletes specific soil nutrients. Planting the same crop in the same field season after season progressively reduces yield and increases disease pressure.

**Game mechanic:** Fields track nutrient levels across 3 categories (N/P/K analogues). Different crops consume different nutrient profiles. Crop rotation — alternating heavy feeders, light feeders, and soil-restorers — maintains productivity. Ignoring rotation means declining yields that eventually force fallow periods (field producing nothing for a full season to recover).

---

## Environmental Threats That Shift Optimal Breeding Strategy

The colony faces recurring threats that change what the farm needs to produce:

### Blight Events
Pathogen outbreaks that target specific genetic lineages. Monocultures are devastated. Diverse populations lose some plants but survive. Blight resistance can be bred for, but there are multiple blight strains, and resistance to one doesn't guarantee resistance to another.

**Breeding pressure:** Diversify genetics, maintain resistant wild lines, accept lower peak yield for higher floor yield.

### Environmental Changes
Shifts in the skerry's conditions — water table changes, soil chemistry drift, light pattern alterations from new construction or collapsed structures, introduction of new microorganisms from trade or scavenging, volcanic venting, tidal shifts. The environment isn't static, and plants bred for today's conditions may not suit tomorrow's.

**Breeding pressure:** Maintain generalist varieties alongside specialists. Bank specimens adapted to conditions you don't currently face — you might face them later.

### Pest Invasions
New pest species introduced from trade, migration, or outpost scavenging runs (ironic — the same activity that brings new plant genetics also brings new threats).

**Breeding pressure:** Maintain defense-heavy wild lines for emergency backcrossing. Invest in aromatic pest-repellent companion plants even though they don't produce food.

### Colony Crises
Raiders destroy fields. A population surge requires emergency food production. A disease outbreak requires specific medicinal compounds. Trade partners demand specific goods.

**Breeding pressure:** Contradicts whatever you were optimizing for. You bred for maximum food? Now you need medicine. You bred for medicine? Now you need food. The colony's needs are never static.

### Soil Contamination
Industrial activity, alchemical waste, corrupted water sources, or the lingering effects of whatever destroyed the outposts in the first place. Changes soil chemistry, rendering some cultivars nonviable.

**Breeding pressure:** Need to breed or backcross for contamination tolerance, which no existing cultivar has — but that weird salt-tolerant specimen from the coastal outpost three seasons ago might carry the genes you need. Did you bank it?

---

## The Seed Bank as Strategic Infrastructure

The seed bank is the most important single piece of colony infrastructure for long-term survival. It's where you store genetic material you don't currently need but might need desperately later.

**Design tension:** The seed bank competes for resources (space, climate control, maintenance labor) with immediate colony needs. A colony under food pressure might convert seed bank space to food storage. A colony under attack might neglect seed bank maintenance. But losing seed lines is **permanent and irreversible** — once a genetic lineage is gone, the only way to recover those traits is to find them again in the wild, which means organizing scavenging runs to outposts that may no longer exist.

The seed bank creates a **long-term vs. short-term strategic tension** that is genuinely hard to optimize. How much of your colony's limited resources do you invest in genetic insurance you may never need?

---

## What This Looks Like in a MUD Text Interface

### Examining a newly scavenged specimen:
```
> examine specimen

 ── FERAL TUBER (Outpost 7-North, Coastal Ruin) ──────────────────
 Family: Rootcrop  │  Domestication: Feral  │  Compat: Rootcrop-B

 You turn the soil-crusted tuber over in your hands. It's roughly 
 the size of your fist, covered in coarse reddish skin with 
 deep-set eyes. A sharp, almost acrid smell rises from a crack 
 where your thumb scraped the surface. Clearly a wild relative of 
 the colony's staple rootcrops — the skin is much thicker, the 
 eyes more pronounced.

     YIELD ■■░░░░░░░░ DEFENSE      Low yield, high defense.
                                    Invests heavily in skin 
                                    armor and chemical deterrents.

     SPEED ■■■■░░░░░░ NUTRIENT     Moderate growth rate. Dense
                                    starch and mineral content 
                                    in the flesh beneath that 
                                    thick skin.

 SPECIALIST ░░░░░░░■■■ GENERALIST  Broad tolerance. Coastal 
                                    origin suggests salt and 
                                    wind resistance, but no 
                                    strong environmental 
                                    specialization.

   UNIFORM ░░░░░░░░■■ DIVERSE      High genetic variability 
                                    in this sample — kernel 
                                    sizes vary, skin color 
                                    ranges from rust to amber.

  EDIBLE ■■■■■░░░░░ UTILITY        Primarily a food crop, 
                                    but the acrid skin 
                                    compounds may have pest-
                                    repellent applications.

 ── KNOWN INTERACTIONS ────────────────────────────────────────────
  ◆ Allelopathic: UNKNOWN (not yet grown near other crops)
  ◆ Companion:    UNKNOWN
  ◆ Recessive:    Possible — variable eye depth suggests hidden 
                   traits that may surface in F2 generation

 ── NOTES ─────────────────────────────────────────────────────────
  Moderate cross-compatibility with colony rootcrop lines. Could 
  introduce salt tolerance and defense chemistry into domestic 
  stock, but expect significant yield drag for 2-3 backcross 
  generations. Worth banking at minimum.
```

### Examining a third-gen colony cultivar:
```
> examine colony-wheat-7

 ── COLONY WHEAT cv.7 "Goldtop" ──────────────────────────────────
 Family: Grain  │  Domestication: Cultivar  │  Compat: Grain-A

 Tall, uniform stalks with heavy seed heads that nod in the 
 breeze. The colony's workhorse grain — three seasons of 
 selective breeding from the original outpost stock, optimized 
 for the south terrace fields.

     YIELD ■■■■■■■■░░ DEFENSE      High yield, low defense.
                                    This is what happens when 
                                    you breed hard for 
                                    production. Blight would 
                                    devastate this line.

     SPEED ■■■■■■░░░░ NUTRIENT     Fast-maturing, two harvests 
                                    per season feasible. But 
                                    grain is starchy — low 
                                    protein, low mineral 
                                    content compared to the 
                                    parent stock.

 SPECIALIST ■■■■░░░░░░ GENERALIST  Tuned for south terrace 
                                    conditions — good sun, 
                                    sheltered from wind, 
                                    loamy soil. Would struggle 
                                    in the north plots or 
                                    exposed ridge fields.

   UNIFORM ■■■░░░░░░░ DIVERSE      Genetically narrow. Third 
                                    generation of clone 
                                    propagation. Every plant 
                                    shares every vulnerability.

  EDIBLE ■■■■■■■■■░ UTILITY        Almost pure food crop. The
                                    straw is usable as bedding 
                                    but brittle — poor fiber.

 ── KNOWN INTERACTIONS ────────────────────────────────────────────
  ◆ Allelopathic: None detected
  ◆ Companion:    +YIELD when adjacent to nitrogen-fixing plots
  ◆ Recessive:    Rust susceptibility confirmed in F2 trials. 
                   ~25% of seedlings from crosses show leaf 
                   curl under wet conditions.

 ── NOTES ─────────────────────────────────────────────────────────
  The backbone of the colony diet, but dangerously overbred. One 
  bad blight season away from catastrophe. Consider backcrossing 
  with wild grain specimens to reintroduce defense genetics — 
  accept 2 seasons of reduced yield to buy resilience.
```

### Examining a rare outpost lab specimen:
```
> examine specimen

 ── ENGINEERED VINE (Outpost 12, Research Lab) ───────────────────
 Family: Creeper  │  Domestication: Engineered  │  Compat: Vine-C

 A sealed sample tube containing a pale rootlet suspended in 
 nutrient gel. The outpost manifest fragment lists it as 
 "Project Thornwall, iteration 14." The rootlet is studded 
 with fine crystalline structures unlike anything in your 
 colony stock.

     YIELD ░░░░░░░░░░ DEFENSE      Zero food yield. This was 
                                    bred to hurt things, not 
                                    feed them. The crystalline 
                                    thorns and dense growth 
                                    habit suggest a living 
                                    barrier plant.

     SPEED ■■■■■■■░░░ NUTRIENT     Extremely fast growth — 
                                    the lab notes mention 
                                    "aggressive establishment." 
                                    No nutritional value.

 SPECIALIST ■■■░░░░░░░ GENERALIST  Engineered for a specific 
                                    outpost's perimeter 
                                    conditions. Unknown how 
                                    it will perform in the 
                                    skerry's environment.

   UNIFORM ■■░░░░░░░░ DIVERSE      Clone-propagated lab stock. 
                                    Genetic monoculture — one 
                                    pathogen could kill every 
                                    specimen.

  EDIBLE ░░░░░░░░░■ UTILITY        Pure utility. Potential 
                                    defensive perimeter plant, 
                                    fiber source from the 
                                    vine structure, possibly 
                                    alchemical applications 
                                    for the crystal thorns.

 ── KNOWN INTERACTIONS ────────────────────────────────────────────
  ◆ Allelopathic: CAUTION — lab manifest notes "aggressive root 
                   competition." Likely suppresses neighbors.
  ◆ Companion:    None expected
  ◆ Recessive:    Unknown. Engineered stock may carry designed 
                   kill-switches or intentional sterility.

 ── NOTES ─────────────────────────────────────────────────────────
  Not food. Not even close. But the colony's eastern margin is 
  open to raider approach and the current thorn-fence is rotting. 
  A living wall that maintains itself could free up labor. The 
  question is whether you can control it — "aggressive 
  establishment" and possible allelopathy means this vine could 
  become a problem if it escapes containment.
```

### Observing a breeding result:
```
> survey field-7

 ── FIELD 7: Flameroot × Colony-Wheat Cross, Gen 3 ──────────────

 The third generation is coming in. You walk the rows slowly. 
 Two distinct phenotypes are emerging from the population:

 PHENOTYPE A — "Tallstock" (majority, ~70% of field)
 ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
     YIELD ■■■■■■■░░░ DEFENSE    Good head fill, colony-wheat
     SPEED ■■■■■░░░░░ NUTRIENT   parentage asserting. Standard
                                  grain performance.

 PHENOTYPE B — "Redstalk" (~30%, clustered east margin)
 ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
     YIELD ■■■■░░░░░░ DEFENSE    Shorter, stockier. Reddish leaf
     SPEED ■■■░░░░░░░ NUTRIENT   margins — the flameroot coming 
                                  through. Thicker stems. Smaller 
                                  seed heads, but denser grain.

 The choice is visible in the rows: select Tallstock seed for 
 yield, or Redstalk seed for the stem thickness that could mean 
 storm resistance — at the cost of roughly 30% less grain per 
 harvest. 

 Or save seed from both and maintain the split. Costs double 
 the field space to keep two lines going.
```

### Discovering an allelopathic interaction:
```
> survey field-12

 ── FIELD 12: Razorthistle + Colony Beans ────────────────────────

 ⚠ INTERACTION DETECTED

 The razorthistle transplant from Outpost 3 is thriving, but 
 colony beans in adjacent plots are yellowing at the margins. 
 Nearest bean plants are visibly stunted. Soil near the 
 razorthistle roots has a faint bitter smell.

 Updating razorthistle entry:

  ◆ Allelopathic: CONFIRMED — root exudates suppress legume-
                   family plants within ~3 adjacent plots. 
                   Severity: HIGH.

 This is manageable. Razorthistle's chemical output may actually 
 suppress the wireweed creeping in from the wasteland margin — 
 useful as a border plant. But nothing from the bean family 
 within three plots, or you'll lose the crop.

 ── FIELD 12 YIELD IMPACT ────────────────────────────────────────
  Razorthistle:  Healthy. On track.
  Colony Beans:  -40% projected yield in affected plots.
  Wireweed:      Suppressed in razorthistle zone (unintended 
                  benefit).
```

---

## Design Principles Summary

1. **No single best crop.** Every plant exists on multiple tradeoff axes. What's "best" depends entirely on the colony's current situation, which changes.

2. **Domestication is loss.** Every breeding improvement costs something. Making a plant more useful to humans makes it less able to survive without humans. This is historically accurate and creates genuine tension.

3. **Diversity is insurance.** Monocultures maximize short-term output. Diversity maximizes long-term survival. The game should make players feel the pull of both.

4. **Information is situational, not gated.** Hidden recessive traits, undiscovered allelopathic interactions, unknown disease susceptibilities — these reveal through *experience* (growing, breeding, encountering new conditions), not through skill-leveling. Every player reads the same stat bars. The hard part is deciding what to do with the information.

5. **Spatial relationships matter.** Plants interact with their neighbors. Field layout is a puzzle that changes as your crop roster changes.

6. **The seed bank is the real endgame.** Short-term farming is about this season's harvest. Long-term farming is about maintaining genetic options for crises you can't predict. The tension between present needs and future insurance is the strategic heart of the system.

7. **Scavenging and breeding are coupled loops.** New genetics come from the dangerous world outside. The farm converts raw wildness into domesticated utility. The colony's willingness to fund scavenging runs is an investment in genetic diversity that may not pay off for years — or may save everyone next season.
