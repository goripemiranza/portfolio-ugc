/* app.js — Portfolio Roblox (UGC + Gallery + Commissions) */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const FILES = {
  user: "data_user.json",
  group: "data_group.json",
  gallery: "gallery.json",
  commissions: "commissions.json",
};

const ROBLOX_ITEM_URL = (assetId) => `https://www.roblox.com/catalog/${assetId}`;

const TYPE_LABEL_FR = {
  // Accessories
  Hat: "Chapeau",
  HairAccessory: "Cheveux",
  FaceAccessory: "Visage",
  NeckAccessory: "Cou",
  ShoulderAccessory: "Épaule",
  FrontAccessory: "Avant",
  BackAccessory: "Dos",
  WaistAccessory: "Taille",
  EarAccessory: "Oreille",
  EyeAccessory: "Yeux",
  EyebrowAccessory: "Sourcils",
  EyelashAccessory: "Cils",

  // Heads / Faces
  Head: "Tête",
  Face: "Visage (Classic)",
  DynamicHead: "Tête (Dynamique)",

  // Classic clothing
  TShirt: "T-Shirt",
  Shirt: "Chemise",
  Pants: "Pantalon",

  // Layered clothing
  TShirtAccessory: "T-Shirt (LC)",
  ShirtAccessory: "Chemise (LC)",
  PantsAccessory: "Pantalon (LC)",
  JacketAccessory: "Veste (LC)",
  SweaterAccessory: "Pull (LC)",
  ShortsAccessory: "Short (LC)",
  LeftShoeAccessory: "Chaussure G. (LC)",
  RightShoeAccessory: "Chaussure D. (LC)",
  DressSkirtAccessory: "Robe/Jupe (LC)",

  // Animations
  Animation: "Animation",
  ClimbAnimation: "Anim. Escalade",
  DeathAnimation: "Anim. Mort",
  FallAnimation: "Anim. Chute",
  IdleAnimation: "Anim. Idle",
  JumpAnimation: "Anim. Saut",
  RunAnimation: "Anim. Course",
  SwimAnimation: "Anim. Nage",
  WalkAnimation: "Anim. Marche",
  PoseAnimation: "Anim. Pose",
  EmoteAnimation: "Emote",
  MoodAnimation: "Anim. Mood",
  Package: "Package",
};

function typeToLabel(type) {
  if (!type || typeof type !== "string") return "Autre";
  return TYPE_LABEL_FR[type] || type;
}

function typeToCategory(type) {
  const t = String(type || "");
  if (t.endsWith("Animation") || t === "Animation" || t === "MoodAnimation" || t === "Package") return "Animations";
  if (t.endsWith("Accessory") || t === "Hat") return "Accessoires";
  if (t === "Head" || t === "DynamicHead") return "Têtes";
  if (t === "Face") return "Visages";
  if (t === "TShirt" || t === "Shirt" || t === "Pants") return "Vêtements";
  if (t.endsWith("Accessory") && (t.includes("Shirt") || t.includes("Pants") || t.includes("Jacket") || t.includes("Sweater") || t.includes("Shorts") || t.includes("Shoe") || t.includes("Dress"))) return "Vêtements";
  if (t.endsWith("Accessory") && (t.includes("Shirt") || t.includes("Pants"))) return "Vêtements";
  if (t.endsWith("Accessory") && (t.includes("Shoe") || t.includes("Dress"))) return "Vêtements";
  if (t.endsWith("Accessory") && (t.includes("Jacket") || t.includes("Sweater") || t.includes("Shorts"))) return "Vêtements";
  if (t.endsWith("Accessory") && (t.includes("TShirt") || t.includes("Shirt") || t.includes("Pants"))) return "Vêtements";
  return "Autres";
}

function safeDate(ts) {
  const d = ts ? new Date(ts) : null;
  if (!d || Number.isNaN(d.getTime())) return "—";
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yy = d.getFullYear();
  return `${dd}/${mm}/${yy}`;
}

function num(n) {
  return typeof n === "number" && Number.isFinite(n) ? n : null;
}

function fmtRobux(price) {
  const p = num(price);
  if (p == null) return "—";
  return `${p} R$`;
}

async function fetchJson(path, { optional = false } = {}) {
  const url = `${path}${path.includes("?") ? "&" : "?"}v=${Date.now()}`;
  try {
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) throw new Error(`${path} HTTP ${r.status}`);
    return await r.json();
  } catch (e) {
    if (optional) return null;
    throw e;
  }
}

