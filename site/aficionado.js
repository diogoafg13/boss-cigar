/* Boss Cigar — funcionalidades de aficionado.
   Usa as globais do script principal: $, DB, esc, lsGet, lsSet, cig, name, unique, meter, STRENGTH,
   goTab, eur, FR, JKEY, HKEY, download, cardHTML, bindCards, parseVitola, spark. */
"use strict";

/* ---------- utilitários ---------- */
const MONTHS_ES = { ENE: 1, FEB: 2, MAR: 3, ABR: 4, MAY: 5, JUN: 6, JUL: 7, AGO: 8, SEP: 9, OCT: 10, NOV: 11, DIC: 12 };
const MONTH_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const GKEY = "bc-hygro", FKEY = "bc-friends";
let FR_ROWS = null, FR_BY_LABEL = null, PRICES = null, HOME = null;

const today = () => new Date().toISOString().slice(0, 10);
const monthsBetween = (a, b = new Date()) => Math.max(0, Math.floor((b - new Date(a)) / 2629800000));
const pct = v => (v > 0 ? "+" : "") + v.toLocaleString("pt-PT", { maximumFractionDigits: 1 }) + "%";

/** Nome a mostrar para um id do diário/humidor: id do seed ou "fr:<referência>". */
function displayName(id) {
  if (!id) return "?";
  if (id.startsWith("fr:")) return id.slice(3);
  return name(cig(id));
}

/** Catálogo oficial carregado uma vez (partilhado com o separador "Preços oficiais"). */
function loadFr() {
  if (FR_ROWS) return Promise.resolve(FR_ROWS);
  return fetch("data/fr_catalog.json").then(r => r.json()).then(d => {
    FR_ROWS = d.rows.map(r => Object.fromEntries(d.fields.map((k, i) => [k, r[i]])));
    FR_BY_LABEL = new Map(FR_ROWS.map(x => [x.label, x]));
    $("#frList").innerHTML = unique(FR_ROWS.filter(x => !x.cigarillo).map(x => x.label)).map(l => `<option value="${esc(l)}">`).join("");
    return FR_ROWS;
  }).catch(() => (FR_ROWS = []));
}

/** Mini-gráfico de uma série [[data, valor], ...]. */
function histSpark(h, W = 90, H = 24) {
  if (!h || h.length < 2) return "";
  const vs = h.map(p => p[1]), mn = Math.min(...vs), mx = Math.max(...vs);
  const t0 = new Date(h[0][0]).getTime(), t1 = new Date(h[h.length - 1][0]).getTime() || t0 + 1;
  const pts = h.map(([d, v]) => `${((new Date(d).getTime() - t0) / ((t1 - t0) || 1) * (W - 4) + 2).toFixed(1)},${(H - 3 - (v - mn) / ((mx - mn) || 1) * (H - 6)).toFixed(1)}`);
  // degraus: o preço mantém-se até à edição seguinte
  const step = pts.map((p, i) => i === 0 ? p : `${p.split(",")[0]},${pts[i - 1].split(",")[1]} ${p}`).join(" ");
  const title = h.map(([d, v]) => `${d}: ${eur(v)}`).join(" · ");
  return `<svg width="${W}" height="${H}" role="img" aria-label="${esc(title)}"><title>${esc(title)}</title><polyline points="${step}" fill="none" stroke="#e0703a" stroke-width="1.6"/></svg>`;
}
const histPct = h => h && h.length > 1 ? Math.round((h[h.length - 1][1] - h[0][1]) / h[0][1] * 1000) / 10 : null;

/* ---------- arranque ---------- */
window.afInit = function () {
  loadFr();
  fetch("data/prices.json").then(r => r.json()).then(p => { PRICES = p; renderPriceHist(); }).catch(() => {});
  fetch("data/home.json").then(r => r.json()).then(h => { HOME = h; renderHomeAdvice(); }).catch(() => { $("#homeAdvice").textContent = "Sem dados de clima."; });
  setupGuides();
  setupBoveda();
  setupGlossary();
  setupFriends();
  setupSync();
  setupLang();
  document.querySelectorAll("#tabs button").forEach(b => b.addEventListener("click", () => {
    if (b.dataset.tab === "me") loadFr().then(renderMe);
    if (b.dataset.tab === "humidor") loadFr().then(() => { renderHumidor(); renderHygro(); });
  }));
  openSharedNote();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
};

/* ---------- ficha: preço oficial e evolução ---------- */
window.afDetail = function (c) {
  let out = "";
  if (c.pairings && c.pairings.ptWines) out += `<p><b>Vinho português:</b> ${esc(c.pairings.ptWines.join(", "))}<br><span class="warn">${esc((c.pairings.ptWhy || []).join(" "))}</span></p>`;
  out += `<p><a href="#" onclick="event.preventDefault();document.getElementById('detail').close();openBrand(${JSON.stringify(c.brand).replace(/"/g, "&quot;")})">Ver a página da marca ${esc(c.brand)} →</a></p>`;
  const h = c.priceFR && c.priceFR.hist;
  if (h) out += `<p class="sub">Evolução do preço oficial em França: ${histSpark(h, 140, 30)} ${pct(histPct(h))} desde ${esc(h[0][0])}</p>`;
  if (c.priceES) {
    const e = c.priceES;
    out += `<p><b>Preço oficial em Espanha:</b> ${e.min === e.max ? eur(e.min) : eur(e.min) + " – " + eur(e.max)} por unidade${c.priceFR && c.priceFR.min ? ` <span class="sub">(${pct(Math.round((e.min - c.priceFR.min) / c.priceFR.min * 1000) / 10)} face a França)</span>` : ""}<br>
      <span class="sub">${e.refs.slice(0, 4).map(r => esc(r.label) + (r.pack_size ? " (" + r.pack_size + ")" : "") + ": " + eur(r.unit_eur)).join(" · ")}</span><br><span class="warn">Origem dos dados: Ministerio de Hacienda (CMT) · ${esc(e.fetched || "")}</span></p>`;
  }
  return out;
};

/* ---------- Preços oficiais: França / Espanha ---------- */
const CATS = { fr: null, es: null }, CAT_META = { fr: {}, es: {} };
let CAT_COUNTRY = "fr", CAT_BOUND = false, COMPARE = null;

function loadCat(country) {
  if (CATS[country]) return Promise.resolve(CATS[country]);
  return fetch(`data/${country}_catalog.json`).then(r => r.json()).then(d => {
    CATS[country] = d.rows.map(r => Object.fromEntries(d.fields.map((k, i) => [k, r[i]])));
    CAT_META[country] = d;
    if (country === "fr" && !FR_ROWS) { FR_ROWS = CATS.fr; FR_BY_LABEL = new Map(FR_ROWS.map(x => [x.label, x])); }
    return CATS[country];
  });
}

function fillCatFilters() {
  const keepB = $("#fBrand").value, keepV = $("#fVit").value;
  $("#fBrand").innerHTML = '<option value="">Todas as marcas</option>' + unique(FR.filter(x => x.brand && !x.cigarillo).map(x => x.brand)).map(b => `<option>${esc(b)}</option>`).join("");
  $("#fVit").innerHTML = '<option value="">Qualquer vitola</option>' + unique(FR.filter(x => x.vitola).map(x => x.vitola)).map(v => `<option>${esc(v)}</option>`).join("");
  if ([...$("#fBrand").options].some(o => o.value === keepB)) $("#fBrand").value = keepB;
  if ([...$("#fVit").options].some(o => o.value === keepV)) $("#fVit").value = keepV;
  const m = CAT_META[CAT_COUNTRY];
  $("#frEdition").textContent = CAT_COUNTRY === "fr" ? `França: ${m.edition || ""}` : `Espanha: lista vigente recolhida a ${m.fetched || "?"} (${m.zone || ""})`;
}

function initFr() {
  const go = () => loadCat(CAT_COUNTRY).then(rows => {
    FR = rows; fillCatFilters();
    if (!CAT_BOUND) {
      CAT_BOUND = true;
      ["#fq", "#fBrand", "#fVit", "#fMax", "#fKind", "#fSortP"].forEach(i => $(i).addEventListener("input", () => { FR_LIMIT = 100; renderFr(); }));
      $("#fCountryP").addEventListener("change", () => { CAT_COUNTRY = $("#fCountryP").value; FR_LIMIT = 100; go(); });
      $("#fMore").onclick = () => { FR_LIMIT += 200; renderFr(); };
    }
    applyPending(); renderFr();
  }).catch(() => { $("#fCount").textContent = "Catálogo indisponível."; });
  go();
  if (!COMPARE) fetch("data/compare.json").then(r => r.json()).then(c => { COMPARE = c; renderCompareFrEs(); }).catch(() => {});
}

function renderCompareFrEs() {
  const c = COMPARE; if (!c || !c.n) { $("#cmpFrEs").style.display = "none"; return; }
  $("#cmpFrEs").innerHTML = `<h3 style="margin-top:0">França ou Espanha: onde é mais barato?</h3>
    <p class="muted">${c.n} referências existem nas duas listas oficiais. Em ${c.es_cheaper} são mais baratas em Espanha; diferença mediana ${pct(c.median_diff_pct)} (preço espanhol face ao francês, por unidade, na tabacaria).</p>
    <div class="filters"><input id="cq" type="search" placeholder="Filtrar a comparação…"><select id="cSort"><option value="d">Maior poupança em Espanha</option><option value="u">Mais caro em Espanha</option><option value="n">Nome</option></select></div>
    <div style="overflow-x:auto"><table id="cTable"></table></div>
    <p class="warn">Compara a mesma referência pelo nome normalizado (tubos e estojos à parte). Em Espanha há também o preço "con recargo" (bares, hotéis), mais alto.</p>`;
  const draw = () => {
    const q = $("#cq").value.trim().toLowerCase(), so = $("#cSort").value;
    let l = c.rows.filter(r => !q || (r.label + " " + (r.brand || "")).toLowerCase().includes(q));
    l.sort(so === "d" ? (a, b) => a.diff_pct - b.diff_pct : so === "u" ? (a, b) => b.diff_pct - a.diff_pct : (a, b) => a.label.localeCompare(b.label, "pt"));
    $("#cTable").innerHTML = "<tr><th>Referência</th><th>Marca</th><th>🇫🇷</th><th>🇪🇸</th><th>Diferença</th></tr>" + l.slice(0, 60).map(r =>
      `<tr><td>${esc(r.label)}</td><td>${esc(r.brand || "—")}</td><td>${eur(r.fr)}</td><td>${eur(r.es)}</td><td>${pct(r.diff_pct)}</td></tr>`).join("");
  };
  $("#cq").addEventListener("input", draw); $("#cSort").addEventListener("input", draw); draw();
}

