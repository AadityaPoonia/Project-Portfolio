const { spawnSync } = require("child_process");
const args = process.argv.slice(2);
const file = args[0] || "questions.json";
const res = spawnSync(process.execPath, [require.resolve("./app.js"), "evaluate", file], { stdio: "inherit" });
process.exit(typeof res.status === "number" ? res.status : 0);