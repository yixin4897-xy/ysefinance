"""Synthetic vintages only; never fetch or execute capture."""
import copy
from decimal import Decimal, Inexact, ROUND_DOWN, getcontext, localcontext
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import aesm_revision_compare as revision
import aesm_capture as capture
import aesm_provenance as provenance


def fixture(new=False, monthly=False):
    request = provenance.read_json(ROOT / 'docs/examples/aesm-capture-e12-quarterly.json')
    request['official_source_url'] = 'https://data.api.abs.gov.au/rest/data/SYNTHETIC_NOT_OFFICIAL'
    request['validation_contract'].update(adapter='ABS_SDMX_CSV', minimum_observations=2,
        dimensions={'SERIES': 'SYNTHETIC_E12', 'UNIT_MEASURE': 'PCT'}, series_id='SYNTHETIC_E12',
        frequency='monthly' if monthly else 'quarterly')
    if monthly:
        request['methodological_variant'] = 'B'
    day = '02' if new else '01'
    with patch.object(capture, 'now', return_value=f'2026-10-{day}T00:00:00+00:00'):
        start = capture.start_record(request, ('b' if new else 'a') * 32, 'HTTPS_DOWNLOAD')
    values = [('2025-Q1', None), ('2025-Q2', '1.10'), ('2025-Q3', '2.20'), ('2025-Q4', '3.30')]
    if new:
        values = [('2025-Q2', '1.1'), ('2025-Q3', '2.3'), ('2025-Q4', None), ('2026-Q1', None)]
    # Missingness is permitted only at the boundaries, as in Phase 2B.
    if monthly:
        values = [(f'2025-{(int(p[:4]) - 2025) * 4 + int(p[-1]):02}', v) for p, v in values]
    text = 'SERIES,UNIT_MEASURE,TIME_PERIOD,OBS_VALUE\n' + ''.join(
        f'SYNTHETIC_E12,PCT,{p},{v or ""}\n' for p, v in values)
    final = copy.deepcopy(start)
    sha = capture.digest(text.encode())
    final.update(outcome='VALIDATED', start_record_id=start['record_id'],
        retrieved_at_utc=f'2026-10-{day}T00:00:01+00:00', completed_at_utc=f'2026-10-{day}T00:00:02+00:00')
    final['source'] = {'original_filename': 'synthetic.csv', 'filename_basis': 'URL_PATH',
        'sha256': sha, 'byte_count': len(text.encode()), 'snapshot_id': 'sha256-' + sha,
        'snapshot_path': 'snapshots/sha256/' + sha}
    rows = [(p, revision.number(v or '')) for p, v in values]
    final['validation'].update(state='PASSED', coverage=capture.coverage(rows, request['validation_contract']['frequency'], 2))
    return {'synthetic_only': True, 'start': start, 'record': capture.record_seal(final), 'source_text': text,
        'methodology': {'definition_version': 'synthetic-v1', 'methodology': 'synthetic annual rate',
            'reference_year': 'NOT_APPLICABLE', 'price_basis': 'percentage change', 'percentage_point_applicable': True}}


def reseal(bundle):
    bundle['start']['request_sha256'] = capture.digest(provenance.canonical(bundle['start']['request']))
    bundle['start'] = capture.record_seal(bundle['start'])
    bundle['record']['request'] = copy.deepcopy(bundle['start']['request'])
    bundle['record']['request_sha256'] = bundle['start']['request_sha256']
    bundle['record']['start_record_id'] = bundle['start']['record_id']
    bundle['record'] = capture.record_seal(bundle['record'])


def source_text(bundle, text):
    """Reseal intentionally edited synthetic bytes, independent of CSV parser."""
    bundle['source_text'] = text
    raw = text.encode('utf-8')
    sha = capture.digest(raw)
    bundle['record']['source'].update(sha256=sha, byte_count=len(raw),
        snapshot_id='sha256-' + sha, snapshot_path='snapshots/sha256/' + sha)
    bundle['record'] = capture.record_seal(bundle['record'])


