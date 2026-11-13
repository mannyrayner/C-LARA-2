/* Creation defaults follow language capabilities until the owner chooses. */
(() => {
  'use strict';
  const form = document.querySelector('form[data-dictionary-create]');
  const data = document.getElementById('dictionary-ai-languages');
  if (!form || !data || form.dataset.bound === 'true') return;
  const supported = new Set(JSON.parse(data.textContent));
  const controls = form.elements;
  const touched = new Set();
  const names = ['image_generation_enabled', 'sentence_capture_enabled'];
  names.forEach(name => controls[name].addEventListener('change', () => touched.add(name)));
  const known = value => supported.has(value.trim().toLowerCase());
  const update = () => {
    const language = controls.language.value.trim();
    const available = !language || known(language);
    if (!touched.has(names[0])) controls[names[0]].checked = available;
    if (!touched.has(names[1])) {
      controls[names[1]].checked = available && controls.tts_enabled.checked &&
        known(controls.explanation_language.value.trim() || 'English');
    }
  };
  [controls.language, controls.explanation_language].forEach(control => {
    control.addEventListener('input', update);
    control.addEventListener('change', update);
  });
  controls.tts_enabled.addEventListener('change', update);
  // Keep the server-rendered initial choices until the language is edited.
})();