/* ---------- Preços oficiais: filtros extra, evolução, histórico ---------- */
function renderFr() {
  const q = $("#fq").value.trim().toLowerCase(), br = $("#fBrand").value, vi = $("#fVit").value, mx = +$("#fMax").value || 0,
        kind = $("#fKind").value, so = $("#fSortP").value;
  let l = FR.filter(x => {
    if (kind === "cig" && x.cigarillo) return false;
    if (kind === "cgl" && !x.cigarillo) return false;
    if (kind === "esp" && !x.special) return false;
    if (kind === "chg" && !x.hist) return false;
    return (!br || x.brand === br) && (!vi || x.vitola === vi) && (!mx || (x.unit_eur != null && x.unit_eur <= mx))
      && (!q || (x.label + " " + (x.brand || "")).toLowerCase().includes(q));
  });
  l.sort(so === "pa" ? (a, b) => (a.unit_eur ?? 1e9) - (b.unit_eur ?? 1e9) : so === "pd" ? (a, b) => (b.unit_eur ?? -1) - (a.unit_eur ?? -1)
    : (a, b) => a.label.localeCompare(b.label, "pt"));
  $("#fCount").textContent = `${l.length} referência(s)` + (l.length > FR_LIMIT ? ` · a mostrar ${FR_LIMIT}` : "");
  $("#fTable").innerHTML = "<tr><th>Referência</th><th>Marca</th><th>Vitola</th><th>Medidas</th><th>Emb.</th><th>€/unidade</th><th>Evolução</th></tr>" + l.slice(0, FR_LIMIT).map(x => {
    const p = histPct(x.hist);
    const wk = wishKey(CAT_COUNTRY, x), on = wishHas(wk);
    return `<tr><td><button class="fav ${on ? "on" : ""}" style="position:static;font-size:1.05rem;padding:0 4px" data-wk="${esc(wk)}" title="Lista de desejos" aria-label="Lista de desejos">${on ? "♥" : "♡"}</button>${esc(x.label)}${x.new ? ' <span class="badge ok">novo</span>' : ""}${x.special ? ` <span class="badge warn">${esc(x.special)}</span>` : ""}${x.sampler ? ' <span class="badge warn">sortido</span>' : ""}</td>
      <td>${esc(x.brand || "—")}${x.brand_source === "inferida" ? "*" : ""}</td><td>${esc(x.vitola || "—")}</td>
      <td class="sub">${x.ring ? x.length_in + '" × ' + x.ring + "<br>" + smokeTime(x.length_in, x.ring).label : "—"}</td><td>${x.pack_size || "—"}</td>
      <td>${eur(x.unit_eur)}</td><td class="sub">${x.hist ? histSpark(x.hist) + " " + pct(p) : (x.first_seen && PRICES && x.first_seen !== PRICES.editions[0].date ? "novo desde " + esc(x.first_seen) : "—")}</td></tr>`;
  }).join("");
  $("#fMore").style.display = l.length > FR_LIMIT ? "" : "none";
  $("#fTable").querySelectorAll("[data-wk]").forEach(b => b.onclick = () => {
    const k = b.dataset.wk, x = FR.find(r => wishKey(CAT_COUNTRY, r) === k);
    toggleWish(k, x, CAT_COUNTRY); const on = wishHas(k); b.classList.toggle("on", on); b.textContent = on ? "♥" : "♡";
  });
}

/* ---------- Lista de desejos ---------- */
const WKEY = "bc-wish";
const wishKey = (country, x) => `${country}|${x.label}|${x.pack_size || ""}`;
const wishHas = k => lsGet(WKEY, []).some(w => w.key === k);
function toggleWish(k, x, country) {
  let l = lsGet(WKEY, []);
  if (l.some(w => w.key === k)) l = l.filter(w => w.key !== k);
  else l.unshift({ key: k, country, label: x.label, pack_size: x.pack_size || null, brand: x.brand || null, price: x.unit_eur, added: today() });
  lsSet(WKEY, l);
}
// renderWish: ver compra.js (lista de desejos + plano de compra)

/* ---------- Sincronização via Gist privado ---------- */
const SYNC_KEYS = ["bc-journal", "bc-humidor", "bc-hygro", "bc-favs", "bc-wish", "bc-friends", "bc-fake"];
const GIST_FILE = "boss-cigar.json";
function gh(path, opts = {}) {
  const tok = lsGet("bc-sync-token", "");
  if (!tok) return Promise.reject(new Error("Falta o token."));
  return fetch("https://api.github.com" + path, { ...opts, headers: { "Accept": "application/vnd.github+json", "Authorization": "Bearer " + tok, ...(opts.body ? { "Content-Type": "application/json" } : {}) } })
    .then(r => r.ok ? r.json() : r.json().catch(() => ({})).then(j => { throw new Error(`GitHub ${r.status}: ${j.message || r.statusText}`); }));
}
function mergeList(local, remote, key) {
  const out = [...local];
  for (const r of remote || []) {
    const k = key ? key(r) : JSON.stringify(r);
    if (!out.some(l => (key ? key(l) : JSON.stringify(l)) === k)) out.push(r);
  }
  return out;
}
const MERGE_KEY = {
  "bc-journal": e => `${e.date}|${e.cigar}|${e.notes}`, "bc-humidor": e => String(e.id), "bc-hygro": e => `${e.date}|${e.rh}|${e.t}`,
  "bc-wish": e => e.key, "bc-friends": e => `${e.from}|${e.date}|${e.cigar}|${e.notes}`,
};
function setupSync() {
  $("#syncToken").value = lsGet("bc-sync-token", "") ? "••••••••" : "";
  $("#syncGist").value = lsGet("bc-sync-gist", "");
  const say = (t, err) => { $("#syncOut").innerHTML = (err ? "⚠ " : "") + esc(t); };
  const saveInputs = () => {
    const t = $("#syncToken").value.trim(); if (t && !/^•+$/.test(t)) lsSet("bc-sync-token", t);
    lsSet("bc-sync-gist", $("#syncGist").value.trim());
  };
  $("#syncPush").onclick = () => {
    saveInputs();
    const payload = { app: "boss-cigar", version: 1, saved: new Date().toISOString(), data: Object.fromEntries(SYNC_KEYS.map(k => [k, lsGet(k, [])])) };
    const body = JSON.stringify({ description: "Boss Cigar — dados pessoais (privado)", public: false, files: { [GIST_FILE]: { content: JSON.stringify(payload, null, 1) } } });
    const id = lsGet("bc-sync-gist", "");
    say("A enviar…");
    (id ? gh(`/gists/${id}`, { method: "PATCH", body }) : gh("/gists", { method: "POST", body }))
      .then(g => { lsSet("bc-sync-gist", g.id); $("#syncGist").value = g.id; lsSet("bc-sync-last", payload.saved); say(`Enviado para o Gist privado ${g.id} (${new Date().toLocaleString("pt-PT")}). Noutro dispositivo, cola o mesmo token e este ID e carrega em "Trazer do Gist".`); })
      .catch(e => say(e.message, true));
  };
  $("#syncPull").onclick = () => {
    saveInputs();
    const id = lsGet("bc-sync-gist", ""); if (!id) { say("Indica o ID do Gist.", true); return; }
    say("A trazer…");
    gh(`/gists/${id}`).then(g => {
      const f = g.files && g.files[GIST_FILE]; if (!f) throw new Error("Este Gist não tem dados do Boss Cigar.");
      return f.truncated ? fetch(f.raw_url).then(r => r.json()) : JSON.parse(f.content);
    }).then(p => {
      let n = 0;
      for (const k of SYNC_KEYS) {
        const local = lsGet(k, []), remote = (p.data || {})[k];
        if (!Array.isArray(remote)) continue;
        const merged = mergeList(local, remote, MERGE_KEY[k]);
        n += merged.length - local.length; lsSet(k, merged);
      }
      say(`Junção feita: ${n} registo(s) novo(s) trazidos do Gist. Nada local foi apagado.`);
      renderJournal(); renderHumidor(); renderHygro(); renderFriends(); renderWish();
    }).catch(e => say(e.message, true));
  };
  $("#syncForget").onclick = () => { lsSet("bc-sync-token", ""); $("#syncToken").value = ""; say("Token esquecido neste browser."); };
}

function renderPriceHist() {
  const p = PRICES; if (!p || !p.editions.length) return;
  const first = p.editions[0].date, last = p.editions[p.editions.length - 1].date;
  const row = c => `<tr><td>${esc(c.label)}</td><td>${esc(c.brand || "—")}</td><td>${eur(c.from)} → ${eur(c.to)}</td><td>${pct(c.pct)}</td><td class="sub">${esc(c.since)}</td></tr>`;
  const big = ["Cohiba", "Montecristo", "Partagás", "Romeo y Julieta", "H. Upmann", "Hoyo de Monterrey", "Trinidad", "Bolívar", "Davidoff", "Arturo Fuente", "Padrón", "Oliva", "My Father", "Plasencia"];
  const bb = p.brands.filter(b => big.includes(b.brand));
  $("#priceHist").innerHTML = `<h3 style="margin-top:0">Evolução de preços</h3>
    <p class="muted">${p.editions.length} edições oficiais entre ${esc(first)} e ${esc(last)}. ${p.n_changed} referências mudaram de preço; variação mediana ${pct(p.median_pct)}.
    ${p.n_anomalies ? `${p.n_anomalies} variações acima de 75% foram excluídas por serem quase sempre erros de origem.` : ""}</p>
    <details open><summary style="cursor:pointer">Marcas clássicas</summary>${bb.length ? `<table><tr><th>Marca</th><th>Referências com mudança</th><th>Variação mediana</th></tr>${bb.map(b => `<tr><td>${esc(b.brand)}</td><td>${b.n}</td><td>${pct(b.median_pct)}</td></tr>`).join("")}</table>` : "<p class='muted'>Sem dados.</p>"}</details>
    <details><summary style="cursor:pointer">Marcas que mais subiram (≥ 5 referências)</summary><table><tr><th>Marca</th><th>Ref.</th><th>Mediana</th></tr>${p.brands.slice(0, 15).map(b => `<tr><td>${esc(b.brand)}</td><td>${b.n}</td><td>${pct(b.median_pct)}</td></tr>`).join("")}</table></details>
    <details><summary style="cursor:pointer">Maiores subidas</summary><table><tr><th>Referência</th><th>Marca</th><th>Preço</th><th>Var.</th><th>Desde</th></tr>${p.up.slice(0, 25).map(row).join("")}</table></details>
    <details><summary style="cursor:pointer">Descidas</summary><table><tr><th>Referência</th><th>Marca</th><th>Preço</th><th>Var.</th><th>Desde</th></tr>${p.down.slice(0, 15).map(row).join("")}</table></details>
    <details><summary style="cursor:pointer">Saíram do mercado no último ano (${p.removed.length})</summary><table><tr><th>Referência</th><th>Emb.</th><th>Último preço</th><th>Visto até</th></tr>${p.removed.map(r => `<tr><td>${esc(r.label)}</td><td>${r.pack_size || "—"}</td><td>${eur(r.last_eur)}</td><td class="sub">${esc(r.last_seen)}</td></tr>`).join("")}</table></details>`;
}

/* ---------- tempo de fumada ---------- */
function smokeTime(len, ring) {
  const m = 10.5 * len * (ring / 46);
  const lo = Math.round(m * 0.8 / 5) * 5, hi = Math.round(m * 1.2 / 5) * 5;
  return { minutes: Math.round(m), label: `≈ ${lo}–${hi} min` };
}

