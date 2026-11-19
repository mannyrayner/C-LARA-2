/* The shared recorder/draft code owns media and recovery. Hidden modes are disabled. */
(() => {
  'use strict';
  const form = document.querySelector('[data-picture-practice]');
  if (!form) return;
  const gettext = window.gettext || (s => s);
  function update() {
    const voice = form.elements.mode.value === 'voice';
    ['type', 'speak'].forEach(kind => {
      const panel = form.querySelector(`[data-practice-${kind}]`);
      const show = kind === 'speak' ? voice : !voice;
      panel.hidden = !show;
      panel.disabled = !show;
    });
    const button = form.querySelector('[data-save-submit]');
    button.textContent = voice ? gettext('Check what I said') : gettext('Get feedback');
  }
  form.addEventListener('change', update);
  form.addEventListener('community-draft-ready', update);
  update();
})();
