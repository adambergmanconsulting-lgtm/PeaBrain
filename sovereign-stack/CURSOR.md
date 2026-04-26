# Using PeaBrain (Nadir + Ollama) from Cursor

Cursor speaks the **OpenAI** chat API. Nadir is **OpenAI-compatible** on `POST /v1/chat/completions`, but it normally expects extra **`nadir` routing** metadata. For editor use, turn on **IDE mode** so every request goes to your **local** model unless you opt into cloud (see below).

## 1. Run the stack

From `sovereign-stack/`, with Docker: `docker compose up -d --build` (or `.\setup.ps1`).

Nadir should listen on **`http://127.0.0.1:8765`**.

## 2. Point Cursor at Nadir

These names differ slightly by Cursor version; look for **OpenAI** / **API** / **Override** under **Settings → Models** (or “Custom OpenAI”).

| Setting | Value |
|--------|--------|
| **Base URL** (OpenAI override) | `http://127.0.0.1:8765/v1` |
| **API key** | Any non-empty string (Nadir does not validate it by default; e.g. `local`) |
| **Model** | Any name Cursor requires; Nadir **replaces** it with `NADIR_LOCAL_MODEL` (e.g. `qwen2.5-coder:14b` in Ollama) |

**`curl` from your own machine to `http://127.0.0.1:8765/health` works, but that does *not* guarantee Cursor can reach the same URL.** If chat/composer use Cursor’s **remote** OpenAI path, the **Override OpenAI Base URL** is still fetched by **Cursor’s servers**, not only from your desktop. Those requests **refuse to connect to “private” addresses** (e.g. `127.0.0.1`, `localhost`, and typical RFC1918 / **Tailscale `100.x`**) as an **SSRF** safeguard. You will see a **`400`** with **`"reason":"ssrf_blocked"`** and **`"connection to private IP is blocked"`**—Nadir is fine; the block is in Cursor’s infrastructure, not in your Docker stack.

### "connection to private IP is blocked" (ssrf_blocked)

**What it means:** The base URL you set points at a **private** host. **Cursor is not (only) opening a socket from the IDE on your PC** for that call; a **server-side** leg validates or proxies the request and **blocks** private IP ranges. So **`http://127.0.0.1:8765/v1` and `http://100.x.y.z:8765/v1` (Tailscale) both count as private** in that check.

**Ways to use Nadir/PeaBrain in Cursor despite that:**