const STATE = {
  all: [],
  filtered: [],
  gallery: [],
  commissions: {
    models: [],
    textures: [],
  },
  commMode: "models",
};

function setActiveView(name) {
  $$(".tabBtn").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
}

function fillSelect(selectEl, options, selectedValue) {
  selectEl.innerHTML = "";
  for (const opt of options) {
    const o = document.createElement("option");
    o.value = opt.value;
    o.textContent = opt.label;
    selectEl.appendChild(o);
  }
  if (selectedValue != null) selectEl.value = selectedValue;
}

function computePodium(items) {
  const list = items.slice().sort((a, b) => (b.createdTs || 0) - (a.createdTs || 0));
  return list.slice(0, 3);
}

function createUgcCard(item, { featured = false } = {}) {
  const card = document.createElement("article");
  card.className = `ugcCard${featured ? " featured" : ""}`;
  card.dataset.assetId = String(item.assetId);

  const badge = document.createElement("div");
  badge.className = "badge";
  badge.textContent = typeToLabel(item.type);

  const pill = document.createElement("div");
  pill.className = "sourcePill";
  pill.textContent = item.source;

  const thumbBtn = document.createElement("button");
  thumbBtn.type = "button";
  thumbBtn.className = "thumbBtn";
  thumbBtn.dataset.action = "zoom";
  thumbBtn.dataset.src = item.thumb || "";
  thumbBtn.dataset.caption = `${item.name} • ${item.assetId}`;

  const img = document.createElement("img");
  img.className = "thumb";
  img.loading = "lazy";
  img.alt = item.name || "UGC";
  img.src = item.thumb || "";
  thumbBtn.appendChild(img);

  const body = document.createElement("div");
  body.className = "body";

  const title = document.createElement("div");
  title.className = "title";
  const titleBtn = document.createElement("button");
  titleBtn.type = "button";
  titleBtn.className = "linkLike";
  titleBtn.dataset.action = "copy-name";
  titleBtn.dataset.copy = item.name || "";
  titleBtn.textContent = item.name || `Item ${item.assetId}`;
  title.appendChild(titleBtn);

  const meta = document.createElement("div");
  meta.className = "metaRow";

  const idBtn = document.createElement("button");
  idBtn.type = "button";
  idBtn.className = "kvBtn";
  idBtn.dataset.action = "copy-id";
  idBtn.dataset.copy = String(item.assetId);
  idBtn.textContent = `Asset ${item.assetId}`;

  const dateTag = document.createElement("span");
  dateTag.className = "metaTag";
  dateTag.textContent = safeDate(item.created);

  const fav = document.createElement("span");
  fav.className = "metaTag";
  const f = num(item.favorites);
  fav.textContent = `❤ ${f == null ? "—" : f}`;

  const cat = document.createElement("span");
  cat.className = "metaTag";
  cat.textContent = typeToCategory(item.type);

  meta.appendChild(idBtn);
  meta.appendChild(dateTag);
  meta.appendChild(fav);
  meta.appendChild(cat);

  const foot = document.createElement("div");
  foot.className = "foot";

  const price = document.createElement("div");
  price.className = "price";
  price.textContent = fmtRobux(item.price);

  const openBtn = document.createElement("button");
  openBtn.type = "button";
  openBtn.className = "btnOpen";
  openBtn.dataset.action = "open";
  openBtn.textContent = "Ouvrir";

  foot.appendChild(price);
  foot.appendChild(openBtn);

  body.appendChild(title);
  body.appendChild(meta);
  body.appendChild(foot);

  card.appendChild(thumbBtn);
  card.appendChild(badge);
  card.appendChild(pill);
  card.appendChild(body);

  return card;
}

function renderPodium() {
  const row = $("#podiumRow");
  const empty = $("#podiumEmpty");
  row.innerHTML = "";

  const podium = computePodium(STATE.all).filter((x) => num(x.price) != null && x.price > 0);
  if (!podium.length) {
    empty.hidden = false;
    $("#podiumHint").textContent = "0 item";
    return;
  }
  empty.hidden = true;

  // order: left=2nd, mid=1st, right=3rd
  const mid = podium[0] || null;
  const left = podium[1] || null;
  const right = podium[2] || null;

  const cards = [
    left ? createUgcCard(left, { featured: false }) : null,
    mid ? createUgcCard(mid, { featured: true }) : null,
    right ? createUgcCard(right, { featured: false }) : null,
  ].filter(Boolean);

  cards.forEach((c) => row.appendChild(c));
  $("#podiumHint").textContent = `${podium.length} item(s)`;
}

