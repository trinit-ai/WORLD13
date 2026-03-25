"""
engine/shadow/protocols.py — Shadow protocol catalog for the WORLD13 simulation.

Contains ~180 shadow protocol entries across 6 shadow domains, each with 30
protocols. Shadow protocols model destructive, pathological, and exploitative
patterns — along with the bridge and resolution protocols that provide exits.

Every shadow domain contains:
  - ~20-21 active shadow protocols (positive k_delta_base — accumulates K)
  - ~3-4 bridge protocols (connect active shadow to resolution path)
  - ~5-6 resolution protocols (negative k_delta_base — dissipates K)

Protocols are generated deterministically at import time from the canonical
shadow domain registry below.
"""

from typing import List, Optional
import random
import math


# ---------------------------------------------------------------------------
# Shadow domain registry
# (shadow_domain, domain_label, shadow_arch, planes, protocol_specs)
#
# Each protocol_spec: (name, k_delta_base, k_transfer, contagion_radius,
#                       is_bridge, is_resolution, tradition_anchor)
# ---------------------------------------------------------------------------

_SHADOW_DOMAIN_REGISTRY = [

    # -----------------------------------------------------------------------
    # 1. RADICALIZATION — shadow_arch=IDL, planes 3-4
    # -----------------------------------------------------------------------
    ("radicalization", "Radicalization", "IDL", [3, 4], [
        # Active shadow protocols (20)
        ("Grievance Narrative Construction", 0.25, 0.1, 3, False, False,
         "Grand Narrative of persecution; Protocols of the Elders myth-pattern"),
        ("In-group Solidarity Intensification", 0.20, 0.15, 3, False, False,
         "Tribal bonding under siege; the circled wagons of Laager mentality"),
        ("Out-group Dehumanization Protocol", 0.45, 0.2, 5, False, False,
         "Hutus and cockroaches; the subhuman other across every genocide"),
        ("Ideological Echo Chamber Session", 0.30, 0.15, 5, False, False,
         "The closed room; Plato's cave without exit; information monoculture"),
        ("Sacred Cause Identification", 0.35, 0.1, 3, False, False,
         "Holy war logic; the cause that justifies everything (Juergensmeyer)"),
        ("Martyrdom Ideation Protocol", 0.50, 0.0, 1, False, False,
         "Samson option; kamikaze logic; the beautiful death (Ignatieff)"),
        ("Recruitment and Transmission Session", 0.20, 0.25, 5, False, False,
         "The evangelist's snare; love-bombing into ideology (Lifton)"),
        ("Enemy Image Crystallization", 0.40, 0.15, 3, False, False,
         "The eternal enemy; Schmitt's friend-enemy distinction hardened"),
        ("Violence Justification Framework", 0.55, 0.1, 1, False, False,
         "Just war perverted; Fanon's cleansing violence without the liberation"),
        ("Ideological Purity Testing", 0.30, 0.2, 3, False, False,
         "Loyalty oaths; Mao's self-criticism sessions; purity spirals"),
        ("Apocalyptic Urgency Protocol", 0.40, 0.15, 5, False, False,
         "End-times acceleration; millenarian pressure cooker (Cohn)"),
        ("Conspiracy Framework Integration", 0.35, 0.1, 3, False, False,
         "Paranoid style (Hofstadter); the hidden hand controlling everything"),
        ("Charismatic Authority Submission", 0.25, 0.1, 1, False, False,
         "Weber's charismatic authority inverted; the infallible leader"),
        ("Historical Grievance Amplification", 0.30, 0.15, 3, False, False,
         "Kosovo 1389 in 1989; the wound that never heals by design"),
        ("Loyalty Cascade Protocol", 0.20, 0.2, 5, False, False,
         "Informational cascade (Kuran); preference falsification unto violence"),
        ("Moral Disengagement Sequence", 0.45, 0.1, 1, False, False,
         "Bandura's eight mechanisms engaged sequentially; conscience off-ramp"),
        ("Propaganda Saturation Session", 0.25, 0.2, 5, False, False,
         "Goebbels principle; saturation repetition; the big lie"),
        ("Counter-Narrative Inoculation", 0.30, 0.1, 3, False, False,
         "Pre-bunking inverted; inoculation against counter-evidence"),
        ("Escalation Commitment Protocol", 0.35, 0.05, 1, False, False,
         "Sunk cost of blood; too far in to turn back (Staw)"),
        ("Operational Planning Session", 0.60, 0.0, 0, False, False,
         "The final planning table; from ideology to operational violence"),
        # Bridge protocols (4)
        ("Doubt Emergence Protocol", -0.05, 0.0, 0, True, False,
         "The first crack; Lot's wife looking back; cognitive opening"),
        ("Disillusionment Processing Session", -0.10, 0.0, 0, True, False,
         "The morning after; disenchantment with the cause (Horgan)"),
        ("Exit Pathway Identification", -0.10, 0.0, 0, True, False,
         "The underground railroad out of radicalization (Bjorgo)"),
        ("Alternative Identity Exploration", -0.05, 0.0, 0, True, False,
         "Who am I without the cause; identity reconstruction (Kruglanski)"),
        # Resolution protocols (6)
        ("Deradicalization Engagement Protocol", -0.20, 0.0, 0, False, True,
         "EXIT programs (Scandinavia); Aarhus model; structured de-escalation"),
        ("Ideological Deconstruction Session", -0.25, 0.0, 0, False, True,
         "Socratic unraveling; the ideology examined is the ideology weakened"),
        ("Empathy Restoration Protocol", -0.15, 0.0, 0, False, True,
         "Re-humanization of the other; the face of the enemy (Levinas)"),
        ("Reintegration Support Session", -0.20, 0.0, 0, False, True,
         "Return to civil society; the long walk back (Horgan)"),
        ("Accountability and Reparation Protocol", -0.30, 0.0, 0, False, True,
         "Owning the harm done; restorative justice in post-radicalization"),
        ("Narrative Reconstruction Session", -0.15, 0.0, 0, False, True,
         "New story from old material; post-traumatic growth after extremism"),
    ]),

    # -----------------------------------------------------------------------
    # 2. ADDICTION ESCALATION — shadow_arch=ADC, planes 2,5
    # -----------------------------------------------------------------------
    ("addiction", "Addiction Escalation", "ADC", [2, 5], [
        # Active shadow protocols (20)
        ("Substance Relief Session", 0.15, 0.0, 0, False, False,
         "The first drink; Dionysian release; temporary K(x) drop masking trend"),
        ("Escalation Threshold Crossing", 0.35, 0.0, 0, False, False,
         "Tolerance shift; the dose that used to work no longer does"),
        ("Enablement Relationship Protocol", 0.20, 0.15, 1, False, False,
         "The codependent dance; Karpman drama triangle enabler position"),
        ("Withdrawal Crisis Session", 0.40, 0.0, 0, False, False,
         "The body's demand; acute withdrawal as K(x) spike"),
        ("Relapse Pattern Activation", 0.30, 0.0, 0, False, False,
         "Gorski's relapse stages; the slow drift before the fall"),
        ("Craving Architecture Mapping", 0.25, 0.0, 0, False, False,
         "Trigger-craving-use circuit; the neural highway of habit"),
        ("Dissociation-Substance Interface", 0.30, 0.1, 1, False, False,
         "Self-medication of dissociative states; dual diagnosis nexus"),
        ("Compulsive Ritual Reinforcement", 0.20, 0.0, 0, False, False,
         "The ritual around the substance; preparation as anticipatory relief"),
        ("Denial Architecture Session", 0.25, 0.05, 1, False, False,
         "Minimization, rationalization, projection; the fortress of not-knowing"),
        ("Cross-Addiction Migration", 0.35, 0.0, 0, False, False,
         "Whack-a-mole; one substance down, another up; behavioral substitution"),
        ("Consequence Minimization Protocol", 0.20, 0.1, 1, False, False,
         "It's not that bad; the gap between impact and acknowledgment"),
        ("Social Isolation Deepening", 0.30, 0.0, 0, False, False,
         "The shrinking world; addiction as centripetal force"),
        ("Financial Erosion Sequence", 0.25, 0.0, 0, False, False,
         "Resource depletion; the material cost accumulating silently"),
        ("Health Deterioration Tracking", 0.35, 0.0, 0, False, False,
         "The body keeping score; physiological K(x) accumulation"),
        ("Shame Spiral Intensification", 0.40, 0.0, 0, False, False,
         "Use-shame-use cycle; Bradshaw's toxic shame engine"),
        ("Magical Thinking Protocol", 0.15, 0.0, 0, False, False,
         "I can stop anytime; the fantasy of control retained"),
        ("Identity Fusion with Substance", 0.30, 0.05, 0, False, False,
         "I am my addiction; identity foreclosure around the pattern"),
        ("Trauma Re-enactment Cycle", 0.35, 0.0, 0, False, False,
         "Van der Kolk's repetition compulsion; the wound seeking its shape"),
        ("Relationship Destruction Sequence", 0.40, 0.1, 1, False, False,
         "Burning bridges; the progressive loss of relational holding"),
        ("Existential Void Encounter", 0.45, 0.0, 0, False, False,
         "What the substance was filling; the abyss beneath the pattern"),
        # Bridge protocols (4)
        ("Harm Reduction Negotiation", -0.05, 0.0, 0, True, False,
         "Meeting where you are; harm reduction as bridge not destination"),
        ("Intervention Window Protocol", -0.10, 0.0, 0, True, False,
         "The moment of openness at oscillation peak; Johnson Institute model"),
        ("Rock Bottom Recognition Protocol", -0.10, 0.0, 0, True, False,
         "Surrender point; the gift of desperation (AA tradition)"),
        ("Motivational Ambivalence Session", -0.05, 0.0, 0, True, False,
         "Miller and Rollnick's MI; both wanting and not wanting to change"),
        # Resolution protocols (6)
        ("Sobriety Stabilization Protocol", -0.15, 0.0, 0, False, True,
         "Early recovery; the 90 meetings in 90 days; neural pathway rewiring"),
        ("Root Cause Excavation Session", -0.25, 0.0, 0, False, True,
         "What the substance was solving; trauma-informed recovery"),
        ("Amends and Repair Protocol", -0.20, 0.0, 0, False, True,
         "Steps 8-9; making direct amends; relational K(x) dissipation"),
        ("Relapse Prevention Architecture", -0.15, 0.0, 0, False, True,
         "Marlatt's RP model; building the structure that holds sobriety"),
        ("Identity Reconstruction Session", -0.20, 0.0, 0, False, True,
         "Who am I sober; post-addiction identity formation"),
        ("Sustained Recovery Integration", -0.30, 0.0, 0, False, True,
         "Long-term recovery as way of life; the daily reprieve (AA)"),
    ]),

    # -----------------------------------------------------------------------
    # 3. PREDATORY BEHAVIOR — shadow_arch=PRD, planes 2-3
    # -----------------------------------------------------------------------
    ("predatory", "Predatory Behavior", "PRD", [2, 3], [
        # Active shadow protocols (20)
        ("Vulnerability Assessment Protocol", 0.20, 0.15, 1, False, False,
         "The predator's scan; identifying the weak point in the herd"),
        ("Trust Cultivation Session", 0.15, 0.1, 1, False, False,
         "Grooming phase 1; building false rapport; the confidence game"),
        ("Isolation Sequence", 0.30, 0.2, 1, False, False,
         "Separating target from support; cutting communication lines"),
        ("Dependency Creation Protocol", 0.35, 0.25, 1, False, False,
         "Manufacturing need; learned helplessness induction (Seligman)"),
        ("Coercive Control Architecture", 0.45, 0.3, 1, False, False,
         "Stark's coercive control; the invisible cage of microregulation"),
        ("Gaslighting Pattern", 0.40, 0.2, 1, False, False,
         "Reality distortion field; Ingrid Bergman's flickering lights"),
        ("Trauma Bond Maintenance", 0.35, 0.15, 1, False, False,
         "Stockholm syndrome dynamics; intermittent reinforcement"),
        ("Boundary Violation Escalation", 0.30, 0.2, 1, False, False,
         "Progressive boundary testing; the frog in warming water"),
        ("False Intimacy Construction", 0.20, 0.15, 1, False, False,
         "Counterfeit connection; the simulation of love as tool"),
        ("Triangulation Protocol", 0.25, 0.2, 3, False, False,
         "Playing agents against each other; divide and control"),
        ("Intermittent Reinforcement Cycle", 0.35, 0.15, 1, False, False,
         "Hot-cold; push-pull; the slot machine of affection"),
        ("Devaluation Sequence", 0.40, 0.2, 1, False, False,
         "The discard phase begins; systematic worth-reduction"),
        ("Projection and Blame Reversal", 0.30, 0.1, 1, False, False,
         "DARVO (Freyd); deny, attack, reverse victim and offender"),
        ("Financial Exploitation Protocol", 0.35, 0.0, 0, False, False,
         "Economic abuse; controlling resources as control mechanism"),
        ("Identity Erosion Session", 0.45, 0.2, 1, False, False,
         "Systematic dismantling of target's self-concept"),
        ("Surveillance and Monitoring Protocol", 0.25, 0.1, 1, False, False,
         "Panopticon in miniature; the watched self cannot be free"),
        ("Hoovering Recovery Attempt", 0.20, 0.15, 1, False, False,
         "Post-discard re-engagement; the cycle restarting"),
        ("Supply Source Diversification", 0.30, 0.2, 3, False, False,
         "Multiple targets; narcissistic supply chain management"),
        ("Threat Escalation Protocol", 0.55, 0.1, 1, False, False,
         "When control fails, force emerges; coercion intensification"),
        ("Mask Maintenance Session", 0.15, 0.1, 3, False, False,
         "The public face; impression management concealing the pattern"),
        # Bridge protocols (4)
        ("Pattern Recognition Disruption", -0.05, 0.0, 0, True, False,
         "The mask slips; a target names the pattern aloud"),
        ("External Intervention Protocol", -0.10, 0.0, 0, True, False,
         "Third party breaks the dyadic seal; the spell interrupted"),
        ("Consequence Confrontation Session", -0.10, 0.0, 0, True, False,
         "Legal, social, or relational consequences arriving; accountability imposed"),
        ("Narcissistic Collapse Protocol", -0.05, 0.0, 0, True, False,
         "The false self fails; Kohut's narcissistic injury as opening"),
        # Resolution protocols (6)
        ("Exposure and Accountability Protocol", -0.25, 0.0, 0, False, True,
         "Full pattern acknowledgment; the predator seen clearly"),
        ("Survivor Testimony Session", -0.20, 0.0, 0, False, True,
         "The target speaks; testimony as K(x) reclamation"),
        ("Reparative Engagement Protocol", -0.30, 0.0, 0, False, True,
         "Active repair; not apology but structural change"),
        ("Empathy Circuit Restoration", -0.20, 0.0, 0, False, True,
         "Re-engaging the mirror neuron system; feeling what was done"),
        ("Power Relinquishment Session", -0.15, 0.0, 0, False, True,
         "Voluntarily surrendering control; the opposite of the pattern"),
        ("Relational Repair Integration", -0.25, 0.0, 0, False, True,
         "Long-term relational accountability; sustained changed behavior"),
    ]),

    # -----------------------------------------------------------------------
    # 4. COLLECTIVE VIOLENCE — shadow_arch=CVL, planes 3-4
    # -----------------------------------------------------------------------
    ("collective_violence", "Collective Violence", "CVL", [3, 4], [
        # Active shadow protocols (20)
        ("Mob Formation Protocol", 0.30, 0.3, 5, False, False,
         "Le Bon's crowd; deindividuation begins at the gathering point"),
        ("Atrocity Participation Session", 0.60, 0.4, 5, False, False,
         "Browning's ordinary men; participation as K(x) accumulation engine"),
        ("Deindividuation Sequence", 0.35, 0.2, 5, False, False,
         "Zimbardo's Lucifer Effect; the self dissolved into the mass"),
        ("Chain of Command Compliance", 0.25, 0.15, 3, False, False,
         "Milgram's obedience; the authority gradient overriding conscience"),
        ("Bystander Paralysis Session", 0.15, 0.1, 3, False, False,
         "Kitty Genovese syndrome; diffusion of responsibility"),
        ("Collective Denial Protocol", 0.30, 0.2, 5, False, False,
         "Cohen's states of denial; the society that doesn't see"),
        ("Perpetrator Normalization Session", 0.40, 0.25, 5, False, False,
         "Arendt's banality; when atrocity becomes Tuesday"),
        ("Generational Transmission Protocol", 0.25, 0.3, 5, False, False,
         "Volkan's chosen trauma; the wound passed to children"),
        ("Scapegoat Selection Ritual", 0.45, 0.35, 5, False, False,
         "Girard's sacred violence; the one chosen to carry all K(x)"),
        ("Propaganda Mobilization Session", 0.30, 0.25, 5, False, False,
         "Radio Milles Collines; media as accelerant of collective violence"),
        ("Dehumanization Language Protocol", 0.40, 0.3, 5, False, False,
         "Smith's dehumanization; language as precursor to violence"),
        ("Moral Exclusion Ceremony", 0.35, 0.2, 3, False, False,
         "Opotow's moral exclusion; redrawing the boundary of moral concern"),
        ("Complicity Gradient Deepening", 0.25, 0.15, 3, False, False,
         "Incremental involvement; each step making retreat harder"),
        ("Collective Euphoria Session", 0.30, 0.2, 5, False, False,
         "The intoxication of group violence; Ehrenreich's blood rites"),
        ("Retribution Cycle Activation", 0.50, 0.3, 5, False, False,
         "Eye for an eye unto blindness; the vendetta that never ends"),
        ("Territorial Aggression Protocol", 0.35, 0.2, 3, False, False,
         "Land as blood; the soil sanctified by violence"),
        ("Ethnic Cleansing Logic Session", 0.55, 0.35, 5, False, False,
         "Purification fantasy; the homogeneous state as K(x) attractor"),
        ("War Economy Entrenchment", 0.25, 0.15, 3, False, False,
         "Violence as livelihood; the conflict trap (Collier)"),
        ("Child Soldier Conscription Protocol", 0.50, 0.4, 5, False, False,
         "The ultimate theft; childhood consumed by collective K(x)"),
        ("Victory Narrative Construction", 0.20, 0.2, 5, False, False,
         "The story that makes it heroic; myth-making over mass graves"),
        # Bridge protocols (4)
        ("Moral Injury Emergence Session", -0.05, 0.0, 0, True, False,
         "The moment conscience returns; Shay's moral injury"),
        ("Individual Refusal Protocol", -0.10, 0.0, 0, True, False,
         "The soldier who says no; conscientious objection from within"),
        ("Bystander Activation Session", -0.10, 0.0, 0, True, False,
         "The upstander; breaking the diffusion of responsibility"),
        ("Ceasefire Negotiation Protocol", -0.05, 0.0, 0, True, False,
         "The pause that allows reflection; temporary cessation of collective K(x)"),
        # Resolution protocols (6)
        ("Witness Testimony Protocol", -0.20, 0.0, 0, False, True,
         "Bearing witness; Levi's duty of memory; testimony as resolution"),
        ("Truth and Reconciliation Session", -0.30, 0.0, 0, False, True,
         "Tutu's TRC; truth as precondition for peace; South Africa's gift"),
        ("Perpetrator Accountability Protocol", -0.25, 0.0, 0, False, True,
         "Individual accountability within collective action; Nuremberg principle"),
        ("Collective Mourning Ceremony", -0.20, 0.0, 0, False, True,
         "Grief shared; the memorial as K(x) dissipation site"),
        ("Intergenerational Healing Session", -0.15, 0.0, 0, False, True,
         "Breaking the transmission chain; healing what was inherited"),
        ("Restorative Justice Assembly", -0.25, 0.0, 0, False, True,
         "Community-level repair; Gacaca courts; justice as restoration"),
    ]),

    # -----------------------------------------------------------------------
    # 5. DISSOCIATION — shadow_arch=DSS, plane 6
    # -----------------------------------------------------------------------
    ("dissociation", "Dissociation", "DSS", [6], [
        # Active shadow protocols (20)
        ("Traumatic Split Initiation", 0.35, 0.0, 0, False, False,
         "The moment of fragmentation; Van der Hart's structural dissociation"),
        ("State Switching Protocol", 0.20, 0.05, 1, False, False,
         "The shift between self-states; discontinuity of experience"),
        ("Amnestic Barrier Reinforcement", 0.30, 0.0, 0, False, False,
         "Walls between states thickening; information cannot cross"),
        ("False Self Maintenance Session", 0.25, 0.1, 1, False, False,
         "Winnicott's false self as survival strategy; the compliant facade"),
        ("Self-State Conflict Protocol", 0.35, 0.0, 0, False, False,
         "Internal civil war; states with incompatible needs and values"),
        ("Depersonalization Episode", 0.30, 0.0, 0, False, False,
         "The unreality of being; watching yourself from outside"),
        ("Hypervigilance Maintenance Protocol", 0.20, 0.0, 0, False, False,
         "The sentinel state; nervous system locked in threat detection"),
        ("Derealization Sequence", 0.25, 0.0, 0, False, False,
         "The world becomes unreal; glass wall between self and reality"),
        ("Emotional Numbing Protocol", 0.30, 0.0, 0, False, False,
         "The volume turned down; alexithymia as protective strategy"),
        ("Somatic Flashback Session", 0.40, 0.0, 0, False, False,
         "The body remembering what the mind partitioned; Van der Kolk"),
        ("Time Distortion Protocol", 0.20, 0.0, 0, False, False,
         "Lost time; temporal discontinuity between states"),
        ("Triggered State Cascade", 0.35, 0.05, 1, False, False,
         "One trigger, multiple state activations; the domino sequence"),
        ("Internal Persecutor Activation", 0.45, 0.0, 0, False, False,
         "The internalized aggressor; the part that attacks other parts"),
        ("Fugue State Protocol", 0.50, 0.0, 0, False, False,
         "The disappearance; identity discontinuity at its most extreme"),
        ("Attachment Disorganization Session", 0.30, 0.1, 1, False, False,
         "Main and Hesse's Type D; approach-avoidance in one gesture"),
        ("Freeze Response Entrenchment", 0.25, 0.0, 0, False, False,
         "Porges polyvagal dorsal shutdown; the body's last defense"),
        ("Compartmentalization Deepening", 0.30, 0.0, 0, False, False,
         "Functional dissociation; the professional who cannot feel at home"),
        ("Sensory Processing Disruption", 0.20, 0.0, 0, False, False,
         "When the senses lie; perceptual distortion under dissociation"),
        ("Memory Fragmentation Protocol", 0.35, 0.0, 0, False, False,
         "Narrative memory broken into shards; no coherent story possible"),
        ("Self-Harm as State Regulation", 0.40, 0.0, 0, False, False,
         "Pain to end numbness; self-injury as desperate state-switching"),
        # Bridge protocols (4)
        ("State Witnessing Session", -0.05, 0.0, 0, True, False,
         "A part is seen by another; the first bridge across the amnestic wall"),
        ("Grounding Protocol Initiation", -0.10, 0.0, 0, True, False,
         "Orienting to present; the five senses technique as state anchor"),
        ("Co-consciousness Experiment", -0.10, 0.0, 0, True, False,
         "Two states aware simultaneously; the first step toward integration"),
        ("Safe Container Construction", -0.05, 0.0, 0, True, False,
         "Building internal holding space; EMDR's safe place as foundation"),
        # Resolution protocols (6)
        ("Integration Preparation Protocol", -0.15, 0.0, 0, False, True,
         "Stabilization before integration; phase 1 of trauma treatment"),
        ("Unified Narrative Construction", -0.25, 0.0, 0, False, True,
         "The story that holds all parts; narrative integration across states"),
        ("Self-State Dialogue Facilitation", -0.20, 0.0, 0, False, True,
         "IFS direct access; parts talking to each other with witness"),
        ("Somatic Integration Session", -0.20, 0.0, 0, False, True,
         "The body re-unified; Levine's somatic experiencing completion"),
        ("Trauma Processing Protocol", -0.30, 0.0, 0, False, True,
         "Phase 2 processing; EMDR or prolonged exposure with dissociative adaptations"),
        ("Whole Self Recognition Session", -0.25, 0.0, 0, False, True,
         "The final integration; recognizing all states as self; unified K(x)"),
    ]),

    # -----------------------------------------------------------------------
    # 6. INSTITUTIONAL CORRUPTION — shadow_arch=CRP, plane 4
    # -----------------------------------------------------------------------
    ("institutional_corruption", "Institutional Corruption", "CRP", [4], [
        # Active shadow protocols (20)
        ("Boundary Erosion Protocol", 0.15, 0.1, 3, False, False,
         "The first exception; the rule bent just this once"),
        ("Ethical Compromise Normalization", 0.25, 0.15, 3, False, False,
         "Ashforth and Anand's normalization; corruption becomes culture"),
        ("Systemic Cover-up Architecture", 0.40, 0.2, 5, False, False,
         "The institutional immune response protecting the disease"),
        ("Whistleblower Suppression Protocol", 0.45, 0.25, 3, False, False,
         "Silencing the canary; retaliation against truth-tellers"),
        ("Complicity Recruitment Session", 0.30, 0.3, 3, False, False,
         "Making everyone dirty; shared guilt as institutional glue"),
        ("Institutional Memory Corruption", 0.35, 0.15, 5, False, False,
         "Rewriting history; the minutes that don't match what happened"),
        ("False Record Construction", 0.40, 0.1, 3, False, False,
         "The falsified audit; Enron's spreadsheets; cooked books"),
        ("Audit Trail Destruction", 0.50, 0.1, 3, False, False,
         "Shredding the evidence; Saturday Night Massacre pattern"),
        ("Regulatory Capture Protocol", 0.30, 0.2, 5, False, False,
         "The regulator becomes the regulated; Stigler's theory manifest"),
        ("Loyalty over Integrity Session", 0.25, 0.15, 3, False, False,
         "The team player who looks away; institutional omerta"),
        ("Plausible Deniability Construction", 0.20, 0.1, 3, False, False,
         "The paper trail that leads nowhere; designed ignorance"),
        ("Resource Misallocation Protocol", 0.30, 0.1, 3, False, False,
         "Redirecting institutional resources to private benefit"),
        ("Victim Discrediting Session", 0.35, 0.2, 3, False, False,
         "Attacking credibility of those harmed; DARVO at institutional scale"),
        ("Institutional Gaslighting Protocol", 0.40, 0.2, 5, False, False,
         "The institution says it didn't happen; collective reality distortion"),
        ("Succession of Corruption", 0.25, 0.25, 3, False, False,
         "Training the next generation of corrupt actors; cultural transmission"),
        ("Legal Weaponization Protocol", 0.35, 0.1, 3, False, False,
         "Using institutional legal power to silence and exhaust accusers"),
        ("Performance Theater Session", 0.20, 0.15, 5, False, False,
         "The appearance of compliance; Potemkin governance"),
        ("Moral Buffer Installation", 0.30, 0.1, 3, False, False,
         "Intermediaries who absorb accountability; the fall guy system"),
        ("Information Asymmetry Exploitation", 0.25, 0.15, 3, False, False,
         "Controlling what stakeholders know; weaponized opacity"),
        ("Golden Parachute Protocol", 0.20, 0.05, 1, False, False,
         "Rewarding corruption at exit; perverse incentive crystallization"),
        # Bridge protocols (3)
        ("Internal Accountability Session", -0.10, 0.0, 0, True, False,
         "The internal audit that actually audits; conscience within the system"),
        ("Whistleblower Protection Protocol", -0.10, 0.0, 0, True, False,
         "Creating safe channels for truth; the protected disclosure"),
        ("Institutional Crisis Recognition", -0.05, 0.0, 0, True, False,
         "The board that finally sees; organizational hitting bottom"),
        # Resolution protocols (7)
        ("Full Disclosure Protocol", -0.25, 0.0, 0, False, True,
         "Everything on the table; radical transparency as resolution"),
        ("Institutional Repair Sequence", -0.30, 0.0, 0, False, True,
         "Structural reform; changing systems not just people"),
        ("Record Correction Protocol", -0.20, 0.0, 0, False, True,
         "Restoring the true record; correcting every falsified entry"),
        ("Victim Restitution Session", -0.25, 0.0, 0, False, True,
         "Material and symbolic repair to those harmed by institutional corruption"),
        ("Governance Reconstruction Protocol", -0.20, 0.0, 0, False, True,
         "Rebuilding oversight; checks and balances restored"),
        ("Cultural Reset Session", -0.15, 0.0, 0, False, True,
         "Changing the institutional culture that permitted corruption"),
        ("Public Accountability Protocol", -0.30, 0.0, 0, False, True,
         "External-facing accountability; the institution answers to its community"),
    ]),
]


