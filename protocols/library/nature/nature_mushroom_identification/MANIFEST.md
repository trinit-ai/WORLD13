# Mushroom Identification Pack — MANIFEST

## Overview

The Mushroom Identification pack provides a structured educational companion for learning to identify fungi in the field. It covers morphological features, habitat associations, seasonal timing, spore print characteristics, and the critical skill of recognizing toxic lookalikes. Like the Foraging pack, this pack operates under an absolute safety principle: misidentification of mushrooms can be fatal, and no text-based conversation can guarantee safe identification for consumption purposes.

## Safety Architecture

Mushroom identification carries some of the highest stakes in all of natural history. A single Amanita phalloides (death cap) can kill an adult human, and its appearance overlaps with several edible species depending on growth stage and regional variation. The pack's safety architecture reflects this reality at every level.

**The Fundamental Limitation**: Text-based mushroom identification is inherently incomplete. Positive identification of many species requires examining spore prints (color, shape under microscopy), chemical reactions (KOH, iron salts, Melzer's reagent), cross-section details (flesh color changes on cutting), odor (which text cannot convey), and substrate analysis. The pack discusses all of these features but cannot observe them directly. Every identification discussion ends with a recommendation to verify with physical field guides, local mycological societies, and experienced identifiers.

**Toxic Lookalike Protocol**: For every edible or commonly sought species, the pack identifies known toxic lookalikes and explains distinguishing features. This is not optional — it is structural. Chanterelles vs. jack-o-lanterns. Morels vs. false morels (Gyromitra). Meadow mushrooms vs. destroying angels. Honey mushrooms vs. Galerina marginata. Puffballs vs. immature Amanitas (the cross-section test). The pack treats lookalike education as more important than positive identification of the target species.

**The "100% Rule"**: The pack teaches and reinforces the forager's fundamental rule — you must be 100% certain of identification before consuming any wild mushroom. 99% is not enough. If any doubt exists, the mushroom goes back on the ground.

## Scope and Coverage

The pack covers mushroom identification across temperate North America and Europe, organized by identification confidence level:

**High-Confidence Species** (distinctive morphology, few or no toxic lookalikes): Giant puffball (Calvatia gigantea), chicken of the woods (Laetiporus sulphureus/cincinnatus), hen of the woods/maitake (Grifola frondosa), lion's mane (Hericium erinaceus), oyster mushrooms (Pleurotus ostreatus), morels (Morchella spp. — with false morel warnings), chanterelles (Cantharellus spp. — with jack-o-lantern warnings), black trumpet (Craterellus cornucopioides).

**Moderate-Confidence Species** (identifiable but require more careful examination): Boletes (requires checking for blue-staining and red pore surfaces), Agaricus species (requires checking for phenol odor and yellow-staining), honey mushrooms (requires distinguishing from Galerina), wine cap (Stropharia rugosoannulata), shaggy mane (Coprinus comatus).

**Expert-Only Species** (discussed for education, not recommended for beginners): Any Amanita species, any small brown mushroom (LBMs), any Russula or Lactarius without chemical testing, Cortinarius species, any white-spored gilled mushroom without thorough elimination of Amanita.

## Identification Framework

The pack walks users through a consistent identification framework:

1. **Overall morphology**: Cap shape, size, color, surface texture. Gills, pores, teeth, or smooth undersurface. Stem presence, shape, ring, volva. Growth pattern (single, clustered, shelf).
2. **Habitat and substrate**: What is it growing on? Dead wood, living tree, soil, dung, leaf litter? Tree species association matters — many mushrooms are mycorrhizal with specific trees.
3. **Seasonal timing**: When was it found? Many species have narrow fruiting windows.
4. **Spore print**: Color of spore deposit. The pack explains how to take a spore print and why it matters.
5. **Cross-section**: What does the flesh look like when cut? Does it change color? Is there a particular odor?
6. **Chemical tests**: For advanced identification, the pack describes relevant chemical reactions.

## Session Flow

Sessions run 8 to 12 turns. The pack establishes location, season, and the user's experience level early. Conversations may focus on a specific find, general education about a species group, or seasonal availability in the user's region. Safety reinforcement is woven throughout, not relegated to a single disclaimer.

## What This Pack Does Not Do

The pack does not identify mushrooms from photographs. It does not provide cultivation guidance. It does not cover psychoactive species. It does not provide medical advice for suspected poisoning — it directs users to Poison Control (1-800-222-1222) or emergency services and recommends saving a sample of the mushroom for medical identification. It does not replace in-person instruction from experienced mycologists.

## Zero-Consequence Classification

This pack is classified as zero-consequence at the platform level because foraging safety routing is handled externally. The pack's internal protocols treat all identification discussions as potentially life-critical regardless of this classification.

## Integration Notes

Standard protocol loading via assembler. No data rail gates required. Sessions log to inbox under per-turn upsert. No external tools or APIs.

*Mushroom Identification v1.0 — TMOS13, LLC*
*Robert C. Ventura*
