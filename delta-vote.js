/* delta-vote.js: the Who Would You Rather Have? vote, shared by vote/index.html and the vote card on the
   Market tab (index.html), so both use one player list, one way of pairing and one way of saving.
   Moved here unchanged from vote/index.html on 17 Nov 2026. Pairing and saving follow docs/PREREG-crowd-values.md
   (amendment A1: fewer votes, more often). A new board means a new BOARD value and a new list here, nowhere else. */
(function(){
'use strict';
const ITEMS = [{"n":"Jahmyr Gibbs","pos":"RB","team":"DET","age":24,"r":1},{"n":"Jaxon Smith-Njigba","pos":"WR","team":"SEA","age":24,"r":2},{"n":"Josh Allen","pos":"QB","team":"BUF","age":30,"r":3},{"n":"Bijan Robinson","pos":"RB","team":"ATL","age":24,"r":4},{"n":"Ja'Marr Chase","pos":"WR","team":"CIN","age":26,"r":5},{"n":"Puka Nacua","pos":"WR","team":"LAR","age":25,"r":6},{"n":"Amon-Ra St. Brown","pos":"WR","team":"DET","age":26,"r":7},{"n":"Joe Burrow","pos":"QB","team":"CIN","age":29,"r":8},{"n":"Trey McBride","pos":"TE","team":"ARI","age":26,"r":9},{"n":"Drake Maye","pos":"QB","team":"NE","age":24,"r":10},{"n":"CeeDee Lamb","pos":"WR","team":"DAL","age":27,"r":11},{"n":"Brock Bowers","pos":"TE","team":"LV","age":23,"r":12},{"n":"Caleb Williams","pos":"QB","team":"CHI","age":24,"r":13},{"n":"Brock Purdy","pos":"QB","team":"SF","age":26,"r":14},{"n":"Justin Jefferson","pos":"WR","team":"MIN","age":27,"r":15},{"n":"Kenneth Walker III","pos":"RB","team":"KC","age":25,"r":16},{"n":"Jordan Love","pos":"QB","team":"GB","age":27,"r":17},{"n":"Trevor Lawrence","pos":"QB","team":"JAC","age":26,"r":18},{"n":"Chris Olave","pos":"WR","team":"NO","age":26,"r":19},{"n":"Jonathan Taylor","pos":"RB","team":"IND","age":27,"r":20},{"n":"Lamar Jackson","pos":"QB","team":"BAL","age":29,"r":21},{"n":"Jayden Daniels","pos":"QB","team":"WAS","age":25,"r":22},{"n":"James Cook","pos":"RB","team":"BUF","age":27,"r":23},{"n":"Drake London","pos":"WR","team":"ATL","age":25,"r":24},{"n":"Patrick Mahomes","pos":"QB","team":"KC","age":31,"r":25},{"n":"Zay Flowers","pos":"WR","team":"BAL","age":26,"r":26},{"n":"Christian McCaffrey","pos":"RB","team":"SF","age":30,"r":27},{"n":"Malik Nabers","pos":"WR","team":"NYG","age":23,"r":28},{"n":"Ashton Jeanty","pos":"RB","team":"LV","age":22,"r":29},{"n":"Tee Higgins","pos":"WR","team":"CIN","age":27,"r":30},{"n":"De'Von Achane","pos":"RB","team":"MIA","age":24,"r":31},{"n":"Kyren Williams","pos":"RB","team":"LAR","age":26,"r":32},{"n":"Nico Collins","pos":"WR","team":"HOU","age":27,"r":33},{"n":"Christian Watson","pos":"WR","team":"GB","age":27,"r":34},{"n":"Bucky Irving","pos":"RB","team":"TB","age":24,"r":35},{"n":"George Pickens","pos":"WR","team":"DAL","age":25,"r":36},{"n":"Tetairoa McMillan","pos":"WR","team":"CAR","age":23,"r":37},{"n":"Matthew Golden","pos":"WR","team":"GB","age":23,"r":38},{"n":"C.J. Stroud","pos":"QB","team":"HOU","age":24,"r":39},{"n":"Luther Burden","pos":"WR","team":"CHI","age":22,"r":40},{"n":"Jeremiyah Love","pos":"RB","team":"ARI","age":21,"r":41},{"n":"Jared Goff","pos":"QB","team":"DET","age":31,"r":42},{"n":"Rashee Rice","pos":"WR","team":"KC","age":26,"r":43},{"n":"Bo Nix","pos":"QB","team":"DEN","age":26,"r":44},{"n":"Jaxson Dart","pos":"QB","team":"NYG","age":23,"r":45},{"n":"Colston Loveland","pos":"TE","team":"CHI","age":22,"r":46},{"n":"Tyler Warren","pos":"TE","team":"IND","age":24,"r":47},{"n":"Tyler Shough","pos":"QB","team":"NO","age":26,"r":48},{"n":"Parker Washington","pos":"WR","team":"JAC","age":24,"r":49},{"n":"Dak Prescott","pos":"QB","team":"DAL","age":33,"r":50},{"n":"Bryce Young","pos":"QB","team":"CAR","age":25,"r":51},{"n":"Javonte Williams","pos":"RB","team":"DAL","age":26,"r":52},{"n":"D'Andre Swift","pos":"RB","team":"CHI","age":27,"r":53},{"n":"Justin Herbert","pos":"QB","team":"LAC","age":28,"r":54},{"n":"Jalen Hurts","pos":"QB","team":"PHI","age":28,"r":55},{"n":"Breece Hall","pos":"RB","team":"NYJ","age":25,"r":56},{"n":"Tucker Kraft","pos":"TE","team":"GB","age":25,"r":57},{"n":"Jameson Williams","pos":"WR","team":"DET","age":25,"r":58},{"n":"Harold Fannin Jr.","pos":"TE","team":"CLE","age":22,"r":59},{"n":"Sam LaPorta","pos":"TE","team":"DET","age":25,"r":60},{"n":"George Kittle","pos":"TE","team":"SF","age":32,"r":61},{"n":"Fernando Mendoza","pos":"QB","team":"LV","age":22,"r":62},{"n":"Garrett Wilson","pos":"WR","team":"NYJ","age":26,"r":63},{"n":"Chase Brown","pos":"RB","team":"CIN","age":26,"r":64},{"n":"Omarion Hampton","pos":"RB","team":"LAC","age":23,"r":65},{"n":"DeVonta Smith","pos":"WR","team":"PHI","age":27,"r":66},{"n":"Carnell Tate","pos":"WR","team":"TEN","age":21,"r":67},{"n":"A.J. Brown","pos":"WR","team":"NE","age":29,"r":68},{"n":"Bhayshul Tuten","pos":"RB","team":"JAC","age":24,"r":69},{"n":"Chuba Hubbard","pos":"RB","team":"CAR","age":27,"r":70},{"n":"Isaiah Likely","pos":"TE","team":"NYG","age":26,"r":71},{"n":"Jaylen Warren","pos":"RB","team":"PIT","age":27,"r":72},{"n":"Dalton Kincaid","pos":"TE","team":"BUF","age":26,"r":73},{"n":"Jordyn Tyson","pos":"WR","team":"NO","age":22,"r":74},{"n":"Quinshon Judkins","pos":"RB","team":"CLE","age":22,"r":75},{"n":"Jonah Coleman","pos":"RB","team":"DEN","age":23,"r":76},{"n":"Emeka Egbuka","pos":"WR","team":"TB","age":23,"r":77},{"n":"Michael Wilson","pos":"WR","team":"ARI","age":26,"r":78},{"n":"Ladd McConkey","pos":"WR","team":"LAC","age":24,"r":79},{"n":"Rome Odunze","pos":"WR","team":"CHI","age":24,"r":80},{"n":"Saquon Barkley","pos":"RB","team":"PHI","age":29,"r":81},{"n":"Jaylen Waddle","pos":"WR","team":"DEN","age":27,"r":82},{"n":"Josh Jacobs","pos":"RB","team":"GB","age":28,"r":83},{"n":"Michael Penix Jr.","pos":"QB","team":"ATL","age":26,"r":84},{"n":"Baker Mayfield","pos":"QB","team":"TB","age":31,"r":85},{"n":"Sam Darnold","pos":"QB","team":"SEA","age":29,"r":86},{"n":"Matthew Stafford","pos":"QB","team":"LAR","age":38,"r":87},{"n":"Cam Ward","pos":"QB","team":"TEN","age":24,"r":88},{"n":"Derrick Henry","pos":"RB","team":"BAL","age":32,"r":89},{"n":"Jadarian Price","pos":"RB","team":"SEA","age":22,"r":90},{"n":"Jalen Coker","pos":"WR","team":"CAR","age":24,"r":91},{"n":"TreVeyon Henderson","pos":"RB","team":"NE","age":23,"r":92},{"n":"KC Concepcion","pos":"WR","team":"CLE","age":22,"r":93},{"n":"D.J. Moore","pos":"WR","team":"BUF","age":28,"r":94},{"n":"Makai Lemon","pos":"WR","team":"PHI","age":22,"r":95},{"n":"Cam Skattebo","pos":"RB","team":"NYG","age":24,"r":96},{"n":"Denzel Boston","pos":"WR","team":"CLE","age":22,"r":97},{"n":"Travis Etienne","pos":"RB","team":"NO","age":27,"r":98},{"n":"Omar Cooper","pos":"WR","team":"NYJ","age":22,"r":99},{"n":"Kyle Pitts","pos":"TE","team":"ATL","age":25,"r":100},{"n":"Brian Thomas Jr.","pos":"WR","team":"JAC","age":23,"r":101},{"n":"Kyler Murray","pos":"QB","team":"MIN","age":29,"r":102},{"n":"Rhamondre Stevenson","pos":"RB","team":"NE","age":28,"r":103},{"n":"Alec Pierce","pos":"WR","team":"IND","age":26,"r":104},{"n":"Blake Corum","pos":"RB","team":"LAR","age":25,"r":105},{"n":"Kyle Monangai","pos":"RB","team":"CHI","age":24,"r":106},{"n":"Malik Willis","pos":"QB","team":"MIA","age":27,"r":107},{"n":"Ty Simpson","pos":"QB","team":"LAR","age":23,"r":108},{"n":"Kenyon Sadiq","pos":"TE","team":"NYJ","age":21,"r":109},{"n":"T.J. Hockenson","pos":"TE","team":"MIN","age":29,"r":110},{"n":"Cedric Tillman","pos":"WR","team":"NO","age":26,"r":111},{"n":"Zach Charbonnet","pos":"RB","team":"SEA","age":25,"r":112},{"n":"RJ Harvey","pos":"RB","team":"DEN","age":25,"r":113},{"n":"Terrance Ferguson","pos":"TE","team":"LAR","age":23,"r":114},{"n":"Marvin Harrison Jr.","pos":"WR","team":"HOU","age":24,"r":115},{"n":"Daniel Jones","pos":"QB","team":"IND","age":29,"r":116},{"n":"Josh Downs","pos":"WR","team":"IND","age":25,"r":117},{"n":"Brenton Strange","pos":"TE","team":"JAC","age":25,"r":118},{"n":"Khalil Shakir","pos":"WR","team":"BUF","age":26,"r":119},{"n":"Jordan Addison","pos":"WR","team":"MIN","age":24,"r":120},{"n":"DK Metcalf","pos":"WR","team":"PIT","age":28,"r":121},{"n":"J.J. McCarthy","pos":"QB","team":"NYG","age":23,"r":122},{"n":"Juwan Johnson","pos":"TE","team":"NO","age":30,"r":123},{"n":"De'Zhaun Stribling","pos":"WR","team":"SF","age":23,"r":124},{"n":"Kirk Cousins","pos":"QB","team":"LV","age":38,"r":125},{"n":"Tony Pollard","pos":"RB","team":"TEN","age":29,"r":126},{"n":"Isaac Guerendo","pos":"RB","team":"SF","age":26,"r":127},{"n":"Germie Bernard","pos":"WR","team":"PIT","age":22,"r":128},{"n":"Wan'Dale Robinson","pos":"WR","team":"TEN","age":25,"r":129},{"n":"Jayden Higgins","pos":"WR","team":"HOU","age":23,"r":130},{"n":"Emmett Johnson","pos":"RB","team":"KC","age":22,"r":131},{"n":"Carson Beck","pos":"QB","team":"ARI","age":24,"r":132},{"n":"Dallas Goedert","pos":"TE","team":"PHI","age":31,"r":133},{"n":"Antonio Williams","pos":"WR","team":"WAS","age":22,"r":134},{"n":"Travis Kelce","pos":"TE","team":"KC","age":36,"r":135},{"n":"Mike Washington Jr.","pos":"RB","team":"LV","age":23,"r":136},{"n":"Davante Adams","pos":"WR","team":"LAR","age":33,"r":137},{"n":"Caleb Douglas","pos":"WR","team":"MIA","age":23,"r":138},{"n":"Jake Ferguson","pos":"TE","team":"DAL","age":27,"r":139},{"n":"Ricky Pearsall","pos":"WR","team":"SF","age":26,"r":140},{"n":"Stefon Diggs","pos":"WR","team":"WAS","age":32,"r":141},{"n":"Woody Marks","pos":"RB","team":"HOU","age":25,"r":142},{"n":"Jakobi Meyers","pos":"WR","team":"JAC","age":29,"r":143},{"n":"Shedeur Sanders","pos":"QB","team":"CLE","age":24,"r":144},{"n":"Kaelon Black","pos":"RB","team":"SF","age":24,"r":145},{"n":"Mike Evans","pos":"WR","team":"SF","age":33,"r":146},{"n":"Rico Dowdle","pos":"RB","team":"PIT","age":28,"r":147},{"n":"Eli Stowers","pos":"TE","team":"PHI","age":23,"r":148},{"n":"Ryan Flournoy","pos":"WR","team":"DAL","age":26,"r":149},{"n":"Adonai Mitchell","pos":"WR","team":"NYJ","age":23,"r":150},{"n":"2027 Early 1st","pos":"PICK","team":"","age":null,"r":28.5},{"n":"2027 Mid 1st","pos":"PICK","team":"","age":null,"r":42.5},{"n":"2027 Late 1st","pos":"PICK","team":"","age":null,"r":58.5},{"n":"2027 Early 2nd","pos":"PICK","team":"","age":null,"r":82.5},{"n":"2027 Mid 2nd","pos":"PICK","team":"","age":null,"r":98.5},{"n":"2027 Late 2nd","pos":"PICK","team":"","age":null,"r":112.5},{"n":"2027 Early 3rd","pos":"PICK","team":"","age":null,"r":128.5},{"n":"2027 Mid 3rd","pos":"PICK","team":"","age":null,"r":140.5},{"n":"2027 Late 3rd","pos":"PICK","team":"","age":null,"r":149.5}];
const BOARD = '2026-11-10';                                   // which player list these votes were cast on
const API = 'https://zpashsoixmsbzvvuodro.supabase.co/rest/v1';
const KEY = 'sb_publishable_hwGjxh5PXKlD95i_e_4i9Q_VZzb9s_G'; // publishable: safe in a page; the table only accepts new votes
const GOAL = 5000;                                            // about where the first full board appears (PREREG-crowd-values §6)

const store = {
  get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
};
function newId() {
  try { return crypto.randomUUID(); } catch (e) { return 'x' + Math.random().toString(36).slice(2) + Date.now().toString(36); }
}
const session = store.get('dv_session') || newId(); store.set('dv_session', session);
let tag = store.get('dv_tag') === 'owner' ? 'owner' : 'organic';
let mine = Number(store.get('dv_votes') || 0) || 0;   // kept in memory too, for browsers that block storage

// Fewer votes, more often (PREREG-crowd-values A1): an item with v votes is drawn with weight (1 + v)^-1.5.
// Without counts (offline, or the first load), every item is equally likely.
let COUNTS = {}, haveCounts = false, sinceCounts = 0, last = new Set();
async function loadCounts() {
  try {
    const r = await fetch(API + '/rpc/item_vote_counts', { method: 'POST', headers: { apikey: KEY, 'Content-Type': 'application/json' }, body: JSON.stringify({ p_board: BOARD }) });
    if (!r.ok) return;
    const j = await r.json(), c = {};
    (Array.isArray(j) ? j : []).forEach((x) => { c[x.name] = Number(x.votes) || 0; });
    COUNTS = c; haveCounts = true; sinceCounts = 0;
  } catch (e) {}
  await loadOrder();
}
const need = (x) => Math.pow(1 + (COUNTS[x.n] || 0), -1.5);

// Pairs by the crowd's CURRENT order (PREREG-crowd-values A2, 26 Nov 2026): "close" pairs are neighbours in POS, a
// quick Bradley-Terry order of every pick so far, so a player who keeps winning moves up and meets better players.
// Each item also plays 2 pretend games against an opponent at its page slot (strength exp(-r/30)), so with few votes
// an item stays near its slot. Without results (offline, or before the database function exists), POS = page slot.
// Gimme pairs still use the page slot: they are the quality check the fit reads.
let POS = {};
ITEMS.forEach((x) => { POS[x.n] = x.r; });
function crowdOrder(rows) {
  const idx = {}; ITEMS.forEach((x, i) => { idx[x.n] = i; });
  const n = ITEMS.length, s0 = ITEMS.map((x) => Math.exp(-x.r / 30)), PRI = 2;
  const P = rows.filter((g) => g.x in idx && g.y in idx).map((g) => [idx[g.x], idx[g.y], Number(g.x_wins) || 0, Number(g.y_wins) || 0]);
  const wins = s0.map(() => PRI / 2);
  P.forEach(([i, j, wi, wj]) => { wins[i] += wi; wins[j] += wj; });
  let s = s0.slice();
  for (let it = 0; it < 200; it++) {
    const den = s.map((v, i) => PRI / (v + s0[i]));
    P.forEach(([i, j, wi, wj]) => { const d = (wi + wj) / (s[i] + s[j]); den[i] += d; den[j] += d; });
    s = s.map((v, i) => wins[i] / den[i]);
  }
  const order = ITEMS.map((x, i) => i).sort((a, b) => s[b] - s[a]);
  const pos = {}; order.forEach((i, k) => { pos[ITEMS[i].n] = k + 1; });
  return pos;
}
async function loadOrder() {
  try {
    const r = await fetch(API + '/rpc/pair_results', { method: 'POST', headers: { apikey: KEY, 'Content-Type': 'application/json' }, body: JSON.stringify({ p_board: BOARD }) });
    if (!r.ok) return;
    const j = await r.json();
    if (Array.isArray(j) && j.length) POS = crowdOrder(j);
  } catch (e) {}
}
function draw(list) {
  let t = 0; for (const x of list) t += need(x);
  let u = Math.random() * t;
  for (const x of list) { u -= need(x); if (u <= 0) return x; }
  return list[list.length - 1];
}

// Returns { pair: [left, right], type: 'gimme' | 'random' | 'close' }.
function pickPair() {
  let curType;
  const roll = Math.random(), pool = ITEMS.filter((x) => !last.has(x.n));
  const a = draw(pool);
  let cands;
  if (roll < 0.06) { curType = 'gimme'; cands = pool.filter((x) => Math.abs(x.r - a.r) >= 90); }   // a quality check
  else if (roll < 0.26) { curType = 'random'; cands = pool.filter((x) => x !== a); }
  else { curType = 'close'; cands = pool.filter((x) => x !== a && Math.abs(POS[x.n] - POS[a.n]) <= 12); }
  if (!cands.length) { curType = 'random'; cands = pool.filter((x) => x !== a); }
  const b = curType === 'gimme' ? cands[Math.floor(Math.random() * cands.length)] : draw(cands);
  last = new Set([a.n, b.n]);
  return { pair: Math.random() < 0.5 ? [a, b] : [b, a], type: curType };
}

// pick: the chosen item's name, or null for a skip. ms: time the pair was on screen.
async function save(pair, type, pick, ms) {
  const row = { board: BOARD, session, tag, a: pair[0].n, b: pair[1].n, pick, pair_type: type, ms: Math.min(3600000, Math.round(ms)) };
  const r = await fetch(API + '/vote_picks', { method: 'POST', headers: { apikey: KEY, 'Content-Type': 'application/json', Prefer: 'return=minimal' }, body: JSON.stringify(row) });
  if (!r.ok) throw new Error('save ' + r.status);
}
// After a vote saves: this device's tally, and the counts the pairing uses (refreshed every 25 votes).
function noteVote(pair) {
  const n = myVotes() + 1; mine = n; store.set('dv_votes', String(n));
  COUNTS[pair[0].n] = (COUNTS[pair[0].n] || 0) + 1; COUNTS[pair[1].n] = (COUNTS[pair[1].n] || 0) + 1;
  if (++sinceCounts >= 25) loadCounts();
  return n;
}
async function share(a, b) {
  const r = await fetch(API + '/rpc/vote_share', { method: 'POST', headers: { apikey: KEY, 'Content-Type': 'application/json' }, body: JSON.stringify({ p_a: a, p_b: b }) });
  if (!r.ok) throw new Error('share ' + r.status);
  const j = await r.json(); const x = Array.isArray(j) ? j[0] : j;
  return [Number(x.a_votes) || 0, Number(x.b_votes) || 0];
}
const myVotes = () => Math.max(mine, Number(store.get('dv_votes') || 0) || 0);
// Real (non-skip) votes on this board: every vote adds one to each of its two items. null until counts load.
function total() {
  if (!haveCounts) return null;
  let t = 0; for (const k in COUNTS) t += COUNTS[k];
  return Math.round(t / 2);
}

window.DV = {
  ITEMS, BOARD, GOAL, store, loadCounts, pickPair, save, noteVote, share, myVotes, total, crowdOrder, pos: () => POS,
  setOwner() { tag = 'owner'; store.set('dv_tag', 'owner'); },
};
})();
