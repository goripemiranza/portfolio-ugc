// /functions/api/like.js
// Global likes (visible to everyone) stored in Cloudflare KV (binding: NOTIFY_KV)

export async function onRequestPost({ request, env }) {
  const kv = env?.NOTIFY_KV;
  if (!kv) return json({ ok: false, error: "kv_not_configured" }, 500);

  const body = await request.json().catch(() => null);
  if (!body) return json({ ok: false, error: "bad_json" }, 400);

  const assetId = String(body.assetId || "").trim();
  const uid = String(body.uid || "").trim();
  const wantLike = !!body.like;

  if (!assetId || !/^\d+$/.test(assetId)) return json({ ok: false, error: "bad_asset" }, 400);
  if (!uid || uid.length > 80) return json({ ok: false, error: "bad_uid" }, 400);

  const countKey = `likes:${assetId}`;
  const userKey = `liked:${uid}:${assetId}`;

  // Read current state
  const [countRaw, already] = await Promise.all([kv.get(countKey), kv.get(userKey)]);
  let count = toInt(countRaw);

  if (wantLike) {
    if (!already) {
      // Mark liked for this browser uid (prevents double-like from the same device)
      await kv.put(userKey, "1", { expirationTtl: 60 * 60 * 24 * 365 });
      count = count + 1;
      await kv.put(countKey, String(count));
    }
    return json({ ok: true, assetId, count, liked: true });
  }

  // Unlike
  if (already) {
    await kv.delete(userKey);
    count = Math.max(0, count - 1);
    await kv.put(countKey, String(count));
  }
  return json({ ok: true, assetId, count, liked: false });
}

function toInt(v) {
  const n = parseInt(String(v ?? "0"), 10);
  return Number.isFinite(n) ? n : 0;
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