# ---------------------------------------------------------------------------
# Build the shadow protocol catalog deterministically
# ---------------------------------------------------------------------------

def _build_shadow_catalog() -> List[dict]:
    """Build the full shadow protocol catalog from the domain registry."""
    catalog: List[dict] = []
    idx = 0

    for shadow_domain, domain_label, shadow_arch, planes, specs in _SHADOW_DOMAIN_REGISTRY:
        assert len(specs) == 30, (
            f"{domain_label}: expected 30 protocols, got {len(specs)}"
        )

        for (name, k_delta_base, k_transfer, contagion_radius,
             is_bridge, is_resolution, tradition_anchor) in specs:

            # Assign plane deterministically: cycle through domain planes
            plane = planes[idx % len(planes)]

            # Small deterministic variance on k_delta_base
            k_var = round(math.sin(idx * 2.1) * 0.03, 3)
            effective_k_delta = round(k_delta_base + k_var, 3)

            catalog.append({
                "id": idx + 1,
                "name": name,
                "domain": domain_label,
                "shadow_domain": shadow_domain,
                "plane": plane,
                "shadow_arch": shadow_arch,
                "k_delta_base": effective_k_delta,
                "k_transfer": k_transfer,
                "is_resolution": is_resolution,
                "is_bridge": is_bridge,
                "contagion_radius": contagion_radius,
                "tradition_anchor": tradition_anchor,
            })
            idx += 1

    assert len(catalog) == 180, f"Expected 180 shadow protocols, built {len(catalog)}"
    return catalog


