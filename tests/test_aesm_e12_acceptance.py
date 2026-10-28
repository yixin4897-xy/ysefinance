"""Deterministic synthetic XLSX fixtures. Never capture or edit source evidence."""
import copy
import datetime as dt
from decimal import Decimal, localcontext
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import aesm_e12_acceptance as acceptance
import aesm_provenance as provenance


def workbook(changes=None, remove=(), duplicate=False, metadata=None, packaging='baseline', last='2026-Q2'):
    """220 dated rows, 174 synthetic observations; no official values embedded."""
    policy = provenance.read_json(acceptance.POLICY_PATH)
    identity = policy['identity']
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    cells = {f'A{r}': v for r, v in acceptance.e12.LABELS.items()}
    cells.update({f'I{r}': v for r, v in {1: identity['description'], 2: 'Percent',
                 3: 'Seasonally Adjusted', 4: 'PERCENT', 5: 'Quarter', 6: '3', 10: identity['series_id']}.items()})
    entries = []
    for year in range(1972, 2028):
        for q in range(1, 5):
            period = f'{year}-Q{q}'
            if not '1972-Q3' <= period <= '2027-Q2' or period in remove:
                continue
            serial = str((dt.date(year, q*3, 1)-dt.date(1899, 12, 30)).days)
            value = '2.5' if '1983-Q1' <= period <= last else ''
            if changes and period in changes:
                value = changes[period]
            entries.append((period, serial, value))
    if duplicate:
        entries.insert(90, entries[90])
    valid = [entry for entry in entries if entry[2] not in ('', '..', 'NA')]
    cells.update({'I7': valid[0][1], 'I8': valid[-1][1], 'I9': str(len(valid))})
    cells.update(metadata or {})
    for row, (_, serial, value) in enumerate(entries, 11):
        cells[f'A{row}'] = serial
        cells[f'I{row}'] = value
    def sheet(mapping):
        root = ET.Element('worksheet', xmlns=ns)
        data = ET.SubElement(root, 'sheetData')
        for address, value in mapping.items():
            row = ET.SubElement(data, 'row')
            cell = ET.SubElement(row, 'c', r=address, t='inlineStr')
            ET.SubElement(ET.SubElement(cell, 'is'), 't').text = value
        return ET.tostring(root)
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as z:
        payloads = {
            'xl/workbook.xml': '<workbook xmlns="'+ns+'" xmlns:r="'+acceptance.workbook_reader.REL+'"><sheets><sheet name="Index" sheetId="1" r:id="r1"/><sheet name="Data1" sheetId="2" r:id="r2"/></sheets></workbook>',
            'xl/_rels/workbook.xml.rels': '<Relationships><Relationship Id="r1" Target="worksheets/index.xml"/><Relationship Id="r2" Target="worksheets/data.xml"/></Relationships>',
            'xl/worksheets/index.xml': sheet({'B6': identity['table']}),
            'xl/worksheets/data.xml': sheet(cells)}
        for name, data in payloads.items():
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            z.writestr(info, data)
        z.comment = packaging.encode('ascii')
    return output.getvalue()


def evidence(raw, policy):
    return {'identity': copy.deepcopy(policy['identity']), 'sha256': acceptance.digest(raw),
            'byte_count': len(raw), 'methodology': {
                'definition_version': 'synthetic-definition-v1', 'compilation_basis': 'pre-October-2025 quarterly',
                'seasonal_adjustment_basis': 'quarterly', 'historical_limitations': 'historical changes unresolved'},
            'release': {'date': '2026-09-30', 'period': 'August 2026',
                        'evidence_url': 'https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/aug-2026',
                        'workbook_url': 'https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/aug-2026/64010Appendix1a.xlsx',
                        'verification_note': 'Synthetic fixture attestation; no official release claim'}}


