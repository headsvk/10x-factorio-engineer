# Claude Artifact Runtime API — Field Research

Discovered by empirical testing (March 2026). None of this is officially documented.

**Test suite:** `dev/artifact-api-test.html` — paste into claude.ai as `application/vnd.ant.html` and run
sections A–H. Compare output against this file to identify what broke.

---

## Environment Summary

| Property | Desktop (Chrome) | Android App |
|----------|-----------------|-------------|
| `window.claude` | object | object |
| `window.storage` | object | object |
| `localStorage` | works, persists | works, NOT synced from desktop |
| `sessionStorage` | works | works |
| `indexedDB` | works | works |
| `document.cookie` | blocked | blocked |
| `navigator.storage.estimate` | works | works |
| Browser quota | ~10 GB | ~140 GB |
| `window.storage` (unpublished) | fails silently (returns object) | throws "Storage set failed: Unexpected response type" |

---

## `window.claude`

Four methods discovered. All are async (return Promises).

### `complete(prompt: string): Promise<string>`

Calls Claude with a plain string prompt. Returns Claude's response as a plain string.

```js
const response = await window.claude.complete('What is 2 + 2?');
// response === "2 + 2 = 4"
```

**Behavior:**
- Single string in, single string out — no messages array, no system prompt parameter
- No built-in conversation history — must manually encode history in the prompt string
- Billed to the signed-in user's account, not the artifact creator
- Latency: ~2.1–2.7 s observed
- Users must be signed into Anthropic to use this

**Multi-turn pattern (manual history encoding):**
```js
const history = []; // { role: 'user'|'assistant', content: string }[]

async function chat(userMessage) {
  history.push({ role: 'user', content: userMessage });
  const prompt = `Conversation so far:\n${
    history.map(m => `${m.role.toUpperCase()}: ${m.content}`).join('\n')
  }\nRespond to the last user message only.`;
  const response = await window.claude.complete(prompt);
  history.push({ role: 'assistant', content: response });
  return response;
}
```

**Confirmed working:** context maintained across 4 turns in a single session.

**Unknown:**
- Maximum prompt length / token limit
- Exact error types thrown on failure
- Whether the model is configurable (appears to be a fixed Claude model)
- Rate limits

---

### `sendConversationMessage(message: string): Promise<undefined>`

**Confirmed:** does not throw, returns `undefined`.
**Confirmed:** does NOT post a visible message to the Claude.ai conversation chat UI.
**Unknown:** what it actually does internally. Possibly a no-op, possibly for future use.

**Decision:** do not use this in the dashboard.

---

### `openExternal(url: string): Promise<undefined>`

Opens a URL outside the artifact sandbox.

```js
await window.claude.openExternal('https://factoriolab.github.io/...');
```

**Behavior:**
- Shows a confirmation dialog: "Do you want to open external URL?" before proceeding
- Returns `undefined`
- Works on both desktop and Android

**Use in dashboard:** wiki links, external resources.

---

### `downloadFile(filename: string, content: string): Promise<undefined>`

Triggers a file download from within the artifact.

```js
await window.claude.downloadFile('factory.json', JSON.stringify(state, null, 2));
```

**Confirmed working:** string content.
**Untested:** Blob content, ArrayBuffer content — the probe tried all three but only confirmed string returned `undefined` (success). Blob/object may also work.
**Returns:** `undefined`

**Use in dashboard:** Export `FACTORY_STATE` as `factory.json` for CLI sync.

---

## `window.storage`

Anthropic's server-side persistent storage. Cross-device. Requires the artifact to be **published** — fails silently on desktop (returns error object) and throws on Android when unpublished.

**API shape:** `get`, `set`, `delete`, `list` (not `getItem`/`setItem` — those are `undefined`)

All methods return **protobuf response objects** with an `@type` field:
`type.googleapis.com/anthropic.claude.usercontent.sandbox.StorageXxxResponse`

