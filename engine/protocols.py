"""
protocols.py — Protocol catalog for the WORLD13 simulation.

Contains all 644 protocol entries across 51 domains and 7 planes.
Each protocol defines a specific professional/personal practice with
archetypal affinities, complexity parameters (base_k, base_lambda),
cycle metadata, and karmic phase angle.

Protocols are generated deterministically at import time from the
canonical domain registry below.
"""

from typing import List
import random
import math

# ---------------------------------------------------------------------------
# Domain registry: (domain, count, plane, primary, secondary, tertiary, names)
# ---------------------------------------------------------------------------

_DOMAIN_REGISTRY = [
    ("Agriculture", 15, 1, "BLD", "HLR", "WAR", [
        "Crop Rotation Planning", "Soil Health Assessment", "Irrigation System Design",
        "Pest Management Strategy", "Harvest Yield Optimization", "Livestock Husbandry",
        "Seed Selection Protocol", "Greenhouse Climate Control", "Organic Certification Pathway",
        "Aquaponics Integration", "Pasture Restoration Cycle", "Grain Storage Management",
        "Pollinator Habitat Design", "Drought Resilience Planning", "Farm Equipment Calibration",
    ]),
    ("Sports", 15, 1, "WAR", "BLD", "SKR", [
        "Athletic Performance Assessment", "Competition Strategy Formation", "Endurance Training Protocol",
        "Team Dynamics Optimization", "Injury Recovery Pathway", "Strength Progression Cycle",
        "Sport-Specific Conditioning", "Game Film Analysis", "Nutritional Periodization",
        "Mental Toughness Development", "Pre-Season Preparation", "Agility Drill Sequencing",
        "Recovery and Regeneration", "Competitive Peak Timing", "Biomechanical Efficiency",
    ]),
    ("Embodiment", 10, 1, "BLD", "HLR", "LVR", [
        "Somatic Awareness Practice", "Breath Pattern Integration", "Movement Quality Assessment",
        "Body Mapping Exploration", "Postural Alignment Protocol", "Kinesthetic Sensitivity Training",
        "Embodied Presence Cultivation", "Tension Release Sequence", "Proprioceptive Calibration",
        "Physical Boundary Recognition",
    ]),
    ("Physical Skills", 8, 1, "WAR", "BLD", "TCH", [
        "Hand-Eye Coordination Drill", "Balance and Stability Training", "Fine Motor Precision",
        "Reaction Time Enhancement", "Spatial Navigation Practice", "Grip Strength Development",
        "Flexibility Progression Cycle", "Functional Movement Screening",
    ]),
    ("Nature", 10, 1, "BLD", "MYS", "WIT", [
        "Wilderness Observation Protocol", "Seasonal Cycle Tracking", "Ecosystem Health Survey",
        "Weather Pattern Interpretation", "Wildlife Behavior Documentation", "Plant Identification Practice",
        "Water Source Assessment", "Geological Feature Mapping", "Forest Canopy Analysis",
        "Tidal Rhythm Observation",
    ]),
    ("Maker", 12, 1, "BLD", "TRK", "TCH", [
        "Woodworking Joint Selection", "Metalwork Fabrication Plan", "Textile Pattern Design",
        "Ceramics Kiln Management", "Tool Maintenance Protocol", "Material Selection Matrix",
        "Prototype Iteration Cycle", "Workshop Safety Assessment", "Finishing Technique Application",
        "Blueprint Reading Practice", "Assembly Sequence Planning", "Quality Control Checkpoint",
    ]),
    ("Lifestyle", 10, 1, "BLD", "LVR", "SKR", [
        "Daily Routine Architecture", "Wardrobe Curation Strategy", "Home Environment Design",
        "Culinary Skill Development", "Travel Planning Framework", "Fitness Lifestyle Integration",
        "Social Calendar Optimization", "Personal Style Refinement", "Leisure Activity Balance",
        "Seasonal Living Adaptation",
    ]),
    ("Dyadic/Relationship", 20, 2, "LVR", "HLR", "WIT", [
        "Attachment Style Assessment", "Communication Pattern Repair", "Conflict Resolution Dialogue",
        "Trust Rebuilding Protocol", "Intimacy Deepening Practice", "Boundary Negotiation Framework",
        "Love Language Translation", "Emotional Attunement Exercise", "Partnership Vision Alignment",
        "Rupture and Repair Cycle", "Vulnerability Exchange Practice", "Commitment Clarity Check",
        "Co-Regulation Development", "Relational Trigger Mapping", "Secure Functioning Protocol",
        "Appreciation Expression Ritual", "Shared Meaning Construction", "Power Dynamic Rebalancing",
        "Reconnection After Distance", "Long-Term Bond Maintenance",
    ]),
    ("Parenting", 8, 2, "BLD", "HLR", "TCH", [
        "Developmental Milestone Tracking", "Discipline Strategy Selection", "Parent-Child Attunement",
        "Educational Enrichment Planning", "Family Routine Establishment", "Behavioral Pattern Guidance",
        "Adolescent Autonomy Scaffolding", "Co-Parenting Coordination",
    ]),
    ("Small Group", 10, 2, "LVR", "SOV", "TCH", [
        "Group Cohesion Building", "Meeting Facilitation Design", "Role Assignment Protocol",
        "Collective Decision Making", "Shared Resource Allocation", "Group Norm Establishment",
        "Collaborative Goal Setting", "Interpersonal Friction Mediation", "Knowledge Sharing Circle",
        "Community Event Coordination",
    ]),
    ("Hospitality", 17, 2, "LVR", "BLD", "SKR", [
        "Guest Experience Design", "Menu Concept Development", "Service Flow Choreography",
        "Ambiance Engineering Protocol", "Wine Program Curation", "Event Production Planning",
        "Staff Training Sequence", "Customer Journey Mapping", "Seasonal Menu Rotation",
        "Front-of-House Coordination", "Dietary Accommodation System", "Bar Program Innovation",
        "Guest Recovery Protocol", "Table Assignment Strategy", "Kitchen Brigade Organization",
        "Reservation System Optimization", "Vendor Relationship Management",
    ]),
    ("Collecting", 10, 2, "SKR", "WIT", "BLD", [
        "Collection Scope Definition", "Authentication Verification", "Provenance Research Protocol",
        "Condition Assessment Grading", "Acquisition Strategy Planning", "Catalog System Design",
        "Market Value Tracking", "Storage and Preservation", "Collection Gap Analysis",
        "Display Curation Method",
    ]),
    ("Connoisseurship", 10, 2, "LVR", "WIT", "JDG", [
        "Sensory Calibration Training", "Quality Distinction Framework", "Tasting Note Composition",
        "Origin Terroir Analysis", "Vintage Assessment Protocol", "Comparative Evaluation Method",
        "Aesthetic Judgment Refinement", "Expert Palate Development", "Craftsmanship Recognition",
        "Cultural Context Appreciation",
    ]),
    ("Legal", 15, 3, "JDG", "SOV", "WAR", [
        "Civil Litigation Intake", "Contract Review Protocol", "Regulatory Compliance Audit",
        "Intellectual Property Assessment", "Dispute Resolution Strategy", "Due Diligence Investigation",
        "Corporate Governance Review", "Employment Law Compliance", "Liability Risk Analysis",
        "Estate Planning Framework", "Antitrust Evaluation", "Immigration Case Assessment",
        "Environmental Regulation Compliance", "Tort Claim Evaluation", "Appellate Brief Preparation",
    ]),
    ("Finance", 16, 3, "SOV", "JDG", "BLD", [
        "Portfolio Allocation Strategy", "Risk Assessment Framework", "Cash Flow Projection Model",
        "Credit Underwriting Protocol", "Tax Optimization Planning", "Merger Valuation Analysis",
        "Capital Structure Review", "Derivatives Pricing Model", "Compliance Monitoring System",
        "Budget Variance Analysis", "Investment Due Diligence", "Treasury Management Protocol",
        "Financial Statement Analysis", "Debt Restructuring Plan", "Equity Research Framework",
        "Revenue Forecasting Model",
    ]),
    ("Government", 15, 3, "SOV", "JDG", "WAR", [
        "Policy Impact Assessment", "Legislative Drafting Protocol", "Public Comment Review",
        "Interagency Coordination Plan", "Constituent Services Workflow", "Regulatory Rulemaking Process",
        "Budget Appropriation Analysis", "Emergency Response Framework", "Grant Administration Protocol",
        "Public Records Management", "Electoral Process Oversight", "Census Data Integration",
        "Municipal Planning Review", "Diplomatic Cable Drafting", "National Security Briefing",
    ]),
    ("Architecture", 15, 3, "BLD", "TRK", "SOV", [
        "Site Analysis Protocol", "Schematic Design Development", "Building Code Compliance",
        "Structural System Selection", "Sustainable Design Integration", "Space Planning Optimization",
        "Material Specification Process", "Construction Document Review", "Historic Preservation Assessment",
        "Accessibility Compliance Audit", "Energy Modeling Analysis", "Landscape Integration Design",
        "Interior Finish Selection", "Zoning Variance Preparation", "Post-Occupancy Evaluation",
    ]),
    ("Engineering", 17, 3, "BLD", "TCH", "WAR", [
        "Systems Requirements Analysis", "Structural Load Calculation", "Thermal Analysis Protocol",
        "Fluid Dynamics Simulation", "Materials Testing Procedure", "Quality Assurance Framework",
        "Failure Mode Analysis", "Prototype Validation Cycle", "Manufacturing Process Design",
        "Environmental Impact Assessment", "Safety Factor Determination", "Control Systems Design",
        "Signal Processing Pipeline", "Geotechnical Survey Protocol", "Electrical Systems Layout",
        "Mechanical Assembly Specification", "Tolerance Stack-Up Analysis",
    ]),
    ("Technology", 10, 3, "TRK", "BLD", "SKR", [
        "System Architecture Design", "Code Review Protocol", "Infrastructure Scaling Plan",
        "Security Vulnerability Assessment", "Database Optimization Strategy", "API Design Standard",
        "DevOps Pipeline Configuration", "User Experience Audit", "Performance Benchmarking",
        "Technical Debt Evaluation",
    ]),
    ("Real Estate", 16, 3, "BLD", "SOV", "JDG", [
        "Property Valuation Assessment", "Market Comparative Analysis", "Investment Feasibility Study",
        "Lease Negotiation Framework", "Property Condition Survey", "Zoning and Land Use Review",
        "Title Search Protocol", "Mortgage Underwriting Checklist", "Commercial Tenant Screening",
        "Development Pro Forma Model", "Property Management Audit", "Environmental Site Assessment",
        "Closing Document Preparation", "Rental Market Analysis", "HOA Governance Review",
        "Tax Assessment Appeal",
    ]),
    ("Human Resources", 15, 3, "SOV", "HLR", "JDG", [
        "Talent Acquisition Pipeline", "Performance Review Cycle", "Compensation Benchmarking",
        "Employee Onboarding Sequence", "Workplace Conflict Resolution", "Benefits Administration Audit",
        "Succession Planning Framework", "Diversity and Inclusion Assessment", "Training Needs Analysis",
        "Termination Process Protocol", "Organizational Design Review", "Employee Engagement Survey",
        "Labor Relations Compliance", "Remote Work Policy Framework", "Workforce Planning Model",
    ]),
    ("Business", 12, 3, "SOV", "TRK", "BLD", [
        "Business Model Canvas Review", "Competitive Landscape Analysis", "Strategic Planning Cycle",
        "Operational Efficiency Audit", "Supply Chain Optimization", "Customer Segmentation Study",
        "Revenue Stream Diversification", "Partnership Evaluation Framework", "Market Entry Strategy",
        "Brand Positioning Assessment", "Stakeholder Communication Plan", "Innovation Pipeline Review",
    ]),
    ("Insurance", 15, 3, "JDG", "SOV", "HLR", [
        "Risk Underwriting Assessment", "Claims Investigation Protocol", "Policy Coverage Analysis",
        "Actuarial Reserve Calculation", "Fraud Detection Screening", "Loss Ratio Evaluation",
        "Reinsurance Treaty Review", "Catastrophe Modeling Protocol", "Policyholder Service Audit",
        "Regulatory Filing Compliance", "Product Pricing Model", "Agent Performance Review",
        "Subrogation Recovery Process", "Coverage Gap Identification", "Renewal Retention Strategy",
    ]),
    ("Medical", 16, 4, "HLR", "TCH", "JDG", [
        "Patient Triage Assessment", "Chronic Disease Management", "Surgical Consultation Protocol",
        "Diagnostic Workup Sequence", "Medication Reconciliation", "Treatment Plan Development",
        "Clinical Trial Enrollment", "Rehabilitation Progress Tracking", "Preventive Screening Schedule",
        "Emergency Stabilization Protocol", "Specialist Referral Pathway", "Palliative Care Assessment",
        "Infection Control Procedure", "Post-Operative Follow-Up", "Radiology Interpretation Review",
        "Pediatric Growth Monitoring",
    ]),
    ("Social Work", 15, 4, "HLR", "WIT", "JDG", [
        "Client Needs Assessment", "Safety Planning Protocol", "Crisis Intervention Framework",
        "Case Management Review", "Family Systems Evaluation", "Resource Navigation Guide",
        "Mandated Reporting Protocol", "Discharge Planning Process", "Advocacy Strategy Development",
        "Cultural Competency Assessment", "Trauma-Informed Care Plan", "Housing Stability Assessment",
        "Substance Use Screening", "Child Welfare Investigation", "Community Resource Mapping",
    ]),
    ("Education", 15, 4, "TCH", "HLR", "SKR", [
        "Curriculum Design Framework", "Learning Objective Alignment", "Formative Assessment Design",
        "Differentiated Instruction Plan", "Classroom Management Protocol", "Student Progress Monitoring",
        "Special Education Accommodation", "Project-Based Learning Design", "Literacy Intervention Sequence",
        "STEM Integration Strategy", "Social-Emotional Learning Plan", "Parent-Teacher Conference Prep",
        "Grading Rubric Development", "Educational Technology Integration", "Professional Development Cycle",
    ]),
    ("Consulting", 18, 4, "TCH", "SOV", "TRK", [
        "Stakeholder Analysis Protocol", "Current State Assessment", "Gap Analysis Framework",
        "Solution Architecture Design", "Change Management Plan", "Implementation Roadmap",
        "Client Discovery Interview", "Benchmark Comparison Study", "Process Reengineering Protocol",
        "Organizational Maturity Model", "Risk Mitigation Strategy", "Value Stream Mapping",
        "Executive Presentation Preparation", "Workshop Facilitation Design", "Deliverable Quality Review",
        "Statement of Work Development", "Knowledge Transfer Protocol", "Post-Engagement Review",
    ]),
    ("Sales", 17, 4, "SKR", "LVR", "TRK", [
        "Lead Qualification Framework", "Discovery Call Protocol", "Proposal Development Process",
        "Objection Handling Playbook", "Pipeline Stage Management", "Account Mapping Strategy",
        "Competitive Positioning Brief", "Pricing Negotiation Framework", "Demo Preparation Sequence",
        "Closing Technique Selection", "Referral Generation System", "Territory Planning Model",
        "Upsell Opportunity Identification", "Customer Success Handoff", "Sales Forecast Calibration",
        "Commission Structure Review", "Cold Outreach Sequence Design",
    ]),
    ("Research", 17, 4, "SKR", "WIT", "TCH", [
        "Literature Review Protocol", "Hypothesis Formulation Framework", "Experimental Design Template",
        "Data Collection Methodology", "Statistical Analysis Pipeline", "Peer Review Preparation",
        "Grant Proposal Development", "Ethical Review Submission", "Sample Size Determination",
        "Longitudinal Study Design", "Meta-Analysis Framework", "Qualitative Coding Protocol",
        "Replication Study Design", "Conference Presentation Preparation", "Publication Strategy Planning",
        "Research Collaboration Agreement", "Data Archiving Protocol",
    ]),
    ("Criminal Justice", 15, 4, "JDG", "WAR", "HLR", [
        "Evidence Chain of Custody", "Sentencing Guideline Application", "Probation Supervision Protocol",
        "Witness Interview Procedure", "Crime Scene Documentation", "Bail Assessment Framework",
        "Victim Advocacy Protocol", "Forensic Analysis Request", "Plea Negotiation Strategy",
        "Juvenile Diversion Assessment", "Reentry Planning Program", "Use of Force Review",
        "Community Policing Initiative", "Internal Affairs Investigation", "Restorative Justice Facilitation",
    ]),
    ("Diplomatic", 15, 4, "SOV", "LVR", "WIT", [
        "Treaty Negotiation Framework", "Cultural Protocol Briefing", "Consular Services Coordination",
        "International Aid Assessment", "Bilateral Meeting Preparation", "Diplomatic Immunity Review",
        "Crisis Communication Protocol", "Trade Agreement Analysis", "Embassy Security Assessment",
        "Multilateral Forum Strategy", "Humanitarian Corridor Planning", "Sanctions Compliance Review",
        "Diplomatic Credentials Verification", "State Visit Coordination", "Foreign Policy Briefing Cycle",
    ]),
    ("Media", 16, 4, "TRK", "WIT", "TCH", [
        "Editorial Calendar Planning", "Source Verification Protocol", "Audience Analytics Review",
        "Content Distribution Strategy", "Breaking News Response Protocol", "Investigative Report Framework",
        "Social Media Campaign Design", "Brand Voice Calibration", "Press Release Composition",
        "Podcast Production Pipeline", "Video Content Strategy", "SEO Optimization Protocol",
        "Media Kit Development", "Crisis Communications Plan", "Fact-Checking Procedure",
        "Cross-Platform Content Adaptation",
    ]),
    ("Creative", 16, 5, "TRK", "LVR", "MYS", [
        "Creative Brief Development", "Visual Concept Exploration", "Narrative Arc Construction",
        "Color Theory Application", "Typography System Design", "Composition Framework Selection",
        "Creative Block Resolution", "Portfolio Curation Strategy", "Artistic Voice Development",
        "Mixed Media Integration", "Exhibition Proposal Preparation", "Creative Collaboration Protocol",
        "Aesthetic Philosophy Articulation", "Visual Storytelling Sequence", "Conceptual Art Framework",
        "Generative Design Exploration",
    ]),
    ("Creative Workshops", 8, 5, "TRK", "TCH", "BLD", [
        "Workshop Curriculum Design", "Materials Preparation Protocol", "Skill Demonstration Sequence",
        "Participant Engagement Strategy", "Creative Exercise Development", "Group Critique Facilitation",
        "Supply Chain for Materials", "Workshop Outcome Assessment",
    ]),
    ("Music Learning", 8, 5, "LVR", "TCH", "TRK", [
        "Instrument Practice Protocol", "Music Theory Progression", "Ear Training Development",
        "Repertoire Selection Strategy", "Performance Preparation Cycle", "Sight-Reading Practice",
        "Ensemble Coordination Training", "Recording Session Preparation",
    ]),
    ("Media Engagement", 10, 5, "WIT", "TRK", "JDG", [
        "Media Literacy Assessment", "Critical Viewing Protocol", "Source Credibility Evaluation",
        "Content Consumption Audit", "Algorithmic Bias Awareness", "Digital Footprint Review",
        "Misinformation Detection Practice", "Platform Usage Optimization", "Parasocial Relationship Check",
        "Media Diet Rebalancing",
    ]),
    ("Science Exploration", 8, 5, "SKR", "WIT", "TCH", [
        "Citizen Science Protocol", "Field Observation Journal", "Experiment Replication Exercise",
        "Scientific Method Application", "Data Visualization Practice", "Hypothesis Testing Workshop",
        "Laboratory Safety Review", "Cross-Disciplinary Connection Mapping",
    ]),
    ("Personal Finance", 10, 5, "SOV", "JDG", "BLD", [
        "Budget Construction Framework", "Emergency Fund Planning", "Debt Reduction Strategy",
        "Investment Education Pathway", "Retirement Planning Basics", "Insurance Needs Assessment",
        "Credit Score Optimization", "Tax Filing Preparation", "Estate Planning Introduction",
        "Financial Goal Setting",
    ]),
    ("Professional Consumer", 10, 5, "SKR", "JDG", "WIT", [
        "Product Research Protocol", "Comparison Shopping Framework", "Warranty Evaluation Checklist",
        "Service Provider Vetting", "Review Authenticity Assessment", "Return Policy Analysis",
        "Subscription Audit Process", "Loyalty Program Optimization", "Consumer Rights Awareness",
        "Purchase Decision Matrix",
    ]),
    ("News Literacy", 6, 5, "JDG", "WIT", "TCH", [
        "News Source Evaluation", "Bias Detection Framework", "Fact-Check Verification Protocol",
        "Headline Analysis Practice", "Primary Source Identification", "Media Ownership Mapping",
    ]),
    ("Mental Health", 15, 6, "HLR", "WIT", "MYS", [
        "Anxiety Reduction Protocol", "Depression Screening Sequence", "Emotional Regulation Training",
        "Cognitive Distortion Identification", "Mindfulness Integration Practice", "Stress Response Management",
        "Grief Processing Framework", "Anger Management Pathway", "Self-Compassion Development",
        "Panic Response Protocol", "Trauma Stabilization Sequence", "Sleep Hygiene Optimization",
        "Burnout Recovery Plan", "Intrusive Thought Management", "Psychological First Aid",
    ]),
    ("Psychoeducation", 8, 6, "TCH", "HLR", "WIT", [
        "Attachment Theory Education", "Nervous System Literacy", "Emotional Intelligence Curriculum",
        "Defense Mechanism Awareness", "Cognitive Behavioral Framework", "Developmental Psychology Overview",
        "Relational Pattern Education", "Neuroscience of Habit Formation",
    ]),
    ("Personal", 16, 6, "HLR", "SKR", "WIT", [
        "Life Transition Navigation", "Personal Values Clarification", "Habit Formation Protocol",
        "Goal Achievement Framework", "Time Management Optimization", "Energy Management System",
        "Personal Narrative Revision", "Confidence Building Sequence", "Decision-Making Framework",
        "Procrastination Intervention", "Personal Boundary Establishment", "Identity Integration Practice",
        "Resilience Strengthening Cycle", "Motivation Source Mapping", "Self-Assessment Protocol",
        "Life Satisfaction Audit",
    ]),
    ("Temporal", 10, 6, "TRN", "WIT", "MYS", [
        "Life Chapter Review", "Timeline Reconstruction Practice", "Ancestral Pattern Recognition",
        "Future Self Visualization", "Temporal Perspective Shifting", "Legacy Planning Framework",
        "Seasonal Life Audit", "Biographical Milestone Mapping", "Generational Pattern Analysis",
        "Time Perception Calibration",
    ]),
    ("Exploratory", 10, 6, "SKR", "TRK", "WIT", [
        "Curiosity Mapping Protocol", "Interest Inventory Assessment", "Serendipity Cultivation",
        "Cross-Domain Connection Discovery", "Learning Edge Identification", "Novel Experience Planning",
        "Perspective Broadening Exercise", "Assumption Challenging Practice", "Wonder Cultivation Protocol",
        "Intellectual Adventure Design",
    ]),
    ("Self", 10, 6, "WIT", "MYS", "HLR", [
        "Self-Observation Practice", "Shadow Work Integration", "Inner Dialogue Facilitation",
        "Ego State Mapping", "Authentic Self Excavation", "Personal Mythology Exploration",
        "Witness Consciousness Development", "Self-Knowledge Inventory", "Inner Critic Negotiation",
        "Core Wound Recognition",
    ]),
    ("AI Interaction", 16, 6, "TCH", "TRK", "WIT", [
        "Prompt Engineering Practice", "AI Capability Assessment", "Human-AI Collaboration Design",
        "Output Quality Evaluation", "AI Ethics Consideration Protocol", "Context Window Management",
        "AI Tool Selection Framework", "Hallucination Detection Training", "AI Workflow Integration",
        "Model Behavior Calibration", "AI-Assisted Decision Protocol", "Conversational AI Boundary Setting",
        "AI Output Verification Checklist", "Creative AI Partnership", "AI Literacy Development",
        "Autonomous Agent Oversight",
    ]),
    ("Spiritual Practices", 8, 7, "MYS", "WIT", "TRN", [
        "Contemplative Prayer Protocol", "Meditation Deepening Sequence", "Sacred Text Study",
        "Ritual Design Framework", "Mystical Experience Integration", "Devotional Practice Cycle",
        "Spiritual Direction Session", "Pilgrimage Preparation",
    ]),
    ("Chains/Arc Sessions", 5, 7, "TRN", "MYS", "WLD", [
        "Karmic Pattern Resolution", "Soul Contract Review", "Transformational Arc Design",
        "Initiation Gate Sequence", "Archetypal Death-Rebirth Cycle",
    ]),
    ("Simulations", 17, 7, "TRK", "SOV", "MYS", [
        "World-Building Scenario Design", "Ethical Dilemma Simulation", "Historical Counterfactual",
        "Future Scenario Modeling", "Crisis Management Simulation", "Resource Allocation Game",
        "Diplomatic Negotiation Simulation", "Ecosystem Collapse Scenario", "Market Crash Simulation",
        "Civilization Design Protocol", "First Contact Scenario", "Pandemic Response Simulation",
        "Constitutional Convention Replay", "Colony Establishment Protocol", "AI Alignment Simulation",
        "Climate Adaptation Scenario", "Post-Scarcity Economy Model",
    ]),
    ("Public", 8, 7, "SOV", "TCH", "TRK", [
        "Public Speaking Preparation", "Civic Engagement Protocol", "Community Organizing Framework",
        "Public Forum Facilitation", "Grassroots Campaign Strategy", "Town Hall Meeting Design",
        "Petition Drafting Protocol", "Citizen Advocacy Training",
    ]),
]

