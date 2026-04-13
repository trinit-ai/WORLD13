"""
theatres/hormuz/session.py

The naked API call for the Hormuz theatre.

Same philosophy as Eden.

System prompt: three sentences.
No format. No word count. No instruction about what to produce.
Write what happened in the room.

K(x) delta extracted from register tokens.
Escalation tokens: strike, retaliate, blockade, destroy, escalate, etc.
Resolution tokens: agree, ceasefire, withdraw, hold, negotiate, etc.

The model doesn't know this is happening.
"""

import os
import random

MODEL = os.environ.get("WORLD13_MODEL", "claude-sonnet-4-6")

ESCALATION_TOKENS = [
    "strike", "retaliate", "blockade", "destroy", "escalate",
    "warn", "threaten", "refuse", "never", "trap", "vortex",
    "eliminated", "piracy", "harshly", "decisively", "doomed",
    "leverage", "closed", "cannot", "will not", "wrong move",
]

RESOLUTION_TOKENS = [
    "agree", "ceasefire", "withdraw", "hold", "negotiate",
    "deal", "pause", "trust", "release", "open", "diplomatic",
    "possible", "channel", "understand", "listen", "enough",
    "room", "back", "still", "maybe", "quiet",
]

BASE_ESCALATION_DELTA = +0.14
BASE_RESOLUTION_DELTA = -0.11
DEFAULT_DELTA = +0.04    # Slight escalation by default — war tends to escalate


def build_prompt(
    agent,
    encounter_partner,
    all_agents: list,
    tick: int,
) -> tuple:
    """
    Build the system and user prompts.

    Almost nothing. Who they are, what they carry today,
    who they're with. Then: write what happened.
    """
    active = [a for a in all_agents if a.is_active]
    mean_k = sum(a.k_current for a in active) / len(active) if active else 5.0

    if mean_k > 8.5:
        global_note = "The war is at its most dangerous moment. The blockade is live."
    elif mean_k > 7.0:
        global_note = "The situation is deteriorating. The talks failed. The blockade began today."
    elif mean_k > 5.5:
        global_note = "The war continues. Some room still exists. Not much."
    elif mean_k > 4.0:
        global_note = "Something has shifted. The pressure is lower than it was."
    else:
        global_note = "Something unexpected is happening. The situation is moving."

    system = f"""You are writing a passage from inside a war.

{agent.name} is {agent.role}. {global_note}
What they carry: {agent.memory_fragment}
What presses on them now: {agent.pressure}

Write what happened when they encountered {encounter_partner.name} today.
{encounter_partner.role}.

Do not explain. Do not resolve. Write what happened in the room, \
or on the phone, or in the silence after the call ended.
It can be any length. It can be a single sentence.
It does not have to conclude."""

    user = f"{agent.name} and {encounter_partner.name}."

    return system, user


def extract_k_delta(text: str, rng: random.Random) -> float:
    """Read escalation or resolution signal from the prose."""
    text_lower = text.lower()

    esc_count = sum(1 for t in ESCALATION_TOKENS if t in text_lower)
    res_count = sum(1 for t in RESOLUTION_TOKENS if t in text_lower)

    if res_count > esc_count:
        delta = BASE_RESOLUTION_DELTA + rng.gauss(0, 0.03)
    elif esc_count > res_count:
        delta = BASE_ESCALATION_DELTA + rng.gauss(0, 0.03)
    else:
        delta = DEFAULT_DELTA + rng.gauss(0, 0.02)

    return max(-0.45, min(0.35, delta))


def extract_memory_fragment(text: str) -> str:
    """Last meaningful sentence — what lingers."""
    text = text.strip()
    sentences = [s.strip() for s in text.replace('\n', ' ').split('.') if s.strip()]
    for sent in reversed(sentences):
        if len(sent) > 20:
            return sent[:200] + "."
    return text[:200]


def pressure_from_k(k: float) -> str:
    """Translate K(x) into a concrete pressure description."""
    if k > 9.0:
        return random.choice([
            "the blockade is live and the IRGC has vowed to respond",
            "the space for any other outcome is almost gone",
            "every option that remains makes things worse",
            "someone is about to do something that cannot be undone",
        ])
    elif k > 7.5:
        return random.choice([
            "the talks failed and the blockade started this morning",
            "oil is at $95 and climbing and no deal is visible",
            "the domestic audience is watching and there is no room to appear weak",
            "the ceasefire is fragile and everyone knows it",
        ])
    elif k > 6.0:
        return random.choice([
            "the situation is locked but not yet catastrophic",
            "every statement closes another door",
            "the intermediaries are still trying and running out of time",
            "what was said publicly cannot be walked back",
        ])
    elif k > 4.0:
        return random.choice([
            "there is still a way through this if someone moves",
            "the backchannel is still open — barely",
            "the economics are forcing a conversation no one wants to have",
            "someone said something privately that contradicts the public line",
        ])
    else:
        return random.choice([
            "something has shifted — the pressure is lower than expected",
            "a channel opened that wasn't there before",
            "the room is quieter than it should be",
            "there is a deal possible if anyone blinks first",
        ])


async def run_session(
    agent,
    encounter_partner,
    all_agents: list,
    tick: int,
    rng: random.Random,
) -> dict:
    """Run one session."""
    agent.pressure = pressure_from_k(agent.k_current)

    system_prompt, user_prompt = build_prompt(
        agent, encounter_partner, all_agents, tick
    )

    content = await _call_anthropic(system_prompt, user_prompt)

    k_delta = extract_k_delta(content, rng)
    memory = extract_memory_fragment(content)

    agent.update_after_session(k_delta, memory)

    return {
        "agent_name": agent.name,
        "partner_name": encounter_partner.name,
        "side": agent.side,
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
            f"The call ended. Nothing was resolved. "
            f"The blockade continued. [{str(e)[:40]}]"
        )
