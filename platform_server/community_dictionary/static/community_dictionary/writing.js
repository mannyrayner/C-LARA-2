/* GET-only progress checks. Never repeat paid work when a mobile page resumes. */
(() => {
  'use strict';
  const gettext = window.gettext || (s => s);
  const draft = document.querySelector('[data-writing-draft]');
  if (draft) {
    let dirty = false;
    draft.addEventListener('input', () => { dirty = true; });
    draft.addEventListener('submit', () => { dirty = false; });
    window.addEventListener('beforeunload', event => {
      if (dirty) { event.preventDefault(); event.returnValue = ''; }
    });
  }
  const state = document.querySelector('[data-writing-state]');
  if (state?.dataset.poll !== 'yes') return;
  const began = Date.now();
  const fingerprint = element => element.textContent.replace(/\s+/g, ' ').trim();
  async function poll() {
    if (Date.now() - began > 300000) return;
    if (document.hidden || [...document.querySelectorAll('audio')].some(a => !a.paused)) {
      setTimeout(poll, 4000); return;
    }
    try {
      const response = await fetch(location.href, {credentials: 'same-origin', cache: 'no-store'});
      if (!response.ok) throw new Error();
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      const fresh = page.querySelector('[data-writing-state]');
      if (!fresh) throw new Error();
      if (fresh.dataset.writingState !== state.dataset.writingState ||
          fresh.dataset.poll !== state.dataset.poll || fingerprint(fresh) !== fingerprint(state)) {
        location.reload(); return;
      }
      setTimeout(poll, 4000);
    } catch (_) {
      const status = document.querySelector('[data-writing-status]');
      if (status) status.append(document.createTextNode(' ' + gettext('Refresh to check progress. Your saved writing is safe.')));
    }
  }
  setTimeout(poll, 2000);
})();
