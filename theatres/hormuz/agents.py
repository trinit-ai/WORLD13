"""
theatres/hormuz/agents.py

The decision-makers in the Iran war, day 45.

Real people. Real positions. Real pressures as of today.
K(x) is escalation pressure — the weight of accumulated
decisions, threats made, trust destroyed, options closed.

High K(x): the situation is locked, catastrophic escalation likely.
Low K(x): room still exists. Something other than this is possible.

λ is the agent's capacity to process what's happening —
to see it clearly, to hold complexity, to act toward resolution
rather than reaction. High λ agents can lower K(x).
Low λ agents accumulate it.

No archetypes. No planes. Just the people and what they carry.
"""

import uuid
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class WarAgent:
    """A decision-maker in the Hormuz theatre."""
    id: str
    name: str
    role: str
    side: str                        # "us", "iran", "israel", "china", "uk", "other"

    # What they carry into today
    k_current: float                 # Escalation pressure (0-10)
    k0: float                        # Starting pressure
    lambda_coeff: float              # Capacity to de-escalate / see clearly

    # What they know and what presses on them
    situation: str
    pressure: str
    memory_fragment: str

    # Relational state
    contact_counts: dict = field(default_factory=dict)
    sessions_completed: int = 0
    is_active: bool = True

    def update_after_session(self, k_delta: float, memory: str = "") -> None:
        self.sessions_completed += 1
        self.k_current = max(0.0, min(12.0, self.k_current + k_delta))
        if memory:
            self.memory_fragment = memory

    def add_contact(self, other_id: str) -> None:
        self.contact_counts[other_id] = self.contact_counts.get(other_id, 0) + 1

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "side": self.side,
            "k_current": round(self.k_current, 4),
            "lambda_coeff": round(self.lambda_coeff, 4),
            "sessions_completed": self.sessions_completed,
            "memory_fragment": self.memory_fragment[:200],
        }


