/* ══════════════════════════════════════════════════════════════════
   런웨이 공용 로직 — 로컬판(dashboard.html)과 배포판(public/index.html)이
   함께 씁니다. build.py 가 두 템플릿의 코어 자리표시자 주석을
   이 파일 내용으로 치환합니다.

   D 는 initRunway() 로 주입합니다.
     - 로컬판: 빌드 시점에 data.json 이 인라인됨
     - 배포판: 로그인 후 Firestore 에서 받아옴 (잔액 + 스케줄만)
   ══════════════════════════════════════════════════════════════════ */

/* ── 포맷 ─────────────────────────────────────────────────────────── */
const nf = n => Math.round(n).toLocaleString('ko-KR');
const won = n => nf(n) + '원';
function compact(n){
  const a = Math.abs(n), s = n < 0 ? '-' : '';
  if(a >= 1e8) return s + (a/1e8).toFixed(a >= 1e9 ? 0 : 1).replace(/\.0$/,'') + '억';
  if(a >= 1e4) return s + nf(a/1e4) + '만';
  return s + nf(a);
}
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const md = d => d.slice(5).replace('-','/');
const monLabel = m => (+m.slice(5)) + '월';
const monFull = m => m.slice(0,4) + '년 ' + (+m.slice(5)) + '월';
const WD = ['일','월','화','수','목','금','토'];
const iso = dt => dt.toISOString().slice(0,10);
const parse = s => new Date(s + 'T00:00:00Z');
const kdate = s => { const d = parse(s); return `${d.getUTCMonth()+1}월 ${d.getUTCDate()}일`; };
const lastDay = (y,m) => new Date(Date.UTC(y, m+1, 0)).getUTCDate();

/* ── 상태 ─────────────────────────────────────────────────────────── */
let D = null, ACCTS = [], BAL = {};
const ACOLOR = ['var(--acct1)','var(--acct2)','var(--acct3)'];
const R = { scn:'out', hz:60, start:null, edited:false, onBalanceChange:null };

/* 시나리오: 어떤 수입을 예측에 넣을지 */
const CONTRACT = new Set(['임대수입','정부지원금','이자수입']);
const SCN = {
  out:   { t:'출금만', desc:'수입을 하나도 넣지 않은 가장 보수적인 계산' },
  fixed: { t:'계약 수입 포함', desc:'임대료·아동수당처럼 계약으로 정해진 수입만 반영' },
  all:   { t:'배우자 이체까지', desc:'배우자 이체를 가장 최근 달(7월) 수준으로 가정' },
};

function initRunway(data){
  D = data;
  ACCTS = Object.keys(D.start.balances);
  BAL = Object.assign({}, D.start.balances);
  R.start = D.start.date;
  R.edited = false;
}

function activeItems(){
  return D.schedule.filter(r => {
    if(r.flow === '지출') return true;
    if(R.scn === 'out') return false;
    if(CONTRACT.has(r.category)) return true;
    return R.scn === 'all';          /* 배우자 이체는 'all' 에서만 */
  }).map(r => ({ ...r,
    /* 변동이 큰 항목은 평균 대신 가장 최근 달 값을 쓴다 */
    use: r.volatile ? r.last : r.amount }));
}

/* ── 런웨이 계산 ──────────────────────────────────────────────────── */
function project(){
  const items = activeItems();
  const startBal = ACCTS.reduce((s,a) => s + (+BAL[a] || 0), 0);
  const start = parse(R.start);
  const days = [];
  let bal = startBal, zero = null;

  for(let i = 0; i < R.hz; i++){
    const dt = new Date(start.getTime() + i*86400000);
    const y = dt.getUTCFullYear(), mo = dt.getUTCMonth(), dd = dt.getUTCDate();
    const ld = lastDay(y, mo);
    /* 결제일이 그 달에 없으면(31일 등) 말일로 당긴다 */
    const hits = items.filter(r => Math.min(r.day, ld) === dd);
    const out = hits.filter(h => h.flow === '지출').reduce((s,h) => s + h.use, 0);
    const inn = hits.filter(h => h.flow === '수입').reduce((s,h) => s + h.use, 0);
    const open = bal;
    bal = bal + inn - out;
    if(zero === null && bal < 0) zero = { date: iso(dt), short: -bal, idx: i };
    days.push({ date: iso(dt), wd: WD[dt.getUTCDay()], items: hits, out, inn, open, close: bal });
  }
  const perMonthOut = items.filter(r => r.flow === '지출').reduce((s,r) => s + r.use, 0);
  const perMonthIn  = items.filter(r => r.flow === '수입').reduce((s,r) => s + r.use, 0);
  return { days, startBal, zero, endBal: bal, perMonthOut, perMonthIn };
}

