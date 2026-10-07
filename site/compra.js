/* Boss Cigar — lista de desejos com plano de compra e onde comprar,
   e navegação: título por página, endereço (#separador) e "limpar filtros". */

/* =====================================================================
   Navegação
   ===================================================================== */
const PAGE_INFO = {
  catalog: "As fichas curadas: força, capa, origem, sabores e harmonizações. Toca num charuto para ver tudo.",
  mapview: "Zonas de cultivo no mapa, com o clima médio de cada uma.",
  compare: "Duas fichas lado a lado.",
  pairing: "Escolhe uma bebida, um prato ou um sabor e vê que charutos combinam.",
  vitolas: "Formatos e medidas à escala.",
  producers: "Quanto tabaco produz cada país (FAOSTAT).",
  frcat: "Todas as referências à venda em França e em Espanha, com o preço oficial. Usa ♡ para juntar à lista de desejos.",
  wishlist: "O que queres comprar: quantidades, custo em cada país, franquia de viagem e onde comprar.",
  frces: "As mesmas referências nos dois países: onde é mais barato.",
  pricehist: "Como mudaram os preços oficiais em França edição a edição.",
  shops: "Tabacarias e lojas de charutos em Portugal (OpenStreetMap).",
  brands: "Marcas e fabricantes (Wikipédia e Wikidata). Toca numa marca para ver a página dela.",
  me: "Sugestões calculadas a partir das tuas provas no Diário, e as tuas estatísticas.",
  humidor: "O que tens guardado, código das caixas, higrómetro e conselhos para o clima de casa.",
  journal: "As tuas provas, prova guiada e notas de amigos.",
  sync: "Copia os teus dados (diário, humidor, lista de desejos…) para outro dispositivo.",
  guide: "O livro em PDF, roteiro de aprendizagem e vinhos portugueses.",
  guides: "Falsificações, código da caixa, tempo de fumada, Boveda, glossário e regras de viagem.",
  tools: "Calculadoras e utilitários.",
  sources: "De onde vêm os dados, licenças e estado de cada fonte.",
};
const TAB_IDS = new Set(GROUPS.flatMap(g => g[1]));
const pageTitle = t => SECTIONS[t] || t;

function setPageHead(tab, title) {
  const g = groupOf(tab);
  $("#pageHead").innerHTML = `<div class="crumb">${g ? `<a href="#${GROUPS.find(x => x[0] === g)[1][0]}">${esc(g)}</a> › ` : ""}<b>${esc(title || pageTitle(tab))}</b></div>${PAGE_INFO[tab] ? `<p class="muted" style="margin:4px 0 0">${esc(PAGE_INFO[tab])}</p>` : ""}`;
}

let ROUTING = false;
function routeFromHash() {
  const h = decodeURIComponent(location.hash.slice(1));
  if (TAB_IDS.has(h)) {
    const cur = document.querySelector("#subtabs > button.active");
    if (!cur || cur.dataset.tab !== h || !$("#" + h).classList.contains("active")) { ROUTING = true; goTab(h); ROUTING = false; }
  } else if (h.startsWith("marca=")) {
    ROUTING = true; openBrand(h.slice(6)); ROUTING = false;
  }
}

function setupRouting() {
  document.querySelectorAll("#subtabs > button[data-tab]").forEach(b => b.addEventListener("click", () => {
    const t = b.dataset.tab;
    setPageHead(t);
    if (!ROUTING && location.hash !== "#" + t) history.pushState(null, "", "#" + t);
    refreshClearButtons();
  }));
  addEventListener("popstate", routeFromHash);
  addEventListener("hashchange", routeFromHash);
  // página de marca: título próprio e endereço partilhável
  const _openBrand = openBrand;
  openBrand = function (brand) {
    _openBrand(brand);
    setPageHead("brands", brand);
    $("#pageHead .crumb").innerHTML = `<a href="#brands">Comprar › Marcas</a> › <b>${esc(brand)}</b>`;
    if (!ROUTING) history.pushState(null, "", "#marca=" + encodeURIComponent(brand));
  };
  if (location.hash && !location.hash.startsWith("#nota=")) routeFromHash();
  if (!$("#pageHead").innerHTML) setPageHead((document.querySelector("#subtabs > button.active") || {}).dataset?.tab || "catalog");
}

