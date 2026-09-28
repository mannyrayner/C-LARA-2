(() => {
  const form = document.querySelector('[data-audio-generate]');
  if (!form) return;
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('button');
    if (button.disabled) return;
    button.disabled = true;
    const status = form.querySelector('[data-audio-status]');
    status.textContent = 'Creating your audio preview… Please keep this page open.';
    try {
      const response = await fetch(form.action, {method:'POST', body:new FormData(form), credentials:'same-origin'});
      if (response.redirected) { location.assign(response.url); return; }
      if (response.ok) {
        const html = await response.text();
        document.open(); document.write(html); document.close();
        return;
      }
      throw new Error('request');
    } catch (_) {
      status.textContent = 'The connection was interrupted. Reopen Create spoken audio from the entry and check Your recent audio before starting another attempt.';
    }
  });
})();