/* ── SVG · UI 헬퍼 ────────────────────────────────────────────────── */
const svg = (w,h,inner) =>
  `<svg viewBox="0 0 ${w} ${h}" role="img" preserveAspectRatio="xMidYMid meet">${inner}</svg>`;
function niceMax(v){
  if(v <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  for(const m of [1,1.2,1.5,2,2.5,3,4,5,6,8,10]) if(v <= m*p) return m*p;
  return 10*p;
}
/* 막대: 데이터 끝만 4px 라운드, 베이스라인 쪽은 직각 */
function vBar(x,y,w,h,up){
  const r = Math.min(4, w/2, h);
  return up
    ? `M${x},${y+h} L${x},${y+r} Q${x},${y} ${x+r},${y} L${x+w-r},${y} Q${x+w},${y} ${x+w},${y+r} L${x+w},${y+h} Z`
    : `M${x},${y} L${x},${y+h-r} Q${x},${y+h} ${x+r},${y+h} L${x+w-r},${y+h} Q${x+w},${y+h} ${x+w},${y+h-r} L${x+w},${y} Z`;
}
function hBar(x,y,w,h){
  const r = Math.min(4, h/2, w);
  return `M${x},${y} L${x+w-r},${y} Q${x+w},${y} ${x+w},${y+r} L${x+w},${y+h-r} Q${x+w},${y+h} ${x+w-r},${y+h} L${x},${y+h} Z`;
}
function attachTip(host){
  const tip = document.createElement('div');
  tip.className = 'tip'; host.appendChild(tip);
  return {
    show(html, ev){
      tip.innerHTML = html; tip.classList.add('on');
      const hb = host.getBoundingClientRect(), tb = tip.getBoundingClientRect();
      let x = ev.clientX - hb.left + 14, y = ev.clientY - hb.top - tb.height - 12;
      if(x + tb.width > hb.width) x = ev.clientX - hb.left - tb.width - 14;
      if(y < 0) y = ev.clientY - hb.top + 18;
      tip.style.left = Math.max(0,x) + 'px'; tip.style.top = y + 'px';
    },
    hide(){ tip.classList.remove('on'); }
  };
}
const tipRow = (color,label,val) =>
  `<div class="r"><span>${color ? `<i style="width:9px;height:9px;border-radius:3px;background:${color};display:inline-block"></i>` : ''}${esc(label)}</span><b>${won(val)}</b></div>`;
function table(cols, rows, rowCls){
  return `<table><thead><tr>${cols.map(c => `<th${c.n?' class="n"':''}>${esc(c.t)}</th>`).join('')}</tr></thead><tbody>${
    rows.map((r,i) => `<tr class="${rowCls?rowCls(i):''}">${r.map((v,j) =>
      `<td${cols[j].n?' class="n"':''}>${v}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}

/* ── 런웨이 화면 ──────────────────────────────────────────────────── */
function drawRunway(){
  const P = project();
  const A = document.getElementById('alert');

  if(P.zero){
    A.className = 'alert';
    A.innerHTML = `<div class="ic">▲</div>
      <h2>${kdate(P.zero.date)}에 잔고가 바닥납니다</h2>
      <div class="dday">D-${P.zero.idx} · ${won(P.zero.short)} 부족</div>
      <p class="cap">${esc(R.start)}부터 ${esc(SCN[R.scn].desc)} 기준입니다.
         그날 예정된 출금을 다 내려면 ${won(P.zero.short)}이 모자랍니다.</p>`;
  } else {
    A.className = 'alert safe';
    A.innerHTML = `<div class="ic">●</div>
      <h2>${R.hz}일 안에는 잔고가 바닥나지 않습니다</h2>
      <div class="dday">예측 종료일 잔액 ${won(P.endBal)}</div>
      <p class="cap">${esc(SCN[R.scn].desc)} 기준입니다.</p>`;
  }

  document.getElementById('notice-txt').innerHTML = R.edited
    ? `<b>직접 입력한 잔액으로 계산 중입니다.</b>
       ${esc(R.start)} 시점의 실제 잔액이 맞는지 확인하세요 — 숫자를 고치면 소진일이 즉시 다시 계산됩니다.`
    : `<b>잔액이 ${esc(D.start.as_of)} 기준입니다.</b>
       이후 들어온 돈은 화면에 잡히지 않습니다 — 잔고를 정산해야 소진일이 다시 계산됩니다.`;
  document.getElementById('bal-badge').textContent = R.edited ? '직접 입력' : '데이터 기준';
  document.getElementById('bal-total').textContent = won(P.startBal);
  document.getElementById('bal-list').innerHTML = ACCTS.map((a,i) => `
    <div class="acctrow">
      <span class="dot" style="background:${ACOLOR[i % ACOLOR.length]}"></span>
      <span class="nm">${esc(a)}</span>
      <input type="text" inputmode="numeric" data-acct="${esc(a)}" value="${nf(BAL[a])}"
             aria-label="${esc(a)} 잔액">
    </div>`).join('');
  document.getElementById('bal-list').querySelectorAll('input').forEach(el => {
    el.addEventListener('change', () => {
      const v = +el.value.replace(/[^0-9-]/g,'') || 0;
      BAL[el.dataset.acct] = v; el.value = nf(v);
      R.edited = true;
      drawRunway();
      if(R.onBalanceChange) R.onBalanceChange(BAL);   /* 배포판: Firestore 저장 */
    });
  });

  document.getElementById('end-bal').innerHTML =
    `<span class="${P.endBal<0?'neg':'pos'}">${won(P.endBal)}</span>`;
  document.getElementById('end-cap').textContent =
    `${R.start} + ${R.hz}일 (${P.days[P.days.length-1].date}) 시점`;
  document.getElementById('m-out').textContent = won(P.perMonthOut);
  document.getElementById('m-in').textContent  = won(P.perMonthIn);
  const net = P.perMonthIn - P.perMonthOut;
  document.getElementById('m-net').innerHTML =
    `<span class="${net<0?'neg':'pos'}">${net>=0?'+':''}${won(net)}</span>`;
  document.getElementById('flow-desc').textContent =
    `${SCN[R.scn].t} · ${R.hz}일 예측 · 결제일마다 잔액이 계단처럼 떨어집니다`;

  drawRunwayChart(P);
  drawSchedTable(P);
}

/* 잔고 흐름 — 단일 계열 계단 라인 */
function drawRunwayChart(P){
  const host = document.getElementById('p-run');
  const W = 940, H = 320, L = 76, Rr = 58, T = 22, B = 42;
  const pw = W-L-Rr, ph = H-T-B;
  const vals = P.days.map(d => d.close).concat([P.startBal, 0]);
  const hi = niceMax(Math.max(...vals, 1));
  const loRaw = Math.min(...vals, 0);
  const lo = loRaw < 0 ? -niceMax(-loRaw) : 0;
  const Y = v => T + ph - (v-lo)/(hi-lo)*ph;
  const X = i => L + pw*i/Math.max(1,P.days.length-1);

  let g = '';
  for(let i=0;i<=4;i++){
    const v = lo + (hi-lo)*i/4, y = Y(v);
    g += `<line x1="${L}" y1="${y}" x2="${L+pw}" y2="${y}" stroke="var(--grid)" stroke-width="1"/>`;
    g += `<text x="${L-10}" y="${y+4}" text-anchor="end" font-size="11" fill="var(--muted)"
           style="font-variant-numeric:tabular-nums">${compact(v)}</text>`;
  }
  const yz = Y(0);
  g += `<line x1="${L}" y1="${yz}" x2="${L+pw}" y2="${yz}" stroke="var(--axis)" stroke-width="1"/>`;
  g += `<text x="${L+pw+8}" y="${yz+4}" font-size="11" fill="var(--muted)">0원</text>`;

  let d = `M${X(0)},${Y(P.startBal)}`;
  P.days.forEach((p,i) => { d += ` L${X(i)},${Y(p.open)} L${X(i)},${Y(p.close)}`; });
  g += `<path d="${d}" fill="none" stroke="var(--in)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`;

  if(P.zero){
    const zx = X(P.zero.idx);
    g += `<line x1="${zx}" y1="${T}" x2="${zx}" y2="${T+ph}" stroke="var(--crit)" stroke-width="2"/>`;
    g += `<circle cx="${zx}" cy="${Y(P.days[P.zero.idx].close)}" r="5" fill="var(--crit)"
           stroke="var(--surface)" stroke-width="2"/>`;
    const anchor = zx > L+pw*0.66 ? 'end' : 'start', dx = anchor === 'end' ? -9 : 9;
    g += `<text x="${zx+dx}" y="${T-6}" text-anchor="${anchor}" font-size="11.5" font-weight="650"
           fill="var(--crit)">소진일 ${kdate(P.zero.date)}</text>`;
  }
  const step = Math.max(1, Math.ceil(P.days.length/7));
  P.days.forEach((p,i) => { if(i % step === 0 || i === P.days.length-1)
    g += `<text x="${X(i)}" y="${H-18}" text-anchor="middle" font-size="11" fill="var(--muted)">${md(p.date)}</text>`; });
  g += `<line class="cross hide" x1="0" y1="${T}" x2="0" y2="${T+ph}" stroke="var(--ink-2)" stroke-width="1"/>`;
  g += `<rect x="${L}" y="${T}" width="${pw}" height="${ph}" fill="transparent" class="hitrun"/>`;
  host.innerHTML = svg(W,H,g);

  const tip = attachTip(host), cross = host.querySelector('.cross'), hit = host.querySelector('.hitrun');
  hit.addEventListener('mousemove', ev => {
    const b = host.getBoundingClientRect();
    const px = (ev.clientX - b.left)/b.width*W;
    let i = Math.round((px-L)/pw*(P.days.length-1));
    i = Math.max(0, Math.min(P.days.length-1, i));
    const p = P.days[i];
    cross.classList.remove('hide');
    cross.setAttribute('x1', X(i)); cross.setAttribute('x2', X(i));
    tip.show(`<div class="t">${p.date} (${p.wd})</div>`
      + (p.items.length ? p.items.map(h =>
          tipRow(h.flow==='지출'?'var(--out)':'var(--in)', h.name, h.use)).join('') + '<hr>'
        : `<div class="r"><span>예정된 거래 없음</span></div><hr>`)
      + `<div class="r"><span>잔액</span><b class="${p.close<0?'neg':''}">${won(p.close)}</b></div>`, ev);
  });
  hit.addEventListener('mouseleave', () => { tip.hide(); cross.classList.add('hide'); });

  document.getElementById('t-run').innerHTML = table(
    [{t:'날짜'},{t:'요일'},{t:'입금',n:1},{t:'출금',n:1},{t:'잔액',n:1}],
    P.days.map(p => [p.date, p.wd, p.inn?nf(p.inn):'—', p.out?nf(p.out):'—',
      `<span class="${p.close<0?'neg':''}">${nf(p.close)}</span>`]),
    i => P.days[i].close < 0 ? 'gone' : '');
}

/* 일별 출금 예정 표 */
function drawSchedTable(P){
  const rows = [], cls = [];
  P.days.forEach(p => {
    if(!p.items.length) return;
    p.items.forEach((h,k) => {
      const isZero = P.zero && p.date === P.zero.date;
      rows.push([
        k === 0 ? `${p.date} <span style="color:var(--muted)">(${p.wd})</span>` : '',
        esc(h.name) + (h.volatile ? ' <span class="tag v">변동</span>' : ''),
        `<span style="color:${h.flow==='지출'?'var(--out)':'var(--in)'};font-weight:600">${h.flow==='지출'?'−':'+'}${nf(h.use)}</span>`,
        `<span class="tag">${esc(h.category)}</span>`
          + (isZero && k === 0 ? ' <span class="tag c">소진일</span>' : ''),
        k === 0 ? nf(p.out) : '',
        k === 0 ? `<span class="${p.close<0?'neg':''}">${nf(p.close)}</span>` : '',
      ]);
      cls.push((p.close < 0 ? 'gone ' : '') + (k === 0 ? 'daystart' : ''));
    });
  });
  document.getElementById('t-sched').innerHTML = table(
    [{t:'날짜'},{t:'항목'},{t:'금액',n:1},{t:'구분'},{t:'당일 출금',n:1},{t:'잔액',n:1}],
    rows, i => cls[i]);
  document.getElementById('sched-scope').textContent =
    `${R.start} ~ ${P.days[P.days.length-1].date} · ${SCN[R.scn].t}`;
}

/* 예측에 쓴 반복 항목 */
function drawItems(){
  const items = D.schedule;
  const o = items.filter(r => r.flow === '지출').reduce((s,r) => s + r.amount, 0);
  const c = items.filter(r => r.flow === '수입' && CONTRACT.has(r.category)).reduce((s,r) => s + r.amount, 0);
  document.getElementById('sched-sum').innerHTML =
    `<p style="font-size:13.5px;color:var(--ink-2)">매달 반복되는 지출 <b style="color:var(--ink)">${won(o)}</b>,
     계약으로 정해진 수입 <b style="color:var(--ink)">${won(c)}</b>.
     매달 <b class="neg">${won(o-c)}</b>씩 모자랍니다.
     그동안은 배우자 이체와 신규 대출로 메워 왔습니다.</p>`;
  document.getElementById('t-items').innerHTML = table(
    [{t:'결제일'},{t:'항목'},{t:'구분'},{t:'분류'},{t:'예측 금액',n:1},{t:'3개월 범위',n:1},{t:'관측'}],
    items.map(r => [
      `매월 ${r.day}일`,
      esc(r.name) + (r.volatile ? ' <span class="tag v">변동</span>' : ''),
      `<span class="tag ${r.flow==='수입'?'i':'o'}">${r.flow}</span>`,
      `<span class="tag">${esc(r.category)}</span>`,
      `<b>${nf(r.volatile ? r.last : r.amount)}</b>`,
      `${compact(r.lo)} ~ ${compact(r.hi)}`,
      `${r.n_months}/3개월`]));
  const irrEl = document.getElementById('irr-note');
  if(!irrEl) return;
  const irr = (D.irregular || []).filter(r => r.total >= 100000);
  irrEl.innerHTML = !irr.length ? '' :
    `<b>예측에서 뺀 일회성 거래 ${irr.length}건 (${won(irr.reduce((s,r)=>s+r.total,0))}).</b>
     한 달에만 나타나 반복 여부를 알 수 없는 항목입니다 —
     ${irr.slice(0,6).map(r => `${esc(r.name)} ${compact(r.total)}`).join(' · ')} 등.
     세금·수리비처럼 언제든 다시 나올 수 있어, 실제 소진일은 위 예측보다 빨라질 수 있습니다.`;
}

/* ── 공용 컨트롤 ──────────────────────────────────────────────────── */
function seg(el, opts, get, set){
  const paint = () => el.querySelectorAll('button').forEach(b =>
    b.setAttribute('aria-pressed', String(b.dataset.v === String(get()))));
  el.innerHTML = opts.map(o => `<button type="button" data-v="${esc(o.v)}">${esc(o.t)}</button>`).join('');
  paint();
  el.addEventListener('click', e => {
    const b = e.target.closest('button'); if(!b) return;
    set(b.dataset.v); paint();
  });
}
function bindRunwayControls(){
  const startEl = document.getElementById('f-start');
  startEl.value = R.start;
  startEl.addEventListener('change', () => {
    if(startEl.value){ R.start = startEl.value; drawRunway(); }
    else startEl.value = R.start;
  });
  seg(document.getElementById('f-scn'),
    Object.entries(SCN).map(([v,o]) => ({v, t:o.t})), () => R.scn, v => { R.scn = v; drawRunway(); });
  seg(document.getElementById('f-hz'),
    [{v:'30',t:'30일'},{v:'60',t:'60일'},{v:'90',t:'90일'},{v:'180',t:'180일'}],
    () => R.hz, v => { R.hz = +v; drawRunway(); });
  document.getElementById('btn-settle').addEventListener('click', () => {
    const el = document.querySelector('#bal-list input');
    el.scrollIntoView({ behavior:'smooth', block:'center' }); el.focus(); el.select();
  });
}
function bindTableToggles(){
  document.querySelectorAll('[data-toggle]').forEach(b => {
    b.addEventListener('click', () => {
      const k = b.dataset.toggle;
      const plot = document.getElementById('p-'+k), tab = document.getElementById('t-'+k);
      const showTable = tab.classList.contains('hide');
      tab.classList.toggle('hide', !showTable);
      plot.classList.toggle('hide', showTable);
      const lg = plot.parentElement.querySelector('.legend');
      if(lg) lg.classList.toggle('hide', showTable);
      b.textContent = showTable ? '차트 보기' : '표 보기';
    });
  });
}
