// /functions/api/likes.js
// Read global like counts (and liked state for a given uid) from Cloudflare KV (binding: NOTIFY_KV)

export async function onRequestGet({ request, env }) {
  const kv = env?.NOTIFY_KV;
  if (!kv) return json({ ok: false, error: "kv_not_configured" }, 500);

  const url = new URL(request.url);
  const idsRaw = String(url.searchParams.get("ids") || "");
  const uid = String(url.searchParams.get("uid") || "").trim();

  const ids = idsRaw
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s && /^\d+$/.test(s))
    .slice(0, 250);

  const counts = {};
  const liked = uid ? {} : undefined;

  await Promise.all(
    ids.map(async (id) => {
      const v = await kv.get(`likes:${id}`);
      counts[id] = toInt(v);

      if (uid) {
        const u = await kv.get(`liked:${uid}:${id}`);
        liked[id] = !!u;
      }
    })
  );

  return json({ ok: true, counts, liked });
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
