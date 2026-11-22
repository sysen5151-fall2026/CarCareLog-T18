// Optional development regression. Requires Playwright and Chromium.
// node CarCareLog/tests/receipt_workflow.browser.cjs
// Set CARCARE_BROWSER_CHANNEL=chrome to use an installed Chrome.
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const path = require('node:path');
const { createInterface } = require('node:readline');
const { chromium } = require('playwright');

// Requests go through the real HTTP parser, application handler and temporary database.
// A pipe also works on machines that disallow connecting a test browser to a local port.
const fixture = String.raw`
import base64, json, os, sys
from datetime import date
from email.parser import BytesParser
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock
from backend import app

class Handler(app.Handler):
    def log_message(self, *args):
        pass

def draft(text, model, receipt_image=None):
    first = base64.b64decode(receipt_image).endswith(b'A')
    return dict(service_date=date.today().isoformat(), service_item='Oil change',
                service_items=['Oil change', 'Inspection', 'Other'] if first else ['Oil change', 'Tire rotation', 'Other'],
                category='Maintenance', odometer_value=22000 if first else 25000,
                odometer_unit='km', cost='74.98' if first else '180.00',
                provider='Shop A' if first else 'Shop B')

with TemporaryDirectory(prefix='carcare-browser-') as folder:
    app.DB_PATH = Path(folder) / 'test.db'
    app.init_db()
    app.draft_receipt = draft
    os.environ['CARCARE_OLLAMA_MODEL'] = 'qwen3.5:4b'
    for line in sys.stdin:
        turn = json.loads(line)
        body = turn['body'].encode()
        head = (f"{turn['method']} {turn['path']} HTTP/1.0\r\nHost: 127.0.0.1:8018\r\n"
                f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n")
        wire = Mock()
        wire.makefile.return_value = BytesIO(head.encode() + body)
        out = BytesIO()
        wire.sendall.side_effect = out.write
        Handler(wire, ('127.0.0.1', 55000), SimpleNamespace(server_port=8018))
        headers, payload = out.getvalue().split(b'\r\n\r\n', 1)
        status, rest = headers.split(b'\r\n', 1)
        media = BytesParser().parsebytes(rest)['Content-Type']
        print(json.dumps(dict(id=turn['id'], status=int(status.split()[1]), media=media,
                              data=base64.b64encode(payload).decode())), flush=True)
`;

