"""Reproduce the predeclared chapter 14 pilot tests using a throwaway database."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
import sys
import tempfile
import time
from unittest.mock import patch


def save_series(path, rows):
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarize(samples, passed):
    n = len(samples)
    p = passed / n
    z = 1.959963984540054
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    radius = z * math.sqrt(p * (1-p)/n + z*z/(4*n*n)) / denominator
    return dict(n=n, passed=passed, median_s=statistics.median(samples),
                nearest_rank_p95_s=sorted(samples)[math.ceil(0.95*n)-1],
                wilson95=[max(0,center-radius),min(1,center+radius)])


def simulate(out):
    steps = json.loads((Path(__file__).with_name('chapter14-simulation-steps.json')).read_text())
    rng = random.Random(515114)
    rows = []
    for trial in range(1, 1001):
        elapsed = 0
        for step in steps:
            p = step['parameters']
            duration = (rng.expovariate(p['lambda']) if step['distribution']=='EXPONENTIAL'
                        else rng.gauss(p['mu'],p['sigma']))
            elapsed += max(0,duration)
        rows.append(dict(trial=trial,seconds=elapsed,within_180s=elapsed<=180))
    save_series(out/'chapter14-simulation-trials.csv',rows)
    return summarize([r['seconds'] for r in rows],sum(r['within_180s'] for r in rows))


def exercise(app_root, out):
    sys.path.insert(0,str(app_root.resolve()))
    sys.path.insert(0,str((app_root/'tests').resolve()))
    import test_app
    from backend import app
    rows = []
    case = test_app.AppTests()
    case.setUp()
    try:
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ,{'CARCARE_OLLAMA_MODEL':'fault-fixture'}), patch.object(
            app,'draft_receipt',side_effect=app.ReceiptRuntimeUnavailable('chapter 14 simulated outage')):
            for i in range(1,31):
                app.DB_PATH=Path(temp)/f'trial-{i}.db'
                app.init_db()
                selected=case.car(f'Bench {i} A')
                other=case.car(f'Bench {i} B')
                amount=i+100
                start=time.perf_counter()
                before=case.dashboard(selected)
                reject_status,reply=case.call('/api/receipt-draft','POST',
                                              {'vehicle_id':selected,'receipt_text':f'Synthetic {i} receipt'})
                after_failure=case.dashboard(selected)
                unconfirmed,_=case.record(selected,cost=f'{amount}.25',owner_confirmed=False)
                still_empty=not case.dashboard(selected)['records']
                status,_=case.record(selected,cost=f'{amount}.25',provider=f'Garage {i}')
                saved=case.dashboard(selected)
                other_data=case.dashboard(other)
                elapsed=time.perf_counter()-start
                records=saved['records']
                matched=(len(records)==1 and records[0]['service_item']=='Oil change' and
                         saved['total_cents']==100*amount+25 and records[0]['provider']==f'Garage {i}'
                         and saved['vehicle']['id']==selected)
                status_clear=(reply.get('status')=='unavailable' and reply.get('reason')=='runtime_unavailable'
                              and reply.get('vehicle_id')==selected and bool(reply.get('message')))
                ok=(reject_status==503 and status_clear and before==after_failure and unconfirmed==400 and
                    still_empty and status==201 and matched and not other_data['records'])
                rows.append(dict(trial=i,seconds=elapsed,read_status=200,fault_http=reject_status,
                                 fault_message=reply.get('message'),unconfirmed_http=unconfirmed,
                                 no_write_before_confirmation=still_empty,save_http=status,selected_rows=len(records),
                                 other_rows=len(other_data['records']),expected_cents=100*amount+25,
                                 observed_cents=saved['total_cents'],ok=bool(ok)))
    finally:
        case.tearDown()
    save_series(out/'chapter14-operating-trials.csv',rows)
    return summarize([r['seconds'] for r in rows],sum(r['ok'] for r in rows))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app',type=Path,help='CarCareLog application directory containing backend and tests')
    parser.add_argument('out',type=Path,help='Output directory for trial records')
    args=parser.parse_args()
    args.out.mkdir(exist_ok=True,parents=True)
    tracked=['backend/app.py','backend/function_f22.py','backend/receipt_runtime.py','frontend/app.js','frontend/index.html']
    hashes={f:hashlib.sha256((args.app/f).read_bytes()).hexdigest() for f in tracked}
    result={'simulation':simulate(args.out),'operating':exercise(args.app,args.out),'product_file_sha256':hashes,
            'protocol_sha256':hashlib.sha256(Path(__file__).with_name('chapter14-protocol.md').read_bytes()).hexdigest()}
    (args.out/'chapter14-results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