function getFilters() {
  const cat = $("#fCategory").value || "all";
  const type = $("#fType").value || "all";
  const sort = $("#fSort").value || "new";
  const q = ($("#fSearch").value || "").trim().toLowerCase();
  return { cat, type, sort, q };
}

function applyFilters() {
  const { cat, type, sort, q } = getFilters();

  let items = STATE.all.slice();

  // Only on-sale paid items (if some slipped in)
  items = items.filter((x) => num(x.price) != null && x.price > 0);

  if (cat !== "all") items = items.filter((x) => typeToCategory(x.type) === cat);
  if (type !== "all") items = items.filter((x) => String(x.type) === type);

  if (q) {
    items = items.filter((x) => {
      const name = String(x.name || "").toLowerCase();
      const id = String(x.assetId || "");
      return name.includes(q) || id.includes(q);
    });
  }

  if (sort === "new") items.sort((a, b) => (b.createdTs || 0) - (a.createdTs || 0));
  if (sort === "old") items.sort((a, b) => (a.createdTs || 0) - (b.createdTs || 0));
  if (sort === "fav") items.sort((a, b) => (num(b.favorites) || -1) - (num(a.favorites) || -1));
  if (sort === "price_desc") items.sort((a, b) => (num(b.price) || 0) - (num(a.price) || 0));
  if (sort === "price_asc") items.sort((a, b) => (num(a.price) || 0) - (num(b.price) || 0));

  STATE.filtered = items;
}

function renderUgcGrid() {
  const grid = $("#ugcGrid");
  const empty = $("#ugcEmpty");
  grid.innerHTML = "";

  const items = STATE.filtered;
  $("#ugcCount").textContent = `${items.length} item(s)`;

  if (!items.length) {
    empty.hidden = false;
    return;
  }
  empty.hidden = true;

  for (const it of items) {
    grid.appendChild(createUgcCard(it));
  }
}

function renderFiltersUI() {
  const catEl = $("#fCategory");
  const typeEl = $("#fType");

  const cats = ["Accessoires", "Vêtements", "Animations", "Têtes", "Visages", "Autres"];
  const presentCats = new Set(STATE.all.map((x) => typeToCategory(x.type)));
  const catOptions = [{ value: "all", label: "Tous" }].concat(
    cats.filter((c) => presentCats.has(c)).map((c) => ({ value: c, label: c }))
  );

  const types = Array.from(new Set(STATE.all.map((x) => String(x.type || "")))).filter(Boolean);
  types.sort((a, b) => typeToLabel(a).localeCompare(typeToLabel(b), "fr"));
  const typeOptions = [{ value: "all", label: "Tous" }].concat(
    types.map((t) => ({ value: t, label: typeToLabel(t) }))
  );

  const prevCat = catEl.value || "all";
  const prevType = typeEl.value || "all";
  fillSelect(catEl, catOptions, prevCat);
  fillSelect(typeEl, typeOptions, prevType);
}

function renderGallery() {
  const grid = $("#galleryGrid");
  const empty = $("#galleryEmpty");
  grid.innerHTML = "";

  const items = STATE.gallery || [];
  $("#galleryCount").textContent = `${items.length} image(s)`;

  if (!items.length) {
    empty.hidden = false;
    return;
  }
  empty.hidden = true;

  for (const g of items) {
    const card = document.createElement("div");
    card.className = "galCard";

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "galBtn";
    btn.dataset.action = "zoom";
    btn.dataset.src = g.url;
    btn.dataset.caption = ""; // captions removed on purpose

    const img = document.createElement("img");
    img.className = "galImg";
    img.loading = "lazy";
    img.alt = "Galerie";
    img.src = g.url;

    btn.appendChild(img);
    card.appendChild(btn);
    grid.appendChild(card);
  }
}

function normalizeCommissionJson(raw) {
  const models = [];
  const textures = [];

  if (!raw) return { models, textures };

  const list = Array.isArray(raw) ? raw : (Array.isArray(raw.commissions) ? raw.commissions : []);

  for (const c of list) {
    if (!c || typeof c !== "object") continue;
    const imgs = c.images || c.media || c;
    const m = imgs.model3d || imgs.models || imgs.model || [];
    const t = imgs.texturing || imgs.textures || imgs.texture || [];

    const pushAll = (arr, target) => {
      if (!arr) return;
      if (Array.isArray(arr)) arr.forEach((x) => typeof x === "string" && target.push(x));
      else if (typeof arr === "string") target.push(arr);
    };

    pushAll(m, models);
    pushAll(t, textures);
  }

  return { models, textures };
}