async function run() {
  const backend = spawn(process.env.PYTHON || 'python', ['-B', '-u', '-c', fixture],
    { cwd: path.resolve(__dirname, '..'), stdio: ['pipe', 'pipe', 'inherit'], windowsHide: true });
  const pending = new Map();
  let counter = 0;
  createInterface({input: backend.stdout}).on('line', line => {
    const response = JSON.parse(line);
    pending.get(response.id).resolve(response);
    pending.delete(response.id);
  });
  backend.on('exit', code => {
    for (const {reject} of pending.values()) reject(new Error('Fixture exited ' + code));
  });
  let browser;
  try {
    browser = await chromium.launch({channel: process.env.CARCARE_BROWSER_CHANNEL || undefined,
      headless: true, args: ['--disable-gpu', '--disable-crash-reporter', '--disable-crashpad-for-testing']});
    const page = await browser.newPage();
    page.setDefaultTimeout(7000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    let dropConfirmedResponse = false;
    const separateOperations = [];
    await page.route('http://127.0.0.1:8018/**', async route => {
      const req = route.request(), url = new URL(req.url()), body = req.postData() || '';
      const response = await new Promise((resolve, reject) => {
        const id = ++counter;
        pending.set(id, {resolve, reject});
        backend.stdin.write(JSON.stringify({id, method:req.method(), path:url.pathname + url.search, body}) + '\n');
      });
      if (url.pathname === '/api/records' && req.method() === 'POST' && response.status === 201) {
        const receipt = JSON.parse(body);
        if (receipt.acknowledged_duplicate_ids) separateOperations.push(receipt.operation_id);
        if (dropConfirmedResponse) {
          dropConfirmedResponse = false;
          return route.abort('failed');
        }
      }
      return route.fulfill({status: response.status, contentType: response.media, body: Buffer.from(response.data, 'base64')});
    });
    await page.goto('http://127.0.0.1:8018/');
    const form = page.locator('#record-form');
    const field = name => form.locator('[name=' + name + ']');
    const count = async n => page.waitForFunction(n => document.querySelector('#count-stat').textContent === String(n), n);
    const submit = () => form.locator('[type=submit]').click();
    await page.locator('#add-vehicle').click();
    await page.locator('#vehicle-form [name=name]').fill('Fixture vehicle');
    await page.locator('#vehicle-form [name=mileage]').fill('0');
    await page.locator('#vehicle-form [type=submit]').click();
    await count(0);
    for (const service of ['Oil change', 'Tire rotation']) {
      await page.locator('#add-reminder').click();
      await page.locator('#reminder-form [name=service_item]').selectOption(service);
      await page.locator('#reminder-form [name=interval_km]').fill('5000');
      await page.locator('#reminder-form [name=reference]').fill('Fixture schedule');
      await page.locator('#reminder-form [type=submit]').click();
      await page.locator('#reminder-dialog').waitFor({state: 'hidden'});
    }
    const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/aWQAAAAASUVORK5CYII=', 'base64');
    const choose = id => page.locator('#receipt-image').setInputFiles({name:id + '.png', mimeType:'image/png', buffer:Buffer.concat([png, Buffer.from(id)])});
    await page.locator('#add-record').click();
    await page.locator('#receipt-assist summary').click();
    await choose('A');
    await page.locator('#draft-receipt').click();
    await page.locator('#draft-banner').waitFor();
    assert.equal(await field('cost').inputValue(), '74.98');
    assert.equal(await page.getByRole('checkbox', {name:'Inspection'}).isChecked(), true);
    await page.getByRole('checkbox', {name:'Other'}).uncheck();
    await page.getByRole('checkbox', {name:'Battery'}).check();
    await field('provider').fill('Checked Garage');
    await choose('B');
    assert.equal(await field('cost').inputValue(), '');
    assert.equal(await field('provider').inputValue(), 'Checked Garage');
    assert.equal(await page.locator('#source-review').isVisible(), true);
    assert.equal(await page.locator('#draft-banner').isVisible(), false);
    assert.equal(await page.getByRole('checkbox', {name:'Inspection'}).isChecked(), false, 'old AI-only service must clear');
    assert.equal(await page.getByRole('checkbox', {name:'Battery'}).isChecked(), true, 'owner checkbox edit must survive');
    await submit();
    assert.equal(await page.locator('#count-stat').textContent(), '0');
    await page.locator('#draft-receipt').click();
    await page.locator('#draft-banner').waitFor();
    assert.equal(await field('cost').inputValue(), '180.00');
    assert.equal(await field('provider').inputValue(), 'Checked Garage');
    assert.equal(await page.getByRole('checkbox', {name:'Tire rotation'}).isChecked(), true);
    assert.equal(await page.getByRole('checkbox', {name:'Other'}).isChecked(), false, 'owner deselection overrides the new suggestion');
    assert.equal(await page.getByRole('checkbox', {name:'Battery'}).isChecked(), true);
    await page.getByRole('checkbox', {name:'Battery'}).uncheck();
    const day = await field('service_date').inputValue();
    await submit();
    await count(1);
    assert.equal(await page.locator('#cost-stat').textContent(), '$180.00');
    assert.equal(await page.locator('.reminder').filter({hasText:'Based on record #1'}).count(), 2);
    await page.locator('#search').fill('no-such-service');
    await page.locator('[data-question=tire_rotation]').click();
    await page.locator('#answer [data-source="1"]').click();
    assert.match(await page.locator('#answer').textContent(), /25,000 km/);
    assert.equal(await page.locator('#search').inputValue(), '');
    assert.equal(await page.evaluate(() => document.activeElement.id), 'record-1');

    async function enterRecord(service, amount, provider, extra) {
      await page.locator('#add-record').click();
      await field('service_date').fill(day);
      await field('mileage').fill('25000');
      await field('service_item').selectOption(service);
      await field('category').selectOption(service === 'Brake service' ? 'Repair' : 'Maintenance');
      await field('cost').fill(amount);
      await field('provider').fill(provider);
      if (extra) await page.getByRole('checkbox', {name:extra, exact:true}).check();
      await submit();
    }
    await enterRecord('Oil change', '180', 'Checked Garage', 'Tire rotation');
    await page.locator('#duplicate-warning').waitFor();
    await page.locator('#duplicate-matches summary').click();
    assert.match(await page.locator('#duplicate-matches details p').innerText(), /Checked Garage.*\$180\.00/);
    assert.equal(await page.locator('#count-stat').textContent(), '1');
    dropConfirmedResponse = true;
    await page.locator('#save-separate').click();
    await page.waitForFunction(() => Boolean(document.querySelector('#record-form .form-error').textContent));
    await page.locator('#save-separate').click();
    await count(2);
    assert.equal(separateOperations.length, 2);
    assert.equal(separateOperations[0], separateOperations[1]);
    assert.equal(await page.locator('#cost-stat').textContent(), '$360.00');
    await enterRecord('Brake service', '65', 'Brake Garage');
    await count(3);
    await enterRecord('Brake service', '120', 'Mixed Garage', 'Inspection');
    await count(4);
    await page.locator('[data-question=brake_spending]').click();
    await page.locator('#answer [data-source="4"]').waitFor();
    const brakes = await page.locator('#answer').textContent();
    assert.match(brakes, /\$65\.00/);
    assert.match(brakes, /exact brake total is unknown/);
    assert.equal(await page.locator('#answer [data-source="3"]').count(), 1);
    assert.deepEqual(errors, []);
    console.log('PASS: source replacement and retained edit; two services and two reminders; duplicate inspection, override and lost-response retry; tire and brake citations; filtered record navigation.');
  } finally {
    if (browser) await browser.close();
    backend.stdin.end();
  }
}
run().catch(error => { console.error(error); process.exitCode = 1; });