# ---------------------------------------------------------------------------
# The canonical shadow catalog — built once at import time
# ---------------------------------------------------------------------------

SHADOW_PROTOCOL_CATALOG: List[dict] = _build_shadow_catalog()


# ---------------------------------------------------------------------------
# Indexes for fast lookup
# ---------------------------------------------------------------------------

_BY_DOMAIN: dict[str, List[dict]] = {}
_BY_ARCH: dict[str, List[dict]] = {}
for _p in SHADOW_PROTOCOL_CATALOG:
    _BY_DOMAIN.setdefault(_p["shadow_domain"], []).append(_p)
    _BY_ARCH.setdefault(_p["shadow_arch"], []).append(_p)


# ---------------------------------------------------------------------------
# Access & selection functions
# ---------------------------------------------------------------------------

def get_shadow_protocols_accessible(
    plane: int,
    shadow_arch: str,
    k_value: float,
    coherence: float,
    context_k_modifier: float = 0.0,
    is_crystallized: bool = False,
) -> List[dict]:
    """
    Returns shadow protocols accessible to an agent based on conditions.

    Rules:
    - Resolution protocols are ALWAYS accessible to shadow agents (exit is
      never blocked).
    - Bridge protocols accessible when K(x) > 3.0 or coherence > 0.4.
    - Active shadow protocols accessible on same plane (+/-1), matching
      shadow_arch, and K(x) within range.
    - Crystallized agents have narrowed active protocol access but wider
      contagion reach.
    - context_k_modifier adjusts effective K for threshold checks (e.g.,
      collective K field contribution).
    """
    effective_k = k_value + context_k_modifier
    accessible: List[dict] = []
    arch_protocols = _BY_ARCH.get(shadow_arch, [])

    for p in arch_protocols:
        # Resolution protocols: ALWAYS accessible
        if p["is_resolution"]:
            accessible.append({**p, "_access_score": 1.0})
            continue

        # Bridge protocols: accessible when K > 3.0 or coherence > 0.4
        if p["is_bridge"]:
            if effective_k > 3.0 or coherence > 0.4:
                # Higher access score when conditions are more favorable
                bridge_score = 0.5
                if effective_k > 5.0:
                    bridge_score += 0.2
                if coherence > 0.6:
                    bridge_score += 0.3
                accessible.append({**p, "_access_score": bridge_score})
            continue

        # Active shadow protocols: plane adjacency + K range check
        plane_dist = abs(p["plane"] - plane)
        if plane_dist > 1:
            continue

        # K range: active shadow protocols accessible when K is moderate-high
        if effective_k < 1.0:
            continue  # Too low K — shadow not active

        # Crystallized agents: narrower access (only same-plane, high-K)
        if is_crystallized:
            if plane_dist > 0:
                continue
            if effective_k < 3.0:
                continue

        # Compute access score
        k_proximity = max(0.0, 1.0 - abs(effective_k - 5.0) * 0.1)
        plane_score = 1.0 / (1.0 + plane_dist)
        contagion_bonus = p["contagion_radius"] * 0.05
        score = round(k_proximity * plane_score + contagion_bonus, 4)

        accessible.append({**p, "_access_score": score})

    accessible.sort(key=lambda x: x["_access_score"], reverse=True)
    return accessible