/* ---------- Limpar filtros ---------- */
const CLEARERS = [];
const NOT_FILTERS = new Set(["fSort", "fSortP", "fCountryP", "cSort"]);
function addClear(box) {
  if (!box || box.dataset.clear) return;
  box.dataset.clear = "1";
  const els = () => [...box.querySelectorAll("input,select")].filter(el => !NOT_FILTERS.has(el.id));
  const def = el => el.tagName === "SELECT" ? ([...el.options].find(o => o.defaultSelected) || el.options[0] || { value: "" }).value : el.defaultValue;
  const wrap = document.createElement("div");
  wrap.className = "row"; wrap.style.cssText = "margin:-4px 0 10px;align-items:center;gap:8px";
  wrap.innerHTML = `<button type="button" class="btn ghost sm"></button><span class="sub"></span>`;
  const btn = wrap.firstChild;
  const upd = () => {
    const n = els().filter(el => el.value !== def(el)).length;
    btn.textContent = n ? `✕ Limpar filtros (${n})` : "Sem filtros ativos";
    btn.disabled = !n; btn.style.opacity = n ? "1" : ".45";
  };
  btn.onclick = () => {
    els().forEach(el => { if (el.value !== def(el)) { el.value = def(el); el.dispatchEvent(new Event("input", { bubbles: true })); el.dispatchEvent(new Event("change", { bubbles: true })); } });
    upd();
  };
  box.addEventListener("input", upd); box.addEventListener("change", upd);
  box.after(wrap); upd();
  CLEARERS.push(upd);
}
const refreshClearButtons = () => setTimeout(() => CLEARERS.forEach(f => f()), 0);

/* =====================================================================
   Lista de desejos + plano de compra
   ===================================================================== */
const PKEY = "bc-plan";
const PT_CITIES = [
  ["Lisboa", 38.722, -9.139], ["Porto", 41.150, -8.611], ["Braga", 41.545, -8.427], ["Viana do Castelo", 41.694, -8.832],
  ["Vila Real", 41.300, -7.744], ["Bragança", 41.806, -6.757], ["Aveiro", 40.641, -8.654], ["Viseu", 40.657, -7.913],
  ["Guarda", 40.537, -7.268], ["Coimbra", 40.203, -8.410], ["Castelo Branco", 39.822, -7.491], ["Leiria", 39.744, -8.807],
  ["Santarém", 39.236, -8.687], ["Portalegre", 39.297, -7.428], ["Setúbal", 38.524, -8.893], ["Évora", 38.571, -7.909],
  ["Beja", 38.015, -7.863], ["Faro", 37.019, -7.930],
];
const ROAD_FACTOR = 1.3;          // estrada ≈ 1,3 × linha reta (aproximação)
const EU_GUIDE = 200;             // nível indicativo UE para uso pessoal (charutos)
const km = (a, b, c, d) => { const R = 6371, r = x => x * Math.PI / 180, dl = r(c - a), dg = r(d - b);
  return 2 * R * Math.asin(Math.sqrt(Math.sin(dl / 2) ** 2 + Math.cos(r(a)) * Math.cos(r(c)) * Math.sin(dg / 2) ** 2)); };
const nkey = s => fold(s).replace(/\s+/g, " ").trim();
let BORDER = null, SHOPS_ALL = null;

const plan = () => Object.assign({ home: "Lisboa", eurKm: 0.15, tolls: 0, people: 1 }, lsGet(PKEY, {}));
const setPlan = p => lsSet(PKEY, Object.assign(plan(), p));
const homeXY = () => PT_CITIES.find(c => c[0] === plan().home) || PT_CITIES[0];
const mapsLink = q => `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}`;
const flag = c => c === "es" ? "🇪🇸" : "🇫🇷";

function updateWishBadge() {
  const b = document.querySelector('[data-tab="wishlist"]'); if (!b) return;
  const n = lsGet(WKEY, []).length;
  let s = b.querySelector(".wcount");
  if (!s) { s = document.createElement("span"); s.className = "wcount"; b.appendChild(s); }
  s.textContent = n ? ` ${n}` : "";
}
const _toggleWish = toggleWish;
toggleWish = function (k, x, country) { _toggleWish(k, x, country); updateWishBadge(); };

