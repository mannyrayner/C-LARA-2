/* Only a seed, IDs and progress are kept, in this tab, for at most two hours.
   Dictionary text, media and recordings are fetched afresh on every return. */
(() => {
  'use strict';
  const prefix = 'community-game:', lifetime = 2 * 60 * 60 * 1000;
  const validToken = value => /^[0-9a-f]{32}$/.test(value || '');
  const forget = token => { try { sessionStorage.removeItem(prefix + token); } catch (_) {} };
  function load(token, scope, category) {
    if (!validToken(token)) return null;
    try {
      const value = JSON.parse(sessionStorage.getItem(prefix + token));
      if (!value || value.version !== 1 || value.scope !== scope || value.category !== category ||
          !Number.isFinite(value.saved) || value.saved > Date.now() || Date.now() - value.saved > lifetime) {
        forget(token); return null;
      }
      return value;
    } catch (_) { forget(token); return null; }
  }
  function save(token, scope, category, state) {
    if (!validToken(token)) return false;
    try {
      for (const key of Object.keys(sessionStorage)) {
        if (!key.startsWith(prefix)) continue;
        try {
          const old = JSON.parse(sessionStorage.getItem(key));
          if (!old || old.scope !== scope || Date.now() - old.saved > lifetime) sessionStorage.removeItem(key);
        } catch (_) { sessionStorage.removeItem(key); }
      }
      // Whitelist progress rather than serializing the game response/DOM.
      const value = {version: 1, scope, category, saved: Date.now(),
        seed: state.seed, revision: state.revision, kind: state.kind, mode: state.mode, style: state.style,
        queue: state.queue, total: state.total, learned: state.learned, current: state.current,
        revealed: state.revealed, solved: state.solved, paths: state.paths,
        mcWrong: state.mcWrong, mcOutcome: state.mcOutcome, mcFirst: state.mcFirst,
        enlarged: state.enlarged, scroll: state.scroll};
      const encoded = JSON.stringify(value);
      if (encoded.length > 16000) return false;
      sessionStorage.setItem(prefix + token, encoded);
      return true;
    } catch (_) { return false; }
  }
  function token() {
    return [...crypto.getRandomValues(new Uint8Array(16))].map(x => x.toString(16).padStart(2, '0')).join('');
  }
  window.CommunityPracticeSession = {load, save, forget, token};
})();
