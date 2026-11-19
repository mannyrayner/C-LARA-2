/* The shared recorder/draft code owns media and recovery. Hidden modes are disabled. */
(() => {
  'use strict';
  const form = document.querySelector('[data-picture-practice]');
  if (!form) return;
  const gettext = window.gettext || (s => s);
  function update() {
    const voice = form.elements.mode.value === 'voice';
    ['type', 'speak', 'audio-options'].forEach(kind => {
      const panel = form.querySelector(`[data-practice-${kind}]`);
      const show = kind !== 'type' ? voice : !voice;
      panel.hidden = !show;
      panel.disabled = !show;
    });
    const button = form.querySelector('[data-save-submit]');
    button.textContent = gettext('Get feedback');
  }
  form.addEventListener('change', update);
  form.addEventListener('community-draft-ready', update);
  update();

  const hints = form.querySelector('[data-practice-hints]');
  if (!hints) return;
  const usage = form.elements.hints_used;
  const player = hints.querySelector('[data-hint-player]');
  const stopButton = hints.querySelector('[data-hint-stop]');
  const status = hints.querySelector('[data-hint-status]');
  let playlist = [], position = 0, activeKind = '', revision = 0;
  if (!usage.value) usage.value = '[]';
  function used(kind) {
    let values;
    try { values = JSON.parse(usage.value); } catch (_) { values = []; }
    if (!Array.isArray(values)) values = [];
    if (values.includes(kind)) return;
    usage.value = JSON.stringify([...values, kind]);
    form.dispatchEvent(new Event('community-practice-hint-used'));
  }
  hints.querySelectorAll('[data-hint-reveal]').forEach(button => {
    const kind = button.dataset.hintReveal;
    const text = hints.querySelector(`[data-hint-text="${kind}"]`);
    const label = button.textContent;
    text.hidden = true;
    button.hidden = false;
    button.addEventListener('click', () => {
      text.hidden = !text.hidden;
      button.setAttribute('aria-expanded', String(!text.hidden));
      button.textContent = text.hidden ? label : gettext(kind === 'words' ? 'Hide words' : 'Hide sentence');
      if (!text.hidden) used(`${kind}_text`);
    });
  });
  function stop() {
    revision++;
    playlist = [];
    activeKind = '';
    player.pause();
    player.hidden = true;
    stopButton.hidden = true;
    status.hidden = true;
  }
  function failed() {
    playlist = [];
    status.textContent = gettext('This recording could not play. Try the player controls.');
    status.hidden = false;
  }
  async function play() {
    const current = revision;
    player.src = playlist[position];
    player.hidden = false;
    stopButton.hidden = false;
    try { await player.play(); }
    catch (error) { if (current === revision && error.name !== 'AbortError') failed(); }
  }
  // Record actual playback, not a failed request to play. Native controls can
  // resume a clip if a phone blocks the next clip's automatic continuation.
  player.addEventListener('playing', () => {
    if (activeKind) used(`${activeKind}_audio`);
    status.hidden = true;
  });
  player.addEventListener('error', () => { if (activeKind) failed(); });
  player.addEventListener('ended', () => {
    if (position + 1 < playlist.length) {
      position++;
      void play();
    } else { playlist = []; stopButton.hidden = true; }
  });
  hints.querySelectorAll('[data-hint-listen]').forEach(button => {
    const kind = button.dataset.hintListen;
    const sources = [...hints.querySelectorAll(`[data-hint-source="${kind}"]`)].map(audio => audio.src);
    button.hidden = false;
    button.addEventListener('click', () => {
      if (form.querySelector('[data-record]')?.classList.contains('recording-now')) {
        status.textContent = gettext('Stop recording before listening to a hint.');
        status.hidden = false;
        return;
      }
      stop();
      playlist = sources;
      position = 0;
      activeKind = kind;
      if (playlist.length) void play();
    });
  });
  hints.querySelectorAll('[data-hint-fallback]').forEach(el => { el.hidden = true; });
  stopButton.addEventListener('click', stop);
  hints.addEventListener('toggle', () => { if (!hints.open) stop(); });
  form.querySelector('[data-record]')?.addEventListener('click', stop);
  form.addEventListener('submit', stop);
  window.addEventListener('pagehide', stop);
  document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
})();
