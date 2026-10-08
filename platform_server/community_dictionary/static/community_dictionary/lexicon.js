/* Inline vocabulary controls. Native audio/details remain usable without JS. */
(() => {
  'use strict';
  // Also include the ordinary entry recordings, so words never speak over them.
  function pauseOthers(current) {
    document.querySelectorAll('audio').forEach(audio => {
      if (audio !== current && !audio.paused) audio.pause();
    });
  }
  document.addEventListener('play', event => {
    if (event.target instanceof HTMLAudioElement) pauseOthers(event.target);
  }, true);

  function initialize() {
  document.querySelectorAll('[data-word-row]').forEach(row => {
    const audio = row.querySelector('[data-word-audio]');
    const button = row.querySelector('[data-word-listen]');
    const status = row.querySelector('[data-word-playback-status]');
    if (!audio || !button || row.dataset.audioBound) return;
    row.dataset.audioBound = 'yes';
    const name = row.querySelector('h3').textContent.trim();
    function update() {
      const playing = !audio.paused && !audio.ended;
      button.textContent = playing ? 'Pause' : 'Listen';
      button.setAttribute('aria-label', (playing ? 'Pause ' : 'Listen to ') + name);
      button.setAttribute('aria-pressed', String(playing));
    }
    function failed() {
      status.textContent = 'This recording could not play. Try again, or open the word page for other recordings.';
      status.hidden = false;
      audio.hidden = false;
      update();
    }
    ['play', 'pause', 'ended'].forEach(type => audio.addEventListener(type, update));
    audio.addEventListener('error', failed);
    button.addEventListener('click', async () => {
      status.hidden = true;
      if (!audio.paused) {
        audio.pause();
        return;
      }
      try {
        pauseOthers(audio);
        audio.currentTime = 0;
        await audio.play();
      } catch (error) {
        // Rapidly selecting another word can deliberately interrupt playback.
        if (error.name !== 'AbortError') failed();
      }
    });
    button.hidden = false;
    audio.hidden = true;
  });
  }
  initialize();
  document.addEventListener('community-audio-updated', initialize);

  // Returning from a word/audio page can restore an old browser snapshot after
  // the capture queue has finished. A replacement belongs to the shared entry,
  // not to that finished job: re-read the page without restarting synthesis.
  let refreshing = false;
  let wasHidden = false;
  async function refreshRecordings() {
    if (refreshing || !document.querySelector('[data-word-row]') ||
        document.querySelector('[data-vocabulary-form]')) return;
    refreshing = true;
    try {
      const response = await fetch(location.href, {credentials:'same-origin', cache:'no-store'});
      if (response.redirected || [401,403,404,409].includes(response.status)) {
        // Access or the saved wording changed: let the server choose the page.
        location.reload(); return;
      }
      if (!response.ok) throw new Error('refresh_failed');
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      const rows = new Map([...page.querySelectorAll('[data-word-row]')].map(row => [row.dataset.entryId, row]));
      document.querySelectorAll('[data-word-row]').forEach(old => {
        const fresh = rows.get(old.dataset.entryId);
        if (!fresh) { old.querySelector('audio')?.pause(); old.remove(); return; }
        if (old.dataset.audioId === fresh.dataset.audioId) return;
        const replacement = fresh.cloneNode(true);
        const translation = replacement.querySelector('details');
        if (translation) translation.open = !!old.querySelector('details')?.open;
        // Only a changed recording replaces a row. Other players keep playing.
        old.querySelector('audio')?.pause();
        old.replaceWith(replacement);
      });
      const oldStatus = document.querySelector('[data-capture-audio-status]');
      const freshStatus = page.querySelector('[data-capture-audio-status]');
      if (oldStatus && freshStatus && oldStatus.innerHTML !== freshStatus.innerHTML) oldStatus.replaceWith(freshStatus);
      document.querySelector('[data-audio-refresh-error]')?.remove();
      initialize();
    } catch (_) {
      if (!document.querySelector('[data-audio-refresh-error]')) {
        const message = document.createElement('p');
        message.dataset.audioRefreshError = ''; message.className = 'notice';
        message.setAttribute('role', 'status');
        message.textContent = 'Could not refresh recordings. Reload this page to check for saved audio.';
        document.querySelector('[data-word-row]')?.before(message);
      }
    } finally { refreshing = false; }
  }
  window.addEventListener('pageshow', event => { if (event.persisted) void refreshRecordings(); });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) wasHidden = true;
    else if (wasHidden) { wasHidden = false; void refreshRecordings(); }
  });
})();
