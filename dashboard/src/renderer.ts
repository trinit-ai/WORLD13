import { AgentState, WorldState } from "./poller";

const RESET = "\x1b[0m";
const BOLD = "\x1b[1m";
const DIM = "\x1b[2m";
const BLUE = "\x1b[34m";
const GREEN = "\x1b[32m";
const YELLOW = "\x1b[33m";
const RED = "\x1b[31m";
const CYAN = "\x1b[36m";
const MAGENTA = "\x1b[35m";

const PHASE_COLORS: Record<string, string> = {
  ACC: DIM,
  CRS: RED,
  RES: YELLOW,
  TRN: MAGENTA,
  LIB: GREEN,
};

const ARCH_SHORT: Record<string, string> = {
  SOV: "SOV", BLD: "BLD", SKR: "SKR", WIT: "WIT",
  WAR: "WAR", HLR: "HLR", TRN: "TRN", TRK: "TRK",
  LVR: "LVR", TCH: "TCH", JDG: "JDG", MYS: "MYS", WLD: "WLD",
};

function bar(value: number, max: number, width: number = 20): string {
  const filled = Math.round((value / max) * width);
  return "█".repeat(Math.min(filled, width)) + "░".repeat(Math.max(0, width - filled));
}

export function render(world: WorldState | null, agents: AgentState[]): void {
  console.clear();

  if (!world) {
    console.log(`${BOLD}WORLD13${RESET}  ·  Waiting for API...`);
    console.log(`${DIM}Ensure the API is running: make api${RESET}`);
    return;
  }

  const w = 68;
  const line = "═".repeat(w);
  const thin = "─".repeat(w);

  console.log(`${BOLD}╔${line}╗${RESET}`);
  console.log(`${BOLD}║${RESET}  ${BLUE}${BOLD}WORLD13${RESET}  ·  Tick: ${world.tick}  ·  Sessions: ${world.sessions_this_tick}  ·  Liberations: ${world.liberated_count}${" ".repeat(Math.max(0, w - 60))}${BOLD}║${RESET}`);
  console.log(`${BOLD}╠${line}╣${RESET}`);
  console.log(`${BOLD}║${RESET}  ${CYAN}CIVILIZATION${RESET}  K(x) mean: ${world.k_mean.toFixed(2)}  λ mean: ${world.lambda_mean.toFixed(2)}  Coh: ${world.coherence_mean.toFixed(2)}${" ".repeat(Math.max(0, w - 62))}${BOLD}║${RESET}`);
  console.log(`${BOLD}║${RESET}  K range: [${world.k_min.toFixed(2)} — ${world.k_max.toFixed(2)}]  Lib rate: ${world.liberation_rate.toFixed(1)}%${" ".repeat(Math.max(0, w - 52))}${BOLD}║${RESET}`);
  console.log(`${BOLD}╠${line}╣${RESET}`);
  console.log(`${BOLD}║${RESET}  ${YELLOW}AGENTS${RESET}${" ".repeat(w - 8)}${BOLD}║${RESET}`);

  for (const a of agents) {
    const phColor = PHASE_COLORS[a.cycle_phase] || DIM;
    const lib = a.is_liberated ? ` ${GREEN}★ LIB${RESET}` : "";
    const kBar = bar(a.k_current, 10, 10);
    const cBar = bar(a.coherence, 1, 8);
    const line = `  ${a.name.padEnd(12)} P${a.plane} ${(ARCH_SHORT[a.primary_arch] || a.primary_arch).padEnd(3)}  K:${a.k_current.toFixed(2)} ${kBar}  C:${a.coherence.toFixed(2)} ${cBar}  ${phColor}${a.cycle_phase}${RESET}${lib}`;
    console.log(`${BOLD}║${RESET}${line}`);
  }

  console.log(`${BOLD}╚${line}╝${RESET}`);
  console.log(`${DIM}Refreshing every 5s...${RESET}`);
}