/* ---------- Guias: anti-falsificação, código da caixa, tempo, viagens ---------- */
const FAKE_CHECKS = [
  ["Comprado numa Casa del Habano, Habanos Specialist ou tabacaria autorizada", 3],
  ["Selo de garantia do governo cubano com holograma e código de barras individual", 3],
  ["Código de barras do selo verificado no sistema da Habanos S.A.", 3],
  ["Carimbo 'Hecho en Cuba' gravado a quente no fundo da caixa", 2],
  ["Marca 'Habanos' de Denominação de Origem na caixa", 2],
  ["'Totalmente a mano' (charutos feitos à mão)", 1],
  ["Código de fábrica + data no formato MÊS AA (ex.: ABR 24) por baixo da caixa", 2],
  ["Selo do importador oficial do país", 2],
  ["Preço coerente com o preço oficial (não muito abaixo)", 3],
  ["Anilhas bem impressas, centradas e iguais entre si; charutos uniformes na cor e no tamanho", 1],
];
function setupGuides() {
  const saved = lsGet("bc-fake", []);
  $("#fakeList").innerHTML = FAKE_CHECKS.map(([t], i) => `<label style="display:flex;gap:8px;align-items:flex-start;padding:4px 0"><input type="checkbox" data-fk="${i}" ${saved.includes(i) ? "checked" : ""} style="width:auto;margin-top:4px"> <span>${esc(t)}</span></label>`).join("")
    + `<button class="btn ghost sm" id="fakeReset" style="margin-top:6px">Limpar</button>`;
  const score = () => {
    const on = [...document.querySelectorAll("[data-fk]")].filter(x => x.checked).map(x => +x.dataset.fk);
    lsSet("bc-fake", on);
    const tot = FAKE_CHECKS.reduce((s, [, w]) => s + w, 0), got = on.reduce((s, i) => s + FAKE_CHECKS[i][1], 0), r = got / tot;
    const critical = [0, 1, 2, 8].filter(i => !on.includes(i)).map(i => FAKE_CHECKS[i][0]);
    const verdict = r >= .85 ? "muito provavelmente autêntico." : !critical.length ? "boa base: os pontos críticos estão confirmados; vê o resto da caixa." : r >= .6 ? "plausível, mas confirma o que falta." : "sinais insuficientes: desconfia.";
    $("#fakeScore").innerHTML = `<b>${Math.round(r * 100)}%</b> de confiança — ${verdict}`
      + (critical.length ? `<div class="warn">Pontos críticos por confirmar: ${critical.map(esc).join("; ")}.</div>` : "");
  };
  document.querySelectorAll("[data-fk]").forEach(x => x.addEventListener("change", score));
  $("#fakeReset").onclick = () => { document.querySelectorAll("[data-fk]").forEach(x => x.checked = false); score(); };
  score();

  $("#boxCode").addEventListener("input", () => { const d = decodeBox($("#boxCode").value); $("#boxOut").innerHTML = d ? d.html : ""; });

  const st = () => {
    const len = +$("#stLen").value, ring = +$("#stRing").value;
    if (!len || !ring) { $("#stOut").textContent = ""; return; }
    const t = smokeTime(len, ring);
    $("#stOut").innerHTML = `<p><b>${t.label}</b> para ${len}" × ${ring}</p>`;
  };
  ["#stLen", "#stRing"].forEach(i => $(i).addEventListener("input", st)); st();
}

/* ---------- Idioma ---------- */
function setupLang() {
  const en = lsGet("bc-lang", "pt") === "en";
  $("#langBtn").textContent = en ? "PT" : "EN";
  $("#langBtn").title = en ? "Ver em português" : "View in English";
  $("#langBtn").onclick = () => { lsSet("bc-lang", en ? "pt" : "en"); location.reload(); };
  if (en && window.bcApplyEnglish) bcApplyEnglish();
}

/* ---------- Calculadora Boveda ---------- */
function setupBoveda() {
  const calc = () => {
    const cap = Math.max(1, +$("#bvCap").value || 0), rh = $("#bvRh").value, season = $("#bvSeason").value === "1";
    if (cap <= 5) { $("#bvOut").innerHTML = `<p><b>1 pacote de 8 g</b> (${rh}%) chega para até 5 charutos (estojo de viagem).</p>`; return; }
    const n60 = Math.ceil(cap / 25);
    const n320 = Math.floor(n60 / 5), rest = n60 - n320 * 5;
    const alt = n320 ? `ou <b>${n320} × 320 g</b>${rest ? ` + <b>${rest} × 60 g</b>` : ""}` : "";
    $("#bvOut").innerHTML = `<p>Para ${cap} charutos de capacidade: <b>${n60} × 60 g</b> de ${rh}% ${alt}.</p>`
      + (season ? `<p class="sub">Humidor novo: primeiro cura a madeira com ${n60} pacote(s) de cura de 84% (1 por cada 25 charutos), cerca de 14 dias, sem charutos lá dentro. Depois troca pelos de ${rh}%.</p>` : "")
      + `<p class="sub">Em Lisboa a humidade exterior é alta quase todo o ano; muitos aficionados preferem 65% (ou 62% se a tiragem ficar presa).</p>`;
  };
  ["#bvCap", "#bvRh", "#bvSeason"].forEach(i => $(i).addEventListener("input", calc)); calc();
}

/* ---------- Glossário ---------- */
const GLOSSARY = [
  ["Capa (wrapper)", "Folha exterior do charuto; dá o aspeto e boa parte do sabor inicial."],
  ["Capote (binder)", "Folha que segura a tripa e lhe dá forma, por baixo da capa."],
  ["Tripa (filler)", "Folhas interiores, que definem o essencial do sabor e da força."],
  ["Tripa longa / curta / mista", "Longa: folhas inteiras de ponta a ponta (charutos premium). Curta: pedaços picados (charutos de máquina). Mista: combinação das duas."],
  ["Ligada (blend)", "Receita de folhas (variedades, colheitas, posições na planta) que compõe o charuto."],
  ["Ligero, seco, volado", "Folhas de cima, do meio e de baixo da planta: mais força e combustão lenta (ligero), aroma (seco), combustão (volado)."],
  ["Puro", "Charuto em que capa, capote e tripa vêm todos do mesmo país."],
  ["Vitola", "Formato e medidas de um charuto (comprimento × ring gauge)."],
  ["Vitola de galera", "Nome de fábrica do formato em Cuba (ex.: Robustos, Cañonazo), independente do nome comercial."],
  ["Ring gauge (cepo)", "Diâmetro em 64 avos de polegada: 50 = 50/64″ ≈ 19,8 mm."],
  ["Parejo", "Charuto de lados retos (Corona, Robusto, Churchill…)."],
  ["Figurado", "Charuto de forma irregular: Torpedo, Belicoso, Pirámide, Perfecto, Culebra."],
  ["Box-pressed", "Charuto prensado em caixa, de secção quadrada."],
  ["Corojo / Criollo / Habano", "Variedades de semente de tabaco de origem cubana, muito usadas em capas e tripas."],
  ["Connecticut Shade", "Capa clara cultivada sob pano (sombra), suave e cremosa; hoje muito cultivada no Equador."],
  ["Connecticut Broadleaf", "Capa escura e grossa cultivada ao sol, típica de Maduros."],
  ["Claro, Colorado, Maduro, Oscuro", "Cores da capa, da mais clara à mais escura; as escuras tendem a ser mais doces e terrosas."],
  ["Primings", "Posição/ordem de colheita das folhas na planta, de baixo para cima."],
  ["Cura", "Secagem das folhas em casas de tabaco, onde perdem a clorofila e ganham cor."],
  ["Fermentação (pilones)", "Pilhas de folhas que aquecem e libertam amónia; arredonda o sabor."],
  ["Añejamiento", "Envelhecimento do tabaco ou dos charutos já feitos, para integrar sabores."],
  ["Torcedor", "Pessoa que enrola os charutos à mão."],
  ["Escogida", "Seleção e classificação das folhas por cor, tamanho e qualidade."],
  ["Cabeça, pé, gorro (cap)", "Cabeça: ponta que vai à boca, fechada pelo gorro. Pé: ponta que se acende."],
  ["Anilha", "Etiqueta à volta do charuto com a marca."],
  ["Tiragem", "Facilidade com que o fumo passa; nem presa nem aberta demais."],
  ["Combustão / túnel / canoa", "Como o charuto arde: túnel é arder só por dentro; canoa é arder só de um lado."],
  ["Retrohale", "Expirar parte do fumo pelo nariz para sentir aromas que a boca não apanha."],
  ["Terços", "Divisão de uma fumada em início, meio e fim; os sabores costumam evoluir entre terços."],
  ["Força vs corpo vs sabor", "Força: efeito da nicotina. Corpo: densidade/peso do fumo na boca. Sabor: intensidade aromática. São independentes."],
  ["Humidor", "Caixa ou armário com humidade controlada (65–70%) para guardar charutos."],
  ["Boveda", "Pacote de humidade de duas vias que mantém uma humidade relativa fixa (62, 65, 69%…)."],
  ["Tupperdor", "Caixa hermética usada como humidor barato, com Boveda."],
  ["Lasioderma (escaravelho do tabaco)", "Praga que faz pequenos furos; prospera acima de ~24 °C com humidade alta."],
  ["Bloom (plume)", "Pó cristalino de óleos à superfície da capa; ao contrário do bolor, limpa-se sem manchas."],
  ["Habanos Specialist / La Casa del Habano", "Lojas autorizadas pela Habanos S.A. para vender charutos cubanos com garantia."],
  ["Edición Limitada", "Lançamento anual da Habanos com folhas envelhecidas e capa normalmente mais escura."],
  ["Edición Regional", "Vitola feita para um mercado específico (ex.: Portugal, Espanha, França), com anilha própria."],
  ["Gran Reserva / Reserva", "Charutos com tabaco envelhecido vários anos antes de enrolar."],
  ["Totalmente a mano", "Marca oficial de charutos cubanos feitos inteiramente à mão."],
  ["Tubo", "Charuto vendido num tubo individual (alumínio ou vidro), útil para transporte."],
];
function setupGlossary() {
  const draw = () => {
    const q = $("#glq").value.trim().toLowerCase();
    const l = GLOSSARY.filter(([t, d]) => !q || (t + " " + d).toLowerCase().includes(q));
    $("#glOut").innerHTML = l.map(([t, d]) => `<div class="item"><b>${esc(t)}</b><div class="sub">${esc(d)}</div></div>`).join("") || "<p class='muted'>Sem resultados.</p>";
  };
  $("#glq").addEventListener("input", draw); draw();
}

