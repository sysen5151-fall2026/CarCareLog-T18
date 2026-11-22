"""Isolated HTTP acceptance check for CarCareLog's image review and save flow."""

import argparse
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import time
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo.resolve() / 'CarCareLog' / 'tools'))
    from smoke_test import App, dashboard
    from backend.receipt_runtime import PINNED_MODEL

    data = args.fixture.read_bytes()
    image = base64.b64encode(data).decode('ascii')
    report = {'started_utc': datetime.now(timezone.utc).isoformat(), 'model': PINNED_MODEL,
              'fixture': args.fixture.name, 'scope': 'loopback HTTP product workflow, isolated temporary SQLite database',
              'checks': []}

    def expect(name, passed, evidence):
        report['checks'].append({'check': name, 'pass': passed, 'observed': evidence})
        args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        if not passed:
            raise AssertionError(name + ': ' + str(evidence))

    with tempfile.TemporaryDirectory(prefix='carcare-image-smoke-') as directory:
        db = Path(directory) / 'image-smoke.db'
        env = {'CARCARE_DB': str(db), 'CARCARE_OLLAMA_MODEL': PINNED_MODEL}
        with App(env) as app:
            status, demo = app.call('POST', '/api/demo', {})
            expect('Demo vehicle seeded', status == 201, {'http': status})
            vehicle_id = demo['vehicle_id']
            initial = dashboard(app, vehicle_id)
            payload = {'vehicle_id': vehicle_id, 'receipt_image': image}
            start = time.perf_counter()
            status, draft = app.call('POST', '/api/receipt-draft', payload)
            duration = round(time.perf_counter() - start, 3)
            expect('PNG returns an unconfirmed draft from the real local model',
                   status == 200 and draft.get('status') == 'needs_review' and draft.get('owner_confirmed') is False,
                   {'http': status, 'status': draft.get('status'), 'owner_confirmed': draft.get('owner_confirmed'), 'seconds': duration})
            flags = {field: value['status'] for field, value in draft['evidence'].items()}
            expect('Each image-derived field requires review', len(flags) == 6 and set(flags.values()) <= {'check','missing'}, flags)
            rows = len(dashboard(app, vehicle_id)['records'])
            expect('Producing the draft leaves persistence unchanged', rows == len(initial['records']), {'rows': rows})
            proposal = draft['proposal']
            record = {**proposal, 'vehicle_id': vehicle_id, 'operation_id': str(uuid4()), 'owner_confirmed': False,
                      'notes': 'Automated synthetic image workflow.'}
            status, _ = app.call('POST', '/api/records', record)
            rows = len(dashboard(app, vehicle_id)['records'])
            expect('Unconfirmed write is rejected', status == 400 and rows == len(initial['records']), {'http': status, 'rows': rows})
            record['owner_confirmed'] = True
            status, first_save = app.call('POST', '/api/records', record)
            expect('Simulated owner confirmation saves one record', status == 201 and len(dashboard(app, vehicle_id)['records']) == rows + 1,
                   {'http': status, 'fields': proposal})
            status, second_save = app.call('POST', '/api/records', record)
            expect('Retry of the same confirmation does not duplicate the record', status == 201 and second_save.get('id') == first_save.get('id') and len(dashboard(app, vehicle_id)['records']) == rows + 1,
                   {'http': status, 'same_record_id': second_save.get('id') == first_save.get('id')})
        with App(env) as app:
            recovered = dashboard(app, vehicle_id)
            expect('Saved record survives app restart', len(recovered['records']) == len(initial['records']) + 1,
                   {'rows': len(recovered['records']), 'total_cents': recovered['total_cents']})
        contents = db.read_bytes()
        expect('Fixture raw bytes and base64 absent from the resulting SQLite file', data not in contents and image.encode('ascii') not in contents,
               {'png_bytes_present': data in contents, 'base64_present': image.encode('ascii') in contents})
    report['finished_utc'] = datetime.now(timezone.utc).isoformat()
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('PASS', len(report['checks']), 'real-model image-workflow checks')


if __name__ == '__main__':
    main()
