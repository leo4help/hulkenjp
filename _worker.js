/**
 * Hulken JP 廣告成效週報 — Cloudflare Pages advanced-mode worker (added 2026-10-14, W41).
 * Same approach as the innodanc weekly report: Insight & Suggestion is editable online,
 * stored in Cloudflare D1.
 *
 *   GET    /api/insights           -> { me, canEdit, insights: { "2026-10-08": {blocks, _by, _at} } }
 *   PUT    /api/insights           -> body { week: "YYYY-MM-DD" (report week start, Thursday), data: { blocks: { overall:{rows,actions}, metaTest:{rows}, metaCreative:{rows}, kol:{rows}, shopify:{rows} } } }
 *   DELETE /api/insights?week=...  -> delete the online version (page falls back to the built-in insights.json draft)
 *   anything else                  -> static files (env.ASSETS; clean URLs like /all keep working)
 *
 * Pages settings (project hulkenjp):
 *   D1 binding DB              -> D1 database hulken-report
 *   var CF_ACCESS_TEAM_DOMAIN  -> lucky-sun-db7c.cloudflareaccess.com
 *   var CF_ACCESS_AUD          -> Access application "hulkenjp.pages.dev" AUD tag
 *   var ALLOWED_EDITORS        -> ads@wakazocorp.com   (only this email can edit; other @wakazocorp.com viewers read only)
 *
 * Identity comes only from the signature-verified Cloudflare Access JWT (Cf-Access-Jwt-Assertion).
 * Tables are created on first call; every save / revert also writes a history row.
 */
const KEY_RE = /^\d{4}-\d{2}-\d{2}$/;
const MAX_BYTES = 60000;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/api/insights") {
      try {
        return await handleInsights(request, env, url);
      } catch (e) {
        return json({ error: "server error: " + (e && e.message ? e.message : String(e)) }, 500);
      }
    }
    return env.ASSETS.fetch(request);
  },
};

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

/* ------------------------------------------------------------------ auth */
let jwksCache = null, jwksAt = 0, jwksFor = "";
async function getKeys(team) {
  if (jwksCache && jwksFor === team && Date.now() - jwksAt < 3600e3) return jwksCache;
  const r = await fetch(`https://${team}/cdn-cgi/access/certs`);
  if (!r.ok) throw new Error("cannot load Access certs");
  jwksCache = (await r.json()).keys || [];
  jwksAt = Date.now();
  jwksFor = team;
  return jwksCache;
}
function b64urlToBytes(s) {
  s = s.replace(/-/g, "+").replace(/_/g, "/");
  while (s.length % 4) s += "=";
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}
const b64urlJson = (s) => JSON.parse(new TextDecoder().decode(b64urlToBytes(s)));

function allowed(email, env) {
  const list = String(env.ALLOWED_EDITORS || "").split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
  if (!list.length) return false; // fail closed: nobody edits unless explicitly listed
  return list.some((x) => (x.startsWith("@") ? email.endsWith(x) : email === x));
}

async function getUser(request, env) {
  const team = (env.CF_ACCESS_TEAM_DOMAIN || "").trim();
  const aud = (env.CF_ACCESS_AUD || "").trim();
  if (!team || !aud) return { error: "server misconfigured: CF_ACCESS_TEAM_DOMAIN / CF_ACCESS_AUD", status: 500 };
  const token = request.headers.get("cf-access-jwt-assertion");
  if (!token) return { error: "not signed in", status: 401 };
  const parts = token.split(".");
  if (parts.length !== 3) return { error: "bad token", status: 401 };
  const header = b64urlJson(parts[0]);
  const payload = b64urlJson(parts[1]);
  const keys = await getKeys(team);
  const jwk = keys.find((k) => k.kid === header.kid);
  if (!jwk) return { error: "unknown signing key", status: 401 };
  const key = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
  const ok = await crypto.subtle.verify(
    "RSASSA-PKCS1-v1_5", key, b64urlToBytes(parts[2]), new TextEncoder().encode(parts[0] + "." + parts[1])
  );
  if (!ok) return { error: "invalid signature", status: 401 };
  const now = Math.floor(Date.now() / 1000);
  if (payload.exp && payload.exp < now) return { error: "token expired", status: 401 };
  const auds = Array.isArray(payload.aud) ? payload.aud : [payload.aud];
  if (!auds.includes(aud)) return { error: "wrong audience", status: 401 };
  if (payload.iss && payload.iss !== `https://${team}`) return { error: "wrong issuer", status: 401 };
  const email = String(payload.email || "").toLowerCase();
  if (!email) return { error: "no email in token", status: 403 };
  return { email, canEdit: allowed(email, env) };
}