function loadPlanData() {
  return Promise.all([
    loadCat("fr").catch(() => []), loadCat("es").catch(() => []),
    COMPARE ? null : fetch("data/compare.json").then(r => r.json()).then(c => { COMPARE = c; }).catch(() => {}),
    BORDER ? null : fetch("data/border.json").then(r => r.json()).then(b => { BORDER = b; }).catch(() => { BORDER = { towns: [] }; }),
    SHOPS_ALL ? null : fetch("data/shops.json").then(r => r.json()).then(s => { SHOPS_ALL = s.shops || []; }).catch(() => { SHOPS_ALL = []; }),
  ]);
}

/* preço por unidade da mesma referência no outro país (lista de comparação, nome normalizado) */
function pricesFor(w, x) {
  const out = { fr: null, es: null };
  if (x) out[w.country] = x.unit_eur;
  const lab = nkey(x ? x.label : w.label);
  const row = COMPARE && COMPARE.rows && COMPARE.rows.find(r => nkey(w.country === "fr" ? r.fr_label : r.es_label) === lab);
  if (row) { if (out.fr == null) out.fr = row.fr; if (out.es == null) out.es = row.es; }
  return out;
}

function renderWish() {
  updateWishBadge();
  const l = lsGet(WKEY, []);
  if (!l.length) {
    $("#wish").innerHTML = `<p class="muted">Ainda está vazia. Vai a <a href="#frcat">Preços oficiais</a>, pesquisa um charuto e toca em ♡.</p>`;
    $("#planBox").innerHTML = ""; renderWhere(0);
    return;
  }
  $("#wish").innerHTML = "<p class='muted'>A carregar preços…</p>";
  loadPlanData().then(() => {
    const p = plan();
    const find = w => (CATS[w.country] || []).find(x => wishKey(w.country, x) === w.key);
    const tot = { es: 0, fr: 0, pt: 0, best: 0 }, miss = { es: 0, fr: 0, pt: 0 };
    let cigars = 0, alerts = 0;
    const rows = l.map((w, i) => {
      const x = find(w), pr = pricesFor(w, x), pack = (x && x.pack_size) || w.pack_size || 1;
      const qty = Math.max(1, +w.qty || 1), n = qty * pack, pt = w.pt != null && w.pt !== "" ? +w.pt : null;
      cigars += n;
      const opts = [["es", pr.es], ["fr", pr.fr], ["pt", pt]].filter(o => o[1] != null);
      const best = opts.length ? opts.reduce((a, b) => b[1] < a[1] ? b : a) : null;
      ["es", "fr"].forEach(k => pr[k] != null ? tot[k] += pr[k] * n : miss[k]++);
      pt != null ? tot.pt += pt * n : miss.pt++;
      if (best) tot.best += best[1] * n;
      let st = "";
      if (!x) { st = "⚠ saiu do catálogo"; alerts++; }
      else if (x.unit_eur != null && w.price != null && x.unit_eur !== w.price) { st = (x.unit_eur > w.price ? "⬆ " : "⬇ ") + pct(Math.round((x.unit_eur - w.price) / w.price * 1000) / 10) + ` desde ${w.added}`; alerts++; }
      const cell = (k, v) => v == null ? `<td class="sub">—</td>` : `<td${best && best[0] === k ? ' style="color:var(--ok);font-weight:bold"' : ""}>${eur(v)}<div class="sub">${eur(v * n)}</div></td>`;
      return `<tr><td>${flag(w.country)}</td><td>${esc(w.label)}<div class="sub">${pack > 1 ? `embalagem de ${pack}` : "à unidade"}${st ? ` · ${st}` : ""}</div></td>
        <td><input type="number" min="1" max="99" value="${qty}" data-q="${i}" style="width:58px" aria-label="Quantidade (embalagens)"><div class="sub">${n} charuto${n > 1 ? "s" : ""}</div></td>
        ${cell("es", pr.es)}${cell("fr", pr.fr)}
        <td><input type="number" min="0" step="0.05" value="${pt ?? ""}" data-pt="${i}" placeholder="€/un." style="width:72px" aria-label="Preço em Portugal por unidade">${pt != null ? `<div class="sub"${best && best[0] === "pt" ? ' style="color:var(--ok)"' : ""}>${eur(pt * n)}</div>` : ""}</td>
        <td style="white-space:nowrap"><button class="btn sm ghost" data-wh="${i}" title="Já comprei: passar para o humidor">→ Humidor</button> <button class="btn sm ghost" data-wd="${i}" title="Tirar da lista">✕</button></td></tr>`;
    }).join("");
    const t = (k, label) => `<td><b>${tot[k] ? eur(tot[k]) : "—"}</b>${miss[k] && tot[k] ? `<div class="sub">sem preço em ${miss[k]}</div>` : ""}</td>`;
    $("#wish").innerHTML = `<div style="overflow-x:auto"><table>
      <tr><th></th><th>Referência</th><th>Quantas<br><span class="sub">embalagens</span></th><th>🇪🇸 Espanha<br><span class="sub">€/un. · total</span></th><th>🇫🇷 França<br><span class="sub">€/un. · total</span></th><th>🇵🇹 Portugal<br><span class="sub">preço que viste</span></th><th></th></tr>
      ${rows}
      <tr><td></td><td><b>Total</b> <span class="sub">(${cigars} charutos)</span></td><td></td>${t("es")}${t("fr")}${t("pt")}<td></td></tr></table></div>
      <p class="warn">Preços oficiais de venda ao público por unidade (Espanha: península e Baleares; França: continente). A verde, o país mais barato para cada referência. O preço em Espanha de uma referência guardada da lista francesa (e vice-versa) vem da comparação por nome; tubos e estojos podem não ter par. Portugal não publica a tabela de preços dos charutos, por isso o preço português é o que tu escreveres (por exemplo, o que viste na loja).</p>
      ${alerts ? `<p class="warn">⚠ ${alerts} alerta(s): preço mudou ou referência retirada desde que a juntaste.</p>` : ""}`;
    $("#wish").querySelectorAll("[data-q]").forEach(inp => inp.onchange = () => { const x = lsGet(WKEY, []); x[+inp.dataset.q].qty = Math.max(1, +inp.value || 1); lsSet(WKEY, x); renderWish(); });
    $("#wish").querySelectorAll("[data-pt]").forEach(inp => inp.onchange = () => { const x = lsGet(WKEY, []); x[+inp.dataset.pt].pt = inp.value === "" ? null : +inp.value; lsSet(WKEY, x); renderWish(); });
    $("#wish").querySelectorAll("[data-wd]").forEach(b => b.onclick = () => { const x = lsGet(WKEY, []); x.splice(+b.dataset.wd, 1); lsSet(WKEY, x); renderWish(); });
    $("#wish").querySelectorAll("[data-wh]").forEach(b => b.onclick = () => {
      const w = l[+b.dataset.wh], x = find(w), pack = (x && x.pack_size) || w.pack_size || 1;
      goTab("humidor"); $("#hOther").value = w.label; $("#hQty").value = (+w.qty || 1) * pack; $("#hPrice").value = (x && x.unit_eur) || w.price || "";
    });
    renderPlan(tot, miss, cigars, l.length);
  });
}

