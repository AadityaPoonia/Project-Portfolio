// Runs everything sequentially via Node, reusing app.js.
// Usage (VS Code launch config provided below):
//   node runner.js ask "Your question" --k 4
//   node runner.js evaluate questions.json

const { spawnSync } = require("child_process");
const path = require("path");

function runStep(args) {
  const res = spawnSync(process.execPath, [path.join(__dirname, "app.js"), ...args], { stdio: "inherit" });
  if (typeof res.status === "number" && res.status !== 0) process.exit(res.status);
}

function main() {
  const [, , mode, ...rest] = process.argv;
  const dataDir = process.env.RAG_DATA_DIR || "data/raw";

  if (mode === "ask") {
    const q = rest[0] || `What is the main idea of 'Acres of Diamonds'?`;
    const kIndex = rest.indexOf("--k");
    const k = kIndex >= 0 ? rest[kIndex + 1] : "4";
    runStep(["ingest", dataDir]);           // 1) build/refresh index
    runStep(["ask", q, "--k", k]);          // 2) ask the question
    return;
  }

  if (mode === "evaluate") {
    const file = rest[0] || "questions.json";
    runStep(["ingest", dataDir]);           // 1) build/refresh index
    runStep(["evaluate", file]);            // 2) run eval
    return;
  }

  console.log(`Usage:
  node runner.js ask "Your question" [--k N]
  node runner.js evaluate [questions.json]`);
}
main();
