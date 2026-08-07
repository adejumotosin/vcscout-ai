from __future__ import annotations

DASHBOARD_HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="description" content="VCScout AI — alternative-data venture sourcing from public engineering momentum." />
  <title>VCScout AI — Venture Signal Intelligence</title>
  <style>
    :root {
      --bg:#07100d; --panel:#0d1713; --panel2:#111e19; --line:#203329;
      --text:#eff7f2; --muted:#8da198; --accent:#72f0a6; --accent2:#b8ffd2;
      --warn:#ffc86a; --danger:#ff8585; --shadow:0 18px 60px rgba(0,0,0,.28);
    }
    *{box-sizing:border-box}
    html{scroll-behavior:smooth}
    body{margin:0;background:radial-gradient(circle at 80% 0%,rgba(114,240,166,.09),transparent 27%),var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    a{color:inherit;text-decoration:none}
    button,input,select{font:inherit}
    .shell{max-width:1460px;margin:0 auto;padding:24px}
    .nav{display:flex;align-items:center;justify-content:space-between;padding:8px 0 26px}
    .brand{display:flex;align-items:center;gap:12px;font-weight:780;letter-spacing:-.02em}
    .mark{width:34px;height:34px;border:1px solid rgba(114,240,166,.45);border-radius:10px;display:grid;place-items:center;background:rgba(114,240,166,.07);box-shadow:inset 0 0 24px rgba(114,240,166,.05)}
    .mark:before{content:"";width:10px;height:10px;border:2px solid var(--accent);transform:rotate(45deg)}
    .navlinks{display:flex;gap:10px;align-items:center}
    .pill,.ghost{border:1px solid var(--line);background:rgba(255,255,255,.025);color:var(--muted);border-radius:999px;padding:8px 12px;font-size:12px}
    .pill.live{color:var(--accent2);border-color:rgba(114,240,166,.26);background:rgba(114,240,166,.06)}
    .live-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--accent);margin-right:7px;box-shadow:0 0 12px var(--accent)}
    .hero{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(300px,.55fr);gap:24px;align-items:end;padding:36px 0 30px}
    .eyebrow{color:var(--accent);font-size:12px;font-weight:800;letter-spacing:.16em;text-transform:uppercase;margin-bottom:16px}
    h1{font-size:clamp(42px,6vw,78px);line-height:.96;letter-spacing:-.055em;margin:0;max-width:930px}
    h1 span{color:var(--accent)}
    .lede{max-width:790px;color:#a8bbb2;font-size:16px;line-height:1.7;margin:22px 0 0}
    .hero-note{border-left:1px solid var(--line);padding-left:22px;color:var(--muted);font-size:13px;line-height:1.65}
    .hero-note strong{display:block;color:var(--text);font-size:14px;margin-bottom:6px}
    .metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:18px 0 24px}
    .card{background:linear-gradient(180deg,rgba(255,255,255,.025),rgba(255,255,255,.012));border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow)}
    .metric{padding:18px 20px;min-height:112px}
    .metric-label{color:var(--muted);font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}
    .metric-value{font-size:31px;letter-spacing:-.045em;font-weight:780;margin-top:14px}
    .metric-sub{font-size:11px;color:#71857b;margin-top:4px}
    .toolbar{padding:14px;display:grid;grid-template-columns:1.5fr repeat(3,1fr) .85fr;gap:10px;margin-bottom:16px}
    .field{background:#09130f;border:1px solid var(--line);border-radius:11px;padding:11px 12px;color:var(--text);outline:none;width:100%}
    .field:focus{border-color:rgba(114,240,166,.55);box-shadow:0 0 0 3px rgba(114,240,166,.07)}
    select.field{color:#c8d7d0}
    .button{cursor:pointer;background:var(--accent);color:#06100b;border:0;border-radius:11px;padding:11px 14px;font-weight:800}
    .button:hover{filter:brightness(1.05)}
    .grid{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(330px,.55fr);gap:16px}
    .section{padding:18px}
    .section-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:15px}
    .section-title{font-size:15px;font-weight:760;letter-spacing:-.015em}
    .section-meta{font-size:11px;color:var(--muted)}
    .table-wrap{overflow:auto;border:1px solid rgba(255,255,255,.035);border-radius:12px}
    table{width:100%;border-collapse:collapse;min-width:980px}
    th{position:sticky;top:0;background:#0b1511;color:#72877d;text-transform:uppercase;letter-spacing:.065em;font-size:9px;text-align:left;padding:11px 12px;border-bottom:1px solid var(--line)}
    td{padding:12px;border-bottom:1px solid rgba(32,51,41,.65);font-size:12px;color:#c5d3cc;vertical-align:middle}
    tr{cursor:pointer;transition:.15s ease}
    tbody tr:hover{background:rgba(114,240,166,.035)}
    tbody tr.selected{background:rgba(114,240,166,.065)}
    .rank{color:#61746b;width:38px}
    .company{font-weight:720;color:#f3faf6;max-width:210px}
    .company small{display:block;color:#71847b;font-weight:500;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:220px}
    .score{font-variant-numeric:tabular-nums;font-weight:820;color:var(--accent2)}
    .score-track{width:70px;height:4px;background:#1a2a22;border-radius:10px;margin-top:5px;overflow:hidden}
    .score-fill{height:100%;background:linear-gradient(90deg,#40bd77,var(--accent));border-radius:10px}
    .tag{display:inline-flex;align-items:center;border:1px solid var(--line);border-radius:999px;padding:4px 7px;color:#a8bbb2;font-size:10px;white-space:nowrap}
    .tag.breakout{color:var(--accent2);border-color:rgba(114,240,166,.23);background:rgba(114,240,166,.06)}
    .delta.up{color:var(--accent)} .delta.down{color:var(--danger)}
    .detail{position:sticky;top:20px;min-height:545px}
    .detail-top{padding-bottom:16px;border-bottom:1px solid var(--line)}
    .detail-kicker{color:var(--muted);font-size:10px;letter-spacing:.1em;text-transform:uppercase}
    .detail h2{font-size:29px;letter-spacing:-.04em;margin:8px 0 6px}
    .detail-desc{color:#91a59b;font-size:12px;line-height:1.6;min-height:38px}
    .big-score{display:flex;align-items:end;justify-content:space-between;margin:18px 0 6px}
    .big-score strong{font-size:46px;line-height:1;letter-spacing:-.055em;color:var(--accent2)}
    .big-score span{color:var(--muted);font-size:11px;margin-bottom:5px}
    .detail-metrics{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:16px}
    .mini{padding:12px;border:1px solid rgba(32,51,41,.8);border-radius:12px;background:rgba(255,255,255,.012)}
    .mini span{display:block;color:#71857b;font-size:9px;text-transform:uppercase;letter-spacing:.07em;margin-bottom:5px}
    .mini strong{font-size:15px}
    .signal{padding:14px;margin-top:12px;border-radius:12px;background:rgba(114,240,166,.045);border:1px solid rgba(114,240,166,.14);font-size:11px;color:#a9c3b7;line-height:1.55}
    .signal b{color:#e7f8ef}
    .links{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}
    .linkbtn{border:1px solid var(--line);border-radius:9px;padding:8px 10px;color:#b6c7bf;font-size:10px}
    .linkbtn:hover{border-color:#456456;color:white}
    .analytics{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}
    .bars{display:flex;flex-direction:column;gap:10px}
    .bar-row{display:grid;grid-template-columns:130px 1fr 40px;align-items:center;gap:10px;font-size:11px}
    .bar-name{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#aabcb3}
    .bar-track{height:6px;border-radius:999px;background:#18271f;overflow:hidden}
    .bar-fill{height:100%;border-radius:999px;background:linear-gradient(90deg,#2f8155,var(--accent))}
    .bar-value{text-align:right;color:#dce8e2;font-variant-numeric:tabular-nums}
    .scatter{position:relative;height:260px;border-left:1px solid #294136;border-bottom:1px solid #294136;margin:10px 10px 24px 36px;background:linear-gradient(to right,transparent 49.8%,rgba(80,110,94,.16) 50%,transparent 50.2%),linear-gradient(to top,transparent 49.8%,rgba(80,110,94,.16) 50%,transparent 50.2%)}
    .dot{position:absolute;width:8px;height:8px;border-radius:50%;background:var(--accent);border:1px solid #caffe0;transform:translate(-50%,50%);opacity:.75;box-shadow:0 0 10px rgba(114,240,166,.18)}
    .dot:hover{opacity:1;z-index:3;transform:translate(-50%,50%) scale(1.5)}
    .axis{position:absolute;color:#61746a;font-size:9px}.axis.x{bottom:-21px;left:50%;transform:translateX(-50%)}.axis.y{left:-34px;top:50%;transform:rotate(-90deg) translateY(-50%);transform-origin:center}
    .empty,.loading,.error{padding:54px 20px;text-align:center;color:var(--muted);font-size:13px}
    .error{color:#ffaaa3}
    footer{display:flex;justify-content:space-between;gap:20px;padding:28px 2px 12px;color:#62756c;font-size:10px;line-height:1.5}
    @media(max-width:1000px){.hero,.grid{grid-template-columns:1fr}.hero-note{border-left:0;padding-left:0}.metrics{grid-template-columns:1fr 1fr}.toolbar{grid-template-columns:1fr 1fr}.detail{position:static}.analytics{grid-template-columns:1fr}}
    @media(max-width:620px){.shell{padding:16px}.navlinks .ghost{display:none}.metrics{grid-template-columns:1fr 1fr}.metric{padding:14px;min-height:94px}.metric-value{font-size:25px}.toolbar{grid-template-columns:1fr}.analytics{grid-template-columns:1fr}h1{font-size:44px}.hero{padding-top:20px}}
  </style>
</head>
<body>
<div class="shell">
  <nav class="nav">
    <div class="brand"><div class="mark"></div><span>VCScout AI</span></div>
    <div class="navlinks"><span class="pill live"><i class="live-dot"></i>LIVE SIGNAL FEED</span><a class="ghost" href="/docs" target="_blank">API Docs ↗</a></div>
  </nav>

  <section class="hero">
    <div>
      <div class="eyebrow">Alternative-data venture intelligence</div>
      <h1>Find engineering <span>momentum</span> before it becomes consensus.</h1>
      <p class="lede">VCScout ranks venture-stage organisations using public engineering activity — commit acceleration, contributor growth, repository expansion and team depth — to surface companies worth investigating earlier.</p>
    </div>
    <div class="hero-note"><strong>Signal, not investment advice.</strong>The VC Scout Score is an explainable sourcing heuristic. It prioritises diligence; it is not presented as a probability that a company will raise capital.</div>
  </section>

  <section class="metrics">
    <div class="card metric"><div class="metric-label">Tracked organisations</div><div id="tracked" class="metric-value">—</div><div class="metric-sub">live source universe</div></div>
    <div class="card metric"><div class="metric-label">Visible candidates</div><div id="visible" class="metric-value">—</div><div class="metric-sub">after current filters</div></div>
    <div class="card metric"><div class="metric-label">Breakout signals</div><div id="breakouts" class="metric-value">—</div><div class="metric-sub">high-momentum profiles</div></div>
    <div class="card metric"><div class="metric-label">Median scout score</div><div id="median" class="metric-value">—</div><div id="period" class="metric-sub">source period</div></div>
  </section>

  <section class="card toolbar">
    <input id="search" class="field" placeholder="Search startup or organisation…" />
    <select id="sector" class="field"><option value="">All sectors</option></select>
    <select id="stage" class="field"><option value="">All stages</option></select>
    <select id="geo" class="field"><option value="">All geographies</option></select>
    <select id="minScore" class="field"><option value="0">Score ≥ 0</option><option value="40">Score ≥ 40</option><option value="50" selected>Score ≥ 50</option><option value="60">Score ≥ 60</option><option value="70">Score ≥ 70</option><option value="80">Score ≥ 80</option></select>
  </section>

  <section class="grid">
    <div class="card section">
      <div class="section-head"><div><div class="section-title">Deal-flow leaderboard</div><div class="section-meta">Ranked by observable engineering momentum</div></div><button id="refresh" class="button">Refresh</button></div>
      <div class="table-wrap"><table><thead><tr><th>#</th><th>Company</th><th>Scout score</th><th>Momentum</th><th>Stage</th><th>Region</th><th>Commits / 14d</th><th>Commit Δ</th><th>Contributor Δ</th><th>Signal</th></tr></thead><tbody id="rows"><tr><td colspan="10"><div class="loading">Loading live venture signals…</div></td></tr></tbody></table></div>
    </div>
    <aside class="card section detail" id="detail"><div class="loading">Select a startup to open the diligence snapshot.</div></aside>
  </section>

  <section class="analytics">
    <div class="card section"><div class="section-head"><div><div class="section-title">Sector heat</div><div class="section-meta">Average score of visible companies</div></div></div><div class="bars" id="sectorBars"></div></div>
    <div class="card section"><div class="section-head"><div><div class="section-title">Momentum map</div><div class="section-meta">Commit acceleration vs contributor growth</div></div></div><div class="scatter" id="scatter"><span class="axis x">commit velocity change →</span><span class="axis y">contributor growth →</span></div></div>
  </section>

  <footer><div>VCScout AI · Alternative-data venture sourcing</div><div id="updated">Live source · loading metadata</div></footer>
</div>
<script>
  let all = [], filtered = [], selected = null, meta = {};
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const fmt = n => Number.isFinite(Number(n)) ? Math.round(Number(n)).toLocaleString() : '—';
  const pct = n => Number.isFinite(Number(n)) ? `${Number(n)>=0?'+':''}${Math.round(Number(n))}%` : '—';
  const median = arr => { if(!arr.length) return null; const a=[...arr].sort((x,y)=>x-y),m=Math.floor(a.length/2); return a.length%2?a[m]:(a[m-1]+a[m])/2; };
  const uniq = key => [...new Set(all.map(x=>x[key]).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
  function hydrateSelect(id,key,label){ const el=$(id), current=el.value; el.innerHTML=`<option value="">All ${label}</option>`+uniq(key).map(v=>`<option>${esc(v)}</option>`).join(''); el.value=current; }
  function deltaClass(n){ return Number(n)>=0?'up':'down'; }
  function filterData(){
    const q=$('search').value.trim().toLowerCase(), s=$('sector').value, st=$('stage').value, g=$('geo').value, min=Number($('minScore').value||0);
    filtered=all.filter(x=>(!q||`${x.name} ${x.description||''}`.toLowerCase().includes(q))&&(!s||x.sector===s)&&(!st||x.stage===st)&&(!g||x.geography===g)&&Number(x.vc_scout_score)>=min);
    render();
  }
  function render(){
    $('visible').textContent=filtered.length.toLocaleString();
    $('breakouts').textContent=filtered.filter(x=>x.momentum_flag==='Breakout').length.toLocaleString();
    const m=median(filtered.map(x=>Number(x.vc_scout_score)).filter(Number.isFinite)); $('median').textContent=m==null?'—':m.toFixed(1);
    const rows=$('rows');
    if(!filtered.length){ rows.innerHTML='<tr><td colspan="10"><div class="empty">No companies match these filters.</div></td></tr>'; selected=null; renderDetail(); renderAnalytics(); return; }
    if(!selected || !filtered.some(x=>x.name===selected.name)) selected=filtered[0];
    rows.innerHTML=filtered.slice(0,100).map((x,i)=>`<tr data-name="${encodeURIComponent(x.name)}" class="${selected&&x.name===selected.name?'selected':''}"><td class="rank">${i+1}</td><td class="company">${esc(x.name)}<small>${esc(x.sector||'Unclassified')}</small></td><td><div class="score">${Number(x.vc_scout_score).toFixed(1)}</div><div class="score-track"><div class="score-fill" style="width:${Math.max(0,Math.min(100,Number(x.vc_scout_score)))}%"></div></div></td><td><span class="tag ${x.momentum_flag==='Breakout'?'breakout':''}">${esc(x.momentum_flag||'—')}</span></td><td>${esc(x.stage||'—')}</td><td>${esc(x.geography||'—')}</td><td>${fmt(x.commit_velocity_14d)}</td><td class="delta ${deltaClass(x.commit_velocity_change)}">${pct(x.commit_velocity_change)}</td><td class="delta ${deltaClass(x.contributor_growth)}">${pct(x.contributor_growth)}</td><td><span class="tag">${esc(x.signal_type||'—')}</span></td></tr>`).join('');
    rows.querySelectorAll('tr[data-name]').forEach(tr=>tr.onclick=()=>{selected=all.find(x=>x.name===decodeURIComponent(tr.dataset.name));render();});
    renderDetail(); renderAnalytics();
  }
  function renderDetail(){
    const d=$('detail'); if(!selected){d.innerHTML='<div class="empty">No company selected.</div>';return;}
    const x=selected, links=[['GitHub',x.github_url],['Website',x.website_url],['Source profile',x.profile_url]].filter(v=>v[1]);
    d.innerHTML=`<div class="detail-top"><div class="detail-kicker">Diligence snapshot · ${esc(x.sector||'Unclassified')}</div><h2>${esc(x.name)}</h2><div class="detail-desc">${esc(x.description||'No company description supplied by the source feed.')}</div></div><div class="big-score"><strong>${Number(x.vc_scout_score).toFixed(1)}</strong><span>VC SCOUT SCORE / 100</span></div><div class="score-track" style="width:100%;height:6px"><div class="score-fill" style="width:${Number(x.vc_scout_score)}%"></div></div><div class="detail-metrics"><div class="mini"><span>Commits / 14d</span><strong>${fmt(x.commit_velocity_14d)} <i class="delta ${deltaClass(x.commit_velocity_change)}">${pct(x.commit_velocity_change)}</i></strong></div><div class="mini"><span>Contributors</span><strong>${fmt(x.contributors)} <i class="delta ${deltaClass(x.contributor_growth)}">${pct(x.contributor_growth)}</i></strong></div><div class="mini"><span>New repos / 30d</span><strong>${fmt(x.new_repos_30d)}</strong></div><div class="mini"><span>Stage · Region</span><strong>${esc(x.stage||'—')} · ${esc(x.geography||'—')}</strong></div></div><div class="signal"><b>Signal:</b> ${esc(x.signal_type||'—')}<br><b>Top score driver:</b> ${esc(x.top_driver||'—')}<br><b>Momentum:</b> ${esc(x.momentum_flag||'—')}${x.risk_flag&&x.risk_flag!=='None'?`<br><b>Risk flag:</b> ${esc(x.risk_flag)}`:''}</div><div class="links">${links.map(([n,u])=>`<a class="linkbtn" href="${esc(u)}" target="_blank" rel="noopener">${n} ↗</a>`).join('')}</div>`;
  }
  function renderAnalytics(){
    const grouped={}; filtered.forEach(x=>{if(!x.sector)return;(grouped[x.sector]??=[]).push(Number(x.vc_scout_score)||0)});
    const sectors=Object.entries(grouped).map(([name,a])=>({name,avg:a.reduce((p,c)=>p+c,0)/a.length,n:a.length})).sort((a,b)=>b.avg-a.avg).slice(0,10);
    $('sectorBars').innerHTML=sectors.length?sectors.map(x=>`<div class="bar-row"><div class="bar-name" title="${esc(x.name)}">${esc(x.name)}</div><div class="bar-track"><div class="bar-fill" style="width:${x.avg}%"></div></div><div class="bar-value">${x.avg.toFixed(1)}</div></div>`).join(''):'<div class="empty">No sector data.</div>';
    const sc=$('scatter'); sc.querySelectorAll('.dot').forEach(n=>n.remove()); const pts=filtered.slice(0,80); if(!pts.length)return;
    const xs=pts.map(x=>Number(x.commit_velocity_change)||0), ys=pts.map(x=>Number(x.contributor_growth)||0); const q=(a,p)=>{const s=[...a].sort((x,y)=>x-y);return s[Math.floor((s.length-1)*p)]||0}; const xmin=q(xs,.05),xmax=q(xs,.95)||1,ymin=q(ys,.05),ymax=q(ys,.95)||1;
    pts.forEach(x=>{const xv=Math.max(xmin,Math.min(xmax,Number(x.commit_velocity_change)||0)),yv=Math.max(ymin,Math.min(ymax,Number(x.contributor_growth)||0));const left=((xv-xmin)/(xmax-xmin||1))*100,bottom=((yv-ymin)/(ymax-ymin||1))*100;const dot=document.createElement('span');dot.className='dot';dot.style.left=`${left}%`;dot.style.bottom=`${bottom}%`;dot.title=`${x.name} · score ${Number(x.vc_scout_score).toFixed(1)}`;dot.onclick=()=>{selected=x;render();window.scrollTo({top:$('detail').offsetTop-20,behavior:'smooth'})};sc.appendChild(dot);});
  }
  async function load(force=false){
    $('refresh').disabled=true; $('refresh').textContent='Loading…';
    try{
      const suffix=force?'?refresh=true':'';
      const [m,r]=await Promise.all([fetch('/meta'+suffix,{cache:'no-store'}),fetch('/startups?limit=200&min_score=0'+(force?'&refresh=true':''),{cache:'no-store'})]);
      if(!m.ok||!r.ok)throw new Error(`API returned ${m.status}/${r.status}`);
      meta=await m.json(); all=await r.json();
      $('tracked').textContent=Number(meta.total_startups||all.length).toLocaleString(); $('period').textContent=meta.period?`source period · ${meta.period}`:'live source period'; $('updated').textContent=`Source updated · ${meta.last_updated||'live'} · ${all.length} ranked profiles loaded`;
      hydrateSelect('sector','sector','sectors');hydrateSelect('stage','stage','stages');hydrateSelect('geo','geography','geographies');filterData();
    }catch(e){$('rows').innerHTML=`<tr><td colspan="10"><div class="error">Could not load the live signal feed. ${esc(e.message)}</div></td></tr>`;$('detail').innerHTML='<div class="error">The data API is temporarily unavailable.</div>';}
    finally{$('refresh').disabled=false;$('refresh').textContent='Refresh';}
  }
  ['search','sector','stage','geo','minScore'].forEach(id=>$(id).addEventListener(id==='search'?'input':'change',filterData));
  $('refresh').onclick=()=>load(true);
  load();
</script>
</body>
</html>'''