/* ------------------------------------------------------------------ db */
let schemaReady = false;
async function ensureSchema(db) {
  if (schemaReady) return;
  await db.batch([
    db.prepare(`CREATE TABLE IF NOT EXISTS insights (
      week TEXT PRIMARY KEY, data TEXT NOT NULL, updated_by TEXT NOT NULL,
      updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')))`),
    db.prepare(`CREATE TABLE IF NOT EXISTS insights_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT, week TEXT NOT NULL, data TEXT,
      action TEXT NOT NULL, updated_by TEXT NOT NULL,
      updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')))`),
  ]);
  schemaReady = true;
}

const BLOCK_KEYS = ["overall", "metaTest", "metaCreative", "kol", "shopify"];

function validRows(rows) {
  if (!Array.isArray(rows)) return "rows must be an array";
  for (const r of rows) {
    if (!r || typeof r !== "object") return "row must be an object";
    for (const k of ["channel", "title", "insight", "suggestion"]) {
      if (r[k] !== undefined && typeof r[k] !== "string") return `row.${k} must be a string`;
    }
  }
  return null;
}

// v2 (2026-10-14): data = { blocks: { overall: {rows, actions}, metaTest: {rows}, metaCreative: {rows}, kol: {rows}, shopify: {rows} } }
function validate(data) {
  if (!data || typeof data !== "object" || !data.blocks || typeof data.blocks !== "object") return "data.blocks must be an object";
  for (const [k, v] of Object.entries(data.blocks)) {
    if (!BLOCK_KEYS.includes(k)) return `unknown block ${k}`;
    if (!v || typeof v !== "object") return `block ${k} must be an object`;
    const e = validRows(v.rows);
    if (e) return `${k}: ${e}`;
    if (v.actions !== undefined) {
      if (!Array.isArray(v.actions)) return `${k}.actions must be an array`;
      for (const a of v.actions) if (typeof a !== "string") return "actions must be strings";
    }
  }
  return null;
}

function cleanData(data) {
  const blocks = {};
  for (const k of BLOCK_KEYS) {
    const v = data.blocks[k];
    if (!v) continue;
    blocks[k] = {
      rows: v.rows.map((r) => ({ channel: r.channel || "", title: r.title || "", insight: r.insight || "", suggestion: r.suggestion || "" })),
    };
    if (Array.isArray(v.actions)) blocks[k].actions = v.actions;
  }
  return { blocks };
}

async function handleInsights(request, env, url) {
  if (!env.DB) return json({ error: "server misconfigured: D1 binding DB missing" }, 500);
  const user = await getUser(request, env);
  if (user.error) return json({ error: user.error }, user.status);
  await ensureSchema(env.DB);

  if (request.method === "GET") {
    const { results } = await env.DB.prepare("SELECT week, data, updated_by, updated_at FROM insights").all();
    const insights = {};
    for (const r of results || []) {
      try { insights[r.week] = { ...JSON.parse(r.data), _by: r.updated_by, _at: r.updated_at }; } catch (e) { /* skip */ }
    }
    return json({ me: user.email, canEdit: user.canEdit, insights });
  }

  if (!user.canEdit) return json({ error: "沒有編輯權限" }, 403);

  if (request.method === "PUT") {
    const body = await request.json().catch(() => null);
    if (!body || !KEY_RE.test(body.week || "")) return json({ error: "week must be YYYY-MM-DD" }, 400);
    const err = validate(body.data);
    if (err) return json({ error: err }, 400);
    const clean = cleanData(body.data);
    const text = JSON.stringify(clean);
    if (text.length > MAX_BYTES) return json({ error: "content too long" }, 413);
    const at = new Date().toISOString().replace(/\.\d+Z$/, "Z");
    await env.DB.batch([
      env.DB.prepare(
        `INSERT INTO insights (week, data, updated_by, updated_at) VALUES (?1, ?2, ?3, ?4)
         ON CONFLICT(week) DO UPDATE SET data = excluded.data, updated_by = excluded.updated_by, updated_at = excluded.updated_at`
      ).bind(body.week, text, user.email, at),
      env.DB.prepare(
        "INSERT INTO insights_history (week, data, action, updated_by, updated_at) VALUES (?1, ?2, 'save', ?3, ?4)"
      ).bind(body.week, text, user.email, at),
    ]);
    return json({ ok: true, item: { ...clean, _by: user.email, _at: at } });
  }

  if (request.method === "DELETE") {
    const week = url.searchParams.get("week") || "";
    if (!KEY_RE.test(week)) return json({ error: "week must be YYYY-MM-DD" }, 400);
    const at = new Date().toISOString().replace(/\.\d+Z$/, "Z");
    await env.DB.batch([
      env.DB.prepare("DELETE FROM insights WHERE week = ?1").bind(week),
      env.DB.prepare(
        "INSERT INTO insights_history (week, data, action, updated_by, updated_at) VALUES (?1, NULL, 'revert', ?2, ?3)"
      ).bind(week, user.email, at),
    ]);
    return json({ ok: true });
  }

  return json({ error: "method not allowed" }, 405);
}