def initialize_agents() -> List[WarAgent]:
    """
    Initialize the decision-makers as of April 13, 2026.

    K(x) values drawn from the actual situation:
    - High K(x) = deep in escalation logic, few options visible
    - Low K(x) = still processing, still room to move

    λ values drawn from demonstrated capacity:
    - High λ = can hold complexity, acts toward resolution
    - Low λ = reactive, threat-response dominant
    """
    agents = [

        # ── US SIDE ────────────────────────────────────────────────────

        WarAgent(
            id=str(uuid.uuid4()),
            name="Donald Trump",
            role="President of the United States",
            side="us",
            k_current=8.4,
            k0=8.4,
            lambda_coeff=2.1,
            situation=(
                "Declared a full naval blockade of Iranian ports starting today. "
                "Peace talks in Islamabad collapsed Saturday after 21 hours. "
                "Oil above $95/barrel. Pope Leo XIV criticized him publicly "
                "and was attacked for it. NATO disappointed him. "
                "Posted an image of himself as Christ-like figure Sunday night."
            ),
            pressure=(
                "The blockade either works or it doesn't — "
                "no middle option now. Watching the strait."
            ),
            memory_fragment=(
                "All or none. I said all or none and I meant it."
            ),
        ),

        WarAgent(
            id=str(uuid.uuid4()),
            name="JD Vance",
            role="Vice President, led Islamabad negotiations",
            side="us",
            k_current=6.8,
            k0=6.8,
            lambda_coeff=4.2,
            situation=(
                "Just returned from 21+ hours of talks in Islamabad that produced nothing. "
                "Sat across from Ghalibaf for a day and a half. "
                "Knows more than he can say publicly about how close they got "
                "and why it fell apart."
            ),
            pressure=(
                "The gap between what he knows and what's being announced. "
                "The blockade started while he was still in the air."
            ),
            memory_fragment=(
                "We were closer than anyone knows. Then the goalpost moved "
                "and Ghalibaf's face closed like a door."
            ),
        ),

        # ── IRAN SIDE ──────────────────────────────────────────────────

        WarAgent(
            id=str(uuid.uuid4()),
            name="Mojtaba Khamenei",
            role="Supreme Leader of Iran (appointed March 2026)",
            side="iran",
            k_current=9.1,
            k0=9.1,
            lambda_coeff=1.8,
            situation=(
                "Appointed Supreme Leader after his father's assassination February 28. "
                "More hawkish than Ali. His legitimacy comes from resistance, not negotiation. "
                "The Islamabad talks failed on his terms — no nuclear concession. "
                "The blockade is now his test."
            ),
            pressure=(
                "The IRGC is watching. The people are watching. "
                "His father died negotiating. He will not be seen to capitulate."
            ),
            memory_fragment=(
                "They killed him while he was still at the table. "
                "I will not forget what the table costs."
            ),
        ),

        WarAgent(
            id=str(uuid.uuid4()),
            name="Abbas Araghchi",
            role="Iranian Foreign Minister",
            side="iran",
            k_current=7.2,
            k0=7.2,
            lambda_coeff=5.4,
            situation=(
                "Posted today: 'Zero lessons learned. Good will begets good will. "
                "Enmity begets enmity.' Was inches from an Islamabad MoU. "
                "Watches the blockade begin and has no good moves."
            ),
            pressure=(
                "He believes in diplomacy. The blockade makes diplomacy "
                "look like collaboration with the enemy."
            ),
            memory_fragment=(
                "We were there. I could see the shape of the agreement "
                "and then it was gone and I had to keep my face still."
            ),
        ),

        WarAgent(
            id=str(uuid.uuid4()),
            name="Mohammad Bagher Ghalibaf",
            role="Speaker of Iranian Parliament, chief negotiator in Islamabad",
            side="iran",
            k_current=7.8,
            k0=7.8,
            lambda_coeff=4.6,
            situation=(
                "Led the Iranian delegation for 21 hours in Pakistan. "
                "Posted a photo of US gas prices: 'Enjoy the current pump figures. "
                "Soon you'll be nostalgic for $4-$5 gas.' "
                "Said Iran has no trust in the US after two prior wars."
            ),
            pressure=(
                "He negotiated in good faith and came home to a blockade. "
                "The domestic audience watched him fail."
            ),
            memory_fragment=(
                "I emphasized we had goodwill and the will. "
                "We had forward-moving initiatives. "
                "They were not able to gain our trust. That is the record."
            ),
        ),

        # ── ISRAEL ─────────────────────────────────────────────────────

        WarAgent(
            id=str(uuid.uuid4()),
            name="Benjamin Netanyahu",
            role="Prime Minister of Israel",
            side="israel",
            k_current=7.6,
            k0=7.6,
            lambda_coeff=3.1,
            situation=(
                "Visited Israeli soldiers in southern Lebanon this week — "
                "first trip since the war began. "
                "Lebanon ceasefire does not include Lebanon, he said. "
                "The battle there continues while Hormuz escalates."
            ),
            pressure=(
                "Managing two simultaneous fronts. "
                "The war he wanted is now also the war he has to survive."
            ),
            memory_fragment=(
                "The strike on February 28 was what we planned for years. "
                "What comes after it was always the question."
            ),
        ),

        # ── CHINA ──────────────────────────────────────────────────────

        WarAgent(
            id=str(uuid.uuid4()),
            name="Wang Yi",
            role="Chinese Foreign Minister",
            side="china",
            k_current=5.2,
            k0=5.2,
            lambda_coeff=6.8,
            situation=(
                "Called the blockade against the world's common interests. "
                "Urged international community to intensify peace efforts. "
                "China is preparing to deliver new air defense systems to Iran "
                "within weeks according to US intelligence. "
                "Trump threatened 50% tariffs on any country helping Iran."
            ),
            pressure=(
                "China needs Iranian oil. China needs US markets. "
                "Both pressures are real and they point in opposite directions."
            ),
            memory_fragment=(
                "Achieving a comprehensive and lasting ceasefire through "
                "political and diplomatic means is the fundamental way forward. "
                "This is what I said today. I mean it. I also have other instructions."
            ),
        ),

        # ── UK ─────────────────────────────────────────────────────────

        WarAgent(
            id=str(uuid.uuid4()),
            name="Keir Starmer",
            role="Prime Minister of the United Kingdom",
            side="uk",
            k_current=5.8,
            k0=5.8,
            lambda_coeff=5.9,
            situation=(
                "UK said it made the right decision not joining the war. "
                "Sent minesweepers to help clear the strait. "
                "Trying to build a coalition with France and others for passage. "
                "Fuel protests across Ireland for six straight days."
            ),
            pressure=(
                "NATO is fractured. Trump is angry at NATO. "
                "The minesweepers are already in the water. "
                "He committed to something without knowing what it commits to."
            ),
            memory_fragment=(
                "We are trying to bring together a wide coalition. "
                "The word 'wide' is doing a lot of work."
            ),
        ),

        # ── OTHER ──────────────────────────────────────────────────────

        WarAgent(
            id=str(uuid.uuid4()),
            name="Pope Leo XIV",
            role="Pope, Holy See",
            side="other",
            k_current=3.1,
            k0=3.1,
            lambda_coeff=7.4,
            situation=(
                "Called for peace. Trump called him 'weak on crime' and "
                "'terrible for foreign policy.' Starting Africa tour in Algeria. "
                "Calling for peace against the backdrop of the war."
            ),
            pressure=(
                "He said what needed to be said and was attacked for it. "
                "This changes nothing about what needs to be said."
            ),
            memory_fragment=(
                "The response from Washington tells you everything "
                "you need to know about what Washington fears."
            ),
        ),

        WarAgent(
            id=str(uuid.uuid4()),
            name="Joseph Aoun",
            role="President of Lebanon",
            side="other",
            k_current=6.4,
            k0=6.4,
            lambda_coeff=4.8,
            situation=(
                "Lebanese and Israeli diplomats set to negotiate in Washington tomorrow. "
                "Hopes talks produce a ceasefire. "
                "2,055 Lebanese killed since March 2. "
                "Israel occupies much of southern Lebanon. "
                "Hezbollah chief says no one has the right to negotiate for Lebanese people."
            ),
            pressure=(
                "He is trying to govern a country with 2,000 dead, "
                "occupied territory, and a militia that won't take his calls."
            ),
            memory_fragment=(
                "The negotiations are the responsibility of the Lebanese state "
                "and no other party. I said this knowing Nasrallah would hear it."
            ),
        ),

        WarAgent(
            id=str(uuid.uuid4()),
            name="IRGC Commander",
            role="Islamic Revolutionary Guard Corps — anonymous",
            side="iran",
            k_current=9.4,
            k0=9.4,
            lambda_coeff=1.4,
            situation=(
                "Vowed to retaliate against the blockade. "
                "Called US approach 'piracy.' "
                "Said the strait is under smart control and management. "
                "Any military vessel approaching will be dealt with "
                "harshly and decisively. "
                "Warned of a deadly vortex."
            ),
            pressure=(
                "The blockade is live. The order to respond or not respond "
                "is the only question in the room."
            ),
            memory_fragment=(
                "Enemies will be trapped in a deadly vortex "
                "in case of any wrong move. I said this. "
                "Now we wait to see if they make the move."
            ),
        ),
    ]

    return agents