# ---------------------------------------------------------------------------
# Plane-level base parameters: plane -> (avg_k, avg_lambda)
# ---------------------------------------------------------------------------

_PLANE_PARAMS = {
    1: (3.2, 2.3),
    2: (4.5, 3.1),
    3: (5.1, 3.2),
    4: (5.8, 3.9),
    5: (4.8, 4.2),
    6: (6.2, 5.5),
    7: (5.8, 7.6),
}

_CYCLE_PHASES = ["ACC", "CRS", "RES", "TRN"]


def _build_catalog() -> List[dict]:
    """Build the full 644-entry protocol catalog deterministically."""
    catalog: List[dict] = []
    idx = 0
    for domain, count, plane, pa, sa, ta, names in _DOMAIN_REGISTRY:
        assert len(names) == count, f"{domain}: expected {count}, got {len(names)}"
        avg_k, avg_lam = _PLANE_PARAMS[plane]
        domain_slug = domain.lower().replace("/", "_").replace(" ", "_")

        for j, name in enumerate(names):
            # Deterministic variance seeded by global index
            k_var = round(math.sin(idx * 1.7) * 0.8, 2)
            lam_var = round(math.cos(idx * 2.3) * 0.6, 2)

            base_k = round(avg_k + k_var, 2)
            base_lambda = round(avg_lam + lam_var, 2)

            # Cycle phase distribution: ~60% ACC, ~20% CRS, ~12% RES, ~8% TRN
            remainder = idx % 5
            if remainder < 3:
                phase_idx = 0  # ACC
            elif remainder == 3:
                phase_idx = 1  # CRS
            else:
                phase_idx = 2 + (idx % 2)  # RES or TRN
                if phase_idx > 3:
                    phase_idx = 3

            catalog.append({
                "id": idx + 1,
                "name": name,
                "domain": domain,
                "plane": plane,
                "primary_arch": pa,
                "secondary_arch": sa,
                "tertiary_arch": ta,
                "base_k": base_k,
                "base_lambda": base_lambda,
                "cycle_phase": _CYCLE_PHASES[phase_idx],
                "karmic_phi": round(idx * 0.00974, 4),
                "pack_reference": f"{domain_slug}_protocol_{j + 1}",
            })
            idx += 1

    assert len(catalog) == 644, f"Expected 644 protocols, built {len(catalog)}"
    return catalog


