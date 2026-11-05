(() => {
  document.querySelectorAll('audio').forEach(player => player.addEventListener('play', () => {
    document.querySelectorAll('audio').forEach(other => { if (other !== player) other.pause(); });
  }));

  const batch = document.querySelector('[data-google-audio-batch]');
  if (!batch || Number(batch.dataset.pendingReplacements) <= 0) return;
  let leaving = false;
  const applyingForms = new WeakSet();
  const samePage = url => url.origin === location.origin && url.pathname === location.pathname;
  // Acknowledge leaving without discarding previews or changing any recordings.
  const allowLeave = event => {
    if (window.confirm(batch.dataset.leaveMessage)) leaving = true;
    else event.preventDefault();
  };
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey ||
        event.shiftKey || event.altKey || (link.target && link.target !== '_self') ||
        link.hasAttribute('download') || link.hasAttribute('data-audio-download')) return;
    const url = new URL(link.href, location.href);
    if (!['http:', 'https:'].includes(url.protocol)) return;
    if (samePage(url) && url.search === location.search && url.hash) return;
    // Pagination/filtering stays in the review; the next response recalculates the warning.
    if (samePage(url) || link.hasAttribute('data-audio-leave-later')) leaving = true;
    else allowLeave(event);
  });
  document.addEventListener('submit', event => {
    if (event.defaultPrevented) return;
    const form = event.target;
    const bulkApply = form.hasAttribute('data-audio-apply-form');
    if (bulkApply && applyingForms.has(form)) {
      event.preventDefault();
      return;
    }
    // The review buttons are named "action", which shadows form.action.
    const action = event.submitter?.getAttribute('formaction') ?? form.getAttribute('action');
    if (!samePage(new URL(action || location.href, location.href))) {
      allowLeave(event);
    }
    // Applying/rejecting, saving a note and changing filters must not prompt.
    // A validation failure or another cancelled handler must leave the guard active.
    queueMicrotask(() => {
      if (event.defaultPrevented) return;
      leaving = true;
      if (!bulkApply) return;
      applyingForms.add(form);
      const status = form.querySelector('[data-audio-apply-status]');
      if (status) status.hidden = false;
      const button = event.submitter || form.querySelector('button[name="action"][value="accept_all"]');
      if (button) {
        // Native disabled would omit action=accept_all from the submitted data.
        button.setAttribute('aria-disabled', 'true');
        button.setAttribute('aria-busy', 'true');
        if (button.dataset.busyLabel) button.textContent = button.dataset.busyLabel;
      }
    });
  });
  window.addEventListener('beforeunload', event => {
    if (!leaving) { event.preventDefault(); event.returnValue = ''; }
  });
  window.addEventListener('pageshow', event => {
    if (event.persisted) { leaving = true; location.reload(); } // Refresh decisions after browser Back.
    else leaving = false;
  });
})();
