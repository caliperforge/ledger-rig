const { appendFileSync } = require("node:fs");
const { execFileSync } = require("node:child_process");

if (process.env.STATE_post) {
  execFileSync("/bin/bash", ["-c", process.env.INPUT_RUN], { stdio: "inherit" });
} else {
  appendFileSync(process.env.GITHUB_STATE, "post=1\n");
}
