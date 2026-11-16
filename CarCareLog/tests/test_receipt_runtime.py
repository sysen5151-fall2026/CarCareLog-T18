"""Exercise the receipt boundary with an isolated local HTTP runtime fixture."""

import json
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

    def ai(self, car_id):
        return self.call('/internal/v1/coordinate-ai', 'POST', {
            'vehicle_id': car_id, 'kind': 'receipt', 'receipt_text': 'Synthetic receipt, oil change, USD 80.25',
        })

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
        self.assertIsNone(result['proposal'])
        self.assertEqual(self.dashboard(car_id), before)
        self.assertEqual(self.record(car_id, cost='9.75')[0], 201)
        self.assertEqual(self.dashboard(car_id)['total_cents'], before['total_cents'] + 975)

    def test_draft_requires_review_and_does_not_write(self):
        car_id = self.car()
        proposal = dict(service_date='2026-01-02', service_item='Oil change',
                        category='Maintenance', mileage=10000, cost='99.99', provider='Garage')
        requests = self.start_runtime(proposal)
        status, result = self.ai(car_id)
        self.assertEqual(status, 200)
        self.assertEqual(result['status'], 'needs_review')
        self.assertIs(result['owner_confirmed'], False)
        self.assertEqual(result['proposal']['cost'], '99.99')  # Plausible value differs from source text.
        self.assertEqual(self.dashboard(car_id)['records'], [])
        self.assertEqual(self.record(car_id, **result['proposal'], owner_confirmed=False)[0], 400)
        self.assertEqual(self.dashboard(car_id)['records'], [])
        self.assertEqual(len(requests), 1)
        self.assertIn('Synthetic receipt', requests[0][1]['prompt'])
        self.assertNotIn('vehicle_id', requests[0][1])
