/* Front-end. No build step, no dependencies. */
window.APP = (() => {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const NS = 'http://www.w3.org/2000/svg';
  const svgEl = (tag, attrs = {}, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
  const COLORS = { S1: '#2F6B3A', S2: '#8A9A2E', S3: '#C98C2D', N: '#B4412A' };
  const TERM_COLORS = ['#B4412A', '#C98C2D', '#2F6B3A', '#3F7D9E', '#8E4B9E'];

  /* ---------- theme ---------- */
  const themeBtn = $('#themeBtn');
  if (themeBtn) themeBtn.addEventListener('click', () => {
    const cur = document.documentElement.dataset.theme || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    const next = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem('soil-theme', next); } catch (e) { }
  });

  /* ---------- scroll reveal (one observer, staggered siblings) ---------- */
  const io = new IntersectionObserver((entries) => {
    entries.forEach((en) => {
      if (!en.isIntersecting) return;
      const el = en.target; const sibs = $$('.reveal', el.parentElement); const i = Math.max(0, sibs.indexOf(el));
      el.style.transitionDelay = reduce ? '0s' : `${Math.min(i, 6) * 70}ms`;
      el.classList.add('in'); io.unobserve(el);
      if (el.classList.contains('stats')) countUp(el);
    });
  }, { threshold: 0.15 });
  $$('.reveal').forEach((el) => io.observe(el));

  function countUp(root) {
    $$('[data-count]', root).forEach((b) => {
      const end = +b.dataset.count; const t0 = performance.now(); const dur = reduce ? 1 : 1100;
      const tick = (t) => { const p = Math.min(1, (t - t0) / dur); const e = 1 - Math.pow(1 - p, 3); b.textContent = Math.round(end * e); if (p < 1) requestAnimationFrame(tick); };
      requestAnimationFrame(tick);
    });
  }

  /* ---------- hero ---------- */
  function splitWords(h) {
    if (!h || reduce) return;
    let i = 0;
    [...h.childNodes].forEach((n) => {
      if (n.nodeType !== 3) { n.classList.add('reveal-word'); n.style.animationDelay = `${0.08 + i++ * 0.07}s`; return; }
      const frag = document.createDocumentFragment();
      n.textContent.split(/(\s+)/).forEach((w) => {
        if (!w.trim()) { frag.appendChild(document.createTextNode(w)); return; }
        const s = document.createElement('span'); s.className = 'reveal-word'; s.textContent = w; s.style.animationDelay = `${0.08 + i++ * 0.07}s`; frag.appendChild(s);
      });
      h.replaceChild(frag, n);
    });
  }
  function swapWords(el, words) {
    if (!el || reduce) return; let i = 0;
    setInterval(() => {
      i = (i + 1) % words.length;
      el.style.transition = 'opacity .25s, transform .25s'; el.style.opacity = 0; el.style.transform = 'translateY(.2em)';
      setTimeout(() => { el.textContent = words[i]; el.style.opacity = 1; el.style.transform = 'none'; }, 260);
    }, 2600);
  }

  /* ---------- dial ---------- */
  function setDial(arc, needle, scoreEl, score, len) {
    const s = Math.max(0, Math.min(100, score));
    arc.style.strokeDashoffset = len * (1 - s / 100);
    needle.style.transform = `rotate(${-90 + 180 * s / 100}deg)`;
    if (scoreEl) animateNumber(scoreEl, s);
  }
  function animateNumber(el, to) {
    const from = parseFloat(el.textContent) || 0; const t0 = performance.now(); const dur = reduce ? 1 : 900;
    const tick = (t) => { const p = Math.min(1, (t - t0) / dur); const e = 1 - Math.pow(1 - p, 3); el.textContent = (from + (to - from) * e).toFixed(1); if (p < 1) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  }

  /* ---------- analyse page ---------- */
  function analyse(cfg) {
    const form = $('#plotForm'); if (!form) return;
    const numeric = Object.keys(cfg.factors).filter((f) => f !== 'texture');
    const stateSel = $('#state'); const zoneLabel = $('#zoneLabel'); const note = $('#presetNote');
    const crop = () => form.querySelector('input[name=crop]:checked').value;
    let timer = null; let ctrl = null;

    // sliders <-> numbers
    numeric.forEach((f) => {
      const num = $(`#in-${f}`); const rng = form.querySelector(`input[type=range][data-for=${f}]`);
      rng.addEventListener('input', () => { num.value = rng.value; schedule(); });
      num.addEventListener('input', () => { rng.value = num.value; schedule(); });
    });
    form.querySelectorAll('input[name=texture], input[name=crop]').forEach((i) => i.addEventListener('change', () => { if (i.name === 'crop') $('#clsCrop').textContent = cfg.crops[i.value].name; schedule(); }));
    // rough-level selects: set the slider to a typical value for that term, for the chosen crop
    $$('select.rough', form).forEach((sel) => sel.addEventListener('change', () => {
      const f = sel.dataset.rough; if (!sel.value) return;
      const v = cfg.rep[crop()][f][sel.value]; $(`#in-${f}`).value = v; form.querySelector(`input[type=range][data-for=${f}]`).value = v; sel.value = ''; schedule();
    }));

    function applyPreset(preset, zoneKey) {
      numeric.forEach((f) => { const v = preset[f]; $(`#in-${f}`).value = v; form.querySelector(`input[type=range][data-for=${f}]`).value = v; });
      const t = form.querySelector(`input[name=texture][value=${preset.texture}]`); if (t) t.checked = true;
      if (zoneKey) { const z = cfg.zones[zoneKey]; zoneLabel.innerHTML = `<span class="badge" style="--bc:${z.palette}">${z.name}</span>`; note.textContent = `Pre-filled with a typical ${z.name} soil. ${z.notes} Adjust anything you have measured.`; note.classList.add('show'); }
      schedule();
    }
    stateSel.addEventListener('change', () => { const zk = cfg.states[stateSel.value]; if (zk) applyPreset(cfg.zones[zk].preset, zk); else { zoneLabel.textContent = 'Choose a state to see its zone'; note.classList.remove('show'); } });

    // initial values
    if (!cfg.hasValues) {
      const zk = cfg.initialZone || cfg.states[stateSel.value];
      if (zk && cfg.zones[zk]) { applyPreset(cfg.zones[zk].preset, zk); if (!stateSel.value) { const first = Object.keys(cfg.states).find((s) => cfg.states[s] === zk); if (first) stateSel.value = first; } }
      else applyPreset(cfg.defaults, null);
    } else {
      numeric.forEach((f) => { form.querySelector(`input[type=range][data-for=${f}]`).value = $(`#in-${f}`).value; });
      schedule();
    }

    // live preview
    function schedule() { clearTimeout(timer); timer = setTimeout(preview, 180); }
    async function preview() {
      const body = { crop: crop(), log: false };
      numeric.forEach((f) => body[f] = $(`#in-${f}`).value);
      const tx = form.querySelector('input[name=texture]:checked'); body.texture = tx ? tx.value : null;
      if (ctrl) ctrl.abort(); ctrl = new AbortController();
      try {
        const res = await fetch('/api/preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: ctrl.signal });
        const data = await res.json();
        if (data.errors) { renderPills(null); showWaiting(data.errors); return; }
        render(data);
      } catch (e) { if (e.name !== 'AbortError') console.error(e); }
    }
    function showWaiting(errors) {
      const b = $('#clsBadge'); b.dataset.c = ''; b.textContent = errors && errors.texture ? 'choose a texture to continue' : 'check the highlighted values';
      $('#clsLabel').innerHTML = '&nbsp;'; $('#dialScore').textContent = '--';
      $('#limList').innerHTML = `<li class="muted">${errors && errors.texture ? 'Squeeze a handful and pick the closest texture.' : 'Fill in the soil values to see.'}</li>`;
    }
    function renderPills(m) {
      const r = cfg.ratings[crop()];
      const tx = form.querySelector('input[name=texture]:checked'); const tp = $('#texPill');
      if (tx && m) { tp.dataset.r = r.texture[tx.value]; tp.style.setProperty('--mu', '100%'); tp.classList.add('on'); tp.firstElementChild.textContent = `${cfg.factors.texture.class_labels[tx.value]} is rated ${r.texture[tx.value]} for ${cfg.crops[crop()].name.toLowerCase()}`; }
      Object.keys(cfg.factors).filter((f) => f !== 'texture').forEach((f) => {
        $$(`[data-pills=${f}] .pill`).forEach((p) => {
          const t = p.dataset.term; const mu = m ? (m[f][t] || 0) : 0;
          p.dataset.r = r[f][t]; p.style.setProperty('--mu', `${Math.round(mu * 100)}%`); p.classList.toggle('on', mu > 0.05);
        });
      });
    }
    function render(d) {
      renderPills(d.memberships);
      setDial($('#dialArc'), $('#needle'), $('#dialScore'), d.score, 251.3);
      const b = $('#clsBadge'); b.dataset.c = d.class; b.textContent = `FAO class ${d.class}`;
      $('#clsLabel').textContent = d.class_label;
      const ul = $('#limList'); ul.innerHTML = '';
      if (!d.limiting.length) ul.innerHTML = '<li><span>Nothing. Every factor is in range.</span></li>';
      d.limiting.forEach((l) => { const li = document.createElement('li'); li.innerHTML = `<span>${l.label} is ${l.term_label}</span><em>${l.rating}</em>`; ul.appendChild(li); });
    }
  }

  /* ---------- result page ---------- */
  function result(r, factors, order) {
    const arc = $('#bigArc'); if (arc) requestAnimationFrame(() => setDial(arc, $('#bigNeedle'), $('#bigScore'), r.score, 408.4));
    const copy = $('#copyLink'); if (copy) copy.addEventListener('click', async () => { try { await navigator.clipboard.writeText(copy.dataset.url); copy.textContent = 'Link copied'; setTimeout(() => copy.textContent = 'Copy link', 1800); } catch (e) { } });
    radar($('#radar'), r, factors, order);
    outputCurve($('#outCurve'), r);
  }
  function radar(svg, r, factors, order) {
    if (!svg) return; const cx = 180, cy = 170, R = 105, n = order.length;
    const ang = (i) => -Math.PI / 2 + i * 2 * Math.PI / n;
    const pt = (i, v) => [cx + Math.cos(ang(i)) * R * v, cy + Math.sin(ang(i)) * R * v];
    [0.25, 0.5, 0.75, 1].forEach((k) => svgEl('polygon', { points: order.map((_, i) => pt(i, k).join(',')).join(' '), fill: k === 1 ? 'none' : 'none', stroke: 'var(--line)', 'stroke-width': 1 }, svg));
    order.forEach((f, i) => { const [x, y] = pt(i, 1); svgEl('line', { x1: cx, y1: cy, x2: x, y2: y, stroke: 'var(--line)' }, svg);
      const [lx, ly] = pt(i, 1.28); const t = svgEl('text', { x: lx, y: ly, 'text-anchor': 'middle', 'dominant-baseline': 'middle', 'font-size': 10.5, fill: 'var(--fg-2)', 'font-family': 'Manrope, sans-serif' }, svg); t.textContent = factors[f].label.replace('Exchangeable ', '').replace('Available ', '').replace('Total ', '').replace(' (ECe)', ''); });
    const vals = order.map((f) => r.factor_scores[f] / 100);
    const poly = svgEl('polygon', { points: order.map((_, i) => pt(i, vals[i]).join(',')).join(' '), fill: COLORS[r.class], 'fill-opacity': .22, stroke: COLORS[r.class], 'stroke-width': 2.2, 'stroke-linejoin': 'round' }, svg);
    if (!reduce) { poly.style.transformOrigin = '180px 170px'; poly.style.transform = 'scale(.2)'; poly.style.opacity = 0; poly.style.transition = 'transform 1s cubic-bezier(.16,1,.3,1), opacity .6s'; requestAnimationFrame(() => requestAnimationFrame(() => { poly.style.transform = 'scale(1)'; poly.style.opacity = 1; })); }
    order.forEach((f, i) => { const [x, y] = pt(i, vals[i]); svgEl('circle', { cx: x, cy: y, r: 4, fill: 'var(--card)', stroke: COLORS[r.class], 'stroke-width': 2 }, svg); });
  }
  function outputCurve(svg, r) {
    if (!svg) return; const W = 320, H = 120, px = 10, py = 10; const xs = r.output_curve.x, ys = r.output_curve.y;
    const X = (v) => px + (v / 100) * (W - 2 * px), Y = (v) => H - py - v * (H - 2 * py - 14);
    [[0, 'N'], [25, 'S3'], [50, 'S2'], [75, 'S1']].forEach(([lo, c]) => { svgEl('rect', { x: X(lo), y: py, width: X(25) - X(0), height: H - 2 * py - 14, fill: COLORS[c], 'fill-opacity': .07 }, svg); const t = svgEl('text', { x: X(lo) + 4, y: H - 2, 'font-size': 9, fill: 'var(--fg-3)', 'font-family': 'IBM Plex Mono, monospace' }, svg); t.textContent = c; });
    const d = xs.map((x, i) => `${i ? 'L' : 'M'}${X(x).toFixed(1)},${Y(ys[i]).toFixed(1)}`).join(' ');
    svgEl('path', { d: d + ` L${X(100)},${Y(0)} L${X(0)},${Y(0)} Z`, fill: COLORS[r.class], 'fill-opacity': .25 }, svg);
    svgEl('path', { d, fill: 'none', stroke: COLORS[r.class], 'stroke-width': 2 }, svg);
    svgEl('line', { x1: X(r.mamdani_centroid), x2: X(r.mamdani_centroid), y1: py, y2: Y(0), stroke: 'var(--fg)', 'stroke-dasharray': '3 3' }, svg);
    const t = svgEl('text', { x: X(r.mamdani_centroid) + 4, y: py + 9, 'font-size': 9, fill: 'var(--fg-2)', 'font-family': 'IBM Plex Mono, monospace' }, svg); t.textContent = `centroid ${r.mamdani_centroid}`;
  }

  /* ---------- membership explorer (method page) ---------- */
  function mfExplorer(factors, crops) {
    const svg = $('#mfSvg'); if (!svg) return;
    const cropSel = $('#mfCrop'), facSel = $('#mfFactor'), val = $('#mfVal'), out = $('#mfValOut'), legend = $('#mfLegend');
    let data = null;
    async function load() {
      const f = facSel.value; const F = factors[f];
      val.min = F.universe[0]; val.max = F.universe[1]; val.step = F.step; if (val.value === '' || +val.value < F.universe[0] || +val.value > F.universe[1]) val.value = (F.universe[0] + F.universe[1]) / 2;
      data = await (await fetch(`/api/mf/${cropSel.value}/${f}`)).json(); draw();
    }
    function draw() {
      if (!data) return; const f = facSel.value; const F = factors[f]; svg.innerHTML = ''; legend.innerHTML = '';
      const W = 640, H = 260, L = 40, Rr = 16, T = 16, B = 40; const [lo, hi] = F.universe;
      const X = (v) => L + (v - lo) / (hi - lo) * (W - L - Rr), Y = (m) => T + (1 - m) * (H - T - B);
      [0, .5, 1].forEach((m) => { svgEl('line', { x1: L, x2: W - Rr, y1: Y(m), y2: Y(m), stroke: 'var(--line)' }, svg); const t = svgEl('text', { x: L - 6, y: Y(m) + 3, 'text-anchor': 'end', 'font-size': 10, fill: 'var(--fg-3)', 'font-family': 'IBM Plex Mono, monospace' }, svg); t.textContent = m; });
      for (let k = 0; k <= 5; k++) { const v = lo + (hi - lo) * k / 5; const t = svgEl('text', { x: X(v), y: H - B + 16, 'text-anchor': 'middle', 'font-size': 10, fill: 'var(--fg-3)', 'font-family': 'IBM Plex Mono, monospace' }, svg); t.textContent = +v.toFixed(2); }
      const u = svgEl('text', { x: W - Rr, y: H - 6, 'text-anchor': 'end', 'font-size': 11, fill: 'var(--fg-2)', 'font-family': 'Manrope, sans-serif' }, svg); u.textContent = `${F.label} (${F.unit})`;
      const terms = Object.keys(data.terms); const v = +val.value; out.textContent = `${v} ${F.unit}`;
      terms.forEach((t, i) => {
        const ys = data.terms[t]; const col = TERM_COLORS[i % TERM_COLORS.length];
        const d = data.x.map((x, j) => `${j ? 'L' : 'M'}${X(x).toFixed(1)},${Y(ys[j]).toFixed(1)}`).join(' ');
        svgEl('path', { d: d + ` L${X(hi)},${Y(0)} L${X(lo)},${Y(0)} Z`, fill: col, 'fill-opacity': .08 }, svg);
        svgEl('path', { d, fill: 'none', stroke: col, 'stroke-width': 2.2, 'stroke-linejoin': 'round' }, svg);
        // membership at probe
        let j = data.x.findIndex((x) => x >= v); if (j < 0) j = data.x.length - 1; if (j === 0) j = 0;
        const mu = j > 0 ? ys[j - 1] + (ys[j] - ys[j - 1]) * ((v - data.x[j - 1]) / (data.x[j] - data.x[j - 1] || 1)) : ys[0];
        if (mu > 0.01) svgEl('circle', { cx: X(v), cy: Y(mu), r: 5, fill: col, stroke: 'var(--card)', 'stroke-width': 2 }, svg);
        const li = document.createElement('span'); li.innerHTML = `<i style="background:${col}"></i>${F.term_labels[t]} <span class="mono">${mu.toFixed(2)}</span>`; legend.appendChild(li);
      });
      svgEl('line', { x1: X(v), x2: X(v), y1: T, y2: Y(0), stroke: 'var(--fg)', 'stroke-dasharray': '4 4' }, svg);
    }
    cropSel.addEventListener('change', load); facSel.addEventListener('change', load); val.addEventListener('input', draw);
    load();
  }

  return { splitWords, swapWords, analyse, result, mfExplorer };
})();
