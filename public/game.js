"use strict";
/* ============ かけざん レベルアップ ============
   5ステージ × 10レベル ＝ レベル50
   1 かぞえて / 2 つくって / 3 とびかぞえ / 4 ならべて / 5 くくで こたえて
   ステージが レベル10（マックス）になると 王冠とスタンプ、つぎのステージが ひらく
   声：VOICEVOX:ずんだもん（audio/z/）                                           */
(() => {
const STAGES = [null,
  { name: "かぞえて",       icon: "🐣", color: "#ff6b5b", v: "st1", how: "tapcount" },
  { name: "つくって",       icon: "🐸", color: "#ffa53b", v: "st2", how: null },
  { name: "とびかぞえ",     icon: "🐰", color: "#47c97a", v: "st3", how: "tobi" },
  { name: "ならべて",       icon: "🐧", color: "#4aa8ff", v: "st4", how: "retsu" },
  { name: "くくで こたえて", icon: "🦖", color: "#a77bff", v: "st5", how: "kuku" },
];
const ITEMS = ["🍡","🍓","🍙","🍩","🍎","🍪","⚽","🚗","🐟","🚀","🍬","🧸","🍕","🐞","🌟","🦕"];
const ROW_ANIMALS = ["🐧","🐥","🐶","🐱","🐸","🐰","🐻","🐼"];
const MAXLV = 10;
const ONES = ["", "いち", "に", "さん", "よん", "ご", "ろく", "なな", "はち", "きゅう"];
const yomi = n => (n >= 20 ? ONES[Math.floor(n / 10)] + "じゅう" : n >= 10 ? "じゅう" : "") + ONES[n % 10];

// 保存
S.g ||= { lv: [0, 1, 0, 0, 0, 0], xp: [0, 0, 0, 0, 0, 0], stamps: [] };
const G = S.g;
const total = () => G.lv.reduce((a, b) => a + b, 0);
const need = L => 3 + Math.floor((L - 1) / 3);               // つぎの レベルまでの せいかい数
const unlockedItems = () => ITEMS.slice(0, Math.min(ITEMS.length, 3 + Math.floor((total() - 1) / 3)));
const roomOpen = () => G.lv[5] > 0 || S.roomOpen;

// 声：ずんだもんの声は 先に ぜんぶ メモリに 読みこんで、タップしたら すぐ 鳴らす
//   （1つずつ ダウンロードすると 待ちが 出るため。読みこみ前は ふつうの再生で 代わりに）
const ZIDS = (() => {
  const ids = ["st1","st2","st3","st4","st5","tapcount","zenbude","noseru","tobi","retsu","kurutto","kuku","kakeru","wa",
    "ok1","ok2","ok3","ok4","ok5","ng","ooi","dekita","lvup","max","stamp","newstage","allmax","start","kukuopen","okaeri"];
  for (let n = 1; n <= 81; n++) ids.push("n" + n);
  for (let n = 1; n <= 9; n++) ids.push("kozu" + n, "sara" + n);
  const prod = new Set();
  for (let a = 1; a <= 9; a++) for (let b = 1; b <= 9; b++) { ids.push(`c${a}x${b}`); prod.add(a * b); }
  prod.forEach(n => ids.push("a" + n));
  return ids;
})();
const ZB = new Map();          // id → { buf, s, e }（前後の 無音を けずった 位置）
let zLoading = null, zSrcs = [], zDuck = null;
function trimInfo(buf){
  const d = buf.getChannelData(0); let pk = 0;
  for (let i = 0; i < d.length; i++) pk = Math.max(pk, Math.abs(d[i]));
  const th = pk * .02; let a = 0, b = d.length - 1;
  while (a < b && Math.abs(d[a]) < th) a++;
  while (b > a && Math.abs(d[b]) < th) b--;
  const sr = buf.sampleRate;
  return { buf, s: Math.max(0, a / sr - .02), e: Math.min(buf.duration, b / sr + .04) };
}
function preloadZ(){
  if (zLoading) return zLoading;
  try { actx ||= new (window.AudioContext || window.webkitAudioContext)(); } catch(e) { return Promise.resolve(); }
  let i = 0;
  const worker = async () => {
    while (i < ZIDS.length) {
      const id = ZIDS[i++];
      try {
        const ab = await (await fetch(`audio/z/${id}.mp3?v=${ZV}`)).arrayBuffer();
        const buf = await new Promise((ok, ng) => actx.decodeAudioData(ab, ok, ng));
        ZB.set(id, trimInfo(buf));
      } catch(e) {}
    }
  };
  zLoading = Promise.all([1,2,3,4,5,6].map(worker));
  return zLoading;
}
function stopZ(){
  zSrcs.forEach(x => { try { x.onended = null; x.stop(); } catch(e) {} }); zSrcs = [];
  if (zDuck !== null) { duck(false, zDuck); zDuck = null; }
}
// いくつかの 声を すきまなく つづけて 鳴らす（前の声は 止める）
function zSeq(ids, gap = .05){
  stopZ();
  if (!actx || !ids.every(i => ZB.has(i))) {
    // まだ 読みこめていない → ふつうの再生で じゅんばんに
    return ids.reduce((pr, i) => pr.then(() => play("z/" + i, i[0] === "n" ? yomi(+i.slice(1)) : i)), Promise.resolve());
  }
  return new Promise(res => {
    const my = zDuck = duck(true);
    let t = actx.currentTime + .02, last = null;
    for (const i of ids) {
      const z0 = ZB.get(i), src = actx.createBufferSource();
      src.buffer = z0.buf; src.connect(actx.destination);
      src.start(t, z0.s, z0.e - z0.s); t += z0.e - z0.s + gap;
      zSrcs.push(src); last = src;
    }
    const fin = () => { if (zDuck === my) { duck(false, my); zDuck = null; } res(); };
    last.onended = fin;
    setTimeout(fin, (t - actx.currentTime) * 1000 + 300);   // 念のため
  });
}
const z = id => zSeq([id]);
const sayEq = (a, b, n) => zSeq(["n" + a, "kakeru", "n" + b, "wa", "n" + n], .03);
// 画面を 出たら 声も 止める
const _stopAll = window.stopAll;
window.stopAll = function(){ stopZ(); return _stopAll.apply(this, arguments); };
const praise = () => z("ok" + (1 + Math.floor(Math.random() * 5)));

/* ---------- ホーム ---------- */
function renderGameHome(){
  const t = total();
  const top = [5, 4, 3, 2, 1].find(s => G.lv[s] > 0);
  const allMax = t >= 50;
  const cur = G.lv[top] < MAXLV ? top : top;
  const pct = G.lv[cur] >= MAXLV ? 100 : 100 * G.xp[cur] / need(G.lv[cur]);
  let h = `<div class="gme"><div class="ava">${STAGES[top].icon}${allMax ? '<span class="crown">👑</span>' : ""}</div>
    <div class="info"><div class="lv">Lv ${t}<small> / 50</small></div>
    <div class="pbar"><div style="width:${allMax ? 100 : pct}%"></div></div></div></div><div class="gstages">`;
  for (let s = 1; s <= 5; s++) {
    const L = G.lv[s], st = STAGES[s], open = L > 0, max = L >= MAXLV;
    const p = max ? 100 : open ? 100 * G.xp[s] / need(L) : 0;
    h += `<button class="gstage ${open ? "" : "lock"} ${max ? "max" : ""}" data-s="${s}" style="background:${st.color}">
      <span class="ic">${st.icon}${max ? '<span class="crown">👑</span>' : ""}</span>
      <span class="meta"><b>${s}. ${st.name}</b><div class="pbar"><div style="width:${p}%"></div></div></span>
      <span class="lvt">${open ? (max ? "MAX" : "Lv " + L) : "🔒"}</span></button>`;
  }
  h += `</div><div class="gstamps"><h3>スタンプ</h3><div class="row">`;
  for (let s = 1; s <= 5; s++) h += `<div class="sp ${G.stamps.includes("s" + s) ? "got" : ""}">${G.stamps.includes("s" + s) ? STAGES[s].icon : ""}<small>${s}</small></div>`;
  for (const m of [10, 20, 30, 40, 50]) h += `<div class="sp ${G.stamps.includes("m" + m) ? "got" : ""}">${G.stamps.includes("m" + m) ? (m === 50 ? "👑" : "🏅") : ""}<small>Lv${m}</small></div>`;
  h += `</div></div><button class="groom ${roomOpen() ? "" : "lock"}" id="gRoom">${roomOpen() ? "🎵 くくの へや" : "🔒 くくの へや（ステージ5で ひらくよ）"}</button>
    <div class="gcredit">こえ・うた：VOICEVOX:ずんだもん</div>`;
  $("#gHome").innerHTML = h;
  $$("#gHome .gstage").forEach(b => b.onclick = () => {
    const s = +b.dataset.s;
    if (!G.lv[s]) { sfx("ng"); b.classList.add("shake"); setTimeout(() => b.classList.remove("shake"), 400); return; }
    GS = s; go("game");
  });
  $("#gRoom").onclick = () => roomOpen() ? go("room") : (sfx("ng"), toast("🔒", 700));
}

/* ---------- 問題づくり ---------- */
const pickIn = arr => arr[Math.floor(Math.random() * arr.length)];
const range = (a, b) => Array.from({ length: b - a + 1 }, (_, i) => a + i);
function makeQ(s, L){
  const i = L - 1;
  let A, B;
  if (s === 1) { A = range(1, [2,2,2,3,3,3,4,4,5,5][i]); B = range(2, [2,3,3,3,4,4,4,5,5,5][i]); }
  if (s === 2) { A = range(1, [2,2,3,3,3,4,4,5,5,5][i]); B = range(2, [2,3,3,4,4,4,5,5,5,5][i]); }
  if (s === 3) { A = [[2],[2],[2,5],[5],[2,5],[3],[3],[4],[3,4],[2,3,4,5]][i]; B = range(2, Math.min(9, 3 + L)); }
  if (s === 4) { A = range(2, [3,3,4,4,5,5,5,6,6,6][i]); B = range(2, [2,3,3,4,4,5,5,5,6,6][i]); }
  if (s === 5) { A = [[2],[5],[2,5],[3],[4],[3,4],[6,7],[8,9],[6,7,8,9],[1,2,3,4,5,6,7,8,9]][i]; B = range(1, L <= 2 ? 5 : 9); }
  let a, b, k = 0;
  do { a = pickIn(A); b = pickIn(B); k++; } while (k < 20 && lastQ === a + "x" + b);
  lastQ = a + "x" + b;
  return { a, b, n: a * b };
}
let lastQ = "";
const PRODUCTS = [...new Set(range(1, 9).flatMap(a => range(1, 9).map(b => a * b)))];
function choices(q, s){
  const n = q.n, cand = new Set();
  const near = s === 5
    ? [q.a * (q.b - 1), q.a * (q.b + 1), (q.a + 1) * q.b, (q.a - 1) * q.b, n + 1, n - 1].filter(x => PRODUCTS.includes(x))
    : [n - q.a, n + q.a, n - 1, n + 1, n + 2, n - 2];
  near.sort(() => Math.random() - .5).forEach(x => { if (x > 0 && x <= 81 && x !== n && cand.size < 2) cand.add(x); });
  for (let x = n + 1; cand.size < 2; x++) if (x !== n && (s !== 5 || PRODUCTS.includes(x))) cand.add(x);
  return [n, ...cand].sort(() => Math.random() - .5);
}

/* ---------- プレイ ---------- */
let GS = 1, qCount = 0;
function head(){
  const L = G.lv[GS], st = STAGES[GS];
  $("#gStage").innerHTML = `${st.icon} ${st.name}`;
  $("#gStage").style.color = st.color;
  $("#gLv").textContent = L >= MAXLV ? "MAX" : "Lv " + L;
  $("#gXp").style.width = (L >= MAXLV ? 100 : 100 * G.xp[GS] / need(L)) + "%";
}
function setEq(c, f){ $("#gEq .c").textContent = c || " "; $("#gEq .f").innerHTML = f || "&nbsp;"; }
function plateClass(b, a){ return (b > 6 ? "xs" : b > 4 ? "sm" : "") + (a > 4 ? " many" : a <= 2 ? " few" : " mid"); }

async function startGame(){
  qCount = 0; head();
  const id = RUN;
  $("#gArea").innerHTML = `<div class="ghint" style="font-size:44px">${STAGES[GS].icon}</div>`;
  setEq("", `${STAGES[GS].name}`); $("#gAns").innerHTML = "";
  preloadZ();
  z(STAGES[GS].v); await sleep(900); if (!alive(id)) return;
  loop(id);
}
async function loop(id){
  while (alive(id)) {
    const L = G.lv[GS], q = makeQ(GS, L);
    qCount++;
    const ok = await [null, qCount1, qMake, qSkip, qArray, qKuku][GS](q, id);
    if (!ok || !alive(id)) return;
    await gain(id);
    if (!alive(id)) return;
    await sleep(150);
  }
}
function item(){ return pickIn(unlockedItems()); }

// こたえボタン → せいかいで true
function askAnswer(q, id, onPick){
  return new Promise(res => {
    const box = $("#gAns"); box.innerHTML = "";
    choices(q, GS).forEach(x => {
      const b = document.createElement("button"); b.textContent = x;
      b.onclick = async () => {
        if (!alive(id) || b.classList.contains("ng") || box.dataset.lock) return;
        if (onPick) onPick(x);
        if (x === q.n) {
          box.dataset.lock = 1; b.classList.add("ok"); sfx("ok");
          [...box.children].forEach(c => { if (c !== b) c.classList.add("ng"); });
          res(true);
        } else {
          sfx("ng"); b.classList.add("ng", "shake"); z("ng", "おしい");
        }
      };
      box.appendChild(b);
    });
    delete box.dataset.lock;
  });
}
async function reveal(q, id){
  setEq(`${q.a}こずつ が ${q.b}こぶん`, `${q.a} × ${q.b} = <span class="q">${q.n}</span>`);
  if (GS === 5) await zSeq(["c" + q.a + "x" + q.b, "a" + q.n], .02);
  else await sayEq(q.a, q.b, q.n);
  if (!alive(id)) return;
  praise(); await sleep(700);
}

// 1 かぞえて：ひとつずつ タッチして かぞえる
async function qCount1(q, id){
  const it = item(), area = $("#gArea");
  area.innerHTML = ""; $("#gAns").innerHTML = "";
  setEq(`${it} ${q.a}こずつ・おさら ${q.b}まい`, `ぜんぶで <span class="q">？</span>`);
  let cnt = 0, resolve;
  const allCounted = new Promise(r => resolve = r);
  for (let p = 0; p < q.b; p++) {
    const pl = document.createElement("div"); pl.className = "plate " + plateClass(q.b, q.a);
    for (let k = 0; k < q.a; k++) {
      const e = document.createElement("span"); e.className = "it"; e.textContent = it;
      e.onclick = ev => {
        ev.stopPropagation();
        if (e.classList.contains("done") || !alive(id)) return;
        cnt++; e.classList.add("done"); e.insertAdjacentHTML("beforeend", `<i class="no">${cnt}</i>`);
        z("n" + cnt);
        if (cnt === q.n) resolve();
      };
      pl.appendChild(e);
    }
    area.appendChild(pl);
  }
  if (qCount === 1) z("tapcount", "ひとつずつ タッチして かぞえるのだ");
  await allCounted; if (!alive(id)) return false;
  await sleep(250); if (!alive(id)) return false;
  z("zenbude", "ぜんぶで いくつ");
  await askAnswer(q, id); if (!alive(id)) return false;
  await reveal(q, id);
  return alive(id);
}

// 2 つくって：おさらに ◯こずつ のせる
async function qMake(q, id){
  const it = item(), area = $("#gArea");
  area.innerHTML = ""; $("#gAns").innerHTML = "";
  setEq(`おさら ${q.b}まいに ${it} ${q.a}こずつ`, `ぜんぶで <span class="q">？</span>`);
  let full = 0, resolve;
  const done = new Promise(r => resolve = r);
  for (let p = 0; p < q.b; p++) {
    const pl = document.createElement("div"); pl.className = "plate " + plateClass(q.b, q.a);
    pl.innerHTML = '<span class="slot"></span>'.repeat(q.a);
    let c = 0;
    pl.onclick = () => {
      if (!alive(id)) return;
      if (c >= q.a) { sfx("ng"); pl.classList.add("shake"); setTimeout(() => pl.classList.remove("shake"), 400); z("ooi", "おおすぎるのだ"); return; }
      const s = pl.children[c]; s.className = "it"; s.textContent = it; c++;
      z("n" + c);
      if (c === q.a) { pl.classList.add("full"); full++; if (full === q.b) resolve(); }
    };
    area.appendChild(pl);
  }
  zSeq(["sara" + q.b, "kozu" + q.a, "noseru"], .06);
  await done; if (!alive(id)) return false;
  await sleep(250); if (!alive(id)) return false;
  zSeq(["dekita", "zenbude"], .1);
  await askAnswer(q, id); if (!alive(id)) return false;
  await reveal(q, id);
  return alive(id);
}

// 3 とびかぞえ：おさらを タッチすると 2、4、6…
async function qSkip(q, id){
  const it = item(), area = $("#gArea");
  area.innerHTML = ""; $("#gAns").innerHTML = "";
  setEq(`${it} ${q.a}こずつ・おさら ${q.b}まい`, `ぜんぶで <span class="q">？</span>`);
  let k = 0, resolve;
  const done = new Promise(r => resolve = r);
  for (let p = 0; p < q.b; p++) {
    const pl = document.createElement("div"); pl.className = "plate dim " + plateClass(q.b, q.a);
    pl.innerHTML = `<span class="it">${it}</span>`.repeat(q.a);
    pl.onclick = () => {
      if (!alive(id) || pl.classList.contains("lit")) return;
      k++; pl.classList.remove("dim"); pl.classList.add("lit");
      pl.insertAdjacentHTML("beforeend", `<span class="tot">${q.a * k}</span>`);
      z("n" + q.a * k);
      if (k === q.b) resolve();
    };
    area.appendChild(pl);
  }
  if (qCount === 1) z("tobi", "おさらを じゅんばんに タッチするのだ");
  await done; if (!alive(id)) return false;
  await sleep(250); if (!alive(id)) return false;
  z("zenbude", "ぜんぶで いくつ");
  await askAnswer(q, id); if (!alive(id)) return false;
  await reveal(q, id);
  return alive(id);
}

// 4 ならべて：たて・よこ に ならんだ どうぶつ（れつを タッチ）
async function qArray(q, id){
  const an = pickIn(ROW_ANIMALS), area = $("#gArea");
  area.innerHTML = ""; $("#gAns").innerHTML = "";
  setEq(`${an} ${q.a}ひきずつ ${q.b}れつ`, `ぜんぶで <span class="q">？</span>`);
  const arr = document.createElement("div"); arr.className = "arr";
  let k = 0, resolve;
  const done = new Promise(r => resolve = r);
  for (let r = 0; r < q.b; r++) {
    const row = document.createElement("div"); row.className = "arow";
    row.innerHTML = `<span>${an}</span>`.repeat(q.a);
    row.onclick = () => {
      if (!alive(id) || row.classList.contains("lit")) return;
      k++; row.classList.add("lit"); row.insertAdjacentHTML("beforeend", `<i class="tot">${q.a * k}</i>`);
      z("n" + q.a * k);
      if (k === q.b) resolve();
    };
    arr.appendChild(row);
  }
  area.appendChild(arr);
  if (qCount === 1) z("retsu", "いちれつずつ タッチするのだ");
  await done; if (!alive(id)) return false;
  await sleep(250); if (!alive(id)) return false;
  z("zenbude", "ぜんぶで いくつ");
  await askAnswer(q, id); if (!alive(id)) return false;
  await reveal(q, id); if (!alive(id)) return false;
  // ときどき くるっと まわして おなじ かず
  if (qCount % 3 === 0 && q.a !== q.b) {
    arr.classList.add("turn"); await sleep(900); if (!alive(id)) return false;
    setEq(`くるっと まわしても`, `${q.b} × ${q.a} = <span class="q">${q.n}</span>`);
    await z("kurutto", "くるっと まわしても おなじ かずなのだ");
  }
  return alive(id);
}

// 5 くくで こたえて：「にさんが？」→ こたえを えらぶ
async function qKuku(q, id){
  const it = item(), area = $("#gArea");
  area.innerHTML = ""; $("#gAns").innerHTML = "";
  for (let p = 0; p < q.b; p++) {
    const pl = document.createElement("div"); pl.className = "plate " + plateClass(q.b, q.a);
    pl.style.cursor = "default";
    pl.innerHTML = `<span class="it">${it}</span>`.repeat(q.a);
    area.appendChild(pl);
  }
  const call = KUKU[q.a][q.b - 1][0];
  setEq(`${call} …？`, `${q.a} × ${q.b} = <span class="q">？</span>`);
  await zSeq(qCount === 1 ? ["kuku", "c" + q.a + "x" + q.b] : ["c" + q.a + "x" + q.b], .25); if (!alive(id)) return false;
  await askAnswer(q, id, x => { if (x !== q.n) return; }); if (!alive(id)) return false;
  await reveal(q, id);
  return alive(id);
}

/* ---------- けいけんち・レベルアップ ---------- */
function confetti(n = 24){
  const em = ["🎉","⭐","✨","🎊","💛"];
  for (let i = 0; i < n; i++) {
    const e = document.createElement("div"); e.className = "confetti"; e.textContent = pickIn(em);
    e.style.left = Math.random() * 100 + "vw"; e.style.animationDuration = (1.6 + Math.random() * 1.6) + "s";
    e.style.animationDelay = Math.random() * .6 + "s";
    document.body.appendChild(e); setTimeout(() => e.remove(), 4000);
  }
}
function showLv(icon, crown, l1, l2, sub, voiceId, voiceText){
  return new Promise(res => {
    $("#lvup .icon").innerHTML = icon + (crown ? '<span class="crown">👑</span>' : "");
    $("#lvup .big1").textContent = l1; $("#lvup .big2").textContent = l2; $("#lvup .sub").textContent = sub || "";
    $("#lvup").classList.add("on"); sfx("fan"); confetti();
    if (voiceId) z(voiceId, voiceText);
    $("#lvOk").onclick = () => { $("#lvup").classList.remove("on"); res(); };
  });
}
async function gain(id){
  const s = GS;
  if (G.lv[s] >= MAXLV) { head(); return; }                       // マックスの ステージは れんしゅう
  G.xp[s]++; save(); head();
  if (G.xp[s] < need(G.lv[s])) return;
  // レベルアップ！ — 先に 記録を ぜんぶ 確定してから 演出（とちゅうで ぬけても なくならない）
  G.xp[s] = 0; G.lv[s]++;
  const shows = [];
  if (G.lv[s] < MAXLV) {
    shows.push([STAGES[s].icon, false, STAGES[s].name, `Lv ${G.lv[s]}`, `ぜんぶで Lv ${total()}`, "lvup", "レベルアップなのだ"]);
  } else {
    if (!G.stamps.includes("s" + s)) G.stamps.push("s" + s);
    shows.push([STAGES[s].icon, true, STAGES[s].name, "MAX!", "おうかんと スタンプ ゲット！", "max", "マックスなのだ"]);
    if (s < 5 && !G.lv[s + 1]) {
      G.lv[s + 1] = 1;
      shows.push([STAGES[s + 1].icon, false, "あたらしい ステージ", `${s + 1}. ${STAGES[s + 1].name}`, "", "newstage", "あたらしい ステージが ひらいたのだ"]);
      if (s + 1 === 5) shows.push(["🎵", false, "くくの へや", "OPEN!", "くくの うたも あるよ", "kukuopen", "くくの へやが ひらいたのだ"]);
    }
  }
  for (const m of [10, 20, 30, 40, 50]) {
    if (total() >= m && !G.stamps.includes("m" + m)) {
      G.stamps.push("m" + m);
      shows.push(m === 50
        ? ["🦖", true, "ぜんぶ マックス！", "Lv 50", "おおきな おうかん ゲット！", "allmax", "レベル ごじゅう ぜんぶ マックスなのだ"]
        : ["🏅", false, "スタンプ", `Lv ${m}`, "スタンプ ゲット！", "stamp", "スタンプ ゲットなのだ"]);
    }
  }
  save(); head();
  await sleep(300);
  for (const sh of shows) { if (!alive(id)) return; await showLv(...sh); }
}

/* ---------- 画面の フック ---------- */
window.HOOKS = window.HOOKS || {};
HOOKS.home = () => { $("#lvup").classList.remove("on"); renderGameHome(); if (started) preloadZ(); };
HOOKS.game = startGame;
renderGameHome();

// おとなよう：タイトルを3びょう長おし → くくのへや を あける/もどす
(() => {
  let t = null; const el = $("#gTitle");
  const st = () => { t = setTimeout(() => { S.roomOpen = !S.roomOpen; save(); renderGameHome(); toast(S.roomOpen ? "🔓 くくのへや" : "🔒 もとに もどしたよ", 1400); }, 3000); };
  const en = () => clearTimeout(t);
  el.addEventListener("touchstart", st, { passive: true }); el.addEventListener("touchend", en);
  el.addEventListener("mousedown", st); el.addEventListener("mouseup", en); el.addEventListener("mouseleave", en);
})();
// テスト用（ブラウザから 状態を みる）
window.__game = { G, total, need, makeQ, get GS(){ return GS; } }; window.ZBX = () => ZB;
})();