/** "ROS ABR 24" -> fábrica (código), mês, ano, idade. */
function decodeBox(txt) {
  const t = (txt || "").toUpperCase().replace(/[^A-Z0-9 ]/g, " ").trim();
  const m = t.match(/\b(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\s*(\d{2})\b/);
  if (!m) return t ? { html: "Não reconheço a data. O formato é MÊS (em espanhol, 3 letras) + ano com 2 dígitos, ex.: ABR 24." } : null;
  const month = MONTHS_ES[m[1]], year = 2000 + +m[2];
  const date = `${year}-${String(month).padStart(2, "0")}-01`;
  if (new Date(date) > new Date()) return { html: "Data no futuro: confirma o código.", date: null };
  const factory = t.replace(m[0], "").trim().split(/\s+/).filter(w => /^[A-Z]{3}$/.test(w))[0];
  const age = monthsBetween(date), years = Math.floor(age / 12), rest = age % 12;
  return {
    date, age,
    html: `Embalado em <b>${MONTH_PT[month - 1]} de ${year}</b> · ${years ? years + " ano(s) " : ""}${rest} mês(es) de idade${factory ? ` · código de fábrica <b>${esc(factory)}</b>` : ""}.<br><span class="warn">${agingNote(age)}</span>`,
  };
}
function agingNote(ageMonths) {
  if (ageMonths < 1) return "Muito recente: deixa descansar algumas semanas no humidor.";
  if (ageMonths < 12) return "Jovem: bom para provar já ou para começar a envelhecer.";
  if (ageMonths < 36) return "1 a 3 anos: muitos Habanos começam a arredondar nesta fase.";
  if (ageMonths < 84) return "3 a 7 anos: envelhecimento sério; prova um e decide se guardas o resto.";
  return "Mais de 7 anos: vintage. Guarda em condições estáveis e prova com calma.";
}

/* ---------- Humidor ---------- */
function setupHumidor() {
  $("#hDate").valueAsDate = new Date();
  $("#hOther").addEventListener("change", () => {
    const x = FR_BY_LABEL && FR_BY_LABEL.get($("#hOther").value);
    if (x && x.unit_eur && !$("#hPrice").value) $("#hPrice").value = x.unit_eur;
  });
  $("#hCigar").addEventListener("change", () => {
    const c = cig($("#hCigar").value);
    if (c && c.priceFR && c.priceFR.min && !$("#hPrice").value) $("#hPrice").placeholder = `Preço pago (oficial FR: ${eur(c.priceFR.min)})`;
  });
  $("#hAdd").onclick = () => {
    const other = $("#hOther").value.trim();
    const l = lsGet(HKEY, []);
    l.unshift({ id: Date.now(), cigar: other ? "fr:" + other : $("#hCigar").value, qty: Math.max(1, +$("#hQty").value || 1),
      date: $("#hDate").value, note: $("#hNote").value.trim(), price: +$("#hPrice").value || null, box: $("#hBox").value.trim() || null });
    lsSet(HKEY, l);
    ["#hNote", "#hOther", "#hPrice", "#hBox"].forEach(i => $(i).value = "");
    renderHumidor();
  };
  $("#hExport").onclick = () => download("humidor-charutos.json", { humidor: lsGet(HKEY, []), higrometro: lsGet(GKEY, []) });
  $("#gAdd").onclick = () => {
    const rh = +$("#gRh").value, t = +$("#gT").value || null;
    if (!rh) return;
    const l = lsGet(GKEY, []); l.push({ date: today(), rh, t }); lsSet(GKEY, l.slice(-200));
    $("#gRh").value = ""; $("#gT").value = ""; renderHygro();
  };
  renderHumidor(); renderHygro();
}

function renderHumidor() {
  const l = lsGet(HKEY, []), total = l.reduce((s, x) => s + x.qty, 0);
  const value = l.reduce((s, x) => s + (x.price || 0) * x.qty, 0);
  const alerts = [];
  const rows = l.map(x => {
    const box = x.box ? decodeBox(x.box) : null;
    const ageRef = box && box.date ? box.date : x.date;
    const age = ageRef ? monthsBetween(ageRef) : null;
    const restDays = x.date ? Math.floor((Date.now() - new Date(x.date)) / 864e5) : null;
    if (restDays !== null && restDays < 21) alerts.push(`${displayName(x.cigar)}: em descanso (${restDays} dia(s) desde a compra; o ideal são 3 semanas).`);
    if (age !== null && [12, 24, 36, 60].some(mm => age >= mm && age < mm + 1)) alerts.push(`${displayName(x.cigar)}: faz ${Math.floor(age / 12)} ano(s) — boa altura para provar um.`);
    return `<div class="item"><b>${esc(displayName(x.cigar))}</b> × ${x.qty}
      <span class="muted">· comprado ${esc(x.date || "?")}${x.price ? " · " + eur(x.price) + "/un." : ""}${x.box ? " · caixa " + esc(x.box) : ""}${age !== null ? ` · ${age} mês(es)${box && box.date ? " desde o embalamento" : " de humidor"}` : ""}${x.note ? " · " + esc(x.note) : ""}</span>
      ${age !== null ? `<div class="warn">${agingNote(age)}</div>` : ""}
      <div class="row" style="margin-top:6px"><button class="btn sm ghost" data-smoke="${x.id}">Fumei um</button><button class="btn sm ghost" data-del="${x.id}">Remover</button></div></div>`;
  }).join("");
  $("#hList").innerHTML = (l.length ? `<p class="muted">${total} charuto(s) em ${l.length} entrada(s)${value ? " · valor pago " + eur(value) : ""}</p>` : "<p class='muted'>Humidor vazio.</p>")
    + (alerts.length ? `<div class="panel" style="border-color:var(--gold)"><b>Alertas</b><ul>${alerts.map(a => `<li>${esc(a)}</li>`).join("")}</ul></div>` : "") + rows;
  $("#hList").querySelectorAll("[data-smoke]").forEach(b => b.onclick = () => {
    let l = lsGet(HKEY, []); const e = l.find(x => x.id == b.dataset.smoke); if (!e) return;
    e.qty--; if (e.qty <= 0) l = l.filter(x => x !== e);
    lsSet(HKEY, l); renderHumidor(); goTab("journal");
    if (e.cigar.startsWith("fr:")) $("#jOther").value = e.cigar.slice(3); else $("#jCigar").value = e.cigar;
  });
  $("#hList").querySelectorAll("[data-del]").forEach(b => b.onclick = () => { lsSet(HKEY, lsGet(HKEY, []).filter(x => x.id != b.dataset.del)); renderHumidor(); });
}

function renderHygro() {
  const l = lsGet(GKEY, []);
  if (!l.length) { $("#gOut").innerHTML = "<p class='muted'>Sem leituras. O ideal é 65–70% de humidade e 16–21 °C.</p>"; return; }
  const last = l[l.length - 1], warn = [];
  if (last.rh < 62) warn.push("Humidade baixa: os charutos secam e queimam depressa. Repõe a água ou troca o Boveda.");
  if (last.rh > 72) warn.push("Humidade alta: risco de bolor e tiragem difícil. Abre o humidor uns minutos ou usa um Boveda de 65% ou 62%.");
  if (last.t && last.t > 24) warn.push("Acima de 24 °C aumenta o risco de escaravelho do tabaco (Lasioderma). Procura um sítio mais fresco.");
  const series = l.slice(-30).map((x, i) => [x.date + "#" + i, x.rh]);
  const vs = series.map(s => s[1]), mn = Math.min(...vs, 60), mx = Math.max(...vs, 75), W = 220, H = 40;
  const pts = series.map((s, i) => `${(i / Math.max(1, series.length - 1) * (W - 4) + 2).toFixed(1)},${(H - 3 - (s[1] - mn) / ((mx - mn) || 1) * (H - 6)).toFixed(1)}`).join(" ");
  const band = (v) => (H - 3 - (v - mn) / ((mx - mn) || 1) * (H - 6)).toFixed(1);
  $("#gOut").innerHTML = `<p>Última leitura (${esc(last.date)}): <b>${last.rh}%</b>${last.t ? ` · ${last.t} °C` : ""}</p>
    <svg width="${W}" height="${H}" role="img" aria-label="Últimas leituras de humidade"><rect x="0" y="${band(70)}" width="${W}" height="${band(65) - band(70)}" fill="rgba(127,176,105,.18)"/><polyline points="${pts}" fill="none" stroke="#e0703a" stroke-width="1.6"/></svg>
    <div class="warn">Faixa verde: 65–70%.</div>${warn.map(w => `<p class="warn">⚠ ${esc(w)}</p>`).join("")}
    <button class="btn ghost sm" id="gClear">Apagar leituras</button>`;
  $("#gClear").onclick = () => { lsSet(GKEY, []); renderHygro(); };
}

function renderHomeAdvice() {
  const k = HOME && HOME.climate; if (!k) { $("#homeAdvice").textContent = "Sem dados de clima."; return; }
  const m = new Date().getMonth(), rh = k.rh_pct_monthly[m], t = k.temp_c_monthly[m];
  const tips = [];
  if (rh >= 75) tips.push(`A humidade exterior em ${esc(HOME.place)} anda nos ${rh}%: o humidor quase não precisa de água. Prefere Boveda de 65% (ou 62% se notares tiragem difícil) e vigia o bolor.`);
  else if (rh < 60) tips.push(`Ar seco (${rh}%): confirma a humidade com mais frequência e repõe a água.`);
  else tips.push(`Humidade exterior moderada (${rh}%): Boveda de 69% ou 65%, conforme o teu gosto.`);
  if (t >= 22) tips.push(`Temperaturas médias de ${t} °C: guarda o humidor longe do sol e de janelas; acima de 24 °C há risco de escaravelho.`);
  else if (t <= 12) tips.push(`Meses frios (${t} °C de média): evita o humidor junto a aquecedores, que secam e aquecem.`);
  else tips.push(`Temperatura média de ${t} °C: confortável para charutos.`);
  $("#homeAdvice").innerHTML = `<p>${MONTH_PT[m][0].toUpperCase() + MONTH_PT[m].slice(1)} em ${esc(HOME.place)}: ${t} °C e ${rh}% de humidade relativa em média (NASA POWER).</p><ul>${tips.map(x => `<li>${x}</li>`).join("")}</ul>`;
}

/* ---------- Prova guiada e roda de sabores ---------- */
const WHEEL = [
  ["Terra", "#8a6a4a", ["terra", "cogumelo", "mineral", "couro", "tabaco cru"]],
  ["Madeira", "#a0763c", ["cedro", "carvalho", "madeira", "lápis"]],
  ["Especiarias", "#c0532c", ["pimenta preta", "pimenta branca", "canela", "noz-moscada", "cravinho", "especiarias"]],
  ["Torrados", "#5b3a26", ["café", "cacau", "chocolate negro", "pão torrado", "tostado"]],
  ["Doce", "#d4a85a", ["mel", "caramelo", "baunilha", "açúcar mascavado", "melaço", "doçura"]],
  ["Frutos secos", "#b28b5e", ["amêndoa", "avelã", "noz", "amendoim", "frutos secos", "nozes"]],
  ["Fruta", "#9e3d48", ["frutos vermelhos", "passas", "figo", "citrinos", "cereja"]],
  ["Cremoso", "#e2cfa6", ["creme", "manteiga", "natas", "leite"]],
  ["Ervas e flores", "#7f9a5a", ["feno", "ervas", "chá", "flores", "relva"]],
];
const G = { third: 1, cat: null, picks: { 1: [], 2: [], 3: [] } };

function drawWheel() {
  const R = 92, r0 = 34, cx = 100, cy = 100, n = WHEEL.length;
  const arc = (a0, a1, ro, ri) => {
    const p = (a, r) => [cx + r * Math.cos(a), cy + r * Math.sin(a)];
    const [x0, y0] = p(a0, ro), [x1, y1] = p(a1, ro), [x2, y2] = p(a1, ri), [x3, y3] = p(a0, ri);
    return `M${x0},${y0} A${ro},${ro} 0 0 1 ${x1},${y1} L${x2},${y2} A${ri},${ri} 0 0 0 ${x3},${y3} Z`;
  };
  $("#wheel").innerHTML = `<svg width="200" height="200" viewBox="0 0 200 200" role="img" aria-label="Roda de sabores">${WHEEL.map(([name, col], i) => {
    const a0 = -Math.PI / 2 + i * 2 * Math.PI / n, a1 = a0 + 2 * Math.PI / n, am = (a0 + a1) / 2;
    const cnt = Object.values(G.picks).flat().filter(f => WHEEL[i][2].includes(f)).length;
    return `<g data-wc="${i}" style="cursor:pointer"><path d="${arc(a0, a1, R, r0)}" fill="${col}" stroke="#1b120d" stroke-width="2" opacity="${G.cat === i ? 1 : .78}"/>
      <text x="${cx + 64 * Math.cos(am)}" y="${cy + 64 * Math.sin(am)}" text-anchor="middle" dominant-baseline="middle" font-size="9" fill="#1b120d" style="pointer-events:none">${esc(name.split(" ")[0])}${cnt ? " •" + cnt : ""}</text></g>`;
  }).join("")}<circle cx="${cx}" cy="${cy}" r="${r0 - 2}" fill="#26180f"/><text x="${cx}" y="${cy}" text-anchor="middle" dominant-baseline="middle" font-size="11" fill="#d4a85a">${G.third}.º terço</text></svg>`;
  $("#wheel").querySelectorAll("[data-wc]").forEach(g => g.onclick = () => { G.cat = +g.dataset.wc; drawWheel(); drawNotes(); });
}
function drawNotes() {
  if (G.cat !== null) {
    const [name, col, notes] = WHEEL[G.cat];
    $("#wheelNotes").innerHTML = `<b>${esc(name)}</b><br>` + notes.map(f => `<button class="tag" data-gf="${esc(f)}" style="cursor:pointer;${G.picks[G.third].includes(f) ? `background:${col};color:#1b120d;border-color:${col}` : "background:none"}">${esc(f)}</button>`).join("");
    $("#wheelNotes").querySelectorAll("[data-gf]").forEach(b => b.onclick = e => {
      e.preventDefault(); const f = b.dataset.gf, l = G.picks[G.third], i = l.indexOf(f);
      i >= 0 ? l.splice(i, 1) : l.push(f); drawWheel(); drawNotes();
    });
  }
  $("#gPicked").innerHTML = [1, 2, 3].map(t => `<div class="sub"><b>${t}.º terço:</b> ${G.picks[t].length ? G.picks[t].map(esc).join(", ") : "—"}</div>`).join("");
}
function setupGuided() {
  document.querySelectorAll('input[name="gThird"]').forEach(r => r.addEventListener("change", () => { G.third = +r.value; drawWheel(); drawNotes(); }));
  drawWheel(); drawNotes();
}
function collectGuided() {
  const g = { thirds: { ...G.picks }, draw: +$("#gDraw").value || null, burn: +$("#gBurn").value || null, ash: +$("#gAsh").value || null,
              strength: +$("#gStr").value || null, retro: $("#gRetro").value.trim() || null };
  const any = Object.values(g.thirds).some(l => l.length) || g.draw || g.burn || g.ash || g.strength || g.retro;
  return any ? g : null;
}
function resetGuided() {
  G.picks = { 1: [], 2: [], 3: [] }; G.cat = null; G.third = 1;
  document.querySelector('input[name="gThird"][value="1"]').checked = true;
  ["#gDraw", "#gBurn", "#gAsh", "#gStr", "#gRetro"].forEach(i => $(i).value = "");
  $("#wheelNotes").textContent = "Toca numa família de sabores."; drawWheel(); drawNotes();
}
function guidedSummary(g) {
  if (!g) return "";
  const t = [1, 2, 3].filter(i => (g.thirds[i] || []).length).map(i => `${i}.º: ${g.thirds[i].join(", ")}`).join(" · ");
  const c = [["tiragem", g.draw], ["combustão", g.burn], ["cinza", g.ash], ["força", g.strength]].filter(x => x[1]).map(x => `${x[0]} ${x[1]}/5`).join(" · ");
  return `<div class="sub">${t ? "🌀 " + esc(t) : ""}${c ? (t ? "<br>" : "") + "🔧 " + esc(c) : ""}${g.retro ? "<br>👃 " + esc(g.retro) : ""}</div>`;
}

/* ---------- Diário: catálogo oficial, partilha ---------- */
function setupJournal() {
  $("#jSave").onclick = () => {
    const other = $("#jOther").value.trim();
    const l = lsGet(JKEY, []);
    const guided = collectGuided();
    l.unshift({ date: today(), cigar: other ? "fr:" + other : $("#jCigar").value, drink: $("#jDrink").value.trim(),
      rating: +$("#jRating").value, notes: $("#jNotes").value.trim(), ...(guided ? { guided } : {}) });
    lsSet(JKEY, l);
    ["#jNotes", "#jDrink", "#jOther"].forEach(i => $(i).value = "");
    resetGuided(); $("#guided").open = false;
    renderJournal();
  };
  $("#jExport").onclick = () => download("diario-charutos.json", lsGet(JKEY, []));
  setupGuided();
  renderJournal();
}

function renderJournal() {
  const l = lsGet(JKEY, []);
  $("#jList").innerHTML = l.map((e, i) => `<div class="item"><b>${esc(displayName(e.cigar))}</b> · ${"★".repeat(e.rating)}${"☆".repeat(5 - e.rating)}
    <span class="muted">· ${esc(e.date)}${e.drink ? " · " + esc(e.drink) : ""}</span><div>${esc(e.notes)}</div>${guidedSummary(e.guided)}
    <div class="row" style="margin-top:6px"><button class="btn sm ghost" data-share="${i}">Partilhar</button><button class="btn sm ghost" data-jdel="${i}">Apagar</button></div></div>`).join("")
    || "<p class='muted'>Ainda sem provas registadas.</p>";
  $("#jList").querySelectorAll("[data-share]").forEach(b => b.onclick = () => shareNote(l[+b.dataset.share], b));
  $("#jList").querySelectorAll("[data-jdel]").forEach(b => b.onclick = () => { const x = lsGet(JKEY, []); x.splice(+b.dataset.jdel, 1); lsSet(JKEY, x); renderJournal(); });
}

const b64 = s => btoa(unescape(encodeURIComponent(s))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const unb64 = s => decodeURIComponent(escape(atob(s.replace(/-/g, "+").replace(/_/g, "/"))));

function shareNote(e, btn) {
  const payload = { n: displayName(e.cigar), r: e.rating, d: e.date, b: e.drink, t: e.notes };
  const url = location.origin + location.pathname + "#nota=" + b64(JSON.stringify(payload));
  const done = () => { btn.textContent = "Link copiado"; setTimeout(() => btn.textContent = "Partilhar", 2000); };
  if (navigator.share) navigator.share({ title: "Nota de prova — Boss Cigar", text: `${payload.n} ${"★".repeat(payload.r)}`, url }).catch(() => {});
  else if (navigator.clipboard) navigator.clipboard.writeText(url).then(done, () => prompt("Copia o link:", url));
  else prompt("Copia o link:", url);
}

function openSharedNote() {
  const m = location.hash.match(/^#nota=([A-Za-z0-9_-]+)/); if (!m) return;
  let n; try { n = JSON.parse(unb64(m[1])); } catch { return; }
  const d = $("#detail");
  d.innerHTML = `<h2 style="margin-top:0">Nota de prova partilhada</h2><p><b>${esc(n.n)}</b> · ${"★".repeat(n.r || 0)}${"☆".repeat(5 - (n.r || 0))}</p>
    <p class="muted">${esc(n.d || "")}${n.b ? " · " + esc(n.b) : ""}</p><p>${esc(n.t || "")}</p>
    <div class="row"><input id="fromWho" placeholder="De quem é? (opcional)" style="max-width:240px"><button class="btn" id="keepNote">Guardar nas notas de amigos</button><button class="btn ghost" id="closeNote">Fechar</button></div>`;
  d.showModal();
  $("#closeNote").onclick = () => { d.close(); history.replaceState(null, "", location.pathname); };
  $("#keepNote").onclick = () => {
    const f = lsGet(FKEY, []); f.unshift({ from: $("#fromWho").value.trim() || "amigo", cigar: "fr:" + n.n, rating: n.r, date: n.d, drink: n.b, notes: n.t });
    lsSet(FKEY, f); d.close(); history.replaceState(null, "", location.pathname); goTab("journal"); renderFriends();
  };
}

function setupFriends() {
  $("#jImport").addEventListener("change", ev => {
    const file = ev.target.files[0]; if (!file) return;
    const who = (file.name.replace(/\.json$/i, "").replace(/diario-charutos-?/i, "") || "amigo");
    file.text().then(t => {
      let arr; try { arr = JSON.parse(t); } catch { alert("Ficheiro inválido."); return; }
      if (!Array.isArray(arr)) { alert("Esperava o JSON exportado do Diário."); return; }
      const f = lsGet(FKEY, []);
      arr.forEach(e => e && e.cigar && f.push({ from: who, cigar: e.cigar.startsWith("fr:") ? e.cigar : "fr:" + displayName(e.cigar), rating: +e.rating || 0, date: e.date, drink: e.drink, notes: e.notes }));
      lsSet(FKEY, f); renderFriends();
    });
    ev.target.value = "";
  });
  renderFriends();
}
function renderFriends() {
  const f = lsGet(FKEY, []);
  $("#friends").innerHTML = f.length ? f.map((e, i) => `<div class="item"><b>${esc(displayName(e.cigar))}</b> · ${"★".repeat(e.rating)}${"☆".repeat(5 - e.rating)} <span class="muted">· ${esc(e.from)} · ${esc(e.date || "")}${e.drink ? " · " + esc(e.drink) : ""}</span><div>${esc(e.notes || "")}</div><button class="btn sm ghost" data-fdel="${i}">Remover</button></div>`).join("")
    : "<p class='muted'>Sem notas de amigos.</p>";
  $("#friends").querySelectorAll("[data-fdel]").forEach(b => b.onclick = () => { const x = lsGet(FKEY, []); x.splice(+b.dataset.fdel, 1); lsSet(FKEY, x); renderFriends(); });
}

/* ---------- Para mim: perfil, recomendações, estatísticas ---------- */
const wrapperClass = w => { w = (w || "").toLowerCase(); return /maduro|oscuro|broadleaf/.test(w) ? "escura" : /connecticut|claro|shade/.test(w) ? "clara" : "natural"; };
const vitClass = v => { v = (v || "").toLowerCase(); for (const k of ["double corona", "churchill", "lancero", "panetela", "petit corona", "corona", "robusto", "toro", "gordo", "torpedo", "belicoso", "pir", "perfecto"]) if (v.includes(k)) return k === "pir" ? "pirámide" : k; return null; };

function buildProfile(entries) {
  const P = { n: 0, strength: [], wrap: {}, country: {}, brand: {}, vit: {}, flavor: {}, price: [], tasted: new Set() };
  const add = (o, k, w) => { if (k) o[k] = (o[k] || 0) + w; };
  for (const e of entries) {
    const w = (e.rating || 3) - 3; // 5★ = +2 … 1★ = -2
    P.tasted.add(e.cigar); P.n++;
    if (e.guided) {  // sabores sentidos na prova guiada contam a dobrar: são observação tua, não descrição do fabricante
      Object.values(e.guided.thirds || {}).flat().forEach(f => add(P.flavor, f, w * 2));
      if (e.guided.strength && w) P.strength.push([e.guided.strength, w]);
    }
    if (e.cigar.startsWith("fr:")) {
      const x = FR_BY_LABEL && FR_BY_LABEL.get(e.cigar.slice(3));
      if (x) { add(P.brand, x.brand, w); add(P.vit, vitClass(x.vitola), w); if (w > 0 && x.unit_eur) P.price.push(x.unit_eur); }
      continue;
    }
    const c = cig(e.cigar); if (!c) continue;
    if (w !== 0 && c.strength) P.strength.push([c.strength, w]);
    add(P.wrap, wrapperClass(c.wrapper), w); add(P.country, c.country, w); add(P.brand, c.brand, w); add(P.vit, vitClass(c.vitola), w);
    c.flavors.forEach(f => add(P.flavor, f, w));
    if (w > 0 && c.priceFR && c.priceFR.min) P.price.push(c.priceFR.min);
  }
  const pos = P.strength.filter(s => s[1] > 0);
  P.prefStrength = pos.length ? pos.reduce((a, s) => a + s[0] * s[1], 0) / pos.reduce((a, s) => a + s[1], 0) : null;
  P.prefPrice = P.price.length ? P.price.sort((a, b) => a - b)[Math.floor(P.price.length / 2)] : null;
  return P;
}
const topKeys = (o, n = 3) => Object.entries(o).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]).slice(0, n).map(([k]) => k);

function scoreSeed(c, P) {
  let s = 0; const why = [];
  if (P.prefStrength && c.strength) { const d = Math.abs(c.strength - P.prefStrength); s += 2 - d; if (d < 0.75) why.push(`força ${STRENGTH[c.strength].toLowerCase()}`); }
  const wc = wrapperClass(c.wrapper); if (P.wrap[wc]) { s += Math.sign(P.wrap[wc]) * Math.min(2, Math.abs(P.wrap[wc])); if (P.wrap[wc] > 0) why.push(`capa ${wc}`); }
  if (P.country[c.country]) { s += Math.sign(P.country[c.country]) * Math.min(1.5, Math.abs(P.country[c.country])); if (P.country[c.country] > 0) why.push(c.country); }
  if (P.brand[c.brand]) { s += Math.sign(P.brand[c.brand]) * 1; if (P.brand[c.brand] > 0) why.push(`gostas de ${c.brand}`); }
  const fl = c.flavors.filter(f => (P.flavor[f] || 0) > 0); s += fl.length * 0.6; if (fl.length) why.push("notas de " + fl.slice(0, 2).join(" e "));
  const v = vitClass(c.vitola); if (v && P.vit[v]) s += Math.sign(P.vit[v]) * 0.5;
  return { s, why };
}

function scoreFr(x, P) {
  let s = 0; const why = [];
  if (x.brand && P.brand[x.brand]) { s += Math.sign(P.brand[x.brand]) * Math.min(3, Math.abs(P.brand[x.brand]) * 1.5); if (P.brand[x.brand] > 0) why.push(`gostas de ${x.brand}`); }
  const v = vitClass(x.vitola); if (v && P.vit[v]) { s += Math.sign(P.vit[v]) * 1; if (P.vit[v] > 0) why.push(`formato ${v}`); }
  if (P.prefPrice && x.unit_eur) { const r = x.unit_eur / P.prefPrice; if (r > 0.6 && r < 1.5) { s += 1; why.push(`preço perto do que costumas gostar (${eur(P.prefPrice)})`); } else if (r > 2.5) s -= 1; }
  return { s, why };
}

function renderMe() {
  const entries = lsGet(JKEY, []);
  const P = buildProfile(entries);
  if (P.n < 3) {
    $("#recoProfile").innerHTML = `<p>Regista pelo menos <b>3 provas</b> no Diário (tens ${P.n}) para começar a ter recomendações.</p><button class="btn" id="goDiary">Ir para o Diário</button>`;
    $("#goDiary").onclick = () => goTab("journal");
    $("#recoSeed").innerHTML = ""; $("#recoFr").innerHTML = "";
  } else {
    const parts = [];
    if (P.prefStrength) parts.push(`força à volta de <b>${STRENGTH[Math.round(P.prefStrength)].toLowerCase()}</b>`);
    if (topKeys(P.wrap, 1).length) parts.push(`capa <b>${topKeys(P.wrap, 1)[0]}</b>`);
    if (topKeys(P.country, 2).length) parts.push(`origem <b>${topKeys(P.country, 2).join("</b> e <b>")}</b>`);
    if (topKeys(P.flavor, 3).length) parts.push(`notas de <b>${topKeys(P.flavor, 3).join(", ")}</b>`);
    if (P.prefPrice) parts.push(`preço típico <b>${eur(P.prefPrice)}</b>`);
    $("#recoProfile").innerHTML = `<p>O teu perfil (${P.n} provas): ${parts.join(" · ") || "ainda pouco definido"}.</p>`;

    const seed = DB.cigars.filter(c => !P.tasted.has(c.id)).map(c => ({ c, ...scoreSeed(c, P) })).filter(r => r.s > 0.5).sort((a, b) => b.s - a.s).slice(0, 6);
    $("#recoSeed").innerHTML = seed.map(r => cardHTML(r.c).replace("</article>", `<div class="warn" style="margin-top:6px">Porquê: ${esc(r.why.join(" · ") || "perfil semelhante")}</div></article>`)).join("")
      || "<p class='muted'>Já provaste tudo o que combina contigo na base de dados.</p>";
    bindCards($("#recoSeed"));

    const perBrand = {};
    const fr = (FR_ROWS || []).filter(x => !x.cigarillo && !x.sampler && x.unit_eur && !P.tasted.has("fr:" + x.label))
      .map(x => ({ x, ...scoreFr(x, P) })).filter(r => r.s > 1).sort((a, b) => b.s - a.s || a.x.unit_eur - b.x.unit_eur)
      .filter((r => { const seen = new Set(); return r2 => { const k = r2.x.label.replace(/\(.*?\)/g, "").trim().toLowerCase(); if (seen.has(k)) return false; seen.add(k); return true; }; })())
      .filter(r => { const b = r.x.brand || r.x.label; perBrand[b] = (perBrand[b] || 0) + 1; return perBrand[b] <= 2; }).slice(0, 12);
    $("#recoFr").innerHTML = fr.length ? `<table><tr><th>Referência</th><th>Marca</th><th>Vitola</th><th>€/unidade</th><th>Porquê</th><th></th></tr>${fr.map((r, i) =>
      `<tr><td>${esc(r.x.label)}</td><td>${esc(r.x.brand || "—")}</td><td>${esc(r.x.vitola || "—")}</td><td>${eur(r.x.unit_eur)}</td><td class="sub">${esc(r.why.join(" · "))}</td><td><button class="btn sm ghost" data-wish="${i}" style="white-space:nowrap">+ Humidor</button></td></tr>`).join("")}</table>`
      : "<p class='muted'>Sem sugestões do catálogo oficial ainda: dá estrelas a provas de marcas e formatos que existam no catálogo.</p>";
    $("#recoFr").querySelectorAll("[data-wish]").forEach(b => b.onclick = () => { const x = fr[+b.dataset.wish].x; goTab("humidor"); $("#hOther").value = x.label; $("#hPrice").value = x.unit_eur || ""; });
  }
  renderStats(entries);
}

function renderStats(entries) {
  const hum = lsGet(HKEY, []);
  if (!entries.length && !hum.length) { $("#stats").innerHTML = "<p class='muted'>Sem dados ainda: usa o Diário e o Humidor.</p>"; return; }
  const now = new Date(), months = [];
  for (let i = 11; i >= 0; i--) { const d = new Date(now.getFullYear(), now.getMonth() - i, 1); months.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`); }
  const perMonth = months.map(m => entries.filter(e => (e.date || "").startsWith(m)).length), mx = Math.max(1, ...perMonth);
  const bars = perMonth.map((v, i) => `<div style="flex:1;text-align:center" title="${months[i]}: ${v}"><div style="height:${Math.round(v / mx * 60)}px;background:var(--ember);margin:0 2px;border-radius:2px"></div><small class="muted">${MONTH_PT[+months[i].slice(5) - 1].slice(0, 3)}</small></div>`).join("");
  const avg = entries.length ? (entries.reduce((s, e) => s + (e.rating || 0), 0) / entries.length).toFixed(1) : "—";
  const brandOf = id => { if (id.startsWith("fr:")) { const x = FR_BY_LABEL && FR_BY_LABEL.get(id.slice(3)); return x && x.brand; } const c = cig(id); return c && c.brand; };
  const cnt = (arr) => Object.entries(arr.reduce((o, k) => (k && (o[k] = (o[k] || 0) + 1), o), {})).sort((a, b) => b[1] - a[1]).slice(0, 5);
  const brands = cnt(entries.map(e => brandOf(e.cigar)));
  const drinks = cnt(entries.filter(e => e.rating >= 4).map(e => (e.drink || "").trim()));
  const best = entries.filter(e => e.rating === 5).slice(0, 5);
  const spent = hum.reduce((s, x) => s + (x.price || 0) * x.qty, 0);
  const stock = hum.reduce((s, x) => s + x.qty, 0);
  const tile = (v, l) => `<div class="panel" style="margin:0;text-align:center"><div style="font-size:1.6rem;color:var(--gold)">${v}</div><div class="sub">${l}</div></div>`;
  $("#stats").innerHTML = `<div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(150px,1fr));margin-bottom:12px">
      ${tile(entries.length, "provas registadas")}${tile(avg, "média de estrelas")}${tile(stock, "no humidor")}${tile(spent ? eur(spent) : "—", "valor do humidor (preço pago)")}</div>
    <p class="muted">Provas por mês (últimos 12 meses)</p><div style="display:flex;align-items:flex-end;height:80px">${bars}</div>
    <div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(240px,1fr));margin-top:12px">
      <div><b>Marcas mais fumadas</b><ol>${brands.map(([k, v]) => `<li>${esc(k)} (${v})</li>`).join("") || "<li class='muted'>—</li>"}</ol></div>
      <div><b>Melhores acompanhamentos (4–5★)</b><ol>${drinks.map(([k, v]) => `<li>${esc(k)} (${v})</li>`).join("") || "<li class='muted'>—</li>"}</ol></div>
      <div><b>5 estrelas</b><ol>${best.map(e => `<li>${esc(displayName(e.cigar))}</li>`).join("") || "<li class='muted'>—</li>"}</ol></div></div>`;
}

/* =====================================================================
   Navegação em grupos, pesquisa global, páginas de marca, livro
   ===================================================================== */
const GROUPS = [
  ["Descobrir", ["catalog", "mapview", "compare", "pairing", "vitolas", "producers"]],
  ["Comprar", ["frcat", "wishlist", "frces", "pricehist", "shops", "brands"]],
  ["O meu", ["me", "humidor", "journal", "sync"]],
  ["Aprender", ["guide", "guides", "tools", "sources"]],
];
const groupOf = tab => (GROUPS.find(g => g[1].includes(tab)) || [null])[0];
let CUR_GROUP = "Descobrir";

function showGroup(name, activate) {
  CUR_GROUP = name;
  document.querySelectorAll("#groups button").forEach(b => b.classList.toggle("active", b.dataset.group === name));
  const tabs = (GROUPS.find(g => g[0] === name) || [, []])[1];
  document.querySelectorAll("#subtabs > button[data-tab]").forEach(b => b.style.display = tabs.includes(b.dataset.tab) ? "" : "none");
  if (activate) { const cur = document.querySelector("#subtabs > button.active"); if (!cur || !tabs.includes(cur.dataset.tab)) goTab(tabs[0]); }
}
let LAST_TAB = "catalog";
function setupGroups() {
  const nav = $("#tabs");
  const bar = document.createElement("div");
  bar.id = "groups"; bar.style.cssText = "display:flex;gap:6px;justify-content:center;flex-wrap:wrap;width:100%;margin-bottom:6px";
  bar.innerHTML = GROUPS.map(([g]) => `<button data-group="${g}" style="font-weight:bold">${g}</button>`).join("");
  nav.prepend(bar);
  nav.style.flexDirection = "column"; nav.style.alignItems = "center";
  const row = document.createElement("div"); row.id = "subtabs";
  row.style.cssText = "display:flex;gap:6px;justify-content:center;flex-wrap:wrap";
  [...nav.querySelectorAll(":scope > button[data-tab]")].forEach(b => row.appendChild(b));
  nav.appendChild(row);
  // os botões passaram para #subtabs; o seletor "#tabs > button" deixa de os apanhar
  bar.querySelectorAll("button").forEach(b => b.onclick = () => showGroup(b.dataset.group, true));
  row.querySelectorAll("button[data-tab]").forEach(b => b.addEventListener("click", () => {
    LAST_TAB = b.dataset.tab;
    showGroup(groupOf(b.dataset.tab) || CUR_GROUP, false);  // o código antigo dos separadores limpa o destaque do grupo
  }));
  showGroup(CUR_GROUP, false);
}
/* ---------- Pesquisa global ---------- */
const fold = s => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
let GS_TIMER = null, BRAND_NAMES = null;
const SECTIONS = { catalog: "Catálogo", compare: "Comparar fichas", pairing: "Harmonizador", vitolas: "Vitolas", mapview: "Mapa de origens", producers: "Países produtores",
  frcat: "Preços oficiais", wishlist: "Lista de desejos e plano de compra", frces: "França vs Espanha", pricehist: "Evolução de preços", sync: "Sincronizar",
  brands: "Marcas", shops: "Lojas em Portugal", me: "Recomendações", humidor: "Humidor", journal: "Diário",
  guide: "Livro", guides: "Guias", tools: "Ferramentas", sources: "Fontes" };

function allBrandNames() {
  if (BRAND_NAMES) return BRAND_NAMES;
  const set = new Map();
  const add = b => { if (b && !set.has(fold(b))) set.set(fold(b), b); };
  DB.cigars.forEach(c => add(c.brand));
  (BRANDS || []).forEach(b => add(b.brand));
  ["fr", "es"].forEach(k => (CATS[k] || []).forEach(x => x.brand && x.brand_source !== "inferida" && add(x.brand)));
  BRAND_NAMES = [...set.values()];
  return BRAND_NAMES;
}

function setupGlobalSearch() {
  const box = $("#gs"), out = $("#gsOut");
  const hide = () => { out.style.display = "none"; };
  document.addEventListener("click", e => { if (!$("#gsBox").contains(e.target)) hide(); });
  box.addEventListener("keydown", e => { if (e.key === "Escape") { box.value = ""; hide(); } });
  box.addEventListener("focus", () => { Promise.all([loadCat("fr").catch(() => []), loadCat("es").catch(() => [])]).then(() => { BRAND_NAMES = null; }); });
  box.addEventListener("input", () => { clearTimeout(GS_TIMER); GS_TIMER = setTimeout(run, 150); });
  function run() {
    const q = fold(box.value.trim());
    if (q.length < 2) { hide(); return; }
    const words = q.split(/\s+/), hit = s => { const f = fold(s); return words.every(w => f.includes(w)); };
    const groups = [];
    const cig = DB.cigars.filter(c => hit(`${c.brand} ${c.line} ${c.country} ${c.vitola} ${c.wrapper} ${c.flavors.join(" ")}`)).slice(0, 6);
    if (cig.length) groups.push(["Fichas", cig.map(c => ({ t: name(c), s: `${c.country} · ${c.vitola}`, go: () => openDetail(c.id) }))]);
    const br = allBrandNames().filter(b => hit(b)).slice(0, 6);
    if (br.length) groups.push(["Marcas", br.map(b => ({ t: b, s: "página da marca", go: () => openBrand(b) }))]);
    for (const [k, flag] of [["fr", "🇫🇷"], ["es", "🇪🇸"]]) {
      const l = (CATS[k] || []).filter(x => !x.cigarillo && hit(`${x.label} ${x.brand || ""}`)).slice(0, 5);
      if (l.length) groups.push([`Preços oficiais ${flag}`, l.map(x => ({ t: x.label, s: `${eur(x.unit_eur)}${x.pack_size ? " · emb. " + x.pack_size : ""}`, go: () => {
        goTab("frcat"); $("#fCountryP").value = k; CAT_COUNTRY = k; initFr(); setTimeout(() => { $("#fq").value = x.label; FR_LIMIT = 100; renderFr(); }, 400); } }))]);
    }
    const gl = GLOSSARY.filter(([t, d]) => hit(t) || (q.length > 3 && hit(d))).slice(0, 4);
    if (gl.length) groups.push(["Glossário", gl.map(([t, d]) => ({ t, s: d.slice(0, 70) + (d.length > 70 ? "…" : ""), go: () => { goTab("guides"); $("#glq").value = t.split(" (")[0]; $("#glq").dispatchEvent(new Event("input")); $("#glq").scrollIntoView({ block: "center" }); } }))]);
    const sec = Object.entries(SECTIONS).filter(([, v]) => hit(v)).slice(0, 4);
    if (sec.length) groups.push(["Secções", sec.map(([k, v]) => ({ t: v, s: "abrir", go: () => goTab(k) }))]);
    const items = [];
    out.innerHTML = groups.length ? groups.map(([g, l]) => `<div class="sub" style="margin:6px 4px 2px;color:var(--gold)">${esc(g)}</div>` + l.map(it => { items.push(it); return `<div class="gsItem" data-i="${items.length - 1}" style="padding:6px 8px;border-radius:8px;cursor:pointer"><b>${esc(it.t)}</b> <span class="sub">${esc(it.s)}</span></div>`; }).join("")).join("")
      : "<p class='muted' style='margin:6px'>Sem resultados.</p>";
    out.style.display = "";
    out.querySelectorAll(".gsItem").forEach(el => {
      el.onmouseenter = () => el.style.background = "var(--panel2)"; el.onmouseleave = () => el.style.background = "";
      el.onclick = () => { hide(); items[+el.dataset.i].go(); };
    });
  }
}

/* ---------- Página de marca ---------- */
function openBrand(brand) {
  document.querySelectorAll("#subtabs > button").forEach(b => b.classList.remove("active"));
  document.querySelectorAll("main > section").forEach(s => s.classList.toggle("active", s.id === "brandpage"));
  scrollTo(0, 0);
  $("#brandOut").innerHTML = "<p class='muted'>A carregar…</p>";
  Promise.all([loadCat("fr").catch(() => []), loadCat("es").catch(() => []), PRICES ? Promise.resolve() : fetch("data/prices.json").then(r => r.json()).then(p => PRICES = p).catch(() => {}),
               COMPARE ? Promise.resolve() : fetch("data/compare.json").then(r => r.json()).then(c => COMPARE = c).catch(() => {})]).then(() => {
    const fb = fold(brand);
    const same = b => b && fold(b) === fb;
    const fichas = DB.cigars.filter(c => same(c.brand));
    const wp = (BRANDS || []).find(b => same(b.brand));
    const facts = (fichas.find(c => c.brandFacts) || {}).brandFacts;
    const fr = (CATS.fr || []).filter(x => same(x.brand) && !x.cigarillo), es = (CATS.es || []).filter(x => same(x.brand) && !x.cigarillo);
    const range = l => { const p = l.map(x => x.unit_eur).filter(v => v != null); return p.length ? `${eur(Math.min(...p))} – ${eur(Math.max(...p))}` : "—"; };
    const trend = PRICES && PRICES.brands.find(b => same(b.brand));
    const cmp = COMPARE ? COMPARE.rows.filter(r => same(r.brand)) : [];
    const cmpMed = cmp.length ? [...cmp.map(r => r.diff_pct)].sort((a, b) => a - b)[Math.floor(cmp.length / 2)] : null;
    const table = (l, flag) => l.length ? `<details><summary style="cursor:pointer">${flag} ${l.length} referências · ${range(l)} por unidade</summary><div style="overflow-x:auto"><table><tr><th>Referência</th><th>Vitola</th><th>Emb.</th><th>€/unidade</th></tr>${[...l].sort((a, b) => (a.unit_eur ?? 1e9) - (b.unit_eur ?? 1e9)).slice(0, 60).map(x => `<tr><td>${esc(x.label)}${x.special ? ` <span class="badge warn">${esc(x.special)}</span>` : ""}</td><td>${esc(x.vitola || "—")}</td><td>${x.pack_size || "—"}</td><td>${eur(x.unit_eur)}</td></tr>`).join("")}</table></div></details>` : `<p class="muted">${flag} sem referências.</p>`;
    $("#brandOut").innerHTML = `<div class="panel"><button class="btn ghost sm" id="brandBack">← Voltar</button>
        <h2 style="margin:10px 0 4px">${esc(brand)}</h2>
        <p class="muted">${wp ? `Fabricante: ${esc(wp.manufacturer || "—")}${wp.notes ? " · " + esc(wp.notes) : ""} <span class="sub">(Wikipédia, CC BY-SA)</span>` : ""}
        ${facts ? `<br>Wikidata: ${facts.inception_year ? "fundada em " + facts.inception_year : "ano desconhecido"}${facts.countries && facts.countries.length ? " · " + esc(facts.countries.join(", ")) : ""} · <a href="${esc(facts.url)}" target="_blank" rel="noopener">fonte</a>` : ""}</p>
        <div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(150px,1fr))">
          ${[[fichas.length, "fichas no Boss Cigar"], [fr.length, "referências 🇫🇷"], [es.length, "referências 🇪🇸"],
             [trend ? pct(trend.median_pct) : "—", "variação mediana 🇫🇷 (desde jan. 2025)"], [cmpMed != null ? pct(cmpMed) : "—", "Espanha face a França (mediana)"]]
            .map(([v, l]) => `<div class="panel" style="margin:0;text-align:center"><div style="font-size:1.4rem;color:var(--gold)">${v}</div><div class="sub">${l}</div></div>`).join("")}</div></div>
      ${fichas.length ? `<div class="panel"><h3 style="margin-top:0">Fichas</h3><div class="grid" id="brandCards">${fichas.map(cardHTML).join("")}</div></div>` : ""}
      <div class="panel"><h3 style="margin-top:0">Catálogos oficiais</h3>${table(fr, "🇫🇷 França")}${table(es, "🇪🇸 Espanha")}</div>
      ${cmp.length ? `<div class="panel" style="overflow-x:auto"><h3 style="margin-top:0">França vs Espanha</h3><table><tr><th>Referência</th><th>🇫🇷</th><th>🇪🇸</th><th>Dif.</th></tr>${cmp.slice(0, 30).map(r => `<tr><td>${esc(r.label)}</td><td>${eur(r.fr)}</td><td>${eur(r.es)}</td><td>${pct(r.diff_pct)}</td></tr>`).join("")}</table></div>` : ""}`;
    $("#brandBack").onclick = () => goTab(LAST_TAB);
    if ($("#brandCards")) bindCards($("#brandCards"));
  });
}
window.openBrand = openBrand;

/* ---------- Lojas: filtro de especialistas ---------- */
const SPECIALIST = /habano|charut|\bcigars?\b|davidoff|\bpuros?\b/i;  // "cigarros" (PT) e "cigarette" são cigarros, não charutos
function renderShops() {
  if (!shopMap) {
    shopMap = L.map("shopMap").setView([39.6, -8.2], 6);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: "© OpenStreetMap contributors" }).addTo(shopMap);
    shopLayer = L.layerGroup().addTo(shopMap);
    $("#sKind").addEventListener("input", renderShops);
  }
  const q = $("#sq").value.trim().toLowerCase(), only = $("#sKind").value === "cig";
  const isSpec = s => s.kind === "cigar" || SPECIALIST.test(s.name);
  const l = SHOPS.filter(s => (!only || isSpec(s)) && (!q || (s.name + " " + (s.city || "")).toLowerCase().includes(q)));
  shopLayer.clearLayers();
  l.forEach(s => L.circleMarker([s.lat, s.lng], { radius: isSpec(s) ? 8 : 5, color: "#d4a85a", fillColor: isSpec(s) ? "#d4a85a" : "#e0703a", fillOpacity: .9, weight: 1 })
    .addTo(shopLayer).bindPopup(`<b>${esc(s.name)}</b>${isSpec(s) ? " ⭐" : ""}<br>${esc([s.street, s.city].filter(Boolean).join(", "))}${s.opening_hours ? "<br><small>" + esc(s.opening_hours) + "</small>" : ""}${s.website ? `<br><a href="${esc(s.website)}" target="_blank" rel="noopener">site</a>` : ""} · <a href="${esc(s.osm)}" target="_blank" rel="noopener">OSM</a>`));
  $("#shopList").innerHTML = SHOPS.length
    ? `<p class="muted">${l.length} local(is)${only ? " especializados" : ""} · ⭐ = especialista em charutos</p>` + l.map(s => `<div class="item"><b>${esc(s.name)}</b>${isSpec(s) ? " ⭐" : ""} <span class="muted">· ${esc([s.street, s.city].filter(Boolean).join(", ") || "morada não indicada")}</span></div>`).join("")
    : "<p class='muted'>Sem dados do OpenStreetMap neste build.</p>";
}

/* ---------- Livro: roteiro, vinhos portugueses, mapa de sabores ---------- */
const ROADMAP = [
  ["Fase 1 — Fundação", "Charutos suaves, 5–10 fumadas. Aprender corte, lume e ritmo; vocabulário base (cremoso, cedro, feno).",
    ["Macanudo Café", "Perdomo Champagne", "Oliva Connecticut Reserve", "Arturo Fuente Chateau Fuente", "Montecristo White", "Davidoff Signature"]],
  ["Fase 2 — Médios e primeiros cubanos", "10–20 fumadas. Reconhecer origens, distinguir força de corpo.",
    ["Arturo Fuente Hemingway Short Story", "Oliva Serie G", "Undercrown Shade", "Plasencia Alma del Campo", "E.P. Carrillo Encore", "Montecristo No. 4", "Hoyo de Monterrey Epicure No. 2", "Romeo y Julieta Short Churchill", "H. Upmann Half Corona"]],
  ["Fase 3 — Encorpados e maduros", "Aguentar e apreciar potência; dominar o retrohale; explorar capas escuras.",
    ["Padrón 2000 Maduro", "Oliva Serie V", "My Father Le Bijou 1922", "Liga Privada No. 9", "Undercrown Maduro", "Aging Room Quattro", "Partagás Serie D No. 4", "Bolívar Belicosos Finos", "Ramón Allones Specially Selected"]],
  ["Fase 4 — Referências absolutas", "Calibrar o topo da escala e afinar o julgamento.",
    ["Padrón 1964 Anniversary", "Padrón 1926", "Fuente Fuente Opus X", "Davidoff Aniversario", "Cohiba Siglo VI", "Cohiba Robustos", "Trinidad Fundadores", "Montecristo No. 2", "My Father The Judge", "Plasencia Alma Fuerte"]],
];
const PT_WINES = [
  ["Porto Tawny 10/20 anos", "A harmonização portuguesa canónica: frutos secos, caramelo e madeira a espelhar cacau e café de um maduro (San Andrés, Broadleaf, Padrón)."],
  ["Porto Vintage / LBV", "Fruta negra e estrutura para nicaraguenses encorpados ou um Partagás cubano. Precisa de charuto com espinha."],
  ["Porto Ruby / branco reserva", "Versátil e fresco com charutos médios frutados; o portonic funciona com um Connecticut numa tarde de verão."],
  ["Madeira Bual / Malmsey", "A acidez corta a densidade do fumo; Malmsey com um oscuro é caramelo salgado líquido."],
  ["Madeira Sercial / Verdelho", "Secos: para charutos suaves a médios."],
  ["Moscatel de Setúbal", "Laranja confitada e mel: brilhante com capas Cameroon e Habanos adocicados (Hoyo, Por Larrañaga)."],
];
const FLAVOR_MAP = [
  ["Cuba (Habanos)", "Twang, mel, cedro, couro fino, terra elegante, café claro", "Média (exceções fortes: Bolívar, Partagás)"],
  ["Nicarágua", "Pimenta, terra doce, cacau, café, açúcar mascavado", "Média-alta a alta"],
  ["Rep. Dominicana", "Cremoso, pão torrado, amêndoa, cedro claro, flor", "Suave a média (exceções: LFD, Opus X)"],
  ["Honduras", "Terra funda, couro, especiaria rústica, madeira", "Média-alta"],
  ["Capa Connecticut Shade", "Natas, feno, manteiga, pimenta branca leve", "Ligeira"],
  ["Capa Connecticut Broadleaf", "Chocolate, café, terra doce, melaço", "Média"],
  ["Capa San Andrés (México)", "Chocolate negro, brownie, terra húmida, mineral", "Média"],
  ["Capa Cameroon", "Doce-picante, pão de especiarias, madeira doce", "Média"],
  ["Capa Habano (Equador/Nicarágua)", "Especiaria, madeira, fruto seco, mais mordida", "Média-alta"],
  ["Capa Sumatra", "Doce especiado, cedro, chá", "Média"],
  ["Brasil (Mata Fina / Arapiraca)", "Café, cacau, doçura escura suave", "Média"],
];
function setupBook() {
  const done = () => lsGet("bc-roadmap", []);
  const draw = () => {
    const d = done();
    $("#roadmap").innerHTML = ROADMAP.map(([t, txt, items], pi) => {
      const n = items.filter(x => d.includes(x)).length;
      return `<details ${pi === 0 || (n > 0 && n < items.length) ? "open" : ""} style="margin-bottom:8px"><summary style="cursor:pointer"><b>${esc(t)}</b> <span class="sub">${n}/${items.length}</span>
        <span style="display:inline-block;width:90px;height:6px;background:var(--line);border-radius:3px;vertical-align:middle;margin-left:6px"><span style="display:block;height:6px;width:${Math.round(n / items.length * 100)}%;background:var(--ember);border-radius:3px"></span></span></summary>
        <p class="sub">${esc(txt)}</p>${items.map(x => `<label style="display:flex;gap:8px;align-items:center;padding:3px 0"><input type="checkbox" data-rm="${esc(x)}" ${d.includes(x) ? "checked" : ""} style="width:auto"> <a href="#" data-rq="${esc(x)}">${esc(x)}</a></label>`).join("")}</details>`;
    }).join("") + `<p class="warn">Método: mesmo charuto em dias diferentes; depois dois da mesma vitola e origens diferentes; uma variável de cada vez. Provar às cegas com amigos é o exame final.</p>`;
    $("#roadmap").querySelectorAll("[data-rm]").forEach(cb => cb.onchange = () => { let l = done(); l = cb.checked ? [...new Set([...l, cb.dataset.rm])] : l.filter(x => x !== cb.dataset.rm); lsSet("bc-roadmap", l); draw(); });
    $("#roadmap").querySelectorAll("[data-rq]").forEach(a => a.onclick = e => { e.preventDefault(); $("#gs").value = a.dataset.rq; $("#gs").focus(); $("#gs").dispatchEvent(new Event("input")); scrollTo(0, 0); });
  };
  draw();
  $("#ptWines").innerHTML = `<div class="grid">${PT_WINES.map(([t, d]) => `<div class="panel" style="margin:0"><b>${esc(t)}</b><div class="sub">${esc(d)}</div></div>`).join("")}</div>`;
  $("#flavorMap").innerHTML = `<table><tr><th>Origem / capa</th><th>Perfil típico</th><th>Força típica</th></tr>${FLAVOR_MAP.map(r => `<tr><td>${esc(r[0])}</td><td class="sub">${esc(r[1])}</td><td>${esc(r[2])}</td></tr>`).join("")}</table>`;
}

/* ---------- arranque desta parte ---------- */
(function bootExtras() {
  const start = () => {
    if (!DB.cigars.length) return setTimeout(start, 100);
    setupGroups(); setupGlobalSearch(); setupBook();
    if (!SYNC_KEYS.includes("bc-roadmap")) SYNC_KEYS.push("bc-roadmap");
  };
  start();
})();
