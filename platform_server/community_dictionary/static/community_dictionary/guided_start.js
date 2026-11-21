/* Route controls only. The existing draft/recorder code owns recovery and upload. */
(() => {
  'use strict';
  const gettext = window.gettext || (s => s);
  const form = document.querySelector('[data-guided-start]');
  if (!form) return;
  const languages = JSON.parse(document.getElementById('guided-language-codes')?.textContent || '{}');
  function update() {
    const words = form.elements.start_with?.value === 'words';
    const voice = form.elements.words_mode?.value === 'voice';
    const panels = {'guided-picture': !words, 'guided-words': words,
      'guided-type': !voice, 'guided-speak': voice,
      'guided-custom': form.elements.picture_style?.value === 'custom'};
    Object.entries(panels).forEach(([key, show]) => {
      const panel = form.querySelector(`[data-${key}]`);
      if (panel) {
        panel.hidden = !show;
        // Hidden controls still participate in native browser validation.
        // A disabled fieldset excludes its entire inactive route from both
        // validation and FormData, while retaining its recoverable draft.
        panel.disabled = !show;
      }
    });
    const button = form.querySelector('[data-words-submit]');
    if (button) button.textContent = voice ? gettext('Check my words') : gettext('Generate picture');
    const input = form.elements.words;
    if (input) input.lang = languages[form.elements.words_language?.value] || '';
    // Save and leave uses this marker to submit the currently visible route.
    form.querySelectorAll('[data-save-submit]').forEach(b => b.removeAttribute('data-save-submit'));
    const active = words ? button : form.querySelector('[data-guided-picture] button:not([type])');
    active?.setAttribute('data-save-submit', '');
  }
  form.addEventListener('change', update);
  form.addEventListener('community-draft-ready', update);
  update();
})();