function renderPlan(tot, miss, cigars, items) {
  const p = plan(), [hn, hla, hlo] = homeXY();
  const towns = (BORDER.towns || []).filter(t => t.estancos.length).map(t => ({ ...t, d: km(hla, hlo, t.lat, t.lng) })).sort((a, b) => a.d - b.d);
  const near = towns.find(t => t.estancos.length >= 5) || towns[0];   // cidade com escolha razoável
  const road = near ? Math.round(near.d * ROAD_FACTOR) : null;
  const trip = road != null ? 2 * road * (+p.eurKm || 0) + (+p.tolls || 0) : null;
  const allowance = EU_GUIDE * Math.max(1, +p.people || 1);
  const over = cigars > allowance;
  let verdict = "";
  if (tot.es && tot.pt && !miss.pt && !miss.es) {
    const save = tot.pt - tot.es - (trip || 0);
    verdict = save > 0
      ? `<p>✅ Comprar em Espanha poupa cerca de <b>${eur(save)}</b> face aos preços portugueses que indicaste, já descontando a viagem.</p>`
      : `<p>➖ Com a viagem incluída, Espanha não compensa para esta lista (diferença de ${eur(save)}).</p>`;
  } else if (tot.es) {
    verdict = `<p class="muted">Escreve o preço português de cada referência para ver se a viagem compensa.</p>`;
  }
  $("#planBox").innerHTML = `<h3 style="margin-top:0">Plano de compra</h3>
    <div class="filters">
      <label class="sub">Partida<select id="plHome">${PT_CITIES.map(c => `<option${c[0] === hn ? " selected" : ""}>${c[0]}</option>`).join("")}</select></label>
      <label class="sub">Custo por km (combustível) €<input id="plKm" type="number" min="0" step="0.01" value="${p.eurKm}"></label>
      <label class="sub">Portagens (ida e volta) €<input id="plToll" type="number" min="0" step="1" value="${p.tolls}"></label>
      <label class="sub">Pessoas adultas na viagem<input id="plPeople" type="number" min="1" max="9" value="${p.people}"></label>
    </div>
    <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(170px,1fr))">
      <div class="panel" style="margin:0"><div class="sub">Lista (${items} referência${items > 1 ? "s" : ""})</div><b style="font-size:1.3rem">${cigars} charutos</b>
        <div class="sub" style="color:${over ? "var(--warn)" : "var(--ok)"}">${over ? `acima de ${allowance} (nível indicativo UE)` : `dentro dos ${allowance} (nível indicativo UE)`}</div></div>
      <div class="panel" style="margin:0"><div class="sub">🇪🇸 Em Espanha</div><b style="font-size:1.3rem">${tot.es ? eur(tot.es) : "—"}</b>${miss.es ? `<div class="sub">${miss.es} sem preço espanhol</div>` : ""}</div>
      <div class="panel" style="margin:0"><div class="sub">Viagem a ${near ? esc(near.name) : "—"} (ida e volta)</div><b style="font-size:1.3rem">${trip != null ? eur(trip) : "—"}</b>${road ? `<div class="sub">≈ ${2 * road} km de estrada (estimativa)</div>` : ""}</div>
      <div class="panel" style="margin:0"><div class="sub">🇵🇹 Em Portugal (os teus preços)</div><b style="font-size:1.3rem">${tot.pt ? eur(tot.pt) : "—"}</b>${miss.pt && tot.pt ? `<div class="sub">${miss.pt} sem preço</div>` : ""}</div>
    </div>
    ${verdict}
    ${over ? `<p class="warn">⚠ Acima de ${allowance} charutos por pessoa, a alfândega pode pedir prova de que a compra é para uso pessoal. Não é um limite rígido, é um indicador.</p>` : ""}
    <details style="margin-top:8px"><summary><b>Regras: o que é permitido</b></summary>
      <ul class="sub">
        <li><b>Comprar online noutro país e receber em Portugal não é permitido</b> a particulares (Lei n.º 37/2007, art. 14.º-A: proibida a venda à distância transfronteiriça de tabaco a consumidores em Portugal).</li>
        <li><b>Comprar pessoalmente em Espanha (ou noutro país da UE)</b> e trazer contigo é legal: os impostos ficam pagos lá e não pagas mais nada à entrada, desde que seja para uso pessoal e o transportes tu.</li>
        <li>Para saber se é uso pessoal, a lei olha para a quantidade. O nível indicativo é de <b>200 charutos</b> (ou 400 cigarrilhas, ou 1 kg de tabaco) por pessoa. Fonte: Portal das Finanças, Guia para Viajantes.</li>
        <li>Vindo de fora da UE (ex.: Andorra, Cuba, aeroportos fora da UE) a franquia é bem menor: <b>50 charutos</b> por pessoa.</li>
        <li>Em Espanha o preço é fixo em todos os estancos (tabela oficial). Nos bares e hotéis há um preço "con recargo", mais alto.</li>
      </ul>
      <p class="warn">Resumo informativo, não é aconselhamento jurídico. As distâncias e o custo da viagem são estimativas (linha reta × ${ROAD_FACTOR}).</p></details>`;
  const save = () => { setPlan({ home: $("#plHome").value, eurKm: +$("#plKm").value || 0, tolls: +$("#plToll").value || 0, people: Math.max(1, +$("#plPeople").value || 1) }); renderWish(); };
  ["#plHome", "#plKm", "#plToll", "#plPeople"].forEach(i => $(i).onchange = save);
  renderWhere(cigars, towns);
}

