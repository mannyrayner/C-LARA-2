/* Show the progress-check time in the learner's local timezone. */
(() => {
  document.querySelectorAll('[data-word-image-checked]').forEach(element => {
    const checked = new Date(element.dateTime);
    if (!Number.isNaN(checked.getTime())) element.textContent = checked.toLocaleTimeString();
  });
})();
