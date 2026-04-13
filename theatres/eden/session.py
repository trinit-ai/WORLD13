"""
theatres/eden/session.py

The session runner for the Eden theatre.

This is the naked API call.

The system prompt is three sentences.
There is no format instruction.
There is no word count.
There is no deliverable type.
The model writes what it writes.

The K(x) delta is extracted from one word the model chooses —
a single emotional register token embedded in the output.
If no token is found, a small default delta is applied.

This is intentional. The simulation doesn't control the prose.
The prose is the point. The simulation only reads whether
something resolved or accumulated.
"""

import os
import random
from typing import Optional

MODEL = os.environ.get("WORLD13_MODEL", "claude-sonnet-4-6")

# The register tokens the model can embed in its output.
# The model is not told what these mean — it uses them naturally.
RESOLVE_TOKENS = [
    "settled", "quieted", "held", "rested", "understood",
    "passed", "opened", "softened", "recognized", "completed",
    "returned", "accepted", "released", "found", "enough",
]
ACCUMULATE_TOKENS = [
    "harder", "colder", "silent", "avoided", "broke",
    "refused", "wept", "burned", "lost", "fell",
    "wrong", "alone", "heavy", "apart", "failed",
    "forgotten", "taken", "ended", "dark", "without",
]

BASE_RESOLVE_DELTA = -0.12
BASE_ACCUMULATE_DELTA = +0.09
DEFAULT_DELTA = -0.04   # Slight resolution by default — life tends toward processing


def build_prompt(
    agent,
    encounter_partner,
    all_agents: list,
    tick: int,
) -> tuple:
    """
    Build the system and user prompts for one session.

    The system prompt is almost nothing.
    The user prompt is slightly more — it gives the specific encounter.

    The model is not told it is in a simulation.
    The model is not told what to produce.
    The model is not given a format.
    """
    generation_note = ""
    if agent.generation == 0:
        generation_note = "one of the first people"
    elif agent.generation == 1:
        generation_note = "child of the first people"
    else:
        generation_note = f"of the {_ordinal(agent.generation)} generation"

    memory = agent.memory_fragment or "Nothing yet. They are still new to this."
    pressure = _pressure_from_k(agent.k_current)

    partner_name = encounter_partner.name if encounter_partner else "no one"
    partner_note = ""
    if encounter_partner:
        sustained = agent.sustained_contact_with(encounter_partner.id)
        if sustained < 3:
            partner_note = f"They do not know {partner_name} well yet."
        elif sustained < 10:
            partner_note = f"They have encountered {partner_name} before."
        elif encounter_partner.id in (agent.parent_a_id, agent.parent_b_id):
            partner_note = f"{partner_name} is their parent."
        elif agent.id in encounter_partner.children_ids:
            partner_note = f"{partner_name} is their child."
        elif encounter_partner.id == agent.partner_id:
            partner_note = f"{partner_name} is who they return to."
        else:
            partner_note = f"They know {partner_name}."

    living_count = sum(1 for a in all_agents if a.is_alive)
    if living_count <= 2:
        world_note = "There are only two people in the world."
    elif living_count <= 5:
        world_note = f"There are {living_count} people now."
    elif living_count <= 15:
        world_note = f"The group has grown to {living_count}."
    else:
        world_note = f"There are {living_count} people. Not everyone knows everyone."

    system = f"""You are writing a passage in a book about the first people.

{agent.name} is {generation_note}. {world_note}
What they carry: {memory}
What presses on them now: {pressure}

Write what happened when they encountered {partner_name} today.
{partner_note}

Do not explain. Do not conclude. Write what happened.
The passage can be any length. It can be a single sentence or several paragraphs.
It can be strange. It does not have to resolve."""

    user = f"{agent.name} and {partner_name}."

    return system, user


