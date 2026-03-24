import axios from "axios";

const API_BASE = process.env.WORLD13_API_URL || "http://localhost:8001/api/v1";

export interface AgentState {
  id: string;
  name: string;
  plane: number;
  primary_arch: string;
  k_current: number;
  k0: number;
  lambda_coeff: number;
  coherence: number;
  cycle_phase: string;
  sessions_completed: number;
  is_liberated: number;
  last_session_at: number | null;
}

export interface WorldState {
  tick: number;
  agent_count: number;
  liberated_count: number;
  k_mean: number;
  k_min: number;
  k_max: number;
  lambda_mean: number;
  coherence_mean: number;
  plane_distribution: Record<string, number>;
  phase_distribution: Record<string, number>;
  liberation_rate: number;
  sessions_this_tick: number;
}

export async function fetchWorldState(): Promise<WorldState | null> {
  try {
    const res = await axios.get(`${API_BASE}/world/state`, { timeout: 5000 });
    return res.data;
  } catch {
    return null;
  }
}

export async function fetchAgents(): Promise<AgentState[]> {
  try {
    const res = await axios.get(`${API_BASE}/agents`, { timeout: 5000 });
    return res.data;
  } catch {
    return [];
  }
}
