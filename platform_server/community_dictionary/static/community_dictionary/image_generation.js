(() => {
  const form = document.querySelector('[data-image-generate]');
  if (!form) return;
  let sending = false;
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (sending) return;
    sending = true;
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    const status = form.querySelector('[data-image-status]');
    status.textContent = 'Creating your picture… This can take a few minutes. Please keep this page open.';
    try {
      const response = await fetch(form.action, {method: 'POST', body: new FormData(form), credentials: 'same-origin'});
      if (response.redirected) { location.assign(response.url); return; }
      if (response.ok) {
        const html = await response.text();
        document.open(); document.write(html); document.close();
        return;
      }
      throw new Error('request');
    } catch (_) {
      status.textContent = 'The connection was interrupted. Reopen Generate a picture (or Image style) and check Your recent attempts before starting another paid request.';
    }
  });
})();