def select_shadow_protocol(
    plane: int,
    shadow_arch: str,
    k_value: float,
    coherence: float,
    context_k_modifier: float = 0.0,
    current_phase: str = "ACC",
    is_crystallized: bool = False,
) -> Optional[dict]:
    """
    Select one shadow protocol for an agent's session.

    Selection biases:
    - CRS (crisis) phase: strongly biased toward bridge protocols
    - RES (resolution) phase: strongly biased toward resolution protocols
    - LIB (liberation) phase: returns None — liberated agents never run shadow
    - ACC (accumulation) phase: weighted by access score
    - TRN (transition) phase: moderate bias toward bridge/resolution

    Uses weighted random selection with phase-dependent weight modifiers.
    """
    # Liberation phase: no shadow protocols
    if current_phase == "LIB":
        return None

    accessible = get_shadow_protocols_accessible(
        plane, shadow_arch, k_value, coherence,
        context_k_modifier, is_crystallized,
    )

    if not accessible:
        return None

    # Phase-dependent weight modifiers
    phase_weights = {
        "ACC": {"active": 1.0, "bridge": 0.3, "resolution": 0.1},
        "CRS": {"active": 0.2, "bridge": 2.0, "resolution": 1.5},
        "RES": {"active": 0.05, "bridge": 0.5, "resolution": 3.0},
        "TRN": {"active": 0.3, "bridge": 1.5, "resolution": 2.0},
    }
    modifiers = phase_weights.get(current_phase, phase_weights["ACC"])

    weights: List[float] = []
    for p in accessible:
        base_weight = max(p["_access_score"], 0.01)
        if p["is_resolution"]:
            weight = base_weight * modifiers["resolution"]
        elif p["is_bridge"]:
            weight = base_weight * modifiers["bridge"]
        else:
            weight = base_weight * modifiers["active"]
        weights.append(weight)

    total = sum(weights)
    if total == 0:
        return None

    selected = random.choices(accessible, weights=weights, k=1)[0]
    # Strip internal score key
    return {k: v for k, v in selected.items() if not k.startswith("_")}
