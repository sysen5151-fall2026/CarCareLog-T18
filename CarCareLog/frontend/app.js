const $ = id => document.getElementById(id);
const services = ['Oil change', 'Tire rotation', 'Brake service', 'Inspection', 'Battery', 'Other'];
let cars = [], currentId = null, data = null;
const bundledDashboard = new URLSearchParams(location.search).get('save') === 'bundled';
let recordOperation;
const money = cents => new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'}).format(cents / 100);
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[ch]));
const today = () => {const now = new Date(); return `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;};

async function api(path, method = 'GET', body) {
  const response = await fetch(path, {method, headers: body ? {'Content-Type': 'application/json'} : {}, body: body ? JSON.stringify(body) : undefined});
  const result = await response.json();
  if (!response.ok) {
    const error = new Error(result.error || 'Request failed.');
    error.details = result;
    throw error;
  }
  return result;
}
function message(text, error = false) {
  $('message').hidden = false; $('message').textContent = text; $('message').className = error ? 'error' : '';
}
function openDialog(id) {
  $(id).querySelector('.form-error').textContent = ''; $(id).showModal();
}
async function reload(selectedId = currentId) {
  cars = await api('/api/vehicles');
  currentId = cars.some(c => c.id === Number(selectedId)) ? Number(selectedId) : cars[0]?.id ?? null;
  $('vehicle-select').innerHTML = cars.length ? cars.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('') : '<option>No vehicles yet</option>';
  $('vehicle-select').value = currentId ?? '';
  $('edit-vehicle').disabled = !currentId;
  $('demo').hidden = cars.length > 0;
  $('welcome').hidden = !!currentId;
  $('dashboard').hidden = !currentId;
  if (currentId) {
    data = await api(`/api/dashboard?vehicle_id=${currentId}`);
    render();
  }
}
function renderReminder(rule) {
  const due = rule.status === 'Due / overdue';
  const dates = [];
  if (rule.due_mileage !== null) dates.push(`Due at ${rule.due_mileage.toLocaleString()} km`);
  if (rule.due_date) dates.push(`Due ${rule.due_date}`);
  if (rule.record_id) dates.push(`Based on record #${rule.record_id}`);
  const details = dates.join(' · ') || 'Add a matching service record to calculate the next due date.';
  const exportAction = rule.due_date && !due
    ? `<button class="link-button" data-calendar="${rule.id}">Save to calendar (.ics)</button>`
    : '';
  return `<div class="reminder"><div class="reminder-head">
      <strong>${escapeHtml(rule.service_item)}</strong>
      <span class="badge ${due ? 'due' : rule.status === 'Upcoming' ? 'upcoming' : ''}">${escapeHtml(rule.status)}</span></div>
    <p>${escapeHtml(details)}</p><p class="reference">${escapeHtml(rule.reference)}</p><div class="actions">
      ${exportAction}<button class="link-button" data-edit-reminder="${rule.id}">Edit interval</button>
      <button class="link-button" data-delete-reminder="${rule.id}">Remove interval</button></div></div>`;
}
async function downloadCalendar(ruleId) {
  const response = await fetch(`/api/reminders/${ruleId}/calendar.ics`);
  if (!response.ok) throw new Error((await response.json()).error || 'Could not export the reminder.');
  const url = URL.createObjectURL(await response.blob());
  const file = document.createElement('a');
  file.href = url;
  file.download = `carcare-reminder-${ruleId}.ics`;
  document.body.append(file);
  file.click();
  file.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
  message('Calendar file downloaded. Import it into your phone calendar and check the alert. If the service date changes, replace the imported event.');
}
function render() {
  $('mileage-stat').textContent = data.vehicle.mileage.toLocaleString() + ' km';
  $('cost-stat').textContent = money(data.total_cents);
  $('count-stat').textContent = data.records.length;
  $('due-stat').textContent = data.reminders.filter(r => r.status === 'Due / overdue').length;
  $('export').href = `/api/export?vehicle_id=${currentId}`;
  $('answer').textContent = '';
  $('reminder-list').innerHTML = data.reminders.length ? data.reminders.map(renderReminder).join('') : '<p class="empty-inline">No intervals configured. Use your vehicle manual to set one.</p>';
  const max = Math.max(1, ...data.monthly.map(m => m.Maintenance + m.Repair));
  $('spending-list').innerHTML = data.monthly.length ? data.monthly.map(m => `<div class="spending-row"><span>${m.month}</span><div class="bar" aria-label="Maintenance ${money(m.Maintenance)}, repairs ${money(m.Repair)}"><span class="maintenance-bar" style="width:${m.Maintenance/max*100}%"></span><span class="repair-bar" style="width:${m.Repair/max*100}%"></span></div><span class="amount">${money(m.Maintenance+m.Repair)}</span></div>`).join('') + '<p class="legend"><span class="maintenance-bar"></span>Maintenance &nbsp; <span class="repair-bar"></span>Repair</p>' : '<p class="empty-inline">Monthly spending appears after you save a record.</p>';
  renderRecords();
}
function listedServices(record) {
  return record.service_items?.length ? record.service_items : [record.service_item];
}
function renderRecords() {
  if (!data) return;
  const term = $('search').value.trim().toLowerCase();
  const rows = data.records.filter(r => (!term || `${listedServices(r).join(' ')} ${r.provider}`.toLowerCase().includes(term)) && (!$('from-date').value || r.service_date >= $('from-date').value) && (!$('to-date').value || r.service_date <= $('to-date').value));
  $('record-list').innerHTML = rows.length ? rows.map(r => `<article class="record" tabindex="-1" id="record-${r.id}"><time datetime="${r.service_date}">${r.service_date}</time><div><strong>${escapeHtml(listedServices(r).join(' · '))}</strong><small>#${r.id} · ${r.category} · ${r.mileage.toLocaleString()} km${r.provider ? ' · ' + escapeHtml(r.provider) : ''}</small>${r.notes ? `<p>${escapeHtml(r.notes)}</p>` : ''}</div><strong class="cost">${money(r.cost_cents)}</strong><div class="record-actions"><button class="link-button" data-edit="${r.id}">Edit</button><button class="link-button" data-delete="${r.id}">Delete</button></div></article>`).join('') : '<p class="empty-inline">No matching records. Add a record or adjust your search.</p>';
}
function editVehicle(car) {
  const form = $('vehicle-form'); form.reset();
  form.elements.id.value = car?.id ?? '';
  form.elements.name.value = car?.name ?? '';
  form.elements.mileage.value = car?.mileage ?? '';
  $('vehicle-title').textContent = car ? 'Update vehicle' : 'Add vehicle';
  openDialog('vehicle-dialog');
}
function editRecord(record) {
  const form = $('record-form'); form.reset();
  recordOperation = undefined;
  clearDuplicate();
  edited.clear();
  serviceEdits.clear();
  hasDraft = false;
  $('source-review').hidden = true;
  form.elements.id.value = record?.id ?? '';
  form.elements.service_date.max = today();
  form.elements.service_date.value = record?.service_date ?? today();
  form.elements.mileage.value = record?.mileage ?? data.vehicle.mileage;
  form.elements.cost.value = record ? (record.cost_cents / 100).toFixed(2) : '';
  for (const field of ['service_item','category','provider','notes']) if (record) form.elements[field].value = record[field];
  $('record-title').textContent = record ? 'Edit service record' : 'Add service record';
  showExtraServices(record ? listedServices(record) : []);
  resetDraft(!record);
  openDialog('record-dialog');
}
function editReminder(rule) {
  const form = $('reminder-form'); form.reset();
  if (rule) for (const field of ['service_item','interval_km','interval_months','reference']) form.elements[field].value = rule[field];
  openDialog('reminder-dialog');
}
// Receipt draft (ASR 1.1.6 / 1.2.2): the local model proposes values, F.2.2.2 checks them
// against the receipt text, and the owner reviews every field before Confirm & save.
const draftFields = ['service_date', 'mileage', 'service_item', 'category', 'cost', 'provider'];
const fieldLabels = {service_date: 'service date', mileage: 'mileage', service_item: 'service item', category: 'category', cost: 'cost', provider: 'provider'};
let assist = {enabled: false, model: null, sample: ''}, draftTimer, draftController, previewUrl;
const edited = new Set();
const serviceEdits = new Map();
let hasDraft = false, pendingDuplicates = [], allowSeparate = false;
function clearDuplicate() {
  pendingDuplicates = [];
  allowSeparate = false;
  $('duplicate-warning').hidden = true;
  $('duplicate-matches').replaceChildren();
}
function selectedExtras() {
  return [...$('extra-options').querySelectorAll('input:checked')].map(input => input.value);
}
function showExtraServices(values) {
  const primary = $('record-form').elements.service_item.value;
  const box = $('extra-options');
  box.replaceChildren();
  for (const item of services.filter(s => s !== primary)) {
    const label = document.createElement('label'), check = document.createElement('input');
    check.type = 'checkbox';
    check.value = item;
    check.checked = serviceEdits.has(item) ? serviceEdits.get(item) : values.includes(item);
    label.append(check, document.createTextNode(item));
    box.append(label);
  }
}
function clearReceiptPreview() {
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = null;
  $('receipt-preview').removeAttribute('src');
  $('receipt-preview').hidden = true;
}
function setNote(field, status, text) {
  const note = document.querySelector(`[data-note="${field}"]`), input = $('record-form').elements[field];
  note.textContent = text; note.className = 'field-note' + (status ? ' ' + status : '');
  input.classList.toggle('needs-check', status === 'check');
  input.classList.toggle('needs-entry', status === 'missing');
}
function resetDraft(show) {
  draftController?.abort();
  clearInterval(draftTimer);
  clearReceiptPreview();
  $('receipt-image').value = '';
  $('receipt-assist').hidden = !show;
  $('receipt-assist').open = false;
  $('receipt-text').value = '';
  $('draft-status').textContent = '';
  $('draft-status').className = 'draft-status';
  $('draft-banner').hidden = true;
  $('draft-receipt').disabled = !assist.enabled;
  for (const field of draftFields) setNote(field, '', '');
}
function applyDraft(result) {
  const form = $('record-form');
  for (const field of draftFields) {
    const value = result.proposal[field], evidence = result.evidence[field];
    if (edited.has(field)) {
      setNote(field, 'edited', 'Kept your edit. Check it against this receipt.');
      continue;
    }
    form.elements[field].value = value ?? '';
    const label = {found: '✓ ', check: 'Check: ', missing: 'Missing: '}[evidence.status];
    setNote(field, evidence.status, label + evidence.note);
  }
  const proposedServices = result.service_items || [];
  showExtraServices(proposedServices);
  $('source-review').hidden = true;
  hasDraft = true;
  if (!edited.has('notes') && !form.elements.notes.value) form.elements.notes.value = `Drafted from receipt by local AI (${result.model}).`;
  const flagged = draftFields.filter(f => result.evidence[f].status !== 'found');
  $('draft-banner').textContent = `AI draft, not saved yet. ${flagged.length ? `Check ${flagged.length} highlighted field${flagged.length > 1 ? 's' : ''} (${flagged.map(f => fieldLabels[f]).join(', ')}), ` : 'Check every field, '}then select Confirm & save.`;
  $('draft-banner').hidden = false;
}
async function draftReceipt() {
  const text = $('receipt-text').value.trim();
  const file = $('receipt-image').files[0], vehicleId = currentId;
  if (Boolean(file) === Boolean(text)) {
    $('draft-status').textContent = 'Choose one receipt image or paste receipt text.';
    $('draft-status').className = 'draft-status error';
    return;
  }
  if (file && (file.size > 4 * 1024 * 1024 || !['image/jpeg', 'image/png'].includes(file.type))) {
    $('draft-status').textContent = 'Choose a JPEG or PNG up to 4 MiB.';
    $('draft-status').className = 'draft-status error';
    return;
  }
  const controller = new AbortController();
  draftController = controller;
  const started = Date.now(), button = $('draft-receipt');
  button.disabled = true;
  $('draft-status').className = 'draft-status';
  const tick = () => { $('draft-status').textContent = `Drafting on this computer with ${assist.model}… ${Math.round((Date.now() - started) / 1000)} s (the first draft loads the model and can take longer)`; };
  tick(); draftTimer = setInterval(tick, 1000);
  try {
    let source = {receipt_text: text};
    if (file) {
      const url = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error('Could not read the receipt image.'));
        reader.readAsDataURL(file);
      });
      source = {receipt_image: url.split(',')[1]};
    }
    const response = await fetch('/api/receipt-draft', {method: 'POST', signal: controller.signal,
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify({vehicle_id: vehicleId, ...source})});
    const result = await response.json();
    if (controller.signal.aborted || vehicleId !== currentId) return;
    if (!response.ok) throw new Error(result.message || result.error || 'AI draft unavailable. Use manual entry.');
    applyDraft(result);
    $('draft-status').textContent = `Draft ready in ${(result.elapsed_ms / 1000).toFixed(1)} s from ${result.model}. Review the fields below.`;
  } catch (error) {
    if (controller.signal.aborted) return;
    $('draft-status').textContent = `${error.message} Your form is unchanged, and you can still enter and save the record yourself.`;
    $('draft-status').className = 'draft-status error';
  } finally {
    if (draftController === controller) {
      clearInterval(draftTimer);
      button.disabled = !assist.enabled;
      draftController = null;
    }
  }
}
async function loadAssist() {
  try { assist = await api('/api/receipt-assist'); } catch { assist = {enabled: false, model: null, sample: ''}; }
  $('assist-tag').textContent = assist.enabled ? 'Local AI' : 'Local AI off';
  $('assist-tag').className = 'tag' + (assist.enabled ? '' : ' off');
  if (!assist.enabled) $('assist-help').textContent = 'AI drafting is off. Start the local model as the README describes, or enter the record yourself below.';
  $('draft-receipt').disabled = !assist.enabled;
  $('sample-receipt').hidden = !assist.sample;
}
$('draft-receipt').onclick = draftReceipt;
function invalidateSource() {
  cancelDraft();
  clearDuplicate();
  if (!hasDraft) return;
  const form = $('record-form');
  for (const field of draftFields) {
    if (!edited.has(field)) form.elements[field].value = '';
    setNote(field, edited.has(field) ? 'edited' : '', edited.has(field) ? 'Kept your edit. Verify for the new receipt.' : '');
  }
  if (!edited.has('notes')) form.elements.notes.value = '';
  showExtraServices([]);
  hasDraft = false;
  $('draft-banner').hidden = true;
  $('draft-status').textContent = '';
  $('source-review').hidden = false;
  $('source-message').textContent = edited.size
    ? 'Receipt changed. The previous AI values were cleared. Review your retained edits or discard them, then generate a draft or continue manually.'
    : 'Receipt changed. The previous draft was cleared. Generate a new draft or continue manually.';
  $('clear-edits').hidden = !edited.size;
}
$('use-manual').onclick = () => {
  cancelDraft();
  $('source-review').hidden = true;
  $('draft-status').textContent = 'Manual entry selected.';
};
$('clear-edits').onclick = () => {
  for (const field of edited) {
    if (field === 'extras') continue;
    $('record-form').elements[field].value = '';
    if (draftFields.includes(field)) setNote(field, '', '');
  }
  edited.clear();
  serviceEdits.clear();
  showExtraServices([]);
  $('clear-edits').hidden = true;
  $('source-message').textContent = 'Your edits were cleared. Generate a new draft or continue manually.';
};
function cancelDraft() {
  if (draftController) {
    draftController.abort();
    draftController = null;
    clearInterval(draftTimer);
    $('draft-status').textContent = '';
    $('draft-receipt').disabled = !assist.enabled;
  }
}
$('record-dialog').addEventListener('close', () => {
  cancelDraft();
  clearReceiptPreview();
  $('receipt-image').value = '';
  $('receipt-text').value = '';
});
$('receipt-image').addEventListener('change', () => {
  invalidateSource();
  clearReceiptPreview();
  const file = $('receipt-image').files[0];
  if (file && file.size <= 4 * 1024 * 1024 && ['image/jpeg', 'image/png'].includes(file.type)) {
    previewUrl = URL.createObjectURL(file);
    $('receipt-preview').src = previewUrl;
    $('receipt-preview').hidden = false;
  }
});
$('receipt-text').addEventListener('input', invalidateSource);
$('sample-receipt').onclick = () => {
  invalidateSource();
  clearReceiptPreview();
  $('receipt-image').value = '';
  $('receipt-text').value = assist.sample;
  $('receipt-text').focus();
};
$('record-form').addEventListener('input', event => {
  const field = event.target.name;
  clearDuplicate();
  if (event.target.closest('#extra-options')) {
    serviceEdits.set(event.target.value, event.target.checked);
    edited.add('extras');
  }
  if (draftFields.includes(field) || field === 'notes') edited.add(field);
  if (field === 'service_item') showExtraServices(selectedExtras());
  if (draftFields.includes(field) && hasDraft) setNote(field, 'edited', 'Edited by you.');
});
function bindForm(id, submit) {
  $(id).addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.target, button = form.querySelector('[type=submit]');
    if (button.disabled) return;
    button.disabled = true;
    form.querySelector('.form-error').textContent = '';
    try {if (await submit(Object.fromEntries(new FormData(form))) !== false) form.closest('dialog').close();}
    catch (error) {form.querySelector('.form-error').textContent = error.message;}
    finally {button.disabled = false;}
  });
}
bindForm('vehicle-form', async body => {
  const car = await api(body.id ? `/api/vehicles/${body.id}` : '/api/vehicles', body.id ? 'PUT' : 'POST', body);
  await reload(car.id); message('Vehicle saved.');
});
bindForm('record-form', async body => {
  if (!$('source-review').hidden) throw new Error('Generate a draft for this receipt or choose manual entry first.');
  if (draftController) throw new Error('Wait for the draft, or close receipt entry and start a manual record.');
  body.service_items = [body.service_item, ...selectedExtras()];
  body.vehicle_id = currentId;
  body.owner_confirmed = true; // Explicit Confirm & save form submission.
  if (!body.id) {
    const fields = JSON.stringify(body);
    if (recordOperation?.fields !== fields) {
      recordOperation = {fields, id: crypto.randomUUID()};
    }
    body.operation_id = recordOperation.id;
    body.check_duplicates = true;
    if (allowSeparate) body.acknowledged_duplicate_ids = pendingDuplicates.map(match => match.id);
  }
  const path = body.id ? `/api/records/${body.id}` :
    bundledDashboard ? '/api/records?include=dashboard' : '/api/records';
  let result;
  try {
    result = await api(path, body.id ? 'PUT' : 'POST', body);
  } catch (error) {
    if (error.details?.code !== 'possible_duplicate') throw error;
    pendingDuplicates = error.details.matches;
    allowSeparate = false;
    $('duplicate-warning').hidden = false;
    $('duplicate-matches').innerHTML = pendingDuplicates.map(r =>
      `<details><summary>Review record #${r.id}</summary><p>${escapeHtml(r.service_date)} · ${escapeHtml(listedServices(r).join(', '))} · ${escapeHtml(r.provider)} · ${money(r.cost_cents)} · ${Number(r.mileage).toLocaleString()} km</p></details>`).join('');
    $('duplicate-matches').querySelector('summary')?.focus();
    return false;
  }
  try {
    if (result.dashboard && Number(body.vehicle_id) === currentId) {
      data = result.dashboard;
      render();
    } else {
      await reload();
    }
    message('Record confirmed and saved. Reminders and spending have been updated.');
  } catch {
    message('Record saved. Refresh the page to reload reminders and spending.', true);
  }
});
$('save-separate').onclick = () => {
  allowSeparate = true;
  $('record-form').requestSubmit();
};
bindForm('reminder-form', async body => {
  body.vehicle_id = currentId;
  await api('/api/reminders', 'POST', body); await reload(); message('Service interval saved.');
});
$('add-vehicle').onclick = () => editVehicle();
$('edit-vehicle').onclick = () => editVehicle(data.vehicle);
$('add-record').onclick = () => editRecord();
$('add-reminder').onclick = () => editReminder();
$('vehicle-select').onchange = async event => {try {await reload(Number(event.target.value));} catch (error) {message(error.message, true);}};
$('demo').onclick = async () => {try {const result = await api('/api/demo','POST',{}); await reload(result.vehicle_id); message('Demo data loaded. These records and intervals are examples only.');} catch (error) {message(error.message, true);}};
for (const id of ['search','from-date','to-date']) $(id).addEventListener('input', renderRecords);
$('clear-filters').onclick = () => {for (const id of ['search','from-date','to-date']) $(id).value = ''; renderRecords();};
document.querySelectorAll('.service-options').forEach(select => select.innerHTML = services.map(s => `<option>${s}</option>`).join(''));
$('record-form').elements.service_item.insertAdjacentHTML('afterbegin', '<option value="" disabled hidden>Choose a service</option>');
loadAssist();
document.addEventListener('click', async event => {
  const target = event.target.closest('button'); if (!target) return;
  try {
    if (target.dataset.source) {
      for (const id of ['search','from-date','to-date']) $(id).value = '';
      renderRecords();
      const record = $('record-' + target.dataset.source);
      if (record) {record.focus(); record.scrollIntoView({block:'center'});}
    }
    if (target.dataset.close) $(target.dataset.close).close();
    if (target.dataset.edit) editRecord(data.records.find(r => r.id === Number(target.dataset.edit)));
    if (target.dataset.calendar) await downloadCalendar(target.dataset.calendar);
    if (target.dataset.editReminder) editReminder(data.reminders.find(r => r.id === Number(target.dataset.editReminder)));
    if (target.dataset.delete && confirm('Delete this confirmed service record?')) {
      await api(`/api/records/${target.dataset.delete}`, 'DELETE'); await reload(); message('Record deleted. Current odometer mileage is retained.');
    }
    if (target.dataset.deleteReminder && confirm('Remove this service interval?')) {
      await api(`/api/reminders/${target.dataset.deleteReminder}`, 'DELETE'); await reload(); message('Service interval removed.');
    }
    if (target.dataset.question) {
      const vehicleId = currentId;
      const result = await api(`/api/answer?vehicle_id=${vehicleId}&question=${target.dataset.question}`);
      if (vehicleId !== currentId) return;
      $('answer').textContent = result.answer + (result.record_ids.length ? ' Sources: ' : ' No supporting record available.');
      for (const id of result.record_ids) {
        const ref = document.createElement('button');
        ref.className = 'link-button';
        ref.dataset.source = id;
        ref.textContent = 'Record #' + id;
        $('answer').append(ref, ' ');
      }
    }
  } catch (error) {message(error.message, true);}
});
reload().catch(error => message('Could not load the app: ' + error.message, true));
