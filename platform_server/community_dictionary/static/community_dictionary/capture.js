/* Store only UI preferences here; app.js owns recoverable picture/audio drafts. */
(() => {
  'use strict';
  document.querySelectorAll('[data-capture-form], [data-capture-choice]').forEach(form => {
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
    const modeKey = `${key}:mode`;
    if (form.dataset.choiceFixed !== 'yes') {
      try {
        const remembered = localStorage.getItem(modeKey);
        if (['text', 'voice', 'ai'].includes(remembered)) mode.value = remembered;
      } catch (_) {}
    }
    function inputChoice() {
      for (const value of ['text', 'voice', 'ai']) {
        const panel = form.querySelector(`[data-description-${value}]`);
        if (panel) panel.hidden = mode.value !== value;
      }
      const label = form.querySelector('[data-description-language-label]');
      if (label) label.textContent = mode.value === 'ai' ? 'Language for feedback' : 'Language I am using';
    }
    form.querySelectorAll('[name="input_mode"]').forEach(input => input.addEventListener('change', () => {
      try { localStorage.setItem(modeKey, mode.value); } catch (_) {}
      inputChoice();
    }));
    inputChoice();
    // Draft recovery is asynchronous. Its selected radio takes precedence.
    form.addEventListener('community-draft-ready', inputChoice);
  });
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
    let timer;
    const began = Date.now();
    function stopped(message) {
      clearTimeout(timer);
      process.querySelector('[data-process-status]').textContent = message;
      process.querySelector('button').disabled = false;
      busy = false;
    }
    function poll(url) {
      if (Date.now() - began >= 180000) {
        stopped('Audio is still pending. You can continue to another picture, refresh its status later, or use Continue creating audio.');
        return;
      }
      timer = setTimeout(() => refresh(url).catch(() => {
        stopped('Could not refresh the audio status. Your saved picture is safe. Reload to check progress.');
      }), 2000);
    }
    async function refresh(url) {
      const current = document.querySelector('[data-capture-stage]');
      if (!vocabulary && current?.dataset.captureStage !== 'saved') {
        location.replace(url); return; // Interpretation finished: show its preview once.
      }
      // GET only: polling never starts or repeats a paid request. Update audio
      // in place, retaining edits, scroll position, open translations and players
      // whose recording has not changed.
      const response = await fetch(url, {credentials:'same-origin'});
      if (!response.ok) throw new Error('Could not refresh the audio status.');
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (!page.querySelector('[data-capture-stage]')) throw new Error('This preview is no longer available. Reload to view the current entry.');
      for (const selector of ['[data-capture-feedback]', '[data-capture-audio-status]']) {
        const old = document.querySelector(selector), fresh = page.querySelector(selector);
        if (old && fresh && old.innerHTML !== fresh.innerHTML) old.replaceWith(fresh);
      }
      if (!vocabulary) {
        page.querySelectorAll('[data-word-row]').forEach(fresh => {
          const old = document.querySelector(`[data-word-row][data-entry-id="${fresh.dataset.entryId}"]`);
          if (old && old.dataset.audioId !== fresh.dataset.audioId) {
            const translation = fresh.querySelector('details');
            if (translation) translation.open = !!old.querySelector('details')?.open;
            old.replaceWith(fresh);
          }
        });
        document.dispatchEvent(new Event('community-audio-updated'));
      }
      if (page.querySelector('[data-capture-process]')) {
        process.querySelector('[data-process-status]').textContent = 'Audio is being prepared in the background. You can continue using this page or go to the next picture.';
        process.querySelector('button').disabled = false; busy = false;
        poll(url);
      } else {
        clearTimeout(timer);
        process.remove();
        busy = false;
      }
    }
    async function run(event) {
      event?.preventDefault(); if (busy) return;
      clearTimeout(timer);
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
      process.querySelector('[data-process-status]').textContent = 'Audio is being prepared in the background. You can go to the next picture.';
      poll(location.href);
    }
  }
})();