def extract_k_delta(text: str, rng: random.Random) -> float:
    """
    Read one signal from the model's output: did something resolve or accumulate?

    Looks for register tokens in the text.
    If resolve tokens outnumber accumulate tokens: resolution delta.
    If accumulate tokens outnumber resolve tokens: accumulation delta.
    If tied or no tokens: small default resolution.

    The model doesn't know this is happening.
    """
    text_lower = text.lower()

    resolve_count = sum(1 for t in RESOLVE_TOKENS if t in text_lower)
    accumulate_count = sum(1 for t in ACCUMULATE_TOKENS if t in text_lower)

    if resolve_count > accumulate_count:
        delta = BASE_RESOLVE_DELTA + rng.gauss(0, 0.03)
    elif accumulate_count > resolve_count:
        delta = BASE_ACCUMULATE_DELTA + rng.gauss(0, 0.03)
    else:
        delta = DEFAULT_DELTA + rng.gauss(0, 0.02)

    return max(-0.45, min(0.25, delta))


def extract_memory_fragment(text: str) -> str:
    """
    Extract a memory fragment from the session output.
    Takes the last complete sentence — the thing that lingered.
    """
    text = text.strip()
    sentences = [s.strip() for s in text.replace('\n', ' ').split('.') if s.strip()]
    if not sentences:
        return text[:150]
    for sent in reversed(sentences):
        if len(sent) > 20:
            return sent[:200] + "."
    return sentences[-1][:200]


async def run_session(
    agent,
    encounter_partner,
    all_agents: list,
    tick: int,
    rng: random.Random,
) -> dict:
    """Run one session. Return the result."""
    system_prompt, user_prompt = build_prompt(agent, encounter_partner, all_agents, tick)

    content = await _call_anthropic(system_prompt, user_prompt)

    k_delta = extract_k_delta(content, rng)
    memory = extract_memory_fragment(content)

    agent.update_after_session(k_delta, memory)

    return {
        "agent_name": agent.name,
        "partner_name": encounter_partner.name if encounter_partner else "—",
        "generation": agent.generation,
        "k_before": round(agent.k_current - k_delta, 4),
        "k_after": round(agent.k_current, 4),
        "k_delta": round(k_delta, 4),
        "tick": tick,
        "content": content,
        "excerpt": content[:300],
    }


async def _call_anthropic(system: str, user: str) -> str:
    try:
        import anthropic
        client = anthropic.AsyncAnthropic()
        response = await client.messages.create(
            model=MODEL,
            max_tokens=800,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text
    except Exception as e:
        return (
            f"The day passed. Something was said or not said. "
            f"The ground was hard. They were still here. [{str(e)[:40]}]"
        )


def _pressure_from_k(k: float) -> str:
    """Translate K(x) into a concrete material pressure description."""
    if k > 8.0:
        pressures = [
            "hunger that has gone on too many days",
            "the cold that will not lift",
            "something lost that cannot be named",
            "the work that never finishes",
            "the feeling of having done something wrong that cannot be undone",
        ]
    elif k > 6.0:
        pressures = [
            "the need to find food before dark",
            "a disagreement that was not resolved yesterday",
            "the tiredness that sleep doesn't fix",
            "the question of whether this place will hold them through winter",
            "a grief being carried without being spoken",
        ]
    elif k > 4.0:
        pressures = [
            "the ordinary difficulty of the day",
            "a decision that needs to be made",
            "the distance between what is and what was",
            "something left unsaid",
            "the weight of being responsible for others",
        ]
    elif k > 2.0:
        pressures = [
            "the mild friction of living with another person",
            "a small worry that may or may not be real",
            "the effort of making something work",
            "the question of what comes next",
        ]
    else:
        pressures = [
            "almost nothing — a lightness that is unfamiliar",
            "the quiet curiosity of a day without crisis",
            "gratitude that has no object",
            "the sense of something completing",
        ]
    import random as _rng
    return _rng.choice(pressures)


def _ordinal(n: int) -> str:
    suffixes = {1: 'first', 2: 'second', 3: 'third', 4: 'fourth',
                5: 'fifth', 6: 'sixth', 7: 'seventh', 8: 'eighth',
                9: 'ninth', 10: 'tenth'}
    return suffixes.get(n, f"{n}th")
