(() => {
  const mount = document.getElementById('grounded-questions');
  if (!mount) return;
  mount.innerHTML = `
    <form id="vehicle-question-form">
      <h3>Ask about this vehicle</h3>
      <label for="vehicle-question">Your question</label>
      <input id="vehicle-question" type="text" required maxlength="600"
             placeholder="Which repair had the highest invoice?" style="width:100%">
      <div class="filters">
        <label>Look in <select id="question-source">
          <option value="auto">Choose automatically</option>
          <option value="history">Confirmed records</option>
          <option value="manual">Imported manual</option>
        </select></label>
        <button type="submit">Ask</button>
      </div>
    </form><div id="grounded-answer" aria-live="polite"></div>`;
  const form = mount.querySelector('form');
  const input = form.querySelector('input');
  const output = mount.querySelector('#grounded-answer');
  const submit = form.querySelector('button');
  let revision = 0;
  let shownVehicle;

  window.resetGroundedQuestions = () => {
    revision++;
    if (shownVehicle !== currentId) form.reset();
    shownVehicle = currentId;
    output.replaceChildren();
    submit.disabled = false;
  };

  function renderPassage(vehicleId, source, requestedRevision) {
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = source.title + ' · p. ' + source.page;
    const quote = document.createElement('blockquote');
    quote.textContent = source.quote;
    const attribution = document.createElement('p');
    attribution.className = 'muted';
    attribution.textContent = source.verification === 'publisher_https'
      ? 'Retrieved from publisher over HTTPS.' : 'Owner-supplied document.';
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'link-button';
    button.textContent = 'Read the full page';
    const page = document.createElement('p');
    page.style.whiteSpace = 'pre-wrap';
    button.addEventListener('click', async () => {
      button.disabled = true;
      const params = new URLSearchParams({vehicle_id: vehicleId, manual_id: source.id, page: source.page});
      try {
        const evidence = await api('/api/manual/page?' + params);
        if (revision !== requestedRevision || currentId !== vehicleId) return;
        page.textContent = evidence.text;
        button.remove();
      } catch (error) {
        page.textContent = error.message;
        button.disabled = false;
      }
    });
    details.append(summary, quote, attribution, button, page);
    details.open = true;
    return details;
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const question = input.value.trim();
    if (!question || !currentId) return;
    const vehicleId = currentId;
    const requestedRevision = ++revision;
    submit.disabled = true;
    output.textContent = 'Looking up sources…';
    try {
      const result = await api('/api/questions', 'POST', {
        vehicle_id: vehicleId, question, source: form.querySelector('select').value
      });
      if (revision !== requestedRevision || currentId !== vehicleId) return;
      output.textContent = result.answer;
      const citations = document.createElement('div');
      citations.className = 'actions';
      for (const id of result.record_ids) {
        const ref = document.createElement('button');
        ref.type = 'button';
        ref.className = 'link-button';
        ref.dataset.source = id;
        ref.textContent = 'Record #' + id;
        citations.append(ref);
      }
      output.append(citations);
      for (const source of result.manual_sources) {
        output.append(renderPassage(vehicleId, source, requestedRevision));
      }
    } catch (error) {
      if (revision === requestedRevision && currentId === vehicleId) output.textContent = error.message;
    } finally {
      if (revision === requestedRevision) submit.disabled = false;
    }
  });
})();
