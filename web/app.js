(() => {
  "use strict";

  // ---------- constants ----------
  const VERDICTS = {
    "Buy the Dip": { key: "buy", label: "Buy the Dip", icon: "★" },
    "Wait": { key: "wait", label: "Wait", icon: "☾" },
    "Avoid (Falling Knife)": { key: "avoid", label: "Falling Knife", icon: "✕" },
    "Not a Dip": { key: "none", label: "Not a dip yet", icon: "·" },
  };
  const ORDER = ["buy", "wait", "avoid", "none"];
  const SUMMARY_TEXT = { buy: "Buy the Dip", wait: "Wait", avoid: "Falling Knife", none: "Not a dip yet" };
  const PROFILES = ["conservative", "balanced", "aggressive"];
  const state = { data: null, profile: "balanced", verdicts: new Set(), sector: "all", query: "", sort: "drawdown" };

  // ---------- helpers ----------
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pct = (x, d = 0, sign = false) => (x == null ? "n/a" : `${sign && x > 0 ? "+" : ""}${(x * 100).toFixed(d)}%`);
  const money = (x) => (x == null ? "n/a" : `$${x.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);
  const verdictOf = (s) => VERDICTS[s.verdicts[state.profile].verdict] || VERDICTS["Not a Dip"];

  function sparkline(values, w, h, opts = {}) {
    if (!values || values.length < 2) return "";
    const min = Math.min(...values), max = Math.max(...values), pad = opts.pad ?? 3;
    const x = (i) => pad + (i / (values.length - 1)) * (w - 2 * pad);
    const y = (v) => pad + (1 - (v - min) / (max - min || 1)) * (h - 2 * pad);
    const pts = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
    const down = values[values.length - 1] < values[0];
    const color = down ? "#ff7a9c" : "#6ee7b7";
    const area = `${pad},${h - pad} ${pts} ${w - pad},${h - pad}`;
    return `<svg class="${opts.cls || "spark"}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">
      <polygon points="${area}" fill="${color}" opacity="0.12"/>
      <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="${opts.stroke || 1.6}" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>
    </svg>`;
  }

  // ---------- Big Dipper constellation (seven gold $ stars) ----------
  function drawDipper() {
    const stars = [
      ["Alkaid", 28, 52], ["Mizar", 84, 68], ["Alioth", 138, 78], ["Megrez", 188, 98],
      ["Phecda", 194, 156], ["Merak", 274, 168], ["Dubhe", 292, 108],
    ];
    const path = [0, 1, 2, 3, 6, 5, 4, 3].map((i) => stars[i].slice(1).join(",")).join(" ");
    const svg = $("dipper");
    svg.innerHTML =
      `<polyline class="link" points="${path}"/>` +
      stars.map(([n, x, y], i) =>
        `<g><text class="star twinkle" x="${x}" y="${y + 8}" style="animation-delay:${(i * 0.45).toFixed(2)}s">$</text>` +
        `<text class="name" x="${x}" y="${y + 26}">${n}</text></g>`).join("");
  }

  // ---------- falling $ star field ----------
  function starfield() {
    const canvas = $("stars"), ctx = canvas.getContext("2d");
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let stars = [], w = 0, h = 0, dpr = 1, raf = 0;
    const colors = ["255,236,190", "255,209,102", "200,210,255", "255,255,255", "190,170,255"];

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = window.innerWidth; h = window.innerHeight;
      canvas.width = w * dpr; canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const n = Math.round(Math.min(110, Math.max(36, (w * h) / 14000)));
      stars = Array.from({ length: n }, () => ({
        x: Math.random() * w, y: Math.random() * h,
        size: 8 + Math.random() * 16, base: 0.12 + Math.random() * 0.5,
        speed: 0.6 + Math.random() * 1.6, phase: Math.random() * 6.28,
        drift: 0.004 + Math.random() * 0.012, color: colors[(Math.random() * colors.length) | 0],
      }));
      draw(0);
    }
    function draw(t) {
      ctx.clearRect(0, 0, w, h);
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      for (const s of stars) {
        const a = reduce ? s.base : s.base * (0.55 + 0.45 * Math.sin(t / 1000 * s.speed + s.phase));
        ctx.font = `${s.size}px Georgia, serif`;
        ctx.fillStyle = `rgba(${s.color},${a.toFixed(3)})`;
        ctx.fillText("$", s.x, s.y);
        if (!reduce) { s.y -= s.drift * 16; if (s.y < -20) { s.y = h + 20; s.x = Math.random() * w; } }
      }
    }
    function loop(t) { draw(t); raf = requestAnimationFrame(loop); }
    window.addEventListener("resize", resize);
    document.addEventListener("visibilitychange", () => {
      if (reduce) return;
      cancelAnimationFrame(raf);
      if (!document.hidden) raf = requestAnimationFrame(loop);
    });
    resize();
    if (!reduce) raf = requestAnimationFrame(loop);
  }

  // ---------- filtering ----------
  function visibleStocks() {
    const q = state.query.trim().toLowerCase();
    const list = state.data.stocks.filter((s) => {
      if (state.verdicts.size && !state.verdicts.has(verdictOf(s).key)) return false;
      if (state.sector !== "all" && s.sector !== state.sector) return false;
      if (q && !(s.ticker.toLowerCase().includes(q) || (s.name || "").toLowerCase().includes(q))) return false;
      return true;
    });
    const k = state.sort;
    list.sort((a, b) => k === "ticker" ? a.ticker.localeCompare(b.ticker)
      : k === "drawdown" || k === "day_change" ? (a[k] ?? 0) - (b[k] ?? 0)
      : (b[k] ?? 0) - (a[k] ?? 0));
    return list;
  }

  // ---------- rendering ----------
  function renderSummary() {
    const counts = { buy: 0, wait: 0, avoid: 0, none: 0 };
    state.data.stocks.forEach((s) => counts[verdictOf(s).key]++);
    $("summary").innerHTML = ORDER.map((k) =>
      `<button class="stat ${k}" data-v="${k}" aria-pressed="${state.verdicts.has(k)}"><span class="n">${counts[k]}</span><span class="t">${SUMMARY_TEXT[k]}</span></button>`).join("");
  }

  function renderChips() {
    $("verdict-chips").innerHTML = ORDER.map((k) =>
      `<button class="chip" data-v="${k}" aria-pressed="${state.verdicts.has(k)}">${esc(VERDICTS[Object.keys(VERDICTS).find((n) => VERDICTS[n].key === k)].icon)} ${SUMMARY_TEXT[k]}</button>`).join("");
  }

  function renderList() {
    const rows = visibleStocks();
    $("count").textContent = `Showing ${rows.length} of ${state.data.stocks.length} stocks` +
      (state.data.total_dippers > state.data.dip_count ? ` (the ${state.data.dip_count} furthest from their highs, out of ${state.data.total_dippers} down 10%+)` : "");
    $("empty").hidden = rows.length > 0;
    $("list").innerHTML = rows.map((s) => {
      const v = verdictOf(s);
      return `<li><button class="row" data-t="${esc(s.ticker)}" aria-label="${esc(s.ticker)} ${esc(s.name)}: ${v.label}. Open details.">
        <div class="who"><b>${esc(s.ticker)}</b><span>${esc(s.name)} · ${esc(s.sector)}</span></div>
        <div><span class="mobile-label">From 52-week high</span><span class="num-cell neg">${pct(s.drawdown, 0)}</span></div>
        <div><span class="mobile-label">Today</span><span class="num-cell ${s.day_change < 0 ? "neg" : "pos"}">${pct(s.day_change, 1, true)}</span></div>
        <div class="score"><span class="mobile-label">Business</span><b>${Math.round(s.fund_score)}</b><div class="bar"><i style="width:${s.fund_score}%"></i></div></div>
        <div class="score"><span class="mobile-label">Price setup</span><b>${Math.round(s.tech_score)}</b><div class="bar"><i style="width:${s.tech_score}%"></i></div></div>
        <div class="spark-cell">${sparkline(s.sparkline, 120, 34)}</div>
        <div><span class="badge ${v.key}">${v.icon} ${v.label}</span></div>
      </button></li>`;
    }).join("");
  }

  function renderAll() { renderSummary(); renderChips(); renderList(); }

  function compRows(comps, cls) {
    return comps.map((c) => `<div class="comp ${c.missing ? "missing" : ""}">
      <div class="nm">${esc(c.name)}<small>${esc(c.value)}. ${esc(c.note)}</small></div>
      <div class="bar big ${cls}"><i style="width:${(c.points / c.max_points) * 100}%"></i></div>
      <div class="pts">${c.points.toFixed(1)} / ${c.max_points}</div></div>`).join("");
  }

  function openDetail(ticker) {
    const s = state.data.stocks.find((x) => x.ticker === ticker);
    if (!s) return;
    const pv = s.verdicts[state.profile], v = verdictOf(s), prof = state.data.profiles[state.profile];
    const fund = s.components.filter((c) => c.group === "fundamental");
    const tech = s.components.filter((c) => c.group === "technical");
    $("d-body").innerHTML = `
      <div class="d-top">
        <div><h2 id="d-title">${esc(s.ticker)}</h2><p>${esc(s.name)} · ${esc(s.sector)}</p></div>
        <button class="close" id="d-close" aria-label="Close details">✕</button>
      </div>
      <div class="d-verdict"><span class="badge ${v.key}">${v.icon} ${v.label}</span>
        <span style="color:var(--muted)">for a <b style="color:var(--text)">${esc(state.profile)}</b> investor · combined score ${Math.round(s.composite)}/100</span></div>
      <p class="why">${esc(pv.explanation)}</p>
      <div class="facts">
        <div class="fact"><span>Price</span><b>${money(s.price)}</b></div>
        <div class="fact"><span>52-week high</span><b>${money(s.high_52w)}</b></div>
        <div class="fact"><span>From high</span><b class="neg">${pct(s.drawdown, 1)}</b></div>
        <div class="fact"><span>RSI (14)</span><b>${s.rsi == null ? "n/a" : s.rsi.toFixed(0)}</b></div>
        ${pv.position_size > 0 ? `<div class="fact"><span>Suggested position</span><b>${pct(pv.position_size, 1)}</b></div>
        <div class="fact"><span>Stop-loss</span><b>${money(pv.stop_price)}</b></div>` : `<div class="fact"><span>Suggested position</span><b>0%</b></div>`}
      </div>
      <div class="d-h">Price, last 6 months <small>${money(s.sparkline[0])} to ${money(s.sparkline[s.sparkline.length - 1])}</small></div>
      ${sparkline(s.sparkline, 700, 120, { cls: "d-spark", pad: 8, stroke: 2 })}
      <div class="d-h">Business quality <small>${Math.round(s.fund_score)} / 100</small></div>
      ${compRows(fund, "")}
      <div class="d-h">Price setup <small>${Math.round(s.tech_score)} / 100</small></div>
      ${compRows(tech, "tech")}
      <div class="d-h">What each investor type would see</div>
      <div class="profiles">${PROFILES.map((p) => {
        const x = s.verdicts[p], vv = VERDICTS[x.verdict] || VERDICTS["Not a Dip"];
        return `<div class="fact"><span>${p}</span><b><span class="badge ${vv.key}">${vv.icon} ${vv.label}</span></b>
          <small>${x.position_size > 0 ? `${pct(x.position_size, 1)} position, stop ${money(x.stop_price)}` : "No position"}</small></div>`;
      }).join("")}</div>
      <p class="fine" style="margin-top:16px">Risk profile "${esc(state.profile)}": about ${pct(prof.risk_budget, 1)} of the portfolio at risk per trade, ${pct(prof.stop_loss, 0)} stop-loss, ${pct(prof.max_position, 0)} maximum position, minimum business score ${prof.min_fundamental_score}. ${s.missing_fundamentals ? `${s.missing_fundamentals} fundamental metric(s) were unavailable and got neutral marks.` : ""} Educational only, not investment advice.</p>`;
    const dlg = $("detail");
    if (!dlg.open) dlg.showModal();
    $("d-close").addEventListener("click", () => dlg.close());
    dlg.scrollTop = 0;
  }

  // ---------- wiring ----------
  function toggleVerdict(k) { state.verdicts.has(k) ? state.verdicts.delete(k) : state.verdicts.add(k); renderAll(); }

  function wire() {
    $("profile-seg").innerHTML = PROFILES.map((p) => `<button role="radio" aria-checked="${p === state.profile}" data-p="${p}">${p}</button>`).join("");
    $("profile-seg").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-p]"); if (!b) return;
      state.profile = b.dataset.p;
      $("profile-seg").querySelectorAll("button").forEach((x) => x.setAttribute("aria-checked", String(x === b)));
      renderAll();
    });
    $("verdict-chips").addEventListener("click", (e) => { const b = e.target.closest("[data-v]"); if (b) toggleVerdict(b.dataset.v); });
    $("summary").addEventListener("click", (e) => { const b = e.target.closest("[data-v]"); if (b) toggleVerdict(b.dataset.v); });
    $("search").addEventListener("input", (e) => { state.query = e.target.value; renderList(); });
    $("sector").addEventListener("change", (e) => { state.sector = e.target.value; renderList(); });
    $("sort").addEventListener("change", (e) => { state.sort = e.target.value; renderList(); });
    $("list").addEventListener("click", (e) => { const b = e.target.closest("[data-t]"); if (b) openDetail(b.dataset.t); });
    $("detail").addEventListener("click", (e) => { if (e.target === $("detail")) $("detail").close(); });
  }

  async function init() {
    drawDipper();
    starfield();
    try {
      const res = await fetch("data/dippers.json", { cache: "no-cache" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      state.data = await res.json();
    } catch (err) {
      $("asof").textContent = "Couldn't load today's data. Please refresh in a minute.";
      console.error(err);
      return;
    }
    const sectors = [...new Set(state.data.stocks.map((s) => s.sector))].sort();
    $("sector").innerHTML = `<option value="all">All sectors</option>` + sectors.map((s) => `<option>${esc(s)}</option>`).join("");
    const asOf = state.data.as_of ? new Date(state.data.as_of + "T12:00:00").toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" }) : "unknown date";
    $("asof").textContent = `Prices as of ${asOf}. ${state.data.total_dippers ?? state.data.dip_count} of ${state.data.universe_size} S&P 500 stocks are 10%+ below their 52-week high.`;
    wire();
    renderAll();
  }

  init();
})();
