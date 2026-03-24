import { fetchWorldState, fetchAgents } from "./poller";
import { render } from "./renderer";

const POLL_INTERVAL = 5000; // 5 seconds

async function poll() {
  const [world, agents] = await Promise.all([
    fetchWorldState(),
    fetchAgents(),
  ]);
  render(world, agents);
}

async function main() {
  console.log("WORLD13 Dashboard starting...");
  await poll();
  setInterval(poll, POLL_INTERVAL);
}

main().catch((err) => {
  console.error("Dashboard error:", err.message);
  process.exit(1);
});
