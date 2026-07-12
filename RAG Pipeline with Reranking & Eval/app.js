
const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

function detectPython() {
  const cands = [process.env.PYTHON, "python3", "python", "py"].filter(Boolean);
  for (const cmd of cands) {
    const res = spawnSync(cmd, ["--version"], { encoding: "utf8" });
    if (!res.error && (res.status === 0 || res.status === null)) return cmd;
  }
  throw new Error("No Python interpreter found (set $PYTHON or install python3).");
}

function ensureData(defaultDir) {
  const expect = [
    "AcresOfDiamonds.pdf",
    "p-t-barnum_art-of-money-getting.pdf",
    "science-of-getting-rich.pdf",
    "Smiles_0379.pdf",
  ];
  const missing = expect.filter(f => !fs.existsSync(path.join(defaultDir, f)));
  if (missing.length) {
    console.warn("[warn] Missing PDFs in", defaultDir, "→", missing.join(", "));
  }
}

function runPy(args) {
  const py = detectPython();
  const script = path.join(__dirname, "app.py");
  const res = spawnSync(py, [script, ...args], { stdio: "inherit" });
  if (typeof res.status === "number") process.exitCode = res.status;
}

function usage() {
  console.log(`
📚🤖 RAG Q&A App (Node wrapper -> Python)
Commands:
  node app.js ingest [folder]            # default: data/raw
  node app.js ask "Your question" [--k N]
  node app.js evaluate [questions.json]  # default: questions.json
`);
}

function main() {
  const [, , cmd, ...rest] = process.argv;
  if (!cmd || ["-h", "--help", "help"].includes(cmd)) return usage();

  if (cmd === "ingest") {
    const dir = rest[0] || "data/raw";
    ensureData(path.resolve(dir));
    return runPy(["ingest", dir]);
  }
  if (cmd === "ask") {
    if (!rest[0]) return usage();
    const kIndex = rest.indexOf("--k");
    const k = kIndex >= 0 ? rest[kIndex + 1] : null;
    const q = rest[0];
    const args = ["ask", q];
    if (k) args.push("--k", k);
    return runPy(args);
  }
  if (cmd === "evaluate") {
    const file = rest[0] || "questions.json";
    return runPy(["evaluate", file]);
  }
  // passthrough for any future subcommands
  runPy([cmd, ...rest]);
}

if (require.main === module) {
  try { main(); } catch (e) { console.error(e); process.exit(1); }
}
