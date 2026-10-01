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

  document.querySelectorAll('[data-word-row]').forEach(row => {
    const audio = row.querySelector('[data-word-audio]');
    const button = row.querySelector('[data-word-listen]');
    const status = row.querySelector('[data-word-playback-status]');
    if (!audio || !button) return;
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
})();