function renderWhere(cigars, towns) {
  const box = $("#whereBox");
  const go = () => {
    const [hn, hla, hlo] = homeXY();
    towns = towns || (BORDER.towns || []).filter(t => t.estancos.length).map(t => ({ ...t, d: km(hla, hlo, t.lat, t.lng) })).sort((a, b) => a.d - b.d);
    const spec = (SHOPS_ALL || []).filter(s => s.kind === "cigar" || SPECIALIST.test(s.name || ""))
      .map(s => ({ ...s, d: km(hla, hlo, s.lat, s.lng) })).sort((a, b) => a.d - b.d).slice(0, 12);
    box.innerHTML = `<h3 style="margin-top:0">Onde comprar</h3>
      <h4>🇪🇸 Estancos junto à fronteira <span class="sub">(mais perto de ${esc(hn)} primeiro)</span></h4>
      <p class="sub">Lista oficial de estancos em funcionamento (${esc(BORDER.as_of || "")}). A lista não diz quais têm humidor nem que charutos têm em stock: os estancos maiores das cidades costumam ter mais escolha. Liga antes se procuras uma referência específica.</p>
      ${towns.map((t, i) => `<details${i === 0 ? " open" : ""} style="margin:6px 0"><summary><b>${esc(t.name)}</b> <span class="sub">(${esc(t.province)})</span> · ${t.estancos.length} estanco${t.estancos.length > 1 ? "s" : ""} · ≈ ${Math.round(t.d * ROAD_FACTOR)} km · passagem: ${esc(t.crossing)}</summary>
        <ul class="sub">${t.estancos.map(e => `<li>${esc(e.address)}${e.locality && fold(e.locality) !== fold(t.name) ? ` (${esc(e.locality)})` : ""} · <a href="${mapsLink(`Estanco ${e.address}, ${e.locality || t.name}, España`)}" target="_blank" rel="noopener">mapa</a></li>`).join("")}</ul></details>`).join("") || "<p class='muted'>Lista de estancos indisponível.</p>"}
      <p class="warn">${esc(BORDER.source || "Origem dos dados: Ministerio de Hacienda")}${BORDER.url ? ` · <a href="${BORDER.url}" target="_blank" rel="noopener">fonte</a>` : ""}. Coordenadas das cidades aproximadas.</p>
      <h4>🇵🇹 Lojas especializadas em Portugal <span class="sub">(mais perto de ${esc(hn)})</span></h4>
      ${spec.length ? `<ul class="sub">${spec.map(s => `<li><b>${esc(s.name)}</b>${s.city ? `, ${esc(s.city)}` : ""} · ≈ ${Math.round(s.d)} km em linha reta · <a href="${s.osm}" target="_blank" rel="noopener">OpenStreetMap</a> · <a href="${mapsLink(`${s.name} ${s.city || ""}`)}" target="_blank" rel="noopener">mapa</a>${s.website ? ` · <a href="${esc(s.website)}" target="_blank" rel="noopener">site</a>` : ""}</li>`).join("")}</ul>` : "<p class='muted'>Sem lojas especializadas identificadas.</p>"}
      <p class="sub">Todas as tabacarias (não só as especializadas) estão em <a href="#shops">Lojas em Portugal</a>.</p>
      <h4>🇫🇷 França</h4><p class="sub">Os preços franceses servem para comparar. Em quase todas as referências, a França é bem mais cara do que a Espanha.</p>`;
  };
  if (BORDER && SHOPS_ALL) go(); else loadPlanData().then(go);
}

/* ---------- arranque ---------- */
(function bootCompra() {
  const start = () => {
    if (!document.getElementById("subtabs")) return setTimeout(start, 100);
    setupRouting();
    ["#catalog .filters", "#frcat .filters", "#brands .filters", "#shops .filters"].forEach(sel => addClear(document.querySelector(sel)));
    updateWishBadge();
    document.querySelector('[data-tab="wishlist"]').addEventListener("click", renderWish);
    document.querySelector('[data-tab="frces"]').addEventListener("click", () => {
      if (COMPARE) { if (!$("#cTable")) renderCompareFrEs(); } else fetch("data/compare.json").then(r => r.json()).then(c => { COMPARE = c; renderCompareFrEs(); }).catch(() => { $("#cmpFrEs").textContent = "Comparação indisponível."; });
    });
    document.querySelector('[data-tab="pricehist"]').addEventListener("click", () => { if (PRICES) renderPriceHist(); });
  };
  start();
})();
