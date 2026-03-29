"""
engine/world_life_pack.py

Life event protocols for WORLD13 world mode.
Not professional domains. Lived human experience.
"""

import random
from typing import Optional


LIFE_EVENTS_BY_PLANE = {
    1: [
        "woke before dawn for no reason",
        "the body asked for something it couldn't name",
        "worked until it hurt",
        "ate alone",
        "walked somewhere without a destination",
        "couldn't sleep",
        "fixed something broken",
        "felt the weather change",
        "carried something heavy",
        "a small physical pleasure, unexpectedly",
        "the work itself, without result",
        "an illness passing",
        "the body remembering something the mind forgot",
    ],
    2: [
        "argued about something small",
        "said something they didn't mean",
        "sat in silence with someone",
        "felt the distance between two people grow",
        "a kindness received unexpectedly",
        "a conversation that went nowhere",
        "missed someone who was still alive",
        "felt protective of someone",
        "said the wrong thing at the right moment",
        "a friendship that had quietly changed",
        "wanted to be closer and didn't know how",
        "love expressed badly",
        "someone left without explanation",
    ],
    3: [
        "made a decision they'd been avoiding",
        "noticed the same pattern repeating",
        "a plan that didn't hold",
        "organized something that kept falling apart",
        "read something that changed a small thing",
        "realized they'd been wrong for a long time",
        "a responsibility they hadn't chosen",
        "the mind running ahead of the present",
        "a problem without a solution, waiting",
        "understood something they'd been told before",
        "made a rule and immediately broke it",
    ],
    4: [
        "looked for meaning in something ordinary",
        "a ritual, performed without knowing why",
        "sat with a decision already made",
        "remembered someone they hadn't thought about in years",
        "felt the weight of accumulated small failures",
        "a moment where two things clicked together",
        "a conversation about what matters",
        "the question underneath the question",
        "work that felt like more than work",
        "a grief visited again, briefly",
        "something they'd built, still standing",
        "the gap between who they are and who they meant to be",
    ],
    5: [
        "made something no one would see",
        "a creative impulse that went nowhere",
        "the frustration of approximation",
        "a moment of genuine surprise at their own work",
        "stared at a blank page",
        "discarded something almost finished",
        "heard music that reached somewhere",
        "saw something beautiful and couldn't say why",
        "tried to explain what they'd made",
        "the pleasure of a thing done well",
        "a vision that wouldn't translate",
        "the fear of showing it",
    ],
    6: [
        "sat with an old letter",
        "recognized themselves in someone they disliked",
        "a memory that changed its meaning",
        "questioned something they had always believed",
        "felt the past touching the present",
        "a conversation with themselves, honest",
        "something they couldn't forgive, briefly",
        "the person they were before, glimpsed",
        "a long-held story, loosening",
        "a dream they remembered",
        "the question of whether they had changed",
        "sat with something unresolved without trying to resolve it",
    ],
    7: [
        "a moment of inexplicable stillness",
        "the sensation of being part of something larger",
        "lost track of time in a good way",
        "felt connected to something they couldn't name",
        "a prayer or its equivalent",
        "the world felt briefly coherent",
        "a stranger who mattered",
        "the feeling of completion, partial",
        "watched something end without sadness",
        "a moment that needed no explanation",
        "the sense of having arrived, temporarily",
        "gratitude without an object",
    ],
}

PHASE_EVENT_BIAS = {
    "ACC": ["ate alone", "the work itself, without result",
            "walked somewhere without a destination",
            "made something no one would see",
            "a ritual, performed without knowing why"],
    "CRS": ["argued about something small", "couldn't sleep",
            "made a decision they'd been avoiding",
            "said something they didn't mean",
            "felt the distance between two people grow",
            "a plan that didn't hold"],
    "RES": ["understood something they'd been told before",
            "a moment where two things clicked together",
            "recognized themselves in someone they disliked",
            "a memory that changed its meaning",
            "a long-held story, loosening",
            "something they'd built, still standing"],
    "TRN": ["discarded something almost finished",
            "a friendship that had quietly changed",
            "watched something end without sadness",
            "sat with something unresolved without trying to resolve it",
            "a grief visited again, briefly"],
    "LIB": ["a moment of inexplicable stillness",
            "the world felt briefly coherent",
            "gratitude without an object",
            "the feeling of completion, partial",
            "a moment that needed no explanation"],
}


def select_life_event(
    plane: int,
    cycle_phase: str,
    k_current: float,
    rng: Optional[random.Random] = None,
) -> dict:
    if rng is None:
        rng = random.Random()

    plane_events = LIFE_EVENTS_BY_PLANE.get(plane, LIFE_EVENTS_BY_PLANE[4])
    phase_events = PHASE_EVENT_BIAS.get(cycle_phase, [])

    if phase_events and rng.random() < 0.6:
        event_name = rng.choice(phase_events)
    else:
        event_name = rng.choice(plane_events)

    return {
        "name": event_name,
        "domain": "life",
        "plane": plane,
        "phase_bias": cycle_phase,
        "k_level": k_current,
    }


def build_life_session_prompt(agent, event: dict, phase_description: str) -> str:
    event_name = event["name"]
    plane = event["plane"]
    k = event["k_level"]
    phase = event.get("phase_bias", "ACC")

    if k > 7.0:
        k_color = "carrying a great deal — years of unprocessed weight, fatigue they don't fully acknowledge"
    elif k > 5.0:
        k_color = "carrying the ordinary accumulation of a complicated life — not broken, not light"
    elif k > 3.0:
        k_color = "moving through things with some ease — not unburdened, but not overwhelmed"
    elif k > 1.0:
        k_color = "approaching something like clarity — the weight has mostly passed through"
    else:
        k_color = "very light — close to the end of a long arc"

    phase_color = {
        "ACC": "Things are as they are. No particular pressure.",
        "CRS": "Something is pressing. The ordinary isn't holding.",
        "RES": "Something is being worked through. Not finished, but moving.",
        "TRN": "A chapter is ending. They can feel it without naming it.",
        "LIB": "Very close to something. The weight is nearly gone.",
    }.get(phase, "")

    plane_color = {
        1: "They live close to the physical world — the body, the hands, the immediate.",
        2: "They live in relation — other people are how they understand themselves.",
        3: "They live in structure — patterns, systems, the way things should work.",
        4: "They live between worlds — the practical and the meaningful, trying to hold both.",
        5: "They live in making — expression is how they process existence.",
        6: "They live in reflection — they watch themselves live more than most people do.",
        7: "They live at the edge of ordinary experience — aware of something beyond it.",
    }.get(plane, "")

    return f"""You are writing a brief account of a moment in a human life.

The person: {agent.name}
{plane_color}
{k_color}
{phase_color}

The moment: {event_name}

Write 150-250 words in the third person. No explanation of what the moment means. No resolution. Just what happened — what they noticed, what moved through them, what they did or didn't do. The way a very good short story handles an ordinary Tuesday.

Do not name the person's feelings. Show them. Do not conclude. End where the moment ends."""


def build_life_user_prompt(event: dict) -> str:
    return f"Write the moment: {event['name']}"
