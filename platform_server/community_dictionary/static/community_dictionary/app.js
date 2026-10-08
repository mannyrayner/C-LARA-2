/* Local drafts are recovery copies, not confirmation of a dictionary save. */
(() => {
  'use strict';
  let database;
  const openDatabase = () => {
    if (!database) database = new Promise((resolve, reject) => {
      if (!window.indexedDB) return reject(new Error('Local storage unavailable'));
      const request = indexedDB.open('clara-community-drafts', 1);
      request.onupgradeneeded = () => request.result.createObjectStore('drafts');
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
      request.onblocked = () => reject(new Error('Close another open dictionary tab and reload.'));
    });
    return database;
  };
  async function draftOperation(key, action, value) {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction('drafts', action === 'get' ? 'readonly' : 'readwrite');
      const store = transaction.objectStore('drafts');
      const request = action === 'get' ? store.get(key) : action === 'put' ? store.put(value, key) : store.delete(key);
      transaction.oncomplete = () => resolve(request.result);
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error);
    });
  }
  document.querySelectorAll('form[data-confirm]').forEach(form => form.addEventListener('submit', event => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  }));

  document.querySelectorAll('[data-draft-form]').forEach(async form => {
    const key = `${document.body.dataset.user}:${new URL(form.action).pathname}:${location.search}`;
    const status = message => form.querySelectorAll('[data-draft-status], [data-save-status]').forEach(el => { el.textContent = message; });
    const error = form.querySelector('[data-submit-error]');
    const files = {};
    const previews = {};
    // dirty means not saved to the SERVER. IndexedDB persistence never clears it.
    let timer, dirty = false, sending = false, ready = false, recorder, leaving = false, confirmed = false;
    let revision = 0, writes = Promise.resolve(), afterSave = null;
    const initialControls = Array.from(form.elements).map(el => [el, el.disabled]);
    initialControls.forEach(([el]) => { el.disabled = true; });
    form.addEventListener('submit', event => { if (!ready) event.preventDefault(); });
    const tellError = message => { error.textContent = message; error.hidden = false; error.focus(); };
    const clearError = () => { error.hidden = true; error.textContent = ''; };
    const fields = () => Array.from(form.elements).filter(el => el.name && !['file', 'submit', 'button'].includes(el.type) && el.name !== 'csrfmiddlewaretoken' && (el.type !== 'radio' || el.checked));
    const snapshot = () => ({values: fields().map(el => [el.name, el.type === 'checkbox' ? el.checked : el.value]), files: {...files}, updated: Date.now()});
    async function persist(force = false) {
      clearTimeout(timer);
      if (!ready || !dirty || (sending && !force)) return;
      const version = revision, value = snapshot();
      // Serialize writes so an older snapshot cannot replace a newer draft or
      // reappear after a confirmed save/discard has deleted it.
      const write = writes.then(() => draftOperation(key, 'put', value));
      writes = write.catch(() => {});
      try {
        await write;
        if (!sending && !leaving && version === revision) status('Not saved to the dictionary yet. A recovery draft is stored on this device. Choose Save when ready.');
      } catch (_) {
        if (!sending && !leaving) status('Not saved. Draft recovery is unavailable on this device. Keep this page open and choose Save.');
      }
    }
    function changed() {
      dirty = true; revision += 1;
      if (!sending) status('Not saved to the dictionary. Preparing a recovery draft…');
      clearTimeout(timer);
      timer = setTimeout(persist, 250);
    }
    function preview(kind) {
      if (previews[kind]) URL.revokeObjectURL(previews[kind]);
      const target = form.querySelector(kind === 'audio' ? '[data-audio-preview]' : '[data-photo-preview]');
      const remove = form.querySelector(kind === 'audio' ? '[data-clear-audio]' : '[data-clear-photo]');
      if (!target) return;
      target.hidden = !files[kind];
      if (remove) remove.hidden = !files[kind];
      if (files[kind]) {
        previews[kind] = URL.createObjectURL(files[kind]);
        target.src = previews[kind];
        const comment = target.closest('[data-recorded-comment]');
        if (comment) comment.open = true;
      } else {
        target.removeAttribute('src');
      }
    }
    async function smallPhoto(file) {
      const url = URL.createObjectURL(file);
      try {
        const image = new Image();
        image.src = url;
        await image.decode();
        const scale = Math.min(1, 1600 / Math.max(image.naturalWidth, image.naturalHeight));
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
        canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
        const context = canvas.getContext('2d');
        context.fillStyle = '#fff';
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', .85));
        return blob ? new File([blob], 'picture.jpg', {type: 'image/jpeg'}) : file;
      } catch (_) {
        return file; // The server will validate and explain unsupported formats.
      } finally { URL.revokeObjectURL(url); }
    }
    form.addEventListener('input', event => { if (event.target.type !== 'file') changed(); });
    form.addEventListener('change', event => { if (event.target.type !== 'file') changed(); });
    let mediaPending = Promise.resolve();
    form.querySelectorAll('input[type=file]').forEach(input => input.addEventListener('change', () => {
      const file = input.files[0];
      if (!file) return;
      const kind = input.name === 'audio' ? 'audio' : 'photo';
      // Retain the original immediately: navigating while a large photo is
      // being resized must already count as unsaved work.
      files[kind] = file; changed(); void persist();
      mediaPending = mediaPending.then(async () => {
        clearError();
        const prepared = kind === 'photo' ? await smallPhoto(file) : file;
        if (files[kind] !== file) return; // Removed or replaced while preparing.
        files[kind] = prepared;
        preview(kind);
        if (files[kind].size > 15 * 1024 * 1024) tellError('This file is larger than 15 MB. Choose a shorter recording or a smaller picture.');
        changed();
        await persist();
      });
    }));
    form.querySelector('[data-clear-photo]')?.addEventListener('click', () => {
      delete files.photo; preview('photo'); form.querySelectorAll('input[name=photo]').forEach(el => { el.value = ''; }); changed();
    });
    form.querySelector('[data-clear-audio]')?.addEventListener('click', () => {
      delete files.audio; preview('audio'); const input = form.querySelector('input[name=audio]'); if (input) input.value = ''; changed();
    });
    try {
      const existing = await draftOperation(key, 'get');
      if (existing) {
        existing.values.forEach(([name, value]) => {
          const element = form.elements.namedItem(name);
          // Old drafts may contain the former consent checkbox. Do not restore
          // its value into the new explicit Save/permission submit button.
          if (element && name !== 'csrfmiddlewaretoken' && !['file', 'submit', 'button'].includes(element.type)) {
            if (element.type === 'checkbox') element.checked = value; else element.value = value;
          }
        });
        Object.assign(files, existing.files);
        preview('photo'); preview('audio');
        dirty = true;
        status('Draft restored on this device. Not confirmed as saved to the dictionary. Choose Save when ready.');
      }
    } catch (_) { status('Draft recovery is unavailable on this device. Keep this page open until you save.'); }
    ready = true;
    form.dispatchEvent(new Event('community-draft-ready'));
    initialControls.forEach(([el, disabled]) => { el.disabled = disabled; });
    const recorderRoot = form.querySelector('[data-recorder]');
    if (recorderRoot && window.CommunityRecorder) {
      recorder = window.CommunityRecorder(recorderRoot, async file => {
        clearError();
        files.audio = file;
        const input = form.querySelector('input[name=audio]');
        if (input) input.value = '';
        preview('audio'); changed(); await persist();
      });
    }
    form.querySelector('[data-discard]')?.addEventListener('click', async () => {
      if (sending) return;
      if (recorder?.busy) { tellError('Finish recording or stop the microphone check first.'); return; }
      if (!confirm('Discard the draft stored on this device? This does not remove anything already saved to the dictionary.')) return;
      sending = true; clearTimeout(timer);
      await mediaPending; clearTimeout(timer); await writes;
      try { await draftOperation(key, 'delete'); }
      catch (_) { sending = false; tellError('Could not remove the recovery draft. Keep editing or try again.'); return; }
      dirty = false; leaving = true; location.reload();
    });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (!ready || sending) return;
      if (recorder?.busy) { afterSave = null; tellError('Finish recording or stop the microphone check before saving.'); return; }
      if (!form.reportValidity()) return;
      clearError();
      const data = new FormData(form);
      // FormData(form) omits the clicked submit button. Its explicit affirmation
      // is required for media uploads, just as on a native (non-JS) submission.
      const submitter = event.submitter || form.querySelector('[data-save-submit]');
      if (submitter?.name) data.set(submitter.name, submitter.value);
      const controls = Array.from(form.elements).map(el => [el, el.disabled]);
      controls.forEach(([el]) => { el.disabled = true; });
      sending = true; dirty = true; clearTimeout(timer);
      status('Saving to the dictionary… waiting for confirmation.');
      const controller = new AbortController();
      let timeout;
      try {
        await mediaPending;
        await persist(true);
        data.delete('photo'); data.delete('audio'); data.delete('camera');
        if (files.photo) data.set('photo', files.photo, files.photo.name || 'picture.jpg');
        if (files.audio) data.set('audio', files.audio, files.audio.name || 'recording.webm');
        if (form.matches('[data-capture-form]')) {
          // Retain unused drafts locally, but send only the chosen input mode.
          if (data.get('input_mode') !== 'voice') data.delete('audio');
          if (data.get('input_mode') !== 'text') data.set('description', '');
        }
        timeout = setTimeout(() => controller.abort(), 60000);
        const response = await fetch(form.action, {method: 'POST', body: data, credentials: 'same-origin', headers: {Accept: 'application/json'}, signal: controller.signal});
        const type = response.headers.get('Content-Type') || '';
        if (!type.includes('application/json')) throw new Error(response.status === 413 ? 'The upload is too large for this server. Try a smaller picture or recording.' : 'Your session may have expired, or the server could not respond. Your draft remains here. Reload or sign in, then retry.');
        const result = await response.json();
        if (!response.ok || !result.saved) throw new Error(result.error || 'The server could not save this yet.');
        try { await draftOperation(key, 'delete'); } catch (_) { /* Replaying the retained token is safe. */ }
        dirty = false; sending = false; confirmed = true; leaving = true;
        status('Saved to the dictionary.');
        if (afterSave) afterSave();
        else location.assign(result.url);
      } catch (exc) {
        tellError(exc.name === 'AbortError' ? 'Confirmation took too long. You can retry safely: the same submission will not be added twice.' : exc.message || 'Connection lost. Keep this page open or restore the draft and retry.');
        status('Not confirmed as saved. Your contribution is still here; choose Save to retry when connected.');
        sending = false; afterSave = null;
        controls.forEach(([el, disabled]) => { el.disabled = disabled; });
      } finally { clearTimeout(timeout); }
    });
    // Links and the POST-only logout form share Save and leave. Browser
    // Back/close/reload use the browser's own warning instead.
    const dialog = document.querySelector('[data-leave-dialog]');
    function guardLeaving(event, leave) {
      if (leaving || !(dirty || sending || recorder?.busy)) return;
      if (!dialog?.showModal) return; // Native beforeunload remains available.
      event.preventDefault();
      if (sending) { tellError('Saving is in progress. Please wait for confirmation.'); return; }
      if (recorder?.busy) { tellError('Finish recording or stop the microphone check before leaving.'); return; }
      if (dialog.open) return;
      const save = form.querySelector('[data-save-submit]') || form.querySelector('button:not([type]), button[type=submit]');
      dialog.querySelector('[data-leave-permission]').hidden = save?.name !== 'consent';
      dialog.querySelector('[data-leave-stay]').onclick = () => dialog.close();
      dialog.querySelector('[data-leave-save]').onclick = () => {
        dialog.close();
        if (!save || !form.reportValidity()) return;
        afterSave = leave;
        form.requestSubmit(save);
      };
      dialog.querySelector('[data-leave-anyway]').onclick = async () => {
        dialog.close();
        sending = true; clearTimeout(timer);
        Array.from(form.elements).forEach(el => { el.disabled = true; });
        await mediaPending; await persist(true); await writes;
        leaving = true; leave();
      };
      dialog.showModal();
    }
    document.addEventListener('click', event => {
      const link = event.target.closest('a[href]');
      if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || link.hasAttribute('download') || (link.target && link.target !== '_self')) return;
      const target = new URL(link.href, location.href);
      if (!['http:', 'https:'].includes(target.protocol) || (target.pathname === location.pathname && target.search === location.search && target.hash)) return;
      guardLeaving(event, () => location.assign(target.href));
    });
    document.addEventListener('submit', event => {
      const logout = event.target;
      if (event.defaultPrevented || !logout.matches('form[data-leave-form]')) return;
      // Submit natively only after the user's decision, retaining CSRF and POST
      // while avoiding a second interception of our own submit event.
      guardLeaving(event, () => HTMLFormElement.prototype.submit.call(logout));
    });
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') void persist();
    });
    window.addEventListener('pagehide', () => { void persist(); });
    window.addEventListener('pageshow', event => {
      if (event.persisted && (confirmed || leaving)) location.reload();
      else if (event.persisted) leaving = false;
    });
    window.addEventListener('beforeunload', event => {
      if (!leaving && (dirty || sending || recorder?.busy)) { event.preventDefault(); event.returnValue = ''; }
    });
  });
})();