def inputs(candidate=None, expected='2026-Q2'):
    baseline = workbook()
    candidate = baseline if candidate is None else candidate
    policy = provenance.read_json(acceptance.POLICY_PATH)
    # Test-only policy copy pins synthetic bytes. The shipped policy is never changed.
    policy['baseline'].update(sha256=acceptance.digest(baseline), byte_count=len(baseline))
    old, new = evidence(baseline, policy), evidence(candidate, policy)
    if expected in ('2026-Q3', '2026-Q4'):
        date, period, slug = ('2026-10-28', 'September 2026', 'sep-2026') if expected == '2026-Q3' else ('2027-01-27', 'December 2026', 'dec-2026')
        new['release']['date'], new['release']['period'] = date, period
        new['release']['evidence_url'] = old['release']['evidence_url'].replace('aug-2026', slug)
        new['release']['workbook_url'] = new['release']['evidence_url'] + '/64010Appendix1a.xlsx'
    reviewed = {label: {k: ev['release'][k] for k in ('date', 'period', 'evidence_url', 'workbook_url')}
                for label, ev in [('baseline', old), ('candidate', new)]}
    profile = {'policy_sha256': acceptance.binding(policy), 'identity': copy.deepcopy(policy['identity']),
               'reviewed_releases': reviewed,
               'reviewed_by': 'synthetic reviewer', 'review_reference': 'test-only', 'expected_last_period': expected}
    return [policy, profile, old, baseline, new, candidate]


def repack(raw, transform, extras=None):
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as old, zipfile.ZipFile(output, 'w') as new:
        for name in old.namelist():
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            new.writestr(info, transform(name, old.read(name)))
        for name, value in (extras or {}).items():
            new.writestr(zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0)), value)
    return output.getvalue()


