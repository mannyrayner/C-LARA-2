/* No external services. Media and words stay in the browser until Share succeeds. */
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
    const status = form.querySelector('[data-draft-status]');
    const error = form.querySelector('[data-submit-error]');
    const files = {};
    const previews = {};
    let timer, dirty = false, sending = false, ready = false, recorder;
    const initialControls = Array.from(form.elements).map(el => [el, el.disabled]);
    initialControls.forEach(([el]) => { el.disabled = true; });
    form.addEventListener('submit', event => { if (!ready) event.preventDefault(); });
    const tellError = message => { error.textContent = message; error.hidden = false; };
    const clearError = () => { error.hidden = true; error.textContent = ''; };
    const fields = () => Array.from(form.elements).filter(el => el.name && !['file', 'submit', 'button'].includes(el.type) && el.name !== 'csrfmiddlewaretoken');
    const snapshot = () => ({values: fields().map(el => [el.name, el.type === 'checkbox' ? el.checked : el.value]), files, updated: Date.now()});
    async function persist() {
      clearTimeout(timer);
      if (!ready || sending) return;
      try {
        await draftOperation(key, 'put', snapshot());
        status.textContent = 'Draft saved on this device. Not yet shared. Clearing browser data will remove it.';
        dirty = false;
      } catch (_) {
        status.textContent = 'Local draft saving is unavailable. Keep this page open until your contribution is shared.';
        dirty = true;
      }
    }
    function changed() {
      dirty = true;
      status.textContent = 'Saving draft on this device…';
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
      mediaPending = mediaPending.then(async () => {
        clearError();
        status.textContent = 'Preparing your media…';
        files[kind] = kind === 'photo' ? await smallPhoto(file) : file;
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
          if (element && name !== 'csrfmiddlewaretoken') {
            if (element.type === 'checkbox') element.checked = value; else element.value = value;
          }
        });
        Object.assign(files, existing.files);
        preview('photo'); preview('audio');
        status.textContent = 'Your draft was restored from this device. It has not yet been confirmed as shared.';
      }
    } catch (_) { status.textContent = 'Local draft saving is unavailable. Keep this page open until you share.'; }
    ready = true;
    initialControls.forEach(([el, disabled]) => { el.disabled = disabled; });
    const recorderRoot = form.querySelector('[data-recorder]');
    if (recorderRoot && window.CommunityRecorder) {
      recorder = window.CommunityRecorder(recorderRoot, async file => {
        files.audio = file;
        const input = form.querySelector('input[name=audio]');
        if (input) input.value = '';
        preview('audio'); changed(); await persist();
      });
    }
    form.querySelector('[data-discard]')?.addEventListener('click', async () => {
      if (!confirm('Discard the draft stored on this device? This does not remove anything already shared.')) return;
      try { await draftOperation(key, 'delete'); } catch (_) { /* No stored copy is available. */ }
      dirty = false; location.reload();
    });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (!ready || sending) return;
      if (recorder?.busy) { tellError('Finish recording or stop the microphone check before sharing.'); return; }
      await mediaPending;
      if (!form.reportValidity()) return;
      clearError(); await persist();
      const data = new FormData(form);
      data.delete('photo'); data.delete('audio'); data.delete('camera');
      if (files.photo) data.set('photo', files.photo, files.photo.name || 'picture.jpg');
      if (files.audio) data.set('audio', files.audio, files.audio.name || 'recording.webm');
      const controls = Array.from(form.elements).map(el => [el, el.disabled]);
      controls.forEach(([el]) => { el.disabled = true; });
      sending = true; status.textContent = 'Sharing… waiting for the server to confirm.';
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 60000);
      try {
        const response = await fetch(form.action, {method: 'POST', body: data, credentials: 'same-origin', headers: {Accept: 'application/json'}, signal: controller.signal});
        const type = response.headers.get('Content-Type') || '';
        if (!type.includes('application/json')) throw new Error(response.status === 413 ? 'The upload is too large for this server. Try a smaller picture or recording.' : 'Your session may have expired, or the server could not respond. Your draft remains here. Reload or sign in, then retry.');
        const result = await response.json();
        if (!response.ok || !result.saved) throw new Error(result.error || 'The server could not save this yet.');
        try { await draftOperation(key, 'delete'); } catch (_) { /* Replaying the retained token is safe. */ }
        dirty = false; sending = false; status.textContent = 'Saved on the server.';
        location.assign(result.url);
      } catch (exc) {
        tellError(exc.name === 'AbortError' ? 'Confirmation took too long. You can retry safely: the same submission will not be added twice.' : exc.message || 'Connection lost. Keep this page open or restore the draft and retry.');
        status.textContent = 'Not confirmed as shared. Your current contribution is still here; retry when connected.';
        sending = false;
        controls.forEach(([el, disabled]) => { el.disabled = disabled; });
      } finally { clearTimeout(timeout); }
    });
    window.addEventListener('beforeunload', event => {
      if (dirty || sending || recorder?.busy) { event.preventDefault(); event.returnValue = ''; }
    });
  });
})();
