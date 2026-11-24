/* Selection contains signed word identifiers, never pictures or translations. */
(() => {
  document.querySelectorAll('[data-word-image-checked]').forEach(element => {
    const checked = new Date(element.dateTime);
    if (!Number.isNaN(checked.getTime())) element.textContent = checked.toLocaleTimeString();
  });
  document.querySelectorAll('[data-batch-date]').forEach(element => {
    const date = new Date(element.dateTime);
    if (!Number.isNaN(date.getTime())) element.textContent = date.toLocaleString();
  });
  const root = document.getElementById('word-picture-overview');
  if (!root) return;
  const key = root.dataset.storageKey;
  let saved = {};
  try { saved = JSON.parse(sessionStorage.getItem(key) || '{}'); } catch (_) {}
  const supplied = JSON.parse(document.getElementById('word-picture-selection').textContent);
  let selected = root.dataset.serverSelection === '1' ? supplied : (saved.selected || {});
  if (!selected || typeof selected !== 'object' || Array.isArray(selected)) selected = {};
  const boxes = [...root.querySelectorAll('[data-picture-id]')];
  const hidden = root.querySelector('[data-selection-tokens]');
  const message = root.querySelector('[data-selection-message]');
  const completedEntries = (root.dataset.completedEntries || '').trim().split(/\s+/);
  function persist(extra = {}) {
    try { sessionStorage.setItem(key, JSON.stringify({selected, ...extra})); } catch (_) {}
  }
  function update(changed = false) {
    boxes.forEach(box => {
      box.checked = Object.hasOwn(selected, box.dataset.pictureId);
      if (box.checked) selected[box.dataset.pictureId] = box.value;
    });
    const count = Object.keys(selected).length;
    hidden.value = JSON.stringify(Object.values(selected));
    root.querySelector('[data-selected-count]').textContent = String(count);
    message.textContent = count >= 50 ? root.dataset.limitMessage : '';
    message.hidden = count < 50;
    const completed = root.querySelector('[data-completed-selection]');
    if (completed) completed.hidden = !completedEntries.some(id => Object.hasOwn(selected, id));
    root.querySelectorAll('[data-clear-selection]').forEach(button => { button.disabled = count === 0; });
    const output = root.querySelector('[data-selected-estimate]');
    if (output) {
      const amount = count * Number(root.dataset.unitMicro) / 1000000;
      output.textContent = amount > 0 && amount < .01 ? amount.toFixed(6).replace(/0+$/, '') : amount.toFixed(2);
    }
    root.querySelectorAll('[data-bulk-button]').forEach(button => { button.disabled = count === 0 || count > 50; });
    if (changed) {
      const confirm = root.querySelector('[data-confirm-generation]');
      if (confirm) { confirm.disabled = true; root.querySelector('[data-selection-changed]').hidden = false; }
    }
    persist();
  }
  boxes.forEach(box => box.addEventListener('change', () => {
    if (box.checked) {
      if (Object.keys(selected).length >= 50 && !Object.hasOwn(selected, box.dataset.pictureId)) {
        box.checked = false; message.textContent = root.dataset.limitMessage; message.hidden = false; return;
      }
      selected[box.dataset.pictureId] = box.value;
    } else delete selected[box.dataset.pictureId];
    update(true);
  }));
  root.querySelector('[data-select-visible]').addEventListener('click', () => {
    const before = Object.keys(selected).sort().join(',');
    for (const box of boxes) {
      if (Object.keys(selected).length >= 50) break;
      selected[box.dataset.pictureId] = box.value;
    }
    update(before !== Object.keys(selected).sort().join(','));
    if (boxes.some(box => !box.checked)) message.textContent = root.dataset.limitMessage;
  });
  root.querySelectorAll('[data-clear-selection]').forEach(button => button.addEventListener('click', () => {
    selected = {}; update(true);
    if (button.hasAttribute('data-return-to-selection')) root.querySelector('[data-selection-controls]').scrollIntoView({block:'start'});
  }));
  root.querySelectorAll('[data-preserve-scroll]').forEach(link => link.addEventListener('click', () => persist({scroll:window.scrollY, restoreScroll:true})));
  root.querySelector('[data-picture-selection]').addEventListener('submit', () => persist());
  update();
  if (saved.restoreScroll && location.hash !== '#word-image-preview') {
    requestAnimationFrame(() => window.scrollTo(0, saved.scroll || 0));
  }
})();
