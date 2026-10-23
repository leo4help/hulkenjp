/**
 * Hulken JP 短網址 — Cloudflare Pages advanced-mode worker (added 2026-10-22).
 * Pages project: hulken-go  (repo leo4help/hulkenjp, root directory "golinks")
 * Public domain: go.hulken.co.jp  (GoDaddy DNS: CNAME go -> hulken-go.pages.dev)
 *
 *   GET /<slug>   -> 302 to links.url (and logs a click)
 *   GET /         -> 302 to https://hulken.co.jp/
 *   unknown slug  -> 302 to https://hulken.co.jp/
 *
 * This project is PUBLIC (no Cloudflare Access) and is read-only on links:
 * links are created/edited only from hulkenjp.pages.dev (behind Access).
 *
 * Pages settings (project hulken-go):
 *   D1 binding DB -> D1 database hulken-report (same DB as hulkenjp)
 */
const HOME = "https://hulken.co.jp/";
const SLUG_RE = /^[A-Za-z0-9_-]{1,64}$/;
const BOT_RE = /bot|crawl|spider|preview|facebookexternalhit|slurp|whatsapp|line-poker|linkexpand|embedly|curl|wget|python|headless/i;

let schemaReady = false;
async function ensureSchema(db) {
  if (schemaReady) return;
  await db.batch([
    db.prepare(`CREATE TABLE IF NOT EXISTS links (
      slug TEXT PRIMARY KEY COLLATE NOCASE, url TEXT NOT NULL, note TEXT,
      active INTEGER NOT NULL DEFAULT 1, clicks INTEGER NOT NULL DEFAULT 0,
      created_by TEXT, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
      last_click_at TEXT)`),
    db.prepare(`CREATE TABLE IF NOT EXISTS link_clicks (
      id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL,
      at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
      country TEXT, referer TEXT, is_bot INTEGER NOT NULL DEFAULT 0)`),
    db.prepare("CREATE INDEX IF NOT EXISTS link_clicks_slug_at ON link_clicks (slug, at)"),
  ]);
  schemaReady = true;
}

function redirect(to) {
  return new Response(null, { status: 302, headers: { Location: to, "cache-control": "no-store" } });
}

async function logClick(env, slug, request) {
  const ua = request.headers.get("user-agent") || "";
  const isBot = BOT_RE.test(ua) ? 1 : 0;
  let ref = "";
  try { ref = new URL(request.headers.get("referer") || "").host; } catch (e) { /* no referer */ }
  const country = (request.cf && request.cf.country) || "";
  const stmts = [
    env.DB.prepare("INSERT INTO link_clicks (slug, country, referer, is_bot) VALUES (?1, ?2, ?3, ?4)").bind(slug, country, ref, isBot),
  ];
  if (!isBot) {
    stmts.push(env.DB.prepare(
      "UPDATE links SET clicks = clicks + 1, last_click_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE slug = ?1"
    ).bind(slug));
  }
  await env.DB.batch(stmts);
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    let slug = url.pathname.replace(/^\/+|\/+$/g, "");
    try { slug = decodeURIComponent(slug); } catch (e) { return redirect(HOME); }

    if (slug === "robots.txt") {
      return new Response("User-agent: *\nDisallow: /\n", { headers: { "content-type": "text/plain" } });
    }
    if (!slug || !SLUG_RE.test(slug) || !env.DB) return redirect(HOME);

    let row = null;
    try {
      await ensureSchema(env.DB);
      row = await env.DB.prepare("SELECT slug, url FROM links WHERE slug = ?1 AND active = 1").bind(slug).first();
    } catch (e) {
      return redirect(HOME);
    }
    if (!row || !/^https?:\/\//i.test(row.url)) return redirect(HOME);

    if (request.method === "GET") ctx.waitUntil(logClick(env, row.slug, request).catch(() => {}));
    return redirect(row.url);
  },
};
