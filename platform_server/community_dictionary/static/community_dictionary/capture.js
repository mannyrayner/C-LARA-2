/* Store only UI preferences here; app.js owns recoverable picture/audio drafts. */
(() => {
  'use strict';
  const form = document.querySelector('[data-capture-form]');
  if (form) {
    const method = form.querySelector('[data-picture-method]');
    const key = `community-capture:${document.body.dataset.user}:${form.dataset.dictionary}`;
    if (method) {
      try { method.value = localStorage.getItem(key) || 'camera'; } catch (_) {}
      function pictureChoice() {
        form.querySelector('[data-camera-choice]').hidden = method.value !== 'camera';
        form.querySelector('[data-upload-choice]').hidden = method.value !== 'upload';
        try { localStorage.setItem(key, method.value); } catch (_) {}
      }
      method.addEventListener('change', pictureChoice); pictureChoice();
    }
    const mode = form.elements.input_mode;
    function inputChoice() {
      form.querySelector('[data-description-text]').hidden = mode.value !== 'text';
      form.querySelector('[data-description-voice]').hidden = mode.value !== 'voice';
    }
    mode.addEventListener('change', inputChoice); inputChoice();
    // Draft recovery completes asynchronously; app.js sends this after restoring fields.
    form.addEventListener('community-draft-ready', inputChoice);
  }
  const vocabulary = document.querySelector('[data-vocabulary-form]');
  let vocabularyDirty = false;
  if (vocabulary) {
    function summarize() {
      const words = [...vocabulary.querySelectorAll('[data-vocabulary-rows] [data-vocabulary-row]')]
        .filter(row => !row.querySelector('[name$="-DELETE"]').checked)
        .map(row => row.querySelector('[name$="-lemma"]').value.trim()).filter(Boolean);
      vocabulary.querySelector('[data-vocabulary-summary]').textContent = words.join(' · ');
    }
    summarize();
    vocabulary.addEventListener('input', () => { vocabularyDirty = true; summarize(); });
    vocabulary.addEventListener('submit', () => { vocabularyDirty = false; });
    window.addEventListener('beforeunload', event => {
      if (vocabularyDirty) { event.preventDefault(); event.returnValue = ''; }
    });
    vocabulary.querySelector('[data-add-word]').addEventListener('click', event => {
      event.preventDefault();
      const rows = vocabulary.querySelector('[data-vocabulary-rows]');
      // Reuse the empty extra row, or a row marked for deletion, before adding.
      for (const row of rows.querySelectorAll('[data-vocabulary-row]')) {
        const lemma = row.querySelector('[name$="-lemma"]');
        const deletion = row.querySelector('[name$="-DELETE"]');
        if (deletion.checked || !lemma.value.trim()) {
          if (deletion.checked) row.querySelectorAll('input:not([type="checkbox"])').forEach(input => { input.value = ''; });
          deletion.checked = false; lemma.focus(); vocabularyDirty = true; summarize(); return;
        }
      }
      const total = vocabulary.elements['words-TOTAL_FORMS'];
      const count = Number(total.value);
      if (count >= 12) {
        vocabulary.querySelector('[data-vocabulary-status]').textContent = 'Keep up to 12 words or expressions for this picture.'; return;
      }
      rows.insertAdjacentHTML('beforeend', vocabulary.querySelector('[data-vocabulary-template]').innerHTML.replaceAll('__prefix__', String(count)));
      total.value = String(count + 1); vocabularyDirty = true;
      rows.lastElementChild.querySelector('[name$="-lemma"]').focus();
    });
  }
  const process = document.querySelector('[data-capture-process]');
  if (process) {
    let busy = false;
    const began = Date.now();
    async function refresh(url) {
      if (!vocabulary) { location.replace(url); return; }
      // Voice feedback may finish while the learner is editing. Update only
      // that panel: never reload and discard their vocabulary corrections.
      const response = await fetch(url, {credentials:'same-origin'});
      if (!response.ok) throw new Error('Could not refresh the spoken confirmation.');
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      const feedback = page.querySelector('[data-capture-feedback]');
      if (feedback) document.querySelector('[data-capture-feedback]').replaceWith(feedback);
      if (page.querySelector('[data-capture-process]')) {
        if (Date.now() - began < 180000) setTimeout(() => refresh(url).catch(() => {}), 2000);
        else {
          process.querySelector('[data-process-status]').textContent = 'Spoken feedback is still pending. You can keep editing or use the written confirmation.';
          process.querySelector('button').disabled = false; busy = false;
        }
      } else {
        process.remove();
        busy = false;
      }
    }
    async function run(event) {
      event?.preventDefault(); if (busy) return;
      busy = true;
      const button = process.querySelector('button');
      const status = process.querySelector('[data-process-status]');
      const data = new FormData(process); data.set('action', 'process');
      button.disabled = true; status.textContent = 'Working… Your saved picture is safe. Audio continues in the background when the worker is running.';
      try {
        const response = await fetch(process.getAttribute('action'), {method:'POST', body:data, credentials:'same-origin', headers:{Accept:'application/json'}});
        const result = await response.json();
        if (!response.ok || !result.saved) throw new Error(result.error || 'The request could not finish.');
        await refresh(result.url);
      } catch (error) {
        status.textContent = `${error.message || 'Connection interrupted.'} Reload to check the result; an in-flight request will not be repeated automatically.`;
        button.disabled = false; busy = false;
      }
    }
    process.addEventListener('submit', run);
    if (process.dataset.auto === 'yes') void run();
    else {
      const key = `capture-poll:${location.pathname}`;
      let began = Date.now();
      try {
        began = Number(sessionStorage.getItem(key)) || began;
        sessionStorage.setItem(key, String(began));
      } catch (_) {}
      process.querySelector('[data-process-status]').textContent = 'Audio is being prepared in the background. You can go to the next picture.';
      if (Date.now() - began < 180000) setTimeout(() => refresh(location.href).catch(() => {}), 2000);
    }
  }
})();
