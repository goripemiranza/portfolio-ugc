export async function onRequestPost({ request, env }) {
  const kv = env?.NOTIFY_KV;
  const secret = env?.NOTIFY_KEY;

  if (!kv || !secret) return json({ ok: false, error: "backend_not_configured" }, 500);

  const body = await request.json().catch(() => null);
  if (!body) return json({ ok: false, error: "bad_json" }, 400);

  const assetId = String(body.assetId || "").trim();
  const uid = String(body.uid || "").trim();
  const wantLike = !!body.like;

  if (!assetId || !/^\d+$/.test(assetId)) return json({ ok: false, error: "bad_asset" }, 400);
  if (!uid) return json({ ok: false, error: "bad_uid" }, 400);

  const uidHash = await hmacId(secret, uid);
  const likedKey = `liked:${assetId}:${uidHash}`;
  const countKey = `likes:${assetId}`;

  const already = await kv.get(likedKey);
  let count = parseInt((await kv.get(countKey)) || "0", 10);
  if (!Number.isFinite(count) || count < 0) count = 0;

  if (wantLike) {
    if (!already) {
      count = count + 1;
      await kv.put(countKey, String(count));
      await kv.put(likedKey, "1", { expirationTtl: 60 * 60 * 24 * 365 });
    }
    return json({ ok: true, liked: true, count });
  }

  // unlike
  if (already) {
    count = Math.max(0, count - 1);
    await kv.put(countKey, String(count));
    await kv.delete(likedKey);
  }
  return json({ ok: true, liked: false, count });
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      "content-type": "application/json",
      "cache-control": "no-store",
    },
  });
}

// HMAC id from secret + message (accept any secret format)
async function hmacId(secret, msg) {
  const keyBytes = await deriveKeyBytes(secret);
  const key = await crypto.subtle.importKey("raw", keyBytes, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(msg));
  return b64url(sig).slice(0, 22);
}

async function deriveKeyBytes(secret) {
  const s = String(secret || "").trim();

  // Try base64 decode first
  try {
    const raw = atob(s);
    const out = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    if (out.length >= 16) return out; // ok
  } catch {}

  // Fallback: hash string => 32 bytes
  const dig = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s || "fallback"));
  return new Uint8Array(dig);
}

function b64url(buf) {
  const bytes = new Uint8Array(buf);
  let s = "";
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}
