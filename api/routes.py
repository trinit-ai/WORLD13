"""
api/routes.py — All REST endpoints for WORLD13.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import json

router = APIRouter()


def _vault():
    from .app import vault
    if vault is None:
        raise HTTPException(status_code=503, detail="Vault not initialized")
    return vault


# ── World State ──

@router.get("/world/state")
async def world_state():
    v = _vault()
    states = v.get_world_state(limit=1)
    if not states:
        return {"tick": 0, "message": "No ticks recorded yet"}
    state = states[0]
    state["plane_distribution"] = json.loads(state["plane_distribution"]) if isinstance(state["plane_distribution"], str) else state["plane_distribution"]
    state["phase_distribution"] = json.loads(state["phase_distribution"]) if isinstance(state["phase_distribution"], str) else state["phase_distribution"]
    return state


@router.get("/world/history")
async def world_history(n: int = Query(default=20, ge=1, le=200)):
    v = _vault()
    states = v.get_world_state(limit=n)
    for s in states:
        s["plane_distribution"] = json.loads(s["plane_distribution"]) if isinstance(s["plane_distribution"], str) else s["plane_distribution"]
        s["phase_distribution"] = json.loads(s["phase_distribution"]) if isinstance(s["phase_distribution"], str) else s["phase_distribution"]
    return states


# ── Agents ──

@router.get("/agents")
async def list_agents():
    v = _vault()
    agents = v.get_all_agents()
    for a in agents:
        if isinstance(a.get("archetype_weights"), str):
            a["archetype_weights"] = json.loads(a["archetype_weights"])
    return agents


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    v = _vault()
    agent = v.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if isinstance(agent.get("archetype_weights"), str):
        agent["archetype_weights"] = json.loads(agent["archetype_weights"])
    return agent


@router.get("/agents/{agent_id}/vault")
async def agent_vault_records(agent_id: str):
    v = _vault()
    records = v.get_agent_vault_records(agent_id, limit=20)
    return records


@router.get("/agents/{agent_id}/context")
async def agent_context(agent_id: str):
    v = _vault()
    agent_data = v.get_agent(agent_id)
    if not agent_data:
        raise HTTPException(status_code=404, detail="Agent not found")

    from engine.agent import Agent
    from engine.context import sample_context
    agent = Agent.from_dict(agent_data)
    ctx = sample_context(agent.tvr)
    ctx.agent_id = agent_id

    leaves_out = {}
    for axis, leaf in ctx.leaves.items():
        leaves_out[axis] = {
            "id": leaf.id,
            "name": leaf.name,
            "description": leaf.description,
            "k_modifier": leaf.k_modifier,
            "lambda_modifier": leaf.lambda_modifier,
        }

    return {
        "agent_id": agent_id,
        "k_total_modifier": round(ctx.k_total_modifier, 3),
        "lambda_total_modifier": round(ctx.lambda_total_modifier, 3),
        "leaves": leaves_out,
    }


# ── Simulation Control ──

@router.post("/simulation/tick")
async def manual_tick():
    from engine.simulation import WorldSimulation
    sim = WorldSimulation()
    result = await sim.tick()
    return result


# ── Vault Query ──

@router.get("/vault/query")
async def vault_query(dim: str = Query(...), val: str = Query(...)):
    v = _vault()
    records = v.query_by_dimension(dim, val)
    return records


# ── Reference Data ──

@router.get("/planes")
async def list_planes():
    from engine.planes import PLANES
    return {str(k): {
        "id": v.id, "name": v.name, "symbol": v.symbol,
        "description": v.description, "domains": v.domains,
        "avg_k": v.avg_k, "avg_lambda": v.avg_lambda,
        "vedanta": v.vedanta, "kabbalah": v.kabbalah,
        "theosophy": v.theosophy, "buddhism": v.buddhism,
    } for k, v in PLANES.items()}


@router.get("/archetypes")
async def list_archetypes():
    from engine.archetypes import ARCHETYPES
    return {k: {
        "code": v.code, "name": v.name, "tarot_anchor": v.tarot_anchor,
        "jungian": v.jungian, "sephira": v.sephira,
        "karmic_role": v.karmic_role, "liberation_path": v.liberation_path,
        "avg_k": v.avg_k, "avg_lambda": v.avg_lambda,
        "plane_affinity": v.plane_affinity, "liberation_path_id": v.liberation_path_id,
    } for k, v in ARCHETYPES.items()}


@router.get("/protocols/accessible")
async def accessible_protocols(agent_id: str = Query(...)):
    v = _vault()
    agent_data = v.get_agent(agent_id)
    if not agent_data:
        raise HTTPException(status_code=404, detail="Agent not found")

    from engine.protocols import get_accessible_protocols
    protocols = get_accessible_protocols(
        agent_data["plane"],
        agent_data["primary_arch"],
        agent_data["k_current"],
    )
    return protocols[:50]  # Cap at 50 for response size