function renderCommissions() {
  const grid = $("#commissionGrid");
  const empty = $("#commissionEmpty");
  grid.innerHTML = "";

  const list = STATE.commissions[STATE.commMode] || [];

  if (!list.length) {
    empty.hidden = false;
    return;
  }
  empty.hidden = true;

  for (const url of list) {
    const card = document.createElement("div");
    card.className = "comCard";

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "comBtn";
    btn.dataset.action = "zoom";
    btn.dataset.src = url;
    btn.dataset.caption = "";

    const img = document.createElement("img");
    img.className = "comImg";
    img.loading = "lazy";
    img.alt = "Commission";
    img.src = url;

    btn.appendChild(img);
    card.appendChild(btn);
    grid.appendChild(card);
  }
}

/* Modal (zoom) */
let ZOOM = { scale: 1, x: 0, y: 0, dragging: false, px: 0, py: 0 };

function setModalTransform() {
  const img = $("#modalImg");
  img.style.transform = `translate(${ZOOM.x}px, ${ZOOM.y}px) scale(${ZOOM.scale})`;
}

function modalReset() {
  ZOOM.scale = 1;
  ZOOM.x = 0;
  ZOOM.y = 0;
  setModalTransform();
  $("#zoomReset").textContent = "1×";
}

function modalZoom(delta) {
  const next = Math.min(4, Math.max(1, ZOOM.scale + delta));
  ZOOM.scale = next;
  if (ZOOM.scale === 1) {
    ZOOM.x = 0;
    ZOOM.y = 0;
  }
  setModalTransform();
  $("#zoomReset").textContent = `${ZOOM.scale.toFixed(1)}×`.replace(".0", "");
}

function openModal(src, caption = "") {
  const modal = $("#modal");
  const img = $("#modalImg");
  const cap = $("#modalCaption");

  img.src = src;
  cap.textContent = caption || "";
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
  modalReset();
}

function closeModal() {
  const modal = $("#modal");
  const img = $("#modalImg");
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
  img.src = "";
}

/* Toast */
let toastTimer = null;
function showToast(text) {
  const t = $("#toast");
  t.textContent = text;
  t.classList.add("show");
  t.setAttribute("aria-hidden", "false");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    t.classList.remove("show");
    t.setAttribute("aria-hidden", "true");
  }, 1200);
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(String(text));
    showToast("Copié ✅");
  } catch {
    // Fallback
    const ta = document.createElement("textarea");
    ta.value = String(text);
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); showToast("Copié ✅"); } catch { showToast("Copie impossible"); }
    document.body.removeChild(ta);
  }
}

/* Delegated actions */
function onClickAction(e) {
  const target = e.target.closest("[data-action]");
  if (!target) return;

  const action = target.dataset.action;

  if (action === "zoom") {
    const src = target.dataset.src;
    const cap = target.dataset.caption || "";
    if (src) openModal(src, cap);
    return;
  }

  if (action === "open") {
    const card = target.closest("[data-asset-id]");
    const assetId = card?.dataset.assetId;
    if (assetId) window.open(ROBLOX_ITEM_URL(assetId), "_blank", "noopener,noreferrer");
    return;
  }

  if (action === "copy-id" || action === "copy-name") {
    const text = target.dataset.copy || "";
    if (text) copyText(text);
    return;
  }
}