1. **Public HTTPS URL in front of Nadir** (what Cursor *can* reach, then forwards to you). This repo can start a **Cloudflare quick tunnel** from Docker (ephemeral `*.trycloudflare.com` URL, no account): from **`sovereign-stack`**, run **`npm run public:url`**, then **`npm run public:url:logs`** to copy the `https://…` host. In Cursor, set **Override OpenAI Base URL** to `https://<host>/v1` (use `https://`, not `http://`). For anything reachable from the internet, set **`NADIR_INBOUND_BEARER_TOKEN`** in **`.env`** to a long random string, restart Nadir, and set Cursor’s **OpenAI API key** to the **same** value. Stop the tunnel when done: **`npm run public:url:down`**. Alternatives you run yourself: [ngrok](https://ngrok.com/) (`docker compose --profile ngrok up -d ngrok` with **`NGROK_AUTHTOKEN`** in **`.env`**), a full [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) with a custom hostname, or [Tailscale Funnel](https://tailscale.com/kb/1247/funnel).

2. **A different client that calls localhost (or your LAN) directly** (bypasses that server check): e.g. [Continue](https://continue.dev/), [Cline](https://github.com/cline/cline), or another **VS Code / local** extension that issues HTTP from your own machine. Point its base URL to `http://127.0.0.1:8765/v1` (or your tailnet) there.

3. **Cursor’s own support / changelog:** product behavior and possible “bypass to local / enterprise allowlist” options change. If a future build documents **“local” or “direct”** OpenAI overrides, re-check; until then, assume the **`ssrf_blocked` rule applies to private base URLs** for the custom OpenAI path you are using.

**For testing Nadir** without Cursor’s proxy, use a browser, `curl`, the repo **`demo`**, or an extension as in (2). **This doc’s earlier `http://127.0.0.1:8765/v1` table** remains the **intended** setup when a Cursor build **does** connect from the desktop; if you only see `ssrf_blocked`, switch to a **public-HTTPS** base URL (1) or a **local** extension (2).

### Make Chat / Composer use Nadir (not just the URL)

The **override** only matters when the active model’s requests go through the **OpenAI**-compatible path. You still have to **choose that model** in the chat UI (and set the key once).

1. **Same place as the base URL** — set **OpenAI API Key** to a placeholder (e.g. `local`) if you have not already. Nadir does not need a real key.
2. **Add a custom model** — **Settings → Models** → **Add model** (or “Custom model” / “Add OpenAI model,” wording varies). Enter any **name** you like, e.g. `peabrain` or `nadir-local` (Nadir will still use `NADIR_LOCAL_MODEL` for Ollama). If Cursor asks for a **provider** or type, pick **OpenAI** / **OpenAI-compatible**, not Azure.
3. **Open Chat** (`Ctrl`+`L` or the chat icon) or **Composer** — at the **bottom of the input** (or the **top of the panel** on some builds) open the **model** dropdown. Switch from **Auto** or a built-in name to **your new custom name** (e.g. `peabrain`). That session will call your **Override OpenAI Base URL** + that model string.
4. On the Nadir side, set **`NADIR_IDE_MODE=true`** in `.env` and restart the stack (see **§3** below) so routing stays on **Ollama** when Cursor does not send `nadir` metadata.
5. Send a message; if it fails, check **Nadir** logs: `docker compose logs nadir` and that `http://127.0.0.1:8765/health` is OK.

**If the dropdown never shows your custom model:** add it again in **Settings → Models**, or restart Cursor once after saving settings.

### “I only see Azure OpenAI (base URL, deployment name, API key)”

That block is for **Microsoft Azure OpenAI** (e.g. `https://YOUR_RESOURCE.openai.azure.com/`), with **deployments** and **API versions**. It is **not** the same as a self-hosted **OpenAI-compatible** URL.

| | Azure OpenAI in Cursor | PeaBrain (Nadir) |
|--|------------------------|------------------|
| Who hosts | Microsoft Azure | Your machine (Docker) |
| API shape | Azure chat/completions, deployment name, `api-version` query | Standard OpenAI: `POST /v1/chat/completions` |
| Filling the Azure form with `http://127.0.0.1:8765` | **Won’t work** — Cursor will call Azure’s protocol, not Nadir’s. | Use the **separate** **OpenAI** / **Override OpenAI Base URL** (non-Azure) control. |

**What to do:** In **Settings → Models**, look for **OpenAI** (without “Azure”): “OpenAI API Key,” **“Override OpenAI Base URL,”** or “Custom OpenAI.” Use that for `http://127.0.0.1:8765/v1`. The Azure section is the wrong one for Nadir.

If this Cursor version **only** shows Azure and no generic OpenAI override, use a small **OpenAI-compatible proxy** in front of Nadir (e.g. [LiteLLM](https://github.com/BerriAI/litellm)) and point **that** at what Cursor supports, or use another tool (Continue, Cline) that has a plain **base URL** field for OpenAI-style APIs.

### “I can only set a custom model by name—where is the URL?”

In Cursor, those are **two different controls**:

1. **Override OpenAI Base URL** (and usually **OpenAI API Key**) — **global** for anything that uses the “OpenAI” provider. This is **not** the same screen as “Add custom model.”
2. **Custom model name** — only the **string** Cursor sends as `model` (Nadir still maps it to your Ollama tag).

**What to do:**

1. Open **Cursor Settings** (`Ctrl`+`,`, or **File → Preferences → Cursor Settings** on some builds).
2. Go to **Models** (or use the settings **search box** and type **`base url`**, **`openai`**, or **`override`**).
3. Find the **OpenAI** section (sometimes under “OpenAI API Key”).
4. Turn **on** **Override OpenAI Base URL** (wording may be “Use custom OpenAI endpoint”).
5. Set **Base URL** to: `http://127.0.0.1:8765/v1` (must end with `/v1`).
6. Set **API Key** to any placeholder (e.g. `local`).
7. **Separately**, add or select your **custom model name** (e.g. `peabrain` or `qwen2.5-coder:14b`) in the model list. That field is **name only**; the URL from step 5 is what actually routes traffic to Nadir.

**If you still do not see a base URL field:** the UI changes between versions. Use the **search** in Settings, or check **Help → About** and compare with [Cursor forum](https://forum.cursor.com) threads on “Override OpenAI Base URL.” The value is often stored in app storage, not in a simple `settings.json` key you can paste.

**Workarounds if the app never exposes a URL:**

- **HTTP compatibility:** **Settings → Network** (or search `HTTP`) → try **HTTP/1.1** if connections to a local server fail.
- **Proxy in front of Nadir:** run **LiteLLM**, **Caddy**, or a tiny **reverse proxy** on `localhost` that maps a path to Nadir, and use that as the single “OpenAI” base URL (some teams standardize on one gateway URL for all tools).
- **Use another client** (Continue, Cline, etc.) that supports base URL + model in one place, and keep Cursor on built-in models until the UI shows the override again.

## 3. Nadir / `.env` for Cursor (required)

Cursor does **not** send the custom `nadir: { lines, multi_file, … }` JSON. Without changes, the default `NADIR_ON_MISSING_METADATA=cloud` would send traffic to **OpenRouter** and fail if you have no key.

**Enable IDE mode** so routing defaults to **local (Ollama)**:

```env
NADIR_IDE_MODE=true
NADIR_OPENROUTER_API_KEY=   # optional: only if you use cloud or nadir.use_cloud
```

Optional for **faster** replies in the editor (less lint work on every completion):

```env
NADIR_VERIFY_WITH_ESLINT=false
NADIR_VERIFY_WITH_PRETTIER=false
```

Keep verification on for “ship quality” if you can afford the latency.

Then restart Nadir: `docker compose up -d` (or rebuild if you change code: `--build`).

## 4. What you do *not* get out of the box

- **Automatic** “file line count” routing: Cursor will not fill `nadir.lines`. In **IDE mode**, that is effectively ignored and traffic stays local.
- **Cloud (OpenRouter) from the same Cursor profile** while IDE mode is on: add a **second** model in Cursor that points **directly** at OpenRouter, or set `NADIR_IDE_MODE=false` and pass `nadir` metadata from another client.
- **Opt-in cloud** through Nadir with IDE mode: only if the request body includes `"nadir": { "use_cloud": true }` (or `"complex": true` with a valid OpenRouter key), which standard Cursor will not add—so this is for custom tools / scripts.

## 5. CORS (only if a web UI fails to call Nadir)

The Cursor **desktop** app usually does not need CORS. If you use a **browser** tool against Nadir, set e.g.:

```env
NADIR_CORS_ORIGINS=*
```

(Use a tight list in production: `http://127.0.0.1:3000,http://localhost:3000`.)

## 6. Checklist

- [ ] `http://127.0.0.1:8765/health` returns `{"status":"ok"}`
- [ ] `NADIR_IDE_MODE=true` in `.env` used by the Nadir container
- [ ] Cursor base URL ends with **`/v1`**
- [ ] Ollama has your model: `docker compose exec ollama ollama list`
- [ ] If you see **`ssrf_blocked`**: use **`npm run public:url`**, read **`npm run public:url:logs`** for `https://…trycloudflare.com`, set Cursor to **`https://<host>/v1`**, and set **`NADIR_INBOUND_BEARER_TOKEN`** + matching **OpenAI API key** in Cursor (see README *Public URL*)

After that, using PeaBrain in Cursor is the same as any other custom OpenAI endpoint: pick the model in the chat/composer UI and iterate on your repo as usual.
