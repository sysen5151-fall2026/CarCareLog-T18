"""Exercise the receipt boundary with an isolated local HTTP runtime fixture."""

import json
from pathlib import Path
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import test_app
from backend import receipt_runtime


class ReceiptRuntimeTests(unittest.TestCase):
    setUp = test_app.AppTests.setUp
    tearDown = test_app.AppTests.tearDown
    call = test_app.AppTests.call
    car = test_app.AppTests.car
    record = test_app.AppTests.record
    dashboard = test_app.AppTests.dashboard

    def start_runtime(self, proposal):
        release = threading.Event()
        requests = []

        class RuntimeFixture(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers['Content-Length']))
                requests.append((self.path, json.loads(body)))
                if proposal is None:
                    release.wait(5)
                    return
                response = json.dumps({'response': json.dumps(proposal)}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(response)))
                self.end_headers()
                self.wfile.write(response)

        server = ThreadingHTTPServer(('127.0.0.1', 0), RuntimeFixture)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def stop_runtime():
            release.set()
            server.shutdown()
            server.server_close()
            thread.join()

        self.addCleanup(stop_runtime)
        port = patch.object(receipt_runtime, 'RUNTIME_PORT', server.server_port)
        port.start()
        self.addCleanup(port.stop)
        model = patch.dict(test_app.app.os.environ, {'CARCARE_OLLAMA_MODEL': 'fixture-model'})
        model.start()
        self.addCleanup(model.stop)
        return requests

    def ai(self, car_id, text='Synthetic receipt, oil change, USD 80.25', path='/internal/v1/coordinate-ai'):
        body = {'vehicle_id': car_id, 'receipt_text': text}
        if path == '/internal/v1/coordinate-ai':
            body['kind'] = 'receipt'
        return self.call(path, 'POST', body)

    def test_R2_runtime_timeout_preserves_ledger_and_manual_save(self):
        car_id = self.car()
        self.assertEqual(self.record(car_id)[0], 201)
        before = self.dashboard(car_id)
        requests = self.start_runtime(proposal=None)
        with patch.object(receipt_runtime, 'RUNTIME_TIMEOUT', 0.25):
            status, result = self.ai(car_id)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0][0], '/api/generate')
        self.assertEqual(status, 503)
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['reason'], 'runtime_unavailable')
        self.assertIsNone(result['proposal'])
        self.assertEqual(self.dashboard(car_id), before)
        self.assertEqual(self.record(car_id, cost='9.75')[0], 201)
        self.assertEqual(self.dashboard(car_id)['total_cents'], before['total_cents'] + 975)

    def test_draft_requires_review_and_does_not_write(self):
        car_id = self.car()
        proposal = dict(service_date='2026-01-02', service_item='Oil change', category='Maintenance',
                        odometer_value=10000, odometer_unit='km', cost='99.99', provider='Garage')
        requests = self.start_runtime(proposal)
        status, result = self.ai(car_id)
        self.assertEqual(status, 200)
        self.assertEqual(result['status'], 'needs_review')
        self.assertIs(result['owner_confirmed'], False)
        self.assertEqual(result['proposal']['cost'], '99.99')  # Plausible value differs from source text.
        self.assertEqual(result['evidence']['cost']['status'], 'check')
        self.assertEqual(self.dashboard(car_id)['records'], [])
        self.assertEqual(self.record(car_id, **result['proposal'], owner_confirmed=False)[0], 400)
        self.assertEqual(self.dashboard(car_id)['records'], [])
        self.assertEqual(len(requests), 1)
        self.assertIn('Synthetic receipt', requests[0][1]['prompt'])
        self.assertNotIn('vehicle_id', requests[0][1])

    def test_ASR_1_2_2_receipt_request_sends_text_only_with_pinned_settings(self):
        """ASR 1.2.2: provide Receipt extraction request to the AI Model Runtime."""
        car_id = self.car(name='Private Corolla', mileage=48123)
        requests = self.start_runtime(dict.fromkeys(receipt_runtime.DRAFT_FIELDS))
        self.assertEqual(self.ai(car_id, path='/api/receipt-draft')[0], 200)
        sent = requests[0][1]
        self.assertEqual(sent['model'], 'fixture-model')
        self.assertEqual(sent['format'], receipt_runtime.DRAFT_SCHEMA)
        self.assertEqual(sent['options'], {'temperature': 0, 'seed': 18})
        self.assertFalse(sent['stream'])
        self.assertNotIn('Private Corolla', sent['prompt'])
        self.assertNotIn('48123', sent['prompt'])
        self.assertEqual(set(sent), {'model', 'prompt', 'stream', 'format', 'options', 'keep_alive'})

    def test_ASR_1_1_6_browser_draft_converts_miles_and_saves_only_after_confirmation(self):
        """ASR 1.1.6: accept proposed date, mileage, items, cost, and provider from the runtime."""
        car_id = self.car()
        receipt = ('QuickLube Express\nDate: 11/02/2026\nOdometer In: 32,311 mi\n'
                   'Synthetic oil change 69.99\nSubtotal 83.32 Tax 6.67\nTOTAL $89.99')
        self.start_runtime(dict(service_date='2026-11-02', service_item='Oil change', category='Maintenance',
                                odometer_value=32311, odometer_unit='mi', cost='89.99',
                                provider='QuickLube Express'))
        status, result = self.ai(car_id, receipt, path='/api/receipt-draft')
        self.assertEqual(status, 200)
        draft = result['proposal']
        self.assertEqual(draft, dict(service_date='2026-11-02', service_item='Oil change', category='Maintenance',
                                     mileage=52000, cost='89.99', provider='QuickLube Express'))
        self.assertEqual({k: v['status'] for k, v in result['evidence'].items()},
                         dict(service_date='found', service_item='found', category='check',
                              mileage='found', cost='found', provider='found'))
        self.assertEqual(self.dashboard(car_id)['records'], [])
        status, saved = self.record(car_id, **draft, owner_confirmed=True)
        self.assertEqual(status, 201)
        stored = self.dashboard(car_id)['records'][0]
        self.assertEqual((stored['id'], stored['mileage'], stored['cost_cents']), (saved['id'], 52000, 8999))

    def test_photo_draft_sends_pixels_only_and_requires_visual_review_and_confirmation(self):
        car_id = self.car(name='Private Corolla')
        # Self-contained, synthetic one-pixel PNG for the transport fixture.
        photo = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/aWQAAAAASUVORK5CYII='
        requests = self.start_runtime(dict(service_date='2026-01-02', service_item='Oil change',
                                           category='Maintenance', odometer_value=10000, odometer_unit='mi',
                                           cost='99.99', provider=None))
        with patch.dict(test_app.app.os.environ, {'CARCARE_OLLAMA_MODEL': receipt_runtime.PINNED_MODEL}):
            status, result = self.call('/api/receipt-draft', 'POST', {'vehicle_id': car_id, 'receipt_image': photo})
        self.assertEqual((status, result['status'], result['owner_confirmed']), (200, 'needs_review', False))
        path, payload = requests[0]
        self.assertEqual(path, '/api/generate')
        self.assertEqual(payload['images'], [photo])
        self.assertEqual(payload['model'], 'qwen3.5:4b')
        self.assertFalse(payload['think'])
        self.assertNotIn('vehicle_id', payload)
        self.assertNotIn('Private Corolla', payload['prompt'])
        self.assertEqual({k: v['status'] for k, v in result['evidence'].items()},
                         dict(service_date='check', service_item='check', category='check', mileage='check',
                              cost='check', provider='missing'))
        self.assertEqual(result['proposal']['mileage'], 16093)
        self.assertEqual(self.dashboard(car_id)['records'], [])
        self.assertEqual(self.record(car_id, **result['proposal'], owner_confirmed=False)[0], 400)
        self.assertEqual(self.record(car_id, **{**result['proposal'], 'provider':'Owner-checked shop'},
                                     owner_confirmed=True)[0], 201)
        stored = self.dashboard(car_id)['records'][0]
        self.assertEqual(stored['provider'], 'Owner-checked shop')
        self.assertNotIn(photo, json.dumps(stored))

    def test_invalid_oversized_or_mixed_photo_input_never_reaches_runtime(self):
        car_id = self.car()
        requests = self.start_runtime(dict.fromkeys(receipt_runtime.DRAFT_FIELDS))
        for source in ({'receipt_image': 'not base64'}, {'receipt_image': 'aGVsbG8='},
                       {'receipt_image': 'A' * (receipt_runtime.MAX_IMAGE_BASE64 + 4)},
                       {'receipt_image': 'aGVsbG8=', 'receipt_text': 'two sources'}):
            status, result = self.call('/api/receipt-draft', 'POST', {'vehicle_id':car_id, **source})
            self.assertEqual(status, 400)
            self.assertIn('error', result)
        self.assertEqual(requests, [])
        self.assertEqual(self.dashboard(car_id)['records'], [])

    def test_receipt_draft_and_unavailable_responses_match_the_contract(self):
        contract = json.loads((Path(__file__).resolve().parents[2] / 'contracts' / 'api-v1.yaml').read_text(encoding='utf-8'))
        schemas = contract['components']['schemas']
        car_id = self.car()
        self.start_runtime(dict.fromkeys(receipt_runtime.DRAFT_FIELDS))
        status, draft = self.ai(car_id, path='/api/receipt-draft')
        self.assertEqual(status, 200)
        self.assertEqual(set(draft), set(schemas['ReceiptDraft']['required']))
        self.assertEqual(set(draft['proposal']), set(schemas['ReceiptDraft']['properties']['proposal']['required']))
        with patch.dict(test_app.app.os.environ, {'CARCARE_OLLAMA_MODEL': ''}):
            status, off = self.ai(car_id, path='/api/receipt-draft')
        self.assertEqual(status, 503)
        self.assertEqual(set(off), set(schemas['AIUnavailable']['required']))
        self.assertIn('/api/receipt-draft', contract['paths'])

    def test_FCS_1_4_2_well_formed_but_wrong_values_are_flagged_for_the_owner(self):
        """FCS.1.4.2: return a receipt proposal, insufficient-evidence result or explicit failure."""
        car_id = self.car()
        receipt = 'Main St Auto, 2026-10-05, odometer 41,200 km, brake pads replaced, total $312.40'
        self.start_runtime(dict(service_date='2026-10-06', service_item='Brake service', category='Repair',
                                odometer_value=42100, odometer_unit='km', cost='321.40', provider='Main Street Auto'))
        status, result = self.ai(car_id, receipt, path='/api/receipt-draft')
        self.assertEqual(status, 200)
        flags = {k: v['status'] for k, v in result['evidence'].items()}
        self.assertEqual(flags, dict(service_date='check', service_item='found', category='check',
                                     mileage='check', cost='check', provider='check'))
        self.assertEqual(self.dashboard(car_id)['records'], [])

    def test_FCS_1_4_2_missing_and_invalid_fields_become_insufficient_evidence(self):
        car_id = self.car()
        self.start_runtime(dict(service_date='2999-01-01', service_item='Detailing', category=None,
                                odometer_value=None, odometer_unit=None, cost='12.345', provider=None))
        status, result = self.ai(car_id, 'Thank you for your visit', path='/api/receipt-draft')
        self.assertEqual(status, 200)
        self.assertEqual(set(result['proposal'].values()), {None})
        self.assertEqual({v['status'] for v in result['evidence'].values()}, {'missing'})

    def test_malformed_runtime_reply_is_an_explicit_failure(self):
        car_id = self.car()
        self.start_runtime(dict(service_date='2026-01-02', mileage=10000))
        status, result = self.ai(car_id, path='/api/receipt-draft')
        self.assertEqual((status, result['reason']), (503, 'runtime_unavailable'))
        self.assertEqual(self.dashboard(car_id)['records'], [])

    def test_browser_route_reports_when_ai_is_not_configured(self):
        car_id = self.car()
        with patch.dict(test_app.app.os.environ, {'CARCARE_OLLAMA_MODEL': ''}):
            status, result = self.ai(car_id, path='/api/receipt-draft')
        self.assertEqual((status, result['status'], result['reason']), (503, 'unavailable', 'not_configured'))
        self.assertIsNone(result['proposal'])
        self.assertEqual(self.dashboard(car_id)['records'], [])