class AcceptanceChecks(unittest.TestCase):
    def test_baseline_manual_c05_not_approval(self):
        result = acceptance.evaluate(*inputs())
        self.assertEqual(result['status'], 'MANUAL_REVIEW_REQUIRED')
        self.assertEqual(result['manual_review_reasons'], ['C05_UNRESOLVED'])
        self.assertTrue(result['structural_checks_passed'])
        self.assertEqual(result['comparison']['counts']['UNCHANGED'], 174)
        self.assertEqual(result['candidate_coverage']['observation_count'], 174)
        self.assertEqual(result['composite_release_statuses'], provenance.HOLD)
        self.assertFalse(result['publication_approved'])

    def test_expansion_174_to_175_and_176(self):
        for last, count in [('2026-Q3', 175), ('2026-Q4', 176)]:
            result = acceptance.evaluate(*inputs(workbook(last=last), expected=last))
            self.assertTrue(result['structural_checks_passed'])
            self.assertEqual(result['candidate_coverage']['observation_count'], count)
            self.assertEqual(result['comparison']['counts']['NEW_OBSERVATION'], count-174)
            self.assertNotEqual(result['baseline_sha256'], result['candidate_sha256'])
            self.assertEqual(result['status'], 'MANUAL_REVIEW_REQUIRED')

    def test_revised_value_decimal_and_no_mutation(self):
        args = inputs(workbook(changes={'2000-Q1': '2.6'}))
        original = copy.deepcopy(args)
        with localcontext() as context:
            context.prec = 2
            result = acceptance.evaluate(*args)
        self.assertEqual(args, original)
        self.assertIn('HISTORICAL_REVISION', result['manual_review_reasons'])
        revised = next(r for r in result['comparison']['observations'] if r['classification'] == 'REVISED')
        self.assertEqual(revised['signed_change_pp'], '0.1')

    def test_packaging_only_changes(self):
        result = acceptance.evaluate(*inputs(workbook(packaging='new-package')))
        self.assertEqual(result['byte_identity'], 'DIFFERENT')
        self.assertEqual(result['comparison']['counts']['UNCHANGED'], 174)
        self.assertNotIn('HISTORICAL_REVISION', result['manual_review_reasons'])
        self.assertTrue(result['structural_checks_passed'])

    def test_truncated_history_even_with_174_values(self):
        for expected in ('2026-Q2', '2026-Q3'):
            candidate = workbook(remove=['1983-Q1'], last=expected)
            result = acceptance.evaluate(*inputs(candidate, expected=expected))
            self.assertEqual(result['status'], 'FAIL')
            self.assertIn('INCOMPLETE_REQUIRED_HISTORY', result['fail_reasons'])
            self.assertEqual(result['comparison']['counts']['REMOVED_OBSERVATION'], 1)

    def test_internal_gap_and_explicit_missing(self):
        result = acceptance.evaluate(*inputs(workbook(remove=['2000-Q1'])))
        self.assertIn('GRID_NOT_CONSECUTIVE', result['fail_reasons'])
        self.assertEqual(result['comparison']['counts']['REMOVED_OBSERVATION'], 1)
        result = acceptance.evaluate(*inputs(workbook(changes={'2000-Q1': '..'})))
        self.assertIn('INTERNAL_MISSING_VALUES', result['fail_reasons'])
        self.assertEqual(result['comparison']['counts']['MISSINGNESS_CHANGED'], 1)

    def test_duplicate_and_declared_count_mismatch(self):
        self.assertEqual(acceptance.evaluate(*inputs(workbook(duplicate=True)))['status'], 'FAIL')
        result = acceptance.evaluate(*inputs(workbook(metadata={'I9': '999'})))
        self.assertIn('DECLARED_COVERAGE_MISMATCH', result['fail_reasons'])

    def test_metadata_mismatches(self):
        for row in (1, 2, 3, 4, 5, 6, 10):
            result = acceptance.evaluate(*inputs(workbook(metadata={f'I{row}': 'WRONG'})))
            self.assertEqual(result['status'], 'FAIL', row)
        for key in ('provider', 'series_id', 'frequency', 'methodological_variant', 'source_role', 'table'):
            args = inputs()
            args[1]['identity'][key] = 'WRONG'
            self.assertIn('IDENTITY_PROFILE_MISMATCH', acceptance.evaluate(*args)['fail_reasons'])

    def test_own_hash_count_and_baseline_pin(self):
        for index in (2, 4):
            for field, value in [('sha256', '0'*64), ('byte_count', 1)]:
                args = inputs()
                args[index][field] = value
                self.assertEqual(acceptance.evaluate(*args)['status'], 'FAIL')
        args = inputs()
        args[0]['baseline']['sha256'] = '0'*64
        args[1]['policy_sha256'] = acceptance.binding(args[0])
        self.assertIn('BASELINE_PIN_MISMATCH', acceptance.evaluate(*args)['fail_reasons'])

    def test_unexpected_or_missing_endpoint(self):
        self.assertEqual(acceptance.evaluate(*inputs(workbook(last='2026-Q3')))['status'], 'FAIL')
        self.assertEqual(acceptance.evaluate(*inputs(expected='2026-Q3'))['status'], 'FAIL')
        for invalid in ('2026-09', '２０２６-Q3', '2026-Q5', '0000-Q1', '2026-Q1'):
            self.assertEqual(acceptance.evaluate(*inputs(expected=invalid))['status'], 'FAIL')

    def test_missing_new_quarter_not_reported_as_an_added_observation(self):
        result = acceptance.evaluate(*inputs(expected='2026-Q3'))
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['comparison']['counts']['NEW_OBSERVATION'], 0)
        self.assertIn('2026-Q3', result['missing_required_periods'])

    def test_bad_bytes_and_changed_baseline_history_fail(self):
        args = inputs(b'not a zip')
        self.assertEqual(acceptance.evaluate(*args)['status'], 'FAIL')
        args = inputs()
        args[3] = workbook(remove=['1983-Q1'])
        args[2] = evidence(args[3], args[0])
        args[0]['baseline'].update(sha256=acceptance.digest(args[3]), byte_count=len(args[3]))
        args[1]['policy_sha256'] = acceptance.binding(args[0])
        self.assertIn('BASELINE_COVERAGE_INVALID', acceptance.evaluate(*args)['fail_reasons'])

    def test_methodology_change_unknown_and_boundary(self):
        args = inputs()
        args[4]['methodology']['compilation_basis'] = 'new basis'
        self.assertIn('METHODOLOGY_CHANGED', acceptance.evaluate(*args)['manual_review_reasons'])
        args[4]['methodology']['compilation_basis'] = 'UNKNOWN'
        self.assertIn('CANDIDATE_METHODOLOGY_UNKNOWN', acceptance.evaluate(*args)['manual_review_reasons'])
        result = acceptance.evaluate(*inputs(workbook(remove=['1972-Q3'])))
        self.assertTrue(result['structural_checks_passed'])
        self.assertIn('BOUNDARY_GRID_CHANGED', result['manual_review_reasons'])

    def test_zero_negative_and_invalid_numbers(self):
        for value in ('0', '-0.3'):
            result = acceptance.evaluate(*inputs(workbook(changes={'2000-Q1': value})))
            self.assertTrue(result['structural_checks_passed'])
            row = next(r for r in result['comparison']['observations'] if r['period'] == '2000-Q1')
            self.assertEqual(row['new_value'], value)
        for value in ('NaN', 'Infinity', '1e3', '1,000'):
            self.assertEqual(acceptance.evaluate(*inputs(workbook(changes={'2000-Q1': value})))['status'], 'FAIL')

    def test_release_unknown_and_date_regression(self):
        args = inputs()
        args[4]['release'] = None
        self.assertIn('CANDIDATE_RELEASE_EVIDENCE_UNKNOWN', acceptance.evaluate(*args)['manual_review_reasons'])
        args = inputs()
        args[4]['release']['date'] = '2025-01-01'
        self.assertIn('CANDIDATE_RELEASE_CHRONOLOGY_CONFLICT', acceptance.evaluate(*args)['manual_review_reasons'])

    def test_release_chronology_identity_and_review_binding(self):
        args = inputs(workbook(last='2026-Q4'), expected='2026-Q4')
        args[4]['release'] = copy.deepcopy(args[2]['release'])
        args[1]['reviewed_releases']['candidate'] = copy.deepcopy(args[1]['reviewed_releases']['baseline'])
        result = acceptance.evaluate(*args)
        self.assertIn('CANDIDATE_RELEASE_CHRONOLOGY_CONFLICT', result['manual_review_reasons'])
        for key, value, reason in [
                ('evidence_url', 'https://www.abs.gov.au/unrelated', 'RELEASE_IDENTITY_CONFLICT'),
                ('workbook_url', 'https://www.abs.gov.au/other.xlsx', 'RELEASE_IDENTITY_CONFLICT'),
                ('date', '2026-10-01', 'RELEASE_REVIEW_BINDING_CONFLICT')]:
            args = inputs(); args[4]['release'][key] = value
            self.assertIn('CANDIDATE_' + reason, acceptance.evaluate(*args)['manual_review_reasons'])
        args = inputs()
        args[1]['reviewed_releases'] = []
        self.assertEqual(acceptance.evaluate(*args)['status'], 'FAIL')
        # A later monthly release can legitimately still contain Q2 observations.
        args = inputs()
        release = args[4]['release']
        release.update(date='2026-10-28', period='September 2026')
        release['evidence_url'] = release['evidence_url'].replace('aug-2026', 'sep-2026')
        release['workbook_url'] = release['evidence_url'] + '/64010Appendix1a.xlsx'
        args[1]['reviewed_releases']['candidate'] = {k: release[k] for k in args[1]['reviewed_releases']['candidate']}
        self.assertEqual(acceptance.evaluate(*args)['manual_review_reasons'], ['C05_UNRESOLVED'])

    def test_release_date_formats_and_unknowns(self):
        for date in ('20260930', '2026-02-30', 'UNKNOWN', None, 20260930):
            args = inputs(); args[4]['release']['date'] = date
            self.assertIn('CANDIDATE_RELEASE_EVIDENCE_UNKNOWN', acceptance.evaluate(*args)['manual_review_reasons'])

    def test_strict_policy_schema_and_limits(self):
        for field, value in [('policy_id', 'OTHER'), ('methodology_declaration_fields', []),
                             ('require_manual_review_for', []), ('maximum_bytes', 10000001),
                             ('maximum_expanded_bytes', 0), ('maximum_zip_members', True),
                             ('maximum_internal_missing', False), ('release_identity_rule', 'HOST_ONLY')]:
            args = inputs(); args[0][field] = value; args[1]['policy_sha256'] = acceptance.binding(args[0])
            self.assertIn('POLICY_RESTRICTIONS', acceptance.evaluate(*args)['fail_reasons'], field)
        for operation in ('missing', 'extra', 'empty_methodologies'):
            args = inputs()
            if operation == 'missing': del args[0]['maximum_bytes']
            if operation == 'extra': args[0]['allow_override'] = True
            if operation == 'empty_methodologies':
                args[0]['methodology_declaration_fields'] = []
                args[2]['methodology'] = args[4]['methodology'] = {}
            args[1]['policy_sha256'] = acceptance.binding(args[0])
            self.assertEqual(acceptance.evaluate(*args)['status'], 'FAIL')

    def test_all_top_level_types_fail_without_exception(self):
        for index in (0, 1, 2, 4):
            for value in (None, [], 'bad', 1, False):
                args = inputs(); args[index] = value
                result = acceptance.evaluate(*args)
                self.assertEqual(result['status'], 'FAIL', (index, value))
                json.dumps(result, allow_nan=False)

    def test_ambiguous_sheets_ids_and_relationships(self):
        ns = {'m': acceptance.workbook_reader.NS['m']}
        for mode in ('name', 'case_name', 'sheet_id', 'reference', 'rel_id', 'target', 'external', 'missing_part'):
            def transform(name, raw):
                if name == 'xl/workbook.xml' and mode in ('name', 'case_name', 'sheet_id', 'reference'):
                    root = ET.fromstring(raw); sheets = root.find('m:sheets', ns)
                    clone = ET.fromstring(ET.tostring(sheets[-1]))
                    clone.set('sheetId', '3')
                    clone.set('name', 'Extra')
                    clone.set('{'+acceptance.workbook_reader.REL+'}id', 'r3')
                    if mode == 'name': clone.set('name', 'Data1')
                    if mode == 'case_name': clone.set('name', 'data1')
                    if mode == 'sheet_id': clone.set('sheetId', '2')
                    if mode == 'reference': clone.set('{'+acceptance.workbook_reader.REL+'}id', 'r2')
                    sheets.append(clone)
                    return ET.tostring(root)
                if name == 'xl/_rels/workbook.xml.rels':
                    root = ET.fromstring(raw)
                    if mode in ('name', 'case_name', 'sheet_id', 'reference'):
                        ET.SubElement(root, 'Relationship', Id='r3', Target='worksheets/extra.xml')
                    if mode == 'rel_id': ET.SubElement(root, 'Relationship', Id='r2', Target='worksheets/index.xml')
                    if mode == 'target': root[-1].set('Target', root[0].get('Target'))
                    if mode == 'external': root[-1].set('TargetMode', 'External')
                    if mode == 'missing_part': root[-1].set('Target', 'worksheets/missing.xml')
                    return ET.tostring(root)
                return raw
            extra = {'xl/worksheets/extra.xml': '<worksheet xmlns="'+acceptance.workbook_reader.NS['m']+'"><sheetData/></worksheet>'}
            result = acceptance.evaluate(*inputs(repack(workbook(), transform, extra)))
            self.assertIn('AMBIGUOUS_WORKBOOK_STRUCTURE', result['fail_reasons'], mode)

    def test_malformed_archive_xml_and_encryption(self):
        for kind in ('compression', 'encrypted', 'xml', 'truncated', 'crc'):
            raw = workbook()
            if kind in ('compression', 'encrypted'):
                data = bytearray(raw)
                for signature, offset in ((b'PK\x03\x04', 8), (b'PK\x01\x02', 10)):
                    start = 0
                    while True:
                        pos = data.find(signature, start)
                        if pos < 0: break
                        shift, value = (offset, 99) if kind == 'compression' else (offset-2, 1)
                        data[pos+shift:pos+shift+2] = value.to_bytes(2, 'little')
                        start = pos+4
                raw = bytes(data)
            if kind == 'xml': raw = repack(raw, lambda name, value: b'<broken' if name == 'xl/workbook.xml' else value)
            if kind == 'truncated': raw = raw[:100]
            if kind == 'crc': raw = raw.replace(b'<workbook ', b'<WorkbooK ', 1)
            result = acceptance.evaluate(*inputs(raw))
            self.assertEqual(result['status'], 'FAIL', kind)
            json.dumps(result, allow_nan=False)

    def test_incompatible_or_unknown_methods_suppress_economic_comparison(self):
        for replacement in ('different method', 'UNKNOWN', None):
            args = inputs(workbook(changes={'2000-Q1': '4.5'}))
            if replacement is None:
                args[2]['methodology'] = args[4]['methodology'] = None
            else: args[4]['methodology']['compilation_basis'] = replacement
            result = acceptance.evaluate(*args)
            self.assertEqual(result['status'], 'MANUAL_REVIEW_REQUIRED')
            self.assertIsNone(result['comparison'])
            self.assertNotIn('HISTORICAL_REVISION', result['manual_review_reasons'])
            self.assertEqual(result['methodological_compatibility'], 'NOT_ESTABLISHED')
            self.assertEqual(result['candidate_coverage']['observation_count'], 174)
            self.assertEqual(result['candidate_sha256'], args[4]['sha256'])

    def test_cli_safe_json_failures_and_bounded_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            args = inputs()
            policy = p/'policy.json'; policy.write_bytes(provenance.canonical(args[0]))
            profile = p/'profile.json'; profile.write_bytes(provenance.canonical(args[1]))
            evidence_path = p/'evidence.json'; evidence_path.write_bytes(provenance.canonical(args[2]))
            book = p/'source.xlsx'; book.write_bytes(args[3])
            argv = ['evaluator', '--profile', str(profile), '--baseline-evidence', str(evidence_path),
                    '--candidate-evidence', str(evidence_path), '--baseline-workbook', str(book), '--candidate-workbook', str(book)]
            for invalid in (b'{', b'[]', b'null', b'{"x":NaN}', b'{"x":1,"x":2}', b'\xff', b'['*2000):
                profile.write_bytes(invalid)
                with patch.object(acceptance, 'POLICY_PATH', policy), patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(acceptance.main(), 1)
                result = json.loads(output.getvalue()); self.assertEqual(result['status'], 'FAIL')
                self.assertNotIn(str(p), output.getvalue())
            profile.write_bytes(provenance.canonical(args[1]))
            # Sparse file: reject from fstat before reading workbook bytes.
            with book.open('wb') as stream: stream.truncate(args[0]['maximum_bytes']+1)
            with patch.object(acceptance, 'POLICY_PATH', policy), patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(acceptance.main(), 1)
            self.assertEqual(json.loads(output.getvalue())['fail_reasons'], ['INVALID_OR_UNREADABLE_BOUNDED_INPUT'])
            book.unlink()
            with patch.object(acceptance, 'POLICY_PATH', policy), patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(acceptance.main(), 1)
            # JSON also uses bounded reads; malformed policy never reaches workbook loading.
            with profile.open('wb') as stream: stream.truncate(acceptance.JSON_LIMIT+1)
            with self.assertRaisesRegex(ValueError, 'INPUT_SIZE_LIMIT'): acceptance.read_json_bounded(profile)
            policy.write_text('[]', encoding='utf-8')
            with patch.object(acceptance, 'POLICY_PATH', policy), patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(acceptance.main(), 1)

    def test_dependency_provenance_includes_phase2b(self):
        report = acceptance.evaluate(*inputs())
        expected = acceptance.digest(Path(acceptance.capture.__file__).read_bytes().replace(b'\r\n', b'\n'))
        self.assertEqual(report['dependency_sha256']['phase2b'], expected)

    def test_json_exponent_overflow_and_nested_nonfinite_rejected(self):
        payloads = [b'1e309', b'-1e309', b'{"a":[{"b":1e309}]}',
                    b'{"a":{"b":[-1e309]}}', b'NaN', b'Infinity', b'-Infinity']
        for payload in payloads:
            with self.subTest(payload=payload), patch.object(acceptance, 'read_bounded', return_value=payload):
                with self.assertRaisesRegex(ValueError, '^NONFINITE_JSON_NUMBER$'):
                    acceptance.read_json_bounded(Path('not-read'))
        with patch.object(acceptance, 'read_bounded', return_value=b'{"finite":1.25e2}'):
            self.assertEqual(acceptance.read_json_bounded(Path('not-read')), {'finite': 125.0})

    def test_api_nonfinite_inputs_fail_before_source_or_manual_review(self):
        for index in (0, 1, 2, 4):
            for value in (float('nan'), float('inf'), float('-inf')):
                args = inputs()
                args[index]['nested_invalid'] = {'values': [value]}
                with patch.object(acceptance, 'extract', side_effect=AssertionError('No source processing')):
                    first = acceptance.evaluate(*args)
                    second = acceptance.evaluate(*args)
                self.assertEqual(first, second)
                self.assertEqual(first['status'], 'FAIL')
                self.assertEqual(first['fail_reasons'], ['CANONICAL_BINDING_FAILED'])
                self.assertFalse(first['structural_checks_passed'])
                self.assertFalse(first['canonical_bindings_valid'])
                self.assertEqual(first['manual_review_reasons'], [])
                self.assertIsNone(first['comparison'])
                self.assertNotIn('candidate_coverage', first)
                json.dumps(first, allow_nan=False)
        # Exact independent-review reproduction in an otherwise permitted field.
        args = inputs()
        args[4]['methodology']['compilation_basis'] = float('inf')
        result = acceptance.evaluate(*args)
        self.assertEqual(result['status'], 'FAIL')
        self.assertIsNone(result['candidate_evidence_sha256'])
        self.assertFalse(result['structural_checks_passed'])

    def test_canonical_serialization_failures_are_hard_failures(self):
        cycle = {}; cycle['self'] = cycle
        for bad in (set(['not-json']), object(), cycle, {1: 'integer key', 'a': 'mixed key'}):
            args = inputs()
            args[4]['methodology']['compilation_basis'] = bad
            result = acceptance.evaluate(*args)
            self.assertEqual(result['fail_reasons'], ['CANONICAL_BINDING_FAILED'])
            self.assertEqual(result['status'], 'FAIL')
            self.assertFalse(result['structural_checks_passed'])
            self.assertIsNone(result['comparison'])
            self.assertEqual(result['manual_review_reasons'], [])
        # Generate valid input before injecting canonicalisation failure.
        args = inputs()
        with patch.object(provenance, 'canonical', side_effect=ValueError('sensitive error text')):
            result = acceptance.evaluate(*args)
        self.assertEqual(result['fail_reasons'], ['CANONICAL_BINDING_FAILED'])
        self.assertNotIn('sensitive error text', json.dumps(result))

    def test_cli_invalid_evidence_overflow_is_deterministic_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory); args = inputs()
            for name, value in [('policy', args[0]), ('profile', args[1]), ('old', args[2])]:
                (p/(name+'.json')).write_bytes(provenance.canonical(value))
            (p/'source.xlsx').write_bytes(args[3])
            argv = ['evaluator', '--profile', str(p/'profile.json'), '--baseline-evidence', str(p/'old.json'),
                    '--candidate-evidence', str(p/'new.json'), '--baseline-workbook', str(p/'source.xlsx'),
                    '--candidate-workbook', str(p/'source.xlsx')]
            for token in ('1e309', '-1e309', 'NaN', 'Infinity', '-Infinity'):
                new = copy.deepcopy(args[4])
                new['methodology']['compilation_basis'] = 'OVERFLOW_TOKEN'
                text = json.dumps(new).replace('"OVERFLOW_TOKEN"', token)
                (p/'new.json').write_text(text, encoding='utf-8')
                outputs = []
                for _ in range(2):
                    with patch.object(acceptance, 'POLICY_PATH', p/'policy.json'), patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()) as output:
                        self.assertEqual(acceptance.main(), 1)
                    outputs.append(output.getvalue())
                self.assertEqual(outputs[0], outputs[1])
                result = json.loads(outputs[0])
                self.assertEqual(result['fail_reasons'], ['NONFINITE_JSON_NUMBER'])
                self.assertFalse(result['structural_checks_passed'])
                self.assertFalse(result['canonical_bindings_valid'])
                self.assertEqual(result['manual_review_reasons'], [])
                self.assertIsNone(result['candidate_evidence_sha256'])
                self.assertIsNone(result['comparison'])
                self.assertNotIn(str(p), outputs[0])

    def test_valid_evaluations_always_have_all_bindings(self):
        for args in (inputs(), inputs(workbook(packaging='new')), inputs(workbook(last='2026-Q3'), expected='2026-Q3')):
            result = acceptance.evaluate(*args)
            self.assertTrue(result['canonical_bindings_valid'])
            self.assertTrue(result['structural_checks_passed'])
            self.assertEqual(result['status'], 'MANUAL_REVIEW_REQUIRED')
            for key, value in zip(('policy_sha256', 'profile_sha256', 'baseline_evidence_sha256', 'candidate_evidence_sha256'),
                                  (args[0], args[1], args[2], args[4])):
                self.assertEqual(result[key], acceptance.binding(value))

    def test_review_binding_and_policy_guards(self):
        for key, value in [('reviewed_by', ''), ('review_reference', 'UNKNOWN'), ('policy_sha256', '0'*64)]:
            args = inputs()
            args[1][key] = value
            self.assertEqual(acceptance.evaluate(*args)['status'], 'FAIL')
        for key, value in [('c05_status', 'RESOLVED'), ('research_only', False), ('publication_approved', True),
                           ('point_in_time_eligible', True), ('composite_release_statuses', {})]:
            args = inputs()
            args[0][key] = value
            self.assertIn('POLICY_RESTRICTIONS', acceptance.evaluate(*args)['fail_reasons'])

    def test_determinism_hash_seeds_cli_and_no_network(self):
        args = inputs()
        self.assertEqual(acceptance.evaluate(*args), acceptance.evaluate(*args))
        # Production CLI cannot accept a synthetic replacement policy. Exercise
        # pure evaluator in subprocesses; block all socket connections explicitly.
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            for name, value in zip(('policy', 'profile', 'old', 'new'), (args[0], args[1], args[2], args[4])):
                (p / (name+'.json')).write_bytes(provenance.canonical(value))
            (p/'old.xlsx').write_bytes(args[3])
            (p/'new.xlsx').write_bytes(args[5])
            code = "import sys,socket,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import aesm_e12_acceptance as a;import aesm_provenance as p;socket.socket.connect=lambda *x:(_ for _ in ()).throw(AssertionError('network'));d=Path(sys.argv[2]);r=a.evaluate(p.read_json(d/'policy.json'),p.read_json(d/'profile.json'),p.read_json(d/'old.json'),(d/'old.xlsx').read_bytes(),p.read_json(d/'new.json'),(d/'new.xlsx').read_bytes());print(json.dumps(r,sort_keys=True))"
            import os
            outputs = [subprocess.check_output([sys.executable, '-B', '-c', code, str(ROOT/'scripts'), str(p)],
                       env={**os.environ, 'PYTHONHASHSEED': seed}) for seed in ('1', '97')]
            self.assertEqual(outputs[0], outputs[1])

    @unittest.skipUnless((ROOT/'research-inputs/e12/64010Appendix1a.xlsx').exists(), 'Local ABS baseline not supplied')
    def test_real_baseline_read_only(self):
        raw = (ROOT/'research-inputs/e12/64010Appendix1a.xlsx').read_bytes()
        policy = provenance.read_json(acceptance.POLICY_PATH)
        profile = inputs()[1]
        profile['policy_sha256'] = acceptance.binding(policy)
        ev = evidence(raw, policy)  # Explicit test attestations, not new approvals.
        result = acceptance.evaluate(policy, profile, ev, raw, ev, raw)
        self.assertTrue(result['structural_checks_passed'], result)
        self.assertEqual(result['candidate_coverage']['observation_count'], 174)
        self.assertEqual(result['comparison']['counts']['UNCHANGED'], 174)
        self.assertEqual(result['status'], 'MANUAL_REVIEW_REQUIRED')
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            for name, value in [('profile', profile), ('evidence', ev)]:
                (p/(name+'.json')).write_bytes(provenance.canonical(value))
            path = ROOT/'research-inputs/e12/64010Appendix1a.xlsx'
            process = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/aesm_e12_acceptance.py'),
                         '--profile', str(p/'profile.json'), '--baseline-evidence', str(p/'evidence.json'),
                         '--candidate-evidence', str(p/'evidence.json'), '--baseline-workbook', str(path),
                         '--candidate-workbook', str(path)], capture_output=True, text=True)
            self.assertEqual(process.returncode, 2, process.stderr)
            self.assertEqual(json.loads(process.stdout), result)


if __name__ == '__main__':
    unittest.main()
