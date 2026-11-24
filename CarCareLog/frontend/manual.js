/* Import a manual for the selected vehicle and review its quoted maintenance rules. */
(() => {
  const mount = document.getElementById('manual-mount');
  if (!mount) return;
  mount.innerHTML = '<details class="assist"><summary>Import a vehicle manual</summary>' +
    '<form id="manual-import"><label>Manual title and edition<input name="title" maxlength="120" required ' +
    'placeholder="e.g. 2024 Corolla Warranty &amp; Maintenance Guide"></label>' +
    '<label>Manual source<select name="method"><option value="text">Paste a passage</option>' +
    '<option value="file">Upload PDF or text</option><option value="link">Read from manufacturer website</option></select></label>' +
    '<label data-method="text">Manual passage<textarea rows="4" name="text" required></textarea></label>' +
    '<label data-method="file" hidden>Text-based PDF or UTF-8 text, up to 16 MiB<input type="file" name="document" accept=".pdf,.txt" disabled></label>' +
    '<label data-method="link" hidden>Manufacturer manual URL<input type="url" name="url" disabled ' +
    'placeholder="https://"><small>Use a direct Toyota publications, Honda TechInfo or Tesla manual link. ' +
    'Downloading here checks the publisher. An uploaded copy is labeled owner-supplied.</small></label>' +
    '<p class="footnote">Import selects the reference for this vehicle. Existing reminders change only when you confirm an interval.</p>' +
    '<button class="secondary" type="submit">Read manual</button></form>' +
    '<p id="manual-status" role="status"></p><div id="manual-suggestions"></div></details>';

  const form = mount.querySelector('form');
  const status = mount.querySelector('#manual-status');
  const suggestions = mount.querySelector('#manual-suggestions');
  let selected = null;
  let revision = 0;
  let loaded = false;

  function selectMethod() {
    for (const label of form.querySelectorAll('[data-method]')) {
      label.hidden = label.dataset.method !== form.elements.method.value;
      const input = label.querySelector('input,textarea');
      input.disabled = label.hidden;
      input.required = !label.hidden;
    }
  }
  form.elements.method.onchange = selectMethod;

  function element(tag, text) {
    const result = document.createElement(tag);
    result.textContent = text;
    return result;
  }

  async function showPage(button, manualId, page) {
    const id = selected;
    button.disabled = true;
    try {
      const result = await api('/api/manual/page?vehicle_id=' + id + '&manual_id=' + manualId + '&page=' + page);
      if (selected !== id || !button.isConnected) return;
      const details = element('details', '');
      details.append(element('summary', 'Source page / section ' + page));
      const passage = element('p', result.text);
      passage.style.whiteSpace = 'pre-wrap';
      details.append(passage);
      details.open = true;
      button.replaceWith(details);
    } catch (error) {
      if (selected === id) status.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }

  function show(result) {
    suggestions.replaceChildren();
    if (!result.manual) return;
    const m = result.manual;
    suggestions.append(element('strong', m.title));
    const provenance = element('p', m.verification === 'publisher_https' ?
      'Fetched over HTTPS from the manufacturer. ' : 'Owner-supplied text or file. ');
    provenance.append(document.createTextNode('Source fingerprint: ' + m.sha256.slice(0, 12) + '. '));
    if (m.source_url) {
      const link = element('a', 'Open publisher original');
      link.href = m.source_url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      provenance.append(link);
    }
    suggestions.append(provenance);
    if (!result.candidates.length) {
      suggestions.append(element('p', 'No clear recurring service interval was found. You can ask about the imported text or use Set interval after checking the manual.'));
      return;
    }
    suggestions.append(element('p', 'Check the model, year, driving conditions and any earlier service triggers in the manual. Confirming replaces the configured interval for that service.'));
    result.candidates.forEach((rule, index) => {
      const box = element('div', '');
      box.className = 'reminder';
      const intervals = [];
      if (rule.interval_km) intervals.push(rule.interval_km.toLocaleString() + ' km');
      if (rule.interval_months) intervals.push(rule.interval_months + ' months');
      box.append(element('strong', rule.service_item + ' · ' + intervals.join(' or ')));
      box.append(element('p', 'Page / section ' + rule.page + ' — “' + rule.quote + '”'));
      const actions = element('div', '');
      actions.className = 'actions';
      const preview = element('button', 'Read full passage');
      preview.type = 'button';
      preview.className = 'link-button';
      preview.onclick = () => showPage(preview, m.id, rule.page);
      const confirm = element('button', 'Confirm and set interval');
      confirm.type = 'button';
      confirm.className = 'secondary';
      confirm.onclick = async () => {
        const vehicleId = selected;
        confirm.disabled = true;
        try {
          await api('/api/manual/confirm', 'POST', {
            vehicle_id: vehicleId, manual_id: m.id, candidate_index: index, owner_confirmed: true
          });
          if (selected !== vehicleId) return;
          await reload(vehicleId);
          if (selected === vehicleId) status.textContent = rule.service_item + ' interval saved with its manual reference.';
        } catch (error) {
          if (selected === vehicleId) status.textContent = error.message;
        } finally {
          confirm.disabled = false;
        }
      };
      actions.append(preview, confirm);
      box.append(actions);
      suggestions.append(box);
    });
  }

  function readFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error('Could not read the selected file.'));
      reader.onload = () => resolve(String(reader.result).split(',')[1]);
      reader.readAsDataURL(file);
    });
  }
  form.onsubmit = async event => {
    event.preventDefault();
    const id = selected;
    if (!id) return;
    const request = ++revision;
    const button = form.querySelector('button');
    button.disabled = true;
    status.textContent = 'Reading manual…';
    try {
      const body = {vehicle_id: id, title: form.elements.title.value};
      switch (form.elements.method.value) {
        case 'link': body.source_url = form.elements.url.value.trim(); break;
        case 'file': {
          const file = form.elements.document.files[0];
          if (!file || file.size > 16 * 1024 * 1024) throw new Error('Choose a PDF or text file up to 16 MiB.');
          body.file_base64 = await readFile(file);
          break;
        }
        default: body.text = form.elements.text.value;
      }
      const result = await api('/api/manual/import', 'POST', body);
      if (selected !== id || request !== revision) return;
      loaded = true;
      show(result);
      status.textContent = 'Manual imported for this vehicle.';
    } catch (error) {
      if (selected === id && request === revision) status.textContent = error.message;
    } finally {
      if (selected === id && revision === request) button.disabled = false;
    }
  };

  async function refresh(id) {
    if (id === selected && loaded) return;
    if (id !== selected) {
      form.reset();
      selectMethod();
      form.querySelector('button').disabled = false;
      suggestions.replaceChildren();
      status.textContent = '';
    }
    selected = id;
    loaded = true;
    const request = ++revision;
    if (!id) return;
    try {
      const result = await api('/api/manual?vehicle_id=' + id);
      if (selected === id && request === revision) show(result);
    } catch (error) {
      if (selected === id && request === revision) {
        loaded = false;
        status.textContent = error.message;
      }
    }
  }
  window.carManual = {refresh};
  refresh(typeof currentId === 'undefined' ? null : currentId);
})();
