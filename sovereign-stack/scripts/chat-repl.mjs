#!/usr/bin/env node
/**
 * Tiny multi-turn chat against Nadir (local routing). Ctrl+C to exit.
 * env: NADIR_BASE, NADIR_CHAT_SYSTEM, NADIR_CHAT_TEMPERATURE, NADIR_CHAT_TOP_P, NADIR_CHAT_MAX_TOKENS
 * (see scripts/lib/chat-defaults.mjs and .env.example)
 */
import * as readline from "node:readline";
import { stdin as input, stdout as output } from "node:process";
import { defaultSystem, getChatSampling } from "./lib/chat-defaults.mjs";

const base = (process.env.NADIR_BASE || "http://127.0.0.1:8765").replace(/\/$/, "");
const messages = [{ role: "system", content: defaultSystem }];

const sampling = getChatSampling();

async function complete(userText) {
  messages.push({ role: "user", content: userText });
  const res = await fetch(`${base}/v1/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "nadir",
      messages,
      ...sampling,
      nadir: { lines: 200, multi_file: false, complex: false },
    }),
  });
  const raw = await res.text();
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${raw}`);
  }
  const j = JSON.parse(raw);
  const c = j.choices?.[0]?.message?.content;
  if (c == null) {
    throw new Error(raw);
  }
  messages.push({ role: "assistant", content: c });
  return c;
}

const rl = readline.createInterface({ input, output });
console.log(`Nadir chat  |  ${base}/v1  |  empty line to quit\n`);
rl.setPrompt("You> ");
rl.prompt();

rl.on("line", async (line) => {
  if (!String(line).trim()) {
    rl.close();
    return;
  }
  try {
    const reply = await complete(String(line));
    console.log(`AI> ${reply}\n`);
  } catch (e) {
    console.error(String(e && e.message ? e.message : e), "\n");
  }
  rl.prompt();
});

rl.on("close", () => process.exit(0));
