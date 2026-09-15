/* Theme button for the landing page.

   Not app.js: that file builds a router over the guide's markup and throws
   here. Same storage key, so a choice made on either page holds on both. */
(function () {
  'use strict';
  var KEY = 'resops-guide';
  var btn = document.getElementById('theme');
  if (!btn) { return; }
  var root = document.documentElement;

  function isDark() {
    var set = root.getAttribute('data-theme');
    if (set) { return set === 'dark'; }
    return window.matchMedia &&
           window.matchMedia('(prefers-color-scheme: dark)').matches;
  }
  function label() {
    var dark = isDark();
    btn.setAttribute('aria-pressed', dark ? 'true' : 'false');
    btn.setAttribute('aria-label',
      dark ? 'Switch to light theme' : 'Switch to dark theme');
  }

  btn.addEventListener('click', function () {
    var next = isDark() ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try {
      var state = JSON.parse(localStorage.getItem(KEY)) || {};
      state.theme = next;
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch (e) { /* private mode: the choice holds for this page only */ }
    label();
  });

  if (window.matchMedia) {
    var mq = window.matchMedia('(prefers-color-scheme: dark)');
    var onChange = function () {
      if (!root.getAttribute('data-theme')) { label(); }
    };
    if (mq.addEventListener) { mq.addEventListener('change', onChange); }
    else if (mq.addListener) { mq.addListener(onChange); }
  }
  label();
}());
