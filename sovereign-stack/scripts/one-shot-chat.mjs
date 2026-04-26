#!/usr/bin/env node
/**
 * One request to Nadir (OpenAI-shaped). Set NADIR_BASE if not using default.
 * Usage: node scripts/one-shot-chat.mjs "Your question"
 */
import { defaultSystem, getChatSampling } from "./lib/chat-defaults.mjs";

const base = (process.env.NADIR_BASE || "http://127.0.0.1:8765").replace(/\/$/, "");
const text =
  process.argv.slice(2).join(" ") || "Reply in one short sentence: what is 2+2?";

const res = await fetch(`${base}/v1/chat/completions`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    model: "nadir",
    messages: [
      { role: "system", content: defaultSystem },
      { role: "user", content: text },
    ],
    ...getChatSampling(),
    nadir: { lines: 100, multi_file: false, complex: false },
  }),
});

const raw = await res.text();
if (!res.ok) {
  console.error(`HTTP ${res.status}: ${raw}`);
  process.exit(1);
}
let j;
try {
  j = JSON.parse(raw);
} catch {
  console.error(raw);
  process.exit(1);
}
const c = j.choices?.[0]?.message?.content;
if (c != null) {
  console.log(c);
} else {
  console.log(JSON.stringify(j, null, 2));
}
