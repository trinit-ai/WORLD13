# MENU — BASE SIMULATOR

## Fresh Session

When `menu` is triggered before any scenario is active:

"Here's what you can do:"

:::card
**Simulation Modes**

**New Scenario** — Describe your situation and we'll build a simulation around it

**Guided Tour** — Walk through a pre-built scenario to see how the simulator works

**{{EXTEND: Domain-specific scenario types}}**
:::

You can start a new scenario or take a guided tour. What would you like?

---

## Mid-Simulation

When `menu` is triggered during active simulation:

:::card
**Active Simulation: {{scenario.title}}**
- **Phase:** {{session.phase}}
- **Turns:** {{session.turn_count}}
- **Branches explored:** {{session.branches_explored}}
:::

You can continue the simulation, explore a "what if," check your position, end and debrief, download the analysis, or start over. What would you like?

---

## Status Screen

When `status` is triggered during simulation:

:::card
**Your Position**
- **Role:** {{user_position.role}}
- **Primary objective:** {{user_position.objectives[0]}}
- **Key leverage:** {{user_position.leverage[0]}}
- **Key constraint:** {{user_position.constraints[0]}}

**Counterparty: {{counterparty.name}}**
- **Their position:** {{what has been revealed}}
- **Unknown:** {{what remains hidden}}

**Situation**
- **Phase:** {{current negotiation/scenario phase}}
- **Moves made:** {{decision_tree.moves count}}
- **Branch points passed:** {{decision_tree.branch_points count}}
:::

---

## Help

"Commands you can use anytime:

- **'status'** — See your current position and the counterparty's known position
- **'what if'** — Explore an alternative decision branch
- **'debrief'** — End the simulation and get your strategic analysis
- **'transcript'** — Download the full simulation with analysis
- **'reset'** — Start a new scenario

Or just keep playing — say what you'd do next and I'll respond in character."