This is a Google protobuf API — internal Anthropic infrastructure.

---

### `set(key: string, value: string): Promise<StorageSetResponse>`

```js
const r = await window.storage.set('factory_state', JSON.stringify(state));
// r === {
//   key: "factory_state",
//   value: "...",
//   shared: false,
//   "@type": "type.googleapis.com/anthropic.claude.usercontent.sandbox.StorageSetResponse"
// }
```

**Note:** value must be a string. JSON-serialize objects before storing.

---

### `get(key: string): Promise<StorageGetResponse>`

```js
const r = await window.storage.get('factory_state');
const value = r?.value;  // the stored string, or undefined if key doesn't exist
// r === {
//   key: "factory_state",
//   value: "...",
//   shared: false,
//   "@type": "type.googleapis.com/anthropic.claude.usercontent.sandbox.StorageGetResponse"
// }
```

**Important:** returns an object, not a raw string. Always access `.value`.

---

### `list(prefix?: string): Promise<StorageListResponse>`

```js
const r = await window.storage.list();
const keys = r.keys; // string[]
// r === {
//   keys: ["factory_state", "other_key"],
//   prefix: null,
//   shared: false,
//   "@type": "type.googleapis.com/anthropic.claude.usercontent.sandbox.StorageListResponse"
// }
```

Prefix filtering may be supported (untested): `window.storage.list('prefix_')`.

---

### `delete(key: string): Promise<?>` — UNTESTED

Exists as a function. Return shape unknown. Presumably:
```js
await window.storage.delete('factory_state');
```

---

### Shared storage — UNTESTED

All observed responses have `shared: false`. The Anthropic support article mentions
"personal storage" and "shared storage" (shared = all users of the artifact see the same data).
Likely accessed via a third argument or a separate API:
```js
// Hypothetical — not confirmed:
await window.storage.set('key', 'value', { shared: true });
```

---

### `window.storage` limits and behaviour

| Property | Value / Status |
|----------|---------------|
| Limit | 20 MB per artifact (per Anthropic support article) |
| Data type | Text only — no binary, no images |
| Requires publishing | Yes — fails when artifact is unpublished |
| Cross-device | Yes — server-side storage |
| Survives browser clear | Yes (server-side) |
| Survives unpublishing | No — "Unpublishing permanently deletes all storage data" |

---

## `localStorage`

Standard browser `localStorage`. Available in JSX artifacts (`application/vnd.ant.react`).
The llmindset.co.uk article notes it's NOT available on the Claude mobile app — use as fallback only.

| Property | Value |
|----------|-------|
| Persists across reloads | Yes (confirmed: count incremented on 2nd load) |
| Cross-device sync | No — device/browser local only |
| Shared across artifacts | Yes — all claude.ai artifacts share the same origin |
| Quota | ~10 GB (browser quota) |

**Origin sharing:** a `tasks` key from a different artifact was visible in our probe.
This means localStorage is NOT isolated per artifact — be careful with key naming.
Use a namespaced prefix: `factorio_engineer_*`.

---

## Storage fallback wrapper (for the dashboard)

```ts
const STORAGE_KEY = 'factorio_engineer_state';

async function saveState(state: object): Promise<void> {
  const json = JSON.stringify(state);
  try {
    await window.storage.set(STORAGE_KEY, json);
  } catch {
    localStorage.setItem(STORAGE_KEY, json);
  }
}

async function loadState(): Promise<object | null> {
  try {
    const r = await window.storage.get(STORAGE_KEY);
    return r?.value ? JSON.parse(r.value) : null;
  } catch {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  }
}
```

---

## Breakage detection checklist

Run these checks if the artifact stops working after a Claude.ai update:

### 1. `window.claude` structure changed
```js
console.assert(typeof window.claude === 'object', 'window.claude missing');
console.assert(typeof window.claude.complete === 'function', 'complete() missing');
console.assert(typeof window.claude.openExternal === 'function', 'openExternal() missing');
console.assert(typeof window.claude.downloadFile === 'function', 'downloadFile() missing');
```