class OperatorConfigurationTests(unittest.TestCase):
    def test_ASR_1_1_3_operator_settings_set_model_port_and_timeout(self):
        """ASR 1.1.3: accept configured AI service contract limits from the Application Operator."""
        with patch.dict(receipt_runtime.os.environ, {'CARCARE_OLLAMA_TIMEOUT': '7.5', 'CARCARE_OLLAMA_PORT': '12345'}):
            self.assertEqual(receipt_runtime._env_number('CARCARE_OLLAMA_TIMEOUT', '60'), 7.5)
            self.assertEqual(receipt_runtime._env_number('CARCARE_OLLAMA_PORT', '11434', int), 12345)
        for bad in ('0', '-3', 'soon'):
            with patch.dict(receipt_runtime.os.environ, {'CARCARE_OLLAMA_TIMEOUT': bad}):
                self.assertEqual(receipt_runtime._env_number('CARCARE_OLLAMA_TIMEOUT', '60'), 60.0)
        request = receipt_runtime.build_request('text', receipt_runtime.PINNED_MODEL)
        self.assertEqual(request['model'], 'qwen3.5:4b')
        self.assertFalse(request['think'])
        self.assertEqual(receipt_runtime.RUNTIME_HOST, '127.0.0.1')


class ReceiptAssistStatusTests(unittest.TestCase):
    setUp = test_app.AppTests.setUp
    tearDown = test_app.AppTests.tearDown
    call = test_app.AppTests.call

    def test_page_learns_whether_ai_drafting_is_on(self):
        with patch.dict(test_app.app.os.environ, {'CARCARE_OLLAMA_MODEL': ''}):
            status, off = self.call('/api/receipt-assist')
        self.assertEqual((status, off['enabled'], off['model']), (200, False, None))
        with patch.dict(test_app.app.os.environ, {'CARCARE_OLLAMA_MODEL': receipt_runtime.PINNED_MODEL}):
            status, on = self.call('/api/receipt-assist')
        self.assertEqual((on['enabled'], on['model']), (True, receipt_runtime.PINNED_MODEL))
        self.assertIn('QuickLube Express', on['sample'])
