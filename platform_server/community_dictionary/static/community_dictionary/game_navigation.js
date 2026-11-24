/* Carry a game return through word, sentence and picture visits only. */
(() => {
  'use strict';
  const control = document.querySelector('[data-game-return]');
  if (!control) return;
  const prefixes = [control.dataset.wordPrefix, control.dataset.entryPrefix];
  document.querySelectorAll('a[href]').forEach(link => {
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin || !prefixes.some(prefix =>
      url.pathname.startsWith(prefix) && /^\d+\/$/.test(url.pathname.slice(prefix.length)))) return;
    url.searchParams.set('return_game', control.dataset.token);
    url.searchParams.set('game_category', control.dataset.category);
    link.href = url.href;
  });
})();
