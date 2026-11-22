"""Measure local image-only drafts against the existing 20 synthetic receipt labels.

Run after installing the pinned Ollama model. Pillow is required only to render
the test fixtures. The label and source text never enter the model request.
"""

import argparse
import base64
from datetime import date, datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import platform
import statistics
import sys
import time

from PIL import Image, ImageDraw, ImageFont, __version__ as pillow_version


def image_from_text(text):
    font = ImageFont.load_default(size=23)
    lines = text.splitlines()
    width = max(500, int(max(font.getlength(line) for line in lines)) + 50)
    image = Image.new('RGB', (width, 48 + 34 * len(lines)), 'white')
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(lines):
        draw.text((24, 20 + index * 34), line, font=font, fill='black')
    output = io.BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2],
                        help='Repository root, inferred when run from CarCareLog/tools.')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--fixtures-only', action='store_true')
    parser.add_argument('--as-of', type=date.fromisoformat, default=date.today(),
                        help='Local review date used by the app for the future-date check (YYYY-MM-DD).')
    args = parser.parse_args()
    product = args.repo.resolve() / 'CarCareLog'
    sys.path[:0] = [str(product), str(product / 'tools')]
    from backend import receipt_runtime as runtime
    from backend.function_f22 import review_receipt_draft
    from evaluate_receipts import load_samples, nearest_rank_p95, score, summarize

    output = args.output_dir.resolve()
    image_dir = output / 'fixtures'
    image_dir.mkdir(parents=True, exist_ok=True)
    samples_path = product / 'data' / 'receipt-samples.jsonl'
    samples = load_samples(samples_path)
    fixture_hashes = {}
    for sample in samples:
        path = image_dir / (sample['id'] + '.png')
        data = image_from_text(sample['text'])
        path.write_bytes(data)
        fixture_hashes[sample['id']] = sha256(data).hexdigest()
    if args.fixtures_only:
        print(f'{len(samples)} clean synthetic PNG fixtures rendered.')
        return

    if runtime.PINNED_MODEL != 'qwen3.5:4b':
        raise SystemExit('Use the checkout implementing qwen3.5:4b receipt image support.')
    details = runtime.runtime_details(runtime.PINNED_MODEL)
    before = runtime._call_runtime('GET', '/api/ps', timeout=10)
    if any(m['name'] == runtime.PINNED_MODEL for m in before['models']):
        runtime._call_runtime('POST', '/api/generate', {'model': runtime.PINNED_MODEL, 'keep_alive': 0}, timeout=30)
    after = runtime._call_runtime('GET', '/api/ps', timeout=10)
    cold = not any(m['name'] == runtime.PINNED_MODEL for m in after['models'])
    tag = next(m for m in runtime._call_runtime('GET', '/api/tags')['models'] if m['name'] == runtime.PINNED_MODEL)
    metadata = {
        'started_utc': datetime.now(timezone.utc).isoformat(), 'local_model': details,
        'ollama_tag_manifest_sha256': tag['digest'], 'model_size_bytes': tag.get('size'),
        'cold_start_verified': cold, 'platform': platform.platform(), 'cpu': platform.processor(),
        'pillow': pillow_version, 'review_date': args.as_of.isoformat(),
        'fixture_type': 'clean PNG renderings of synthetic text; no photos, skew, or glare',
        'source': 'CarCareLog/data/receipt-samples.jsonl', 'source_sha256': sha256(samples_path.read_bytes()).hexdigest(),
        'input_to_model': 'receipt image pixels and application prompt only; source text and labels withheld',
        'scope': 'adapter request and six-field review; excludes file selection, human review, and saving',
        'settings': runtime.GENERATION_OPTIONS, 'keep_alive': runtime.KEEP_ALIVE,
        'timeout_seconds': runtime.RUNTIME_TIMEOUT, 'source_images_sha256': fixture_hashes,
    }
    results = []
    for sample in samples:
        data = (image_dir / (sample['id'] + '.png')).read_bytes()
        encoded = base64.b64encode(data).decode('ascii')
        started = time.perf_counter()
        record = {'id': sample['id'], 'focus': sample['focus'], 'error': None}
        try:
            raw = runtime.draft_receipt('', runtime.PINNED_MODEL, receipt_image=encoded)
            reviewed = review_receipt_draft(raw, None, today=args.as_of)
            record['seconds'] = round(time.perf_counter() - started, 3)
            record['raw'] = raw
            record['fields'] = score(sample['label'], reviewed)
        except runtime.ReceiptRuntimeUnavailable as exc:
            record['seconds'] = round(time.perf_counter() - started, 3)
            record['error'] = str(exc)
        results.append(record)
        save_json(output / 'image-progress.json', {'run': metadata, 'results': results})
        print(record['id'], record['seconds'], record['error'] or 'draft returned', flush=True)
    summary = summarize(results)
    completed_seconds = [r['seconds'] for r in results[1:] if 'fields' in r]
    summary['completed_warm_median_seconds'] = round(statistics.median(completed_seconds), 3) if completed_seconds else None
    summary['completed_warm_p95_seconds'] = nearest_rank_p95(completed_seconds)
    summary['completed_warm_requests'] = len(completed_seconds)
    summary['correct_fields'] = summary['field_values'] - summary['wrong_values']
    summary['all_attempted_fields'] = len(samples) * 6
    summary['accuracy_counting_failed_drafts_as_no_credit'] = round(summary['correct_fields'] / summary['all_attempted_fields'], 4)
    metadata['finished_utc'] = datetime.now(timezone.utc).isoformat()
    save_json(output / 'qwen35-receipt-images.json', {'run': metadata, 'summary': summary, 'results': results})
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