def observations(bundle, rows):
    text = 'SERIES,UNIT_MEASURE,TIME_PERIOD,OBS_VALUE\n' + ''.join(
        f'SYNTHETIC_E12,PCT,{p},{v if v is not None else ""}\n' for p, v in rows)
    bundle['record']['validation']['coverage'] = capture.coverage(
        [(p, Decimal(v) if v is not None else None) for p, v in rows],
        bundle['record']['request']['validation_contract']['frequency'], 2)
    source_text(bundle, text)


class RevisionChecks(unittest.TestCase):
    def test_all_classifications_and_exact_decimal(self):
        report = revision.compare(fixture(), fixture(True))
        self.assertEqual(report['summary']['counts'], dict.fromkeys(revision.CLASSES, 1))
        revised = report['observations'][2]
        self.assertEqual((revised['signed_change'], revised['absolute_change'], revised['percentage_point_change']), ('0.1', '0.1', '0.1'))
        self.assertEqual(report['summary']['mean_absolute_change'], '0.05')
        self.assertEqual(report['composite_release_statuses'], provenance.HOLD)
        self.assertFalse(report['point_in_time_eligible'])

    def test_deterministic_no_mutation_no_network(self):
        a, b = fixture(), fixture(True)
        before = copy.deepcopy((a, b))
        with patch.object(capture, 'open_official', side_effect=AssertionError('No network')):
            first = revision.compare(a, b)
            self.assertEqual(first, revision.compare(a, b))
        self.assertEqual((a, b), before)

    def test_decimal_context_and_negative_zero(self):
        previous = getcontext().prec
        try:
            getcontext().prec = 2
            a = revision.compare(fixture(), fixture(True))
            getcontext().prec = 50
            self.assertEqual(a, revision.compare(fixture(), fixture(True)))
        finally:
            getcontext().prec = previous
        self.assertEqual(revision.decimal_text(revision.number('-0.00')), '0')

    def test_identity_mismatches(self):
        for key, value, nested in [('provider', 'RBA', False), ('indicator', 'E04', False),
            ('methodological_variant', 'B', False), ('source_role', 'other', False),
            ('series_id', 'other', True), ('unit', 'Index', True),
            ('seasonal_adjustment', 'Original', True), ('frequency', 'monthly', True)]:
            with self.subTest(key=key):
                b = fixture(True)
                target = b['start']['request']['validation_contract'] if nested else b['start']['request']
                target[key] = value
                reseal(b)
                with self.assertRaises(ValueError):
                    revision.compare(fixture(), b)

    def test_methodology_breaks_block_numerical_comparison(self):
        for key in revision.METHOD_FIELDS:
            b = fixture(True)
            b['methodology'][key] = False if key == 'percentage_point_applicable' else 'changed'
            report = revision.compare(fixture(), b)
            self.assertEqual(report['status'], 'MANUAL_REVIEW_REQUIRED')
            self.assertEqual(report['observations'], [])
            self.assertIsNone(report['summary'])

    def test_description_table_and_data_type_changes_require_review(self):
        for key in ('description', 'table', 'data_type'):
            b = fixture(True)
            b['start']['request']['validation_contract'][key] = 'changed'
            reseal(b)
            self.assertEqual(revision.compare(fixture(), b)['manual_review_reasons'], [key])

    def test_invalid_capture_hash_linkage_and_approvals(self):
        for key, value in [('record_id', 'sha256-' + '0' * 64), ('capture_id', 'c' * 32),
                           ('outcome', 'INTERRUPTED'), ('outcome', 'TRANSFER_FAILED'),
                           ('outcome', 'STARTED'), ('retrieved_at_utc', None)]:
            b = fixture(True)
            b['record'][key] = value
            with self.assertRaises(ValueError):
                revision.compare(fixture(), b)
        b = fixture(True)
        b['record']['approval']['publication_approved'] = True
        b['record'] = capture.record_seal(b['record'])
        with self.assertRaises(ValueError):
            revision.compare(fixture(), b)

    def test_source_tampering_and_synthetic_gate(self):
        for key, value in [('source_text', 'tampered'), ('synthetic_only', False)]:
            b = fixture(True)
            b[key] = value
            with self.assertRaises(ValueError):
                revision.compare(fixture(), b)

    def test_invalid_numbers_and_periods(self):
        for v in ('NaN', 'Infinity', '1e9999', 'True', '1,000', 'x'):
            with self.assertRaises(ValueError):
                revision.number(v)
        b = fixture(True)
        b['source_text'] = b['source_text'].replace('2025-Q3', '2025 Q3')
        raw = b['source_text'].encode()
        sha = capture.digest(raw)
        b['record']['source'].update(sha256=sha, byte_count=len(raw), snapshot_id='sha256-'+sha, snapshot_path='snapshots/sha256/'+sha)
        b['record'] = capture.record_seal(b['record'])
        with self.assertRaises(ValueError):
            revision.compare(fixture(), b)

    def test_coverage_tampering(self):
        b = fixture(True)
        b['record']['validation']['coverage']['observation_count'] = 99
        b['record'] = capture.record_seal(b['record'])
        with self.assertRaises(ValueError):
            revision.compare(fixture(), b)

    def test_reversed_or_same_capture(self):
        for a, b in [(fixture(True), fixture()), (fixture(), fixture())]:
            with self.assertRaises(ValueError):
                revision.compare(a, b)

    def test_monthly_keys(self):
        self.assertEqual(revision.compare(fixture(monthly=True), fixture(True, monthly=True))['observations'][0]['period'], '2025-01')

    def test_percentage_points_not_inferred_from_unit(self):
        a, b = fixture(), fixture(True)
        for x in (a, b):
            x['methodology']['percentage_point_applicable'] = False
        self.assertTrue(all(r['percentage_point_change'] is None for r in revision.compare(a, b)['observations']))

    def test_checked_in_fixtures(self):
        folder = ROOT / 'tests/fixtures/aesm_revision'
        report = revision.compare(provenance.read_json(folder / 'old.json'), provenance.read_json(folder / 'new.json'))
        self.assertEqual(report['summary']['counts'], dict.fromkeys(revision.CLASSES, 1))

    def test_zero_negative_and_both_missing(self):
        a, b = fixture(), fixture()
        b['start']['capture_id'] = 'b' * 32
        b['record']['capture_id'] = 'b' * 32
        for key in ('started_at_utc',):
            b['start'][key] = b['start'][key].replace('10-01', '10-02')
            b['record'][key] = b['start'][key]
        for key in ('retrieved_at_utc', 'completed_at_utc'):
            b['record'][key] = b['record'][key].replace('10-01', '10-02')
        for x in (a, b):
            x['source_text'] = x['source_text'].replace('1.10', '0.00').replace('2.20', '-2.20')
            raw = x['source_text'].encode()
            sha = capture.digest(raw)
            x['record']['source'].update(sha256=sha, byte_count=len(raw), snapshot_id='sha256-'+sha, snapshot_path='snapshots/sha256/'+sha)
            reseal(x)
        report = revision.compare(a, b)
        self.assertEqual(report['summary']['counts']['UNCHANGED'], 4)
        self.assertEqual(report['summary']['maximum_absolute_change'], '0')
        self.assertIsNone(report['observations'][0]['signed_change'])

    def test_duplicate_and_gap_periods_rejected_even_with_new_hash(self):
        for period in ('2025-Q2', '2026-Q3'):
            b = fixture(True)
            b['source_text'] = b['source_text'].replace('2025-Q3', period)
            raw = b['source_text'].encode()
            sha = capture.digest(raw)
            b['record']['source'].update(sha256=sha, byte_count=len(raw), snapshot_id='sha256-'+sha, snapshot_path='snapshots/sha256/'+sha)
            b['record'] = capture.record_seal(b['record'])
            with self.assertRaises(ValueError):
                revision.compare(fixture(), b)

    def test_unknown_declarations_block_even_when_equal(self):
        for key in revision.METHOD_FIELDS - {'percentage_point_applicable'}:
            for placeholder in ('UNKNOWN', ' pending ', 'TBD'):
                a, b = fixture(), fixture(True)
                a['methodology'][key] = b['methodology'][key] = placeholder
                report = revision.compare(a, b)
                self.assertEqual(report['status'], 'MANUAL_REVIEW_REQUIRED')
                self.assertIn(f'old.{key}_unknown', report['manual_review_reasons'])
                self.assertEqual(report['observations'], [])
                self.assertIsNone(report['summary'])

    def test_source_percentage_units_must_agree_with_declaration(self):
        for code, unit in [('PCT', 'Index'), ('NUM', 'Percent'), (None, 'Percent')]:
            a, b = fixture(), fixture(True)
            for x in (a, b):
                c = x['start']['request']['validation_contract']
                c['unit'] = unit
                x['methodology']['percentage_point_applicable'] = False
                if code is None:
                    del c['dimensions']['UNIT_MEASURE']
                else:
                    c['dimensions']['UNIT_MEASURE'] = code
                source_text(x, x['source_text'].replace(',PCT,', f',{code},'))
                reseal(x)
            with self.assertRaisesRegex(ValueError, 'UNIT_MEASURE'):
                revision.compare(a, b)

    def test_filename_provenance_and_success_error_consistency(self):
        for mutate in (lambda b: b['record']['source'].update(filename_basis='LOCAL_BASENAME'),
                       lambda b: b['record']['validation'].update(error_type='RuntimeError')):
            b = fixture(True)
            mutate(b)
            b['record'] = capture.record_seal(b['record'])
            # Phase 2B accepts these resealed records; Phase 2C must reject them.
            capture.validate_record(b['record'])
            with self.assertRaises(ValueError):
                revision.compare(fixture(), b)

    def test_malformed_csv_duplicate_headers_and_ragged_rows(self):
        for change in (lambda s: s.rstrip('\n') + '"',
                       lambda s: s.replace('SERIES,UNIT_MEASURE', 'SERIES,SERIES', 1),
                       lambda s: s.replace('2025-Q3,2.3', '2025-Q3,2.3,extra'),
                       lambda s: s.replace('2025-Q3,2.3', '2025-Q3')):
            b = fixture(True)
            source_text(b, change(b['source_text']))
            with self.assertRaises(ValueError):
                revision.compare(fixture(), b)

    def test_ascii_periods_year_zero_and_unicode_numbers(self):
        for number in ('\u0661.\u0662', '1\u0662', '9' * 101):
            with self.assertRaises(ValueError):
                revision.number(number)
        for period in ('0000-Q3', '\u0662\u0660\u0662\u0665-Q3', '2025-Q0', '2025-Q5', '2025-3'):
            b = fixture(True)
            source_text(b, b['source_text'].replace('2025-Q3', period))
            with self.assertRaises(ValueError):
                revision.compare(fixture(), b)

    def test_valid_failed_terminal_records_are_ineligible(self):
        for outcome in ('TRANSFER_FAILED', 'INTERRUPTED', 'VALIDATION_FAILED'):
            b = fixture(True)
            b['record']['outcome'] = outcome
            b['record']['validation'].update(state='NOT_RUN', coverage=None, error_type='SyntheticFailure')
            if outcome == 'VALIDATION_FAILED':
                b['record']['source']['snapshot_path'] = b['record']['source']['snapshot_path'].replace('snapshots/', 'quarantine/')
                b['record']['validation']['state'] = 'FAILED'
            else:
                b['record']['source'] = dict.fromkeys(b['record']['source'])
                b['record']['retrieved_at_utc'] = None
            b['record'] = capture.record_seal(b['record'])
            capture.validate_record(b['record'])
            with self.assertRaisesRegex(ValueError, 'Only complete VALIDATED'):
                revision.compare(fixture(), b)

    def test_resealed_start_linkage_schema_and_hash_count_failures(self):
        for mutate in (lambda b: b['record'].update(start_record_id='sha256-' + '0' * 64),
                       lambda b: b['record'].update(implementation_sha256='0' * 64),
                       lambda b: b['record']['source'].update(byte_count=1)):
            b = fixture(True)
            mutate(b)
            b['record'] = capture.record_seal(b['record'])
            with self.assertRaises(ValueError):
                revision.compare(fixture(), b)
        b = fixture(True)
        for k in ('start', 'record'):
            b[k]['record_schema_sha256'] = '0' * 64
        reseal(b)
        with self.assertRaisesRegex(ValueError, 'Unsupported capture schema'):
            revision.compare(fixture(), b)

    def test_local_import_preserves_unknown_retrieval_time(self):
        a, b = fixture(), fixture(True)
        for x in (a, b):
            x['start']['transport'] = x['record']['transport'] = 'LOCAL_IMPORT'
            x['record']['retrieved_at_utc'] = None
            x['record']['source']['filename_basis'] = 'LOCAL_BASENAME'
            reseal(x)
        report = revision.compare(a, b)
        self.assertIsNone(report['old_vintage']['retrieved_at_utc'])
        self.assertIsNone(report['new_vintage']['retrieved_at_utc'])
        self.assertFalse(report['point_in_time_eligible'])

    def test_disjoint_coverage_has_null_statistics(self):
        a, b = fixture(), fixture(True)
        observations(b, [('2026-Q1', '1'), ('2026-Q2', '2')])
        report = revision.compare(a, b)
        self.assertEqual(report['summary']['overlap_period_count'], 0)
        self.assertEqual(report['summary']['numeric_pair_count'], 0)
        for key in ('mean_signed_change', 'mean_absolute_change', 'maximum_absolute_change'):
            self.assertIsNone(report['summary'][key])
        self.assertEqual(report['summary']['counts']['REMOVED_OBSERVATION'], 4)

    def test_missing_to_value_internal_missing_and_all_missing(self):
        a, b = fixture(), fixture(True)
        observations(b, [('2025-Q1', '0'), ('2025-Q2', '1.1'), ('2025-Q3', '2.2'), ('2025-Q4', '3.3')])
        self.assertEqual(revision.compare(a, b)['observations'][0]['classification'], 'MISSINGNESS_CHANGED')
        # Rehash invalid payloads while retaining valid capture coverage: never fill gaps.
        for text in (b['source_text'].replace('2025-Q2,1.1', '2025-Q2,'),
                     'SERIES,UNIT_MEASURE,TIME_PERIOD,OBS_VALUE\nSYNTHETIC_E12,PCT,2025-Q1,\n'):
            source_text(b, text)
            with self.assertRaises(ValueError):
                revision.compare(a, b)

    def test_decimal_extremes_and_nonterminating_mean_ignore_caller_context(self):
        a, b = fixture(), fixture(True)
        rows = [('2025-Q1', '0'), ('2025-Q2', '0'), ('2025-Q3', '0')]
        observations(a, rows)
        observations(b, [('2025-Q1', '1'), ('2025-Q2', '0'), ('2025-Q3', '0')])
        with localcontext() as ctx:
            ctx.prec = 2
            ctx.rounding = ROUND_DOWN
            ctx.traps[Inexact] = True
            report = revision.compare(a, b)
        self.assertEqual(report['summary']['mean_signed_change'], '0.' + '3' * 256)
        huge, tiny = '9' * 99, '0.' + '0' * 97 + '1'
        observations(a, [('2025-Q1', huge), ('2025-Q2', tiny)])
        observations(b, [('2025-Q1', huge), ('2025-Q2', '0')])
        report = revision.compare(a, b)
        self.assertEqual(report['observations'][1]['signed_change'], '-' + tiny)

    def test_cli_deterministic_across_hash_seeds_and_failure_exit_codes(self):
        import os
        folder = ROOT / 'tests/fixtures/aesm_revision'
        command = [sys.executable, '-B', str(ROOT / 'scripts/aesm_revision_compare.py'),
                   '--old', str(folder / 'old.json'), '--new', str(folder / 'new.json')]
        runs = [subprocess.run(command, capture_output=True, env={**os.environ, 'PYTHONHASHSEED': seed}) for seed in ('1', '7')]
        self.assertTrue(all(r.returncode == 0 and not r.stderr for r in runs))
        self.assertEqual(runs[0].stdout, runs[1].stdout)
        self.assertEqual(json.loads(runs[0].stdout)['summary']['union_period_count'], 5)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'new.json'
            b = fixture(True)
            b['methodology']['reference_year'] = 'changed'
            path.write_text(json.dumps(b), encoding='utf-8')
            cmd = command[:-1] + [str(path)]
            result = subprocess.run(cmd, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)['status'], 'MANUAL_REVIEW_REQUIRED')
            path.write_text('{"synthetic_only":true,"synthetic_only":false}', encoding='utf-8')
            result = subprocess.run(cmd, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, b'')


if __name__ == '__main__':
    unittest.main()
