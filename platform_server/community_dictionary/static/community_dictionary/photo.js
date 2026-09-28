/* This page never automatically repeats an AI request. */
(() => {
  const form = document.querySelector('[data-photo-upload]');
  if (form) {
    const input = form.querySelector('input[type=file]');
    const preview = form.querySelector('[data-photo-preview]');
    const status = form.querySelector('[data-photo-status]');
    let previewURL;
    if (input) input.addEventListener('change', () => {
      if (previewURL) URL.revokeObjectURL(previewURL);
      preview.hidden = !input.files.length;
      if (input.files.length) preview.src = previewURL = URL.createObjectURL(input.files[0]);
    });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const button = form.querySelector('button');
      if (button.disabled) return;
      button.disabled = true;
      status.textContent = 'Uploading and identifying… Please keep this page open.';
      const data = new FormData(form);
      // Large phone photos become a small JPEG before upload; server validates again.
      try {
        const file = input && input.files[0];
        if (!file) throw new Error('existing image');
        const bitmap = await createImageBitmap(file, {imageOrientation: 'from-image'});
        const scale = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height));
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(bitmap.width * scale));
        canvas.height = Math.max(1, Math.round(bitmap.height * scale));
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height); bitmap.close();
        const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', .85));
        if (blob) data.set('photo', blob, 'photo.jpg');
      } catch (_) { /* Original upload still gets server validation. */ }
      try {
        const response = await fetch(form.action, {method: 'POST', body: data, credentials: 'same-origin'});
        if (response.redirected) { location.assign(response.url); return; }
        // Validation needs a rendered form, preserving escaped server errors.
        if (response.ok) {
          const html = await response.text();
          document.open(); document.write(html); document.close();
          return;
        }
        throw new Error('request');
      } catch (_) {
        status.textContent = 'The connection was interrupted. Open “Learn from a photo” again and check Your recent photos before starting another attempt.';
        // Leave this submitted form disabled: a new page exposes the durable receipt.
      }
    });
  }
  const speak = document.querySelector('[data-photo-speak]');
  if (!speak) return;
  const status = document.querySelector('[data-voice-status]');
  const synth = window.speechSynthesis;
  let voice;
  function chooseVoice() {
    const language = speak.dataset.language.toLowerCase();
    const voices = synth ? synth.getVoices() : [];
    voice = voices.find(v => v.lang.toLowerCase() === language) || voices.find(v => v.lang.toLowerCase().split('-')[0] === language.split('-')[0]);
    speak.hidden = !voice;
    status.textContent = voice ? 'Synthetic preview using an available device voice. No recording is saved. Your device’s speech service may process the word.' : 'No matching device voice is available. You can add a human recording after saving.';
  }
  chooseVoice();
  if (synth) synth.addEventListener('voiceschanged', chooseVoice);
  speak.addEventListener('click', () => {
    if (!voice) return;
    synth.cancel();
    const speech = new SpeechSynthesisUtterance(document.querySelector('[data-spoken-word]').textContent);
    speech.voice = voice; speech.lang = voice.lang;
    speech.onerror = () => { status.textContent = 'The device voice could not play. You can add a recording after saving.'; };
    synth.speak(speech);
  });
})();
