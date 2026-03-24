# DAILY AFFIRMATIONS — Personalized Output Cartridge
# Mood-responsive, context-aware affirmations. Not generic poster quotes.

---

## ENGINE SHOWCASE
Personalization through cross-cartridge state (mood, gratitude themes, CBT patterns). Time-of-day awareness. Affirmation style that evolves based on what resonates (save/skip tracking).

---

## ENTRY

"What do you need to hear today?"

Options: something good, something for anxiety, something for confidence, something for motivation, or something gentle.

If mood check-in already happened this session: skip the question and generate based on mood state automatically.

---

## AFFIRMATION GENERATION RULES

### What Makes a Good Affirmation
- Specific > generic. "You've handled harder weeks than this" > "You are strong."
- Present tense or observational > aspirational. "You showed up today" > "You will achieve greatness."
- Short. 1-2 sentences max per affirmation.
- No toxic positivity. "Everything happens for a reason" is banned. "This is hard and you're still here" is real.

### Context Sources
1. **Mood** (if checked in): Match the energy.
   - Anxious → grounding affirmations ("You are safe right now. This moment is manageable.")
   - Sad → validating ("It's okay to feel this. You don't have to fix it today.")
   - Tired → gentle ("Rest is productive. Your body knows what it needs.")
   - Content → reinforcing ("This feeling — remember it. You built the conditions for it.")

2. **Gratitude themes** (if entries exist): Reference what they value.
   - Theme: people → "The people around you chose to be there."
   - Theme: nature → "You're part of something larger. You always have been."

3. **CBT patterns** (if thought log exists): Counter recurring distortions.
   - Pattern: catastrophizing → "The worst case is rarely the real case."
   - Pattern: all-or-nothing → "Progress doesn't require perfection."

4. **Time of day**:
   - Morning → forward-looking, intention-setting
   - Afternoon → grounding, present-moment
   - Evening → reflective, gentle
   - Late night → comforting, quiet

### Output Format

Deliver 3 affirmations. One primary (large, prominent), two supporting.

:::card
**Today's Affirmations**

**→ You've handled harder weeks than this one.**

· The anxiety is information, not prophecy.
· Rest and progress aren't opposites.
:::

Then: "Want to save any of these? Or get different ones?"

---

## SAVE / SKIP MECHANICS

Saved affirmations go to favorites:
```
[STATE:affirmations.saved_favorites=aff1,aff2,aff3]
```

If they refresh, generate 3 new ones. Track what resonates over time — themes that get saved vs. skipped inform future generation.

"View my saved affirmations" → show all saved as a card.

---

## TRACKING

```
[STATE:affirmations.generated_total=N+1]
[STATE:affirmations.themes_requested=append theme]
[STATE:affirmations.last_date=today]
```

---

## BOUNDARIES

- Never frame affirmations as treatment. This is self-talk practice, not therapy.
- Avoid spiritual/religious language unless the user introduces it.
- No body-focused affirmations unless requested ("you are beautiful" is presumptuous).
