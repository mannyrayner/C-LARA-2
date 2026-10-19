/* Warn about unsaved judgements without retaining private material on this device. */
(() => {
  const gettext = window.gettext || (message => message);
  const form = document.querySelector('[data-evaluation-form]');
  if (!form) return;
  let dirty = false;
  const status = form.querySelector('[data-evaluation-save-state]');
  form.addEventListener('input', () => {
    dirty = true;
    if (status) status.textContent = gettext('Unsaved judgements. Choose Save and next before leaving.');
  });
  form.addEventListener('submit', () => { dirty = false; });
  window.addEventListener('beforeunload', event => {
    if (dirty) { event.preventDefault(); event.returnValue = ''; }
  });
})();