function wireUI() {
  // Tabs
  $$(".tabBtn").forEach((b) => {
    b.addEventListener("click", () => setActiveView(b.dataset.view));
  });

  // Refresh
  $("#btnRefresh").addEventListener("click", () => boot());

  // Filters
  ["fCategory", "fType", "fSort", "fSearch"].forEach((id) => {
    const el = $(`#${id}`);
    el.addEventListener(id === "fSearch" ? "input" : "change", () => {
      applyFilters();
      renderPodium();
      renderUgcGrid();
    });
  });

  // Commissions segment
  $$(".segBtn").forEach((b) => {
    b.addEventListener("click", () => {
      $$(".segBtn").forEach((x) => {
        x.classList.toggle("active", x === b);
        x.setAttribute("aria-selected", x === b ? "true" : "false");
      });
      STATE.commMode = b.dataset.comm;
      renderCommissions();
    });
  });

  // Click actions (UGC + gallery + commissions)
  $("#ugcGrid").addEventListener("click", onClickAction);
  $("#podiumRow").addEventListener("click", onClickAction);
  $("#galleryGrid").addEventListener("click", onClickAction);
  $("#commissionGrid").addEventListener("click", onClickAction);

  // Modal close
  $("#modalClose").addEventListener("click", closeModal);
  $("#modal").addEventListener("click", (e) => {
    if (e.target.id === "modal") closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });

  // Modal tools
  $("#zoomIn").addEventListener("click", () => modalZoom(+0.25));
  $("#zoomOut").addEventListener("click", () => modalZoom(-0.25));
  $("#zoomReset").addEventListener("click", modalReset);

  // Modal wheel zoom + drag
  const stage = $("#modalStage");
  stage.addEventListener("wheel", (e) => {
    if (!$("#modal").classList.contains("open")) return;
    e.preventDefault();
    modalZoom(e.deltaY < 0 ? +0.2 : -0.2);
  }, { passive: false });

  stage.addEventListener("pointerdown", (e) => {
    if (!$("#modal").classList.contains("open")) return;
    if (ZOOM.scale <= 1) return;
    ZOOM.dragging = true;
    ZOOM.px = e.clientX;
    ZOOM.py = e.clientY;
    stage.setPointerCapture(e.pointerId);
  });

  stage.addEventListener("pointermove", (e) => {
    if (!ZOOM.dragging) return;
    const dx = e.clientX - ZOOM.px;
    const dy = e.clientY - ZOOM.py;
    ZOOM.px = e.clientX;
    ZOOM.py = e.clientY;
    ZOOM.x += dx;
    ZOOM.y += dy;
    setModalTransform();
  });

  stage.addEventListener("pointerup", () => { ZOOM.dragging = false; });
  stage.addEventListener("pointercancel", () => { ZOOM.dragging = false; });
}

function normalizeItems(raw, sourceLabel) {
  const items = Array.isArray(raw?.items) ? raw.items : [];
  const updated = raw?.updated || null;
  const out = [];

  for (const it of items) {
    if (!it || typeof it !== "object") continue;
    const assetId = it.assetId ?? it.id;
    const price = it.price ?? it.priceInRobux;
    const created = it.created ?? it.createdUtc ?? null;
    const fav = it.favorites ?? it.favoriteCount ?? it.favoritesCount ?? null;

    if (!assetId) continue;

    out.push({
      assetId,
      name: it.name || `Item ${assetId}`,
      type: it.type || it.assetType || "Autre",
      price,
      created,
      createdTs: created ? Date.parse(created) : 0,
      thumb: it.thumb || it.thumbnail || "",
      favorites: fav,
      source: sourceLabel,
      updated,
    });
  }

  return { items: out, updated };
}

async function boot() {
  // keep UI responsive during reload
  $("#ugcGrid").innerHTML = "";
  $("#podiumRow").innerHTML = "";
  $("#ugcEmpty").hidden = true;
  $("#podiumEmpty").hidden = true;
  $("#ugcCount").textContent = "…";
  $("#podiumHint").textContent = "…";
  $("#updateInfo").textContent = "";

  let userRaw = null;
  let groupRaw = null;

  try {
    [userRaw, groupRaw] = await Promise.all([
      fetchJson(FILES.user, { optional: true }),
      fetchJson(FILES.group, { optional: true }),
    ]);
  } catch {
    // ignore, handled below
  }

  const u = normalizeItems(userRaw, "Profil");
  const g = normalizeItems(groupRaw, "Groupe");

  // Merge
  STATE.all = [...u.items, ...g.items].filter((x) => x.thumb);

  // If nothing, show empty and bail early (but keep page usable)
  if (!STATE.all.length) {
    $("#ugcCount").textContent = "0 item(s)";
    $("#podiumHint").textContent = "0 item";
    $("#ugcEmpty").hidden = false;
    $("#podiumEmpty").hidden = false;
  }

  // Update info
  const parts = [];
  if (u.updated) parts.push(`MAJ Profil: ${u.updated}`);
  if (g.updated) parts.push(`MAJ Groupe: ${g.updated}`);
  $("#updateInfo").textContent = parts.join(" • ");

  // Filters + grid
  renderFiltersUI();
  applyFilters();
  renderPodium();
  renderUgcGrid();

  // Gallery
  const gal = await fetchJson(FILES.gallery, { optional: true });
  STATE.gallery = Array.isArray(gal) ? gal : (Array.isArray(gal?.images) ? gal.images : []);
  renderGallery();

  // Commissions (optional)
  const comRaw = await fetchJson(FILES.commissions, { optional: true });
  const com = normalizeCommissionJson(comRaw);
  STATE.commissions = com;
  renderCommissions();
}

document.addEventListener("DOMContentLoaded", () => {
  wireUI();
  boot();
});