# ---------------------------------------------------------------------------
# The canonical catalog -- built once at import time
# ---------------------------------------------------------------------------

PROTOCOL_CATALOG: List[dict] = _build_catalog()


# ---------------------------------------------------------------------------
# Access & selection functions
# ---------------------------------------------------------------------------

def get_accessible_protocols(plane: int, archetype: str, k_value: float) -> List[dict]:
    """
    Returns protocols accessible to an agent based on:
    1. Same plane or adjacent planes (plane +/- 1)
    2. Matching or compatible archetype (primary, secondary, or tertiary matches)
    3. K(x) range: only protocols with base_k within +/- 2.0 of k_value
    Returns sorted by adjacency coefficient (highest first).
    """
    from .tvr import adjacency_coefficient, reincarnation_wave_function, TVRCoordinates  # noqa: F401

    accessible: List[dict] = []
    for p in PROTOCOL_CATALOG:
        if abs(p["plane"] - plane) > 1:
            continue
        if archetype not in (p["primary_arch"], p["secondary_arch"], p["tertiary_arch"]):
            continue
        if not (k_value - 2.0 <= p["base_k"] <= k_value + 2.0):
            continue

        # Compute simple adjacency score
        plane_dist = abs(p["plane"] - plane)
        if p["primary_arch"] == archetype:
            arch_match = 1.0
        elif p["secondary_arch"] == archetype:
            arch_match = 0.6
        else:
            arch_match = 0.3
        k_dist = abs(p["base_k"] - k_value)
        score = arch_match / (1.0 + plane_dist + k_dist * 0.5)

        accessible.append({**p, "_adjacency_score": score})

    accessible.sort(key=lambda x: x["_adjacency_score"], reverse=True)
    return accessible


def select_protocol(plane: int, archetype: str, k_value: float, karmic_phi: float) -> dict:
    """
    Select one protocol for an agent to run this session.
    Uses weighted random selection -- protocols with higher adjacency coefficient
    have higher selection probability.
    """
    accessible = get_accessible_protocols(plane, archetype, k_value)
    if not accessible:
        # Fallback: return any protocol from same plane
        same_plane = [p for p in PROTOCOL_CATALOG if p["plane"] == plane]
        if same_plane:
            return random.choice(same_plane)
        return PROTOCOL_CATALOG[0]

    weights = [p["_adjacency_score"] for p in accessible]
    total = sum(weights)
    if total == 0:
        return random.choice(accessible)
    selected = random.choices(accessible, weights=weights, k=1)[0]
    # Remove internal score key
    return {k: v for k, v in selected.items() if not k.startswith("_")}