### 2. `complete()` return type changed
```js
const r = await window.claude.complete('say: PING');
console.assert(typeof r === 'string', `complete() returned ${typeof r}, expected string`);
```

### 3. `window.storage` structure changed
```js
console.assert(typeof window.storage === 'object', 'window.storage missing');
console.assert(typeof window.storage.get === 'function', 'storage.get missing');
console.assert(typeof window.storage.set === 'function', 'storage.set missing');
```

### 4. `window.storage` return shape changed
```js
const r = await window.storage.set('__probe__', 'test');
console.assert('value' in r, `storage.set response missing .value — got: ${JSON.stringify(r)}`);
const g = await window.storage.get('__probe__');
console.assert('value' in g, `storage.get response missing .value — got: ${JSON.stringify(g)}`);
console.assert(g.value === 'test', `storage round-trip failed — got: ${g.value}`);
```

### 5. `localStorage` no longer available
```js
try {
  localStorage.setItem('__probe__', '1');
  console.assert(localStorage.getItem('__probe__') === '1', 'localStorage read/write broken');
  localStorage.removeItem('__probe__');
} catch (e) {
  console.error('localStorage blocked:', e.message);
}
```

### 6. `window.storage` works when published
After publishing the artifact, rerun the storage round-trip above. If it still fails,
the API changed or the publish step is broken.

---

## External scripts via cdnjs

**Confirmed working** (March 2026): `<script src="...">` tags pointing to `cdnjs.cloudflare.com`
load successfully inside `application/vnd.ant.html` artifacts.

Test proof: `dev/cdn-test-explosion.html` loaded `animejs` from cdnjs with no CSP errors.

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/animejs/3.2.2/anime.min.js"
  crossorigin="anonymous" referrerpolicy="no-referrer"></script>
```

**Key findings:**
- CDN scripts load without Content-Security-Policy violations
- `crossorigin="anonymous" referrerpolicy="no-referrer"` attributes work correctly
- The subdomain `cdnjs.cloudflare.com` is allowed; other CDNs (unpkg, jsdelivr) untested but likely also work
- This means vanilla HTML artifacts can load third-party libraries without bundling them inline

**Decision for dashboard:** no external scripts needed — dashboard is pure vanilla HTML/JS with no runtime dependencies. CDN loading is available as an option if future features require a library.

---

## What to retest when the artifact breaks

Priority order:

1. **Does `window.claude` exist?** — if not, API was removed/renamed
2. **Does `complete()` return a string?** — if it returns an object, parse shape changed
3. **Does `window.storage.get()` return `{value: string}`?** — if return shape changed, update `.value` access everywhere
4. **Does `window.storage` work unpublished?** — if Anthropic changes the gating, our fallback logic may need updating
5. **Does `localStorage` still work?** — if CSP changes, the fallback breaks
6. **Does `openExternal` still show a dialog?** — UX change, not a breakage but affects trust messaging
7. **Does `downloadFile` still accept plain strings?** — if it now requires Blob, update export function

---

## Untested / open questions

| Question | Why it matters |
|----------|---------------|
| `window.storage.delete()` return shape | Needed for state cleanup |
| `window.storage` shared mode API | Could enable multi-user / public factory sharing |
| `window.storage.list(prefix)` with prefix | Useful for namespacing multiple saves |
| `window.claude.complete()` error types | Need to handle gracefully in chat UI |
| `window.claude.complete()` token limit | Matters if FACTORY_STATE + history gets large |
| `window.storage` behaviour after republish | Does existing data survive a republish? |
| `fetch()` availability | If unblocked, could call external APIs (e.g. factoriolab) |
| `sendConversationMessage` actual purpose | Currently a no-op from our perspective |
| `shared: false` — is `shared: true` possible? | Cross-user shared state for multiplayer factories |
