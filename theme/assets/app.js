/* Router, copy, progress. Vanilla JS, no dependencies. Everything
   degrades: no JS = a scrollable document, no localStorage = no resume
   ticks, no clipboard API = execCommand fallback. */
(function () {
  'use strict';

  /* ---- storage, tolerant of file:// profiles that forbid it ---- */
  var KEY = 'resops-guide';
  function load() {
    try { return JSON.parse(localStorage.getItem(KEY)) || {}; }
    catch (e) { return {}; }
  }
  function save(state) {
    try { localStorage.setItem(KEY, JSON.stringify(state)); }
    catch (e) { /* private mode: resume off, everything else works */ }
  }

  /* ---- router ---- */
  var pages = Array.prototype.slice.call(
    document.querySelectorAll('main > .page'));
  var routes = pages.map(function (p) { return p.dataset.route; });
  var navRows = Array.prototype.slice.call(
    document.querySelectorAll('.nav-row'));
  var here = document.getElementById('topbar-here');
  var brandName = document.querySelector('.brand-name').textContent;

  document.documentElement.classList.add('routed');

  function currentIndex() {
    return routes.indexOf(location.hash);
  }

  function show(index) {
    pages.forEach(function (p, k) {
      p.classList.toggle('active', k === index);
    });
    var page = pages[index];
    navRows.forEach(function (r) {
      var active = r.dataset.route === page.dataset.route;
      r.classList.toggle('active', active);
      if (active) { r.setAttribute('aria-current', 'page'); }
      else { r.removeAttribute('aria-current'); }
    });
    /* the Overview is the only page with the aura masthead, and the aura is
       painted on `main` so it can share the topbar's viewport origin. */
    document.documentElement.classList.toggle(
      'at-overview', page.dataset.route === '#/overview');
    here.textContent = page.dataset.title;
    document.title = page.dataset.title + ' · ' + brandName;
    var state = load();
    state.last = page.dataset.route;   // resume-on-reopen, nothing more
    save(state);
    window.scrollTo(0, 0);
  }

  function route() {
    var i = currentIndex();
    if (i === -1) {
      /* no or unknown hash: resume where they were, else start */
      var last = load().last;
      var k = routes.indexOf(last);
      location.replace(routes[k === -1 ? 0 : k]);
      return;
    }
    show(i);
  }

  window.addEventListener('hashchange', route);
  route();

  /* ---- keyboard: mirrors the pager ---- */
  document.addEventListener('keydown', function (e) {
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) { return; }
    var i = currentIndex();
    if (i === -1) { return; }
    if (e.key === 'ArrowRight' && i < routes.length - 1) {
      location.hash = routes[i + 1];
    } else if (e.key === 'ArrowLeft' && i > 0) {
      location.hash = routes[i - 1];
    }
  });

  /* ---- theme. The <head> script already stamped any stored choice before
     the first paint; this only handles pressing the button and keeping the
     label truthful. No third "system" state: the default IS the system, and
     a two-hour workshop does not need a way back to it that clearing site
     data would not give. ---- */
  var themeBtn = document.getElementById('theme');
  if (themeBtn) {
    var root = document.documentElement;

    function systemDark() {
      return window.matchMedia &&
             window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    function isDark() {
      var set = root.getAttribute('data-theme');
      return set ? set === 'dark' : systemDark();
    }
    function label() {
      var dark = isDark();
      themeBtn.setAttribute('aria-pressed', dark ? 'true' : 'false');
      themeBtn.setAttribute(
        'aria-label', dark ? 'Switch to light theme' : 'Switch to dark theme');
    }

    themeBtn.addEventListener('click', function () {
      var next = isDark() ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      var state = load();
      state.theme = next;
      save(state);
      label();
    });

    /* An unchosen reader follows the OS, including when it changes mid-read. */
    if (window.matchMedia) {
      var mq = window.matchMedia('(prefers-color-scheme: dark)');
      var onChange = function () { if (!root.getAttribute('data-theme')) { label(); } };
      if (mq.addEventListener) { mq.addEventListener('change', onChange); }
      else if (mq.addListener) { mq.addListener(onChange); }
    }
    label();
  }

  /* ---- checkpoints. A chapter is done when its checkpoint says so, and
     the sidebar rung is the same fact seen from the navigation. Stored per
     route, so renaming a chapter keeps the tick and reordering does not
     silently move it onto its neighbour.

     Everything here degrades: without localStorage the boxes still tick for
     the session, and without JS at all the checkpoint sentence still reads,
     which is the part that carries the teaching. ---- */
  var boxes = Array.prototype.slice.call(
    document.querySelectorAll('input[data-done]'));
  var tally = document.querySelector('.nav-tally');

  function paint() {
    var state = load();
    var done = state.done || {};
    var count = 0;
    boxes.forEach(function (box) {
      var on = !!done[box.dataset.done];
      box.checked = on;
      if (on) { count += 1; }
    });
    navRows.forEach(function (row) {
      row.classList.toggle('done', !!done[row.dataset.route]);
    });
    if (tally) { tally.querySelector('b').textContent = String(count); }
  }

  boxes.forEach(function (box) {
    box.addEventListener('change', function () {
      var state = load();
      state.done = state.done || {};
      if (box.checked) { state.done[box.dataset.done] = 1; }
      else { delete state.done[box.dataset.done]; }
      save(state);
      paint();
    });
  });

  paint();

  /* ---- copy: the whole command block is the target; the button is the
     affordance, the button text and a border pulse are the feedback. A
     manual text selection never triggers it. ---- */
  function copyText(text, block, button) {
    function done() {
      button.textContent = 'copied';
      block.classList.remove('copied');
      void block.offsetWidth;  /* restart the pulse animation */
      block.classList.add('copied');
      setTimeout(function () { button.textContent = 'copy'; }, 1200);
    }
    function fallback() {
      var ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); } catch (e) { /* quiet */ }
      document.body.removeChild(ta);
      done();
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, fallback);
    } else {
      fallback();
    }
  }

  Array.prototype.slice.call(document.querySelectorAll('[data-copy]'))
    .forEach(function (block) {
      var button = block.querySelector('.copy');
      var code = block.querySelector('code');
      block.addEventListener('click', function (e) {
        var selection = window.getSelection();
        if (selection && selection.toString().length > 0 &&
            e.target !== button) { return; }
        copyText(code.innerText, block, button);
      });
    });
})();
