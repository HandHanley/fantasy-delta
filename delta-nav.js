/* DELTA — bottom navigation bar for phones (redesign step 2, 31 Oct 2026, owner-approved plan).
 *
 * ONE source for how the bar looks, loaded by index.html, player.html, cfb-player.html and live.html.
 *   - index.html already has the phone section switcher (.seg, shown below 760px, wired to
 *     setSection() and the What's New dots). This file only styles it and adds icons; it never
 *     rewires it.
 *   - The other three pages have no switcher, so this file adds one: four links back to the
 *     main page's sections (index.html?sec=…) and to Live.
 * Phones only (below 760px, the same line the .seg/.eyebrow switch already uses). Desktop keeps
 * the top bar. Colours are tokens only; every page defines them in its own :root.
 *
 * Skipped inside a frame: live.html opens player cards in an iframe sheet, and a second bar
 * inside that sheet would read as broken.
 */
(function () {
  'use strict';
  if (window.__dlNav) return; window.__dlNav = true;
  var framed = false; try { framed = window.self !== window.top; } catch (e) { framed = true; }

  var ICON = {
    nfl:  'M12 3.5 L4 19.5 L20 19.5 Z M12 9 L12 19.5',
    cfb:  'M12 3.5 L4 19.5 L20 19.5 Z',
    me:   'M5 20 c0-3.6 3.1-5.6 7-5.6 s7 2 7 5.6 M12 11.6 a3.9 3.9 0 1 0 0-7.8 a3.9 3.9 0 1 0 0 7.8',
    live: 'M3 12.5 h3.6 l2.6 -6.5 l4.4 13 l2.6 -6.5 h4.8'
  };
  function svg(k) {
    return '<svg class="dl-bn-ic" width="24" height="24" viewBox="0 0 24 24" aria-hidden="true">'
      + '<path d="' + ICON[k] + '"/></svg>';
  }

  var CSS = ''
    /* Full-screen layout (viewport-fit=cover) lets a phone turned sideways put the notch over the
       page; this keeps content clear of it. Zero on phones without a notch and on desktop. */
    + 'html{padding-left:env(safe-area-inset-left,0px);padding-right:env(safe-area-inset-right,0px)}'
    + '@media (max-width:759px){'
    /* the bar. Bottom padding is the home-line area less 12px (owner, 31 Oct: the full 34px left
       too much empty space under the labels on an iPhone). Apple's own tab bars overlap that area
       the same way; the labels still end well above the home line. */
    + '.seg.dl-bnav{position:fixed;left:0;right:0;bottom:0;z-index:30;display:flex;margin:0;gap:0;'
    +   'padding:4px max(6px,env(safe-area-inset-right)) max(4px,calc(env(safe-area-inset-bottom) - 12px)) max(6px,env(safe-area-inset-left));'
    +   'background:var(--ink-2);border:0;border-top:1px solid var(--line);border-radius:0;'
    +   'box-shadow:0 -10px 24px var(--ink)}'
    + '.seg.dl-bnav .seg-btn{flex:1;position:relative;display:flex;flex-direction:column;align-items:center;justify-content:center;'
    +   'gap:2px;min-height:52px;padding:4px 2px !important;border:0;border-radius:10px;background:none !important;'
    +   'color:var(--fog);font-family:var(--sans);font-size:11px;font-weight:700;letter-spacing:.01em;text-decoration:none;cursor:pointer}'
    + '.seg.dl-bnav .seg-btn.on{color:var(--teal-br)}'
    + '.seg.dl-bnav .seg-btn:focus-visible{outline:2px solid var(--teal-br);outline-offset:-2px}'
    + '.dl-bn-ic{display:block;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}'
    + '.seg.dl-bnav .seg-btn .dl-nw-dot{top:5px;right:calc(50% - 19px);width:7px;height:7px}'
    /* room for it at the end of every page */
    + '.dl-bn-space{display:block;height:calc(72px + max(0px,calc(env(safe-area-inset-bottom) - 12px)))}'
    + '}'
    + '@media (min-width:760px){.dl-bn-space,.dl-bnav-added{display:none !important}}';

  function addStyle() {
    var s = document.createElement('style'); s.id = 'dl-bnav-css'; s.textContent = CSS;
    (document.head || document.documentElement).appendChild(s);
  }
  function addSpace() {
    if (document.querySelector('.dl-bn-space')) return;
    var d = document.createElement('div'); d.className = 'dl-bn-space'; d.setAttribute('aria-hidden', 'true');
    document.body.appendChild(d);
  }

  /* index.html: dress the existing switcher. Labels stay text nodes, so setSection(),
     dlNewsSeenArm() and the What's New dots keep working untouched. */
  function dressIndex(seg) {
    seg.classList.add('dl-bnav');
    seg.querySelectorAll('.seg-btn').forEach(function (b) {
      if (b.querySelector('.dl-bn-ic')) return;
      var k = b.getAttribute('data-sec') || b.getAttribute('data-arm');
      if (!ICON[k]) return;
      var label = document.createElement('span'); label.className = 'dl-bn-l';
      while (b.firstChild) label.appendChild(b.firstChild);
      b.insertAdjacentHTML('afterbegin', svg(k)); b.appendChild(label);
    });
  }

  /* player.html / cfb-player.html / live.html: add a bar of plain links. */
  function addBar(active) {
    var items = [['nfl', 'NFL', 'index.html?sec=nfl'], ['cfb', 'College', 'index.html?sec=cfb'],
                 ['me', 'My Team', 'index.html?sec=me'], ['live', 'Live', 'live.html']];
    var nav = document.createElement('nav');
    nav.className = 'seg dl-bnav dl-bnav-added'; nav.setAttribute('aria-label', 'Sections');
    nav.innerHTML = items.map(function (it) {
      var on = it[0] === active;
      return '<a class="seg-btn' + (on ? ' on' : '') + '" href="' + it[2] + '"' + (on ? ' aria-current="page"' : '') + '>'
        + svg(it[0]) + '<span class="dl-bn-l">' + it[1] + '</span></a>';
    }).join('');
    document.body.appendChild(nav);
  }

  function init() {
    if (framed) return;
    addStyle();
    var seg = document.querySelector('.seg');
    if (seg) dressIndex(seg);
    else addBar(document.documentElement.getAttribute('data-dl-sec') || 'nfl');
    addSpace();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
