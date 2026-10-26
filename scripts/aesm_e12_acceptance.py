"""Deterministic offline E12 A research evaluator. Reads bytes; JSON stdout only.

No capture, archive writes, approval overrides or production integration.

Inputs: a profile with policy_sha256 (canonical JSON), identity, reviewed_by,
review_reference, expected_last_period and reviewed_releases (baseline/candidate
date, period, evidence_url and workbook_url); two evidence objects with identity,
sha256 (exact bytes), byte_count, methodology and release; and two byte strings.
Methodology keys are listed in the policy. Release keys are date, period,
evidence_url, workbook_url and verification_note. Declarations are supplied
attestations, not signatures or a fresh review of official methodology.

The CLI fixes the policy path; API callers must supply their independently trusted
policy. Synthetic tests pin synthetic bytes only in an in-memory policy copy.
Baseline hash stays fixed; each candidate is verified against its own hash.
C05 cannot be overridden: clean inputs return MANUAL_REVIEW_REQUIRED. The generic
PASS_RESEARCH_CHECKS tier is reserved; it is unreachable under policy 0.1.1.
Unexpected endpoints fail this explicit-endpoint profile and require a new
reviewed request, never silent expansion. Reports are diagnostic, not approvals.
Exit codes: 0 pass, 2 manual review, 1 fail. No report writer is provided.
"""
import argparse
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
import datetime as dt
import calendar
import hashlib
import io
import json
import math
from pathlib import Path
import re
import posixpath
import os
import stat
import xml.etree.ElementTree as ET
import zipfile
import zlib

import aesm_provenance as provenance
import aesm_capture as capture
import aesm_revision_compare as revision
import aehi_e04_import as workbook_reader
import aehi_e12_import as e12

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / 'docs/aesm-e12-acceptance-policy-v0.1.json'
UNKNOWN = revision.UNKNOWN_DECLARATIONS | {'NOT_REVIEWED'}
METHOD_FIELDS = ['definition_version', 'compilation_basis', 'seasonal_adjustment_basis', 'historical_limitations']
TRIGGERS = ['C05_UNRESOLVED', 'HISTORICAL_REVISION', 'METHODOLOGY_CHANGED_OR_UNKNOWN',
            'BOUNDARY_GRID_CHANGED', 'RELEASE_EVIDENCE_UNKNOWN_OR_CONFLICTING']
JSON_LIMIT = 1000000


def validate_policy(policy):
    """Closed, versioned semantics; API callers still establish policy trust externally."""
    keys = {'policy_id', 'policy_version', 'research_only', 'c05_status', 'identity', 'baseline',
            'maximum_bytes', 'maximum_expanded_bytes', 'maximum_zip_members', 'maximum_internal_missing',
            'methodology_declaration_fields', 'require_manual_review_for', 'publication_approved',
            'point_in_time_eligible', 'composite_release_statuses', 'release_identity_rule'}
    if (type(policy) is not dict or set(policy) != keys
            or policy['policy_id'] != 'AESM_E12_A_OFFLINE_ACCEPTANCE' or policy['policy_version'] != '0.1.1'
            or policy['research_only'] is not True or policy['c05_status'] != 'UNRESOLVED'
            or policy['publication_approved'] is not False or policy['point_in_time_eligible'] is not False
            or policy['composite_release_statuses'] != provenance.HOLD
            or type(policy['maximum_internal_missing']) is not int or policy['maximum_internal_missing'] != 0
            or policy['methodology_declaration_fields'] != METHOD_FIELDS
            or policy['require_manual_review_for'] != TRIGGERS
            or policy['release_identity_rule'] != 'EXACT_REVIEWED_ABS_CPI_RELEASE_URLS_AND_CHRONOLOGY'):
        raise ValueError('POLICY_RESTRICTIONS')
    for key, cap in [('maximum_bytes', 10000000), ('maximum_expanded_bytes', 100000000), ('maximum_zip_members', 10000)]:
        if type(policy[key]) is not int or not 0 < policy[key] <= cap:
            raise ValueError('POLICY_RESTRICTIONS')
    base = policy['baseline']
    expected = {'first_period': '1983-Q1', 'last_period': '2026-Q2', 'observation_count': 174,
                'grid_first': '1972-Q3', 'grid_last': '2027-Q2', 'leading_missing_count': 42,
                'trailing_missing_count': 4}
    if (type(base) is not dict or set(base) != set(expected) | {'sha256', 'byte_count'}
            or any(type(base[k]) is not type(v) or base[k] != v for k, v in expected.items())
            or not isinstance(base['sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', base['sha256'])
            or type(base['byte_count']) is not int or not 0 < base['byte_count'] <= policy['maximum_bytes']):
        raise ValueError('POLICY_RESTRICTIONS')
    if type(policy['identity']) is not dict:
        raise ValueError('POLICY_RESTRICTIONS')


def read_bounded(path, limit):
    """Bound actual reads, including a file growing after stat; no read_bytes first."""
    if not stat.S_ISREG(Path(path).stat().st_mode):
        raise ValueError('INPUT_NOT_REGULAR_FILE')
    with Path(path).open('rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('INPUT_NOT_REGULAR_FILE')
        if info.st_size > limit:
            raise ValueError('INPUT_SIZE_LIMIT')
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('INPUT_SIZE_LIMIT')
    return raw


def read_json_bounded(path):
    raw = read_bounded(path, JSON_LIMIT)
    def pairs(items):
        value = {}
        for key, child in items:
            if key in value:
                raise ValueError('INVALID_JSON')
            value[key] = child
        return value
    def nonfinite(_):
        raise ValueError('NONFINITE_JSON_NUMBER')
    def finite_float(token):
        value = float(token)
        if not math.isfinite(value):
            raise ValueError('NONFINITE_JSON_NUMBER')
        return value
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=nonfinite, parse_float=finite_float)


def release_identity(release):
    """Check syntax and exact reviewed-release URL identity, never fetch evidence."""
    if type(release) is not dict or set(release) != {'date', 'period', 'evidence_url', 'workbook_url', 'verification_note'}:
        raise ValueError('RELEASE_EVIDENCE_UNKNOWN')
    if any(not isinstance(v, str) or not v.strip() or v.strip().upper() in UNKNOWN for v in release.values()):
        raise ValueError('RELEASE_EVIDENCE_UNKNOWN')
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', release['date']):
        raise ValueError('RELEASE_EVIDENCE_UNKNOWN')
    date = dt.date.fromisoformat(release['date'])
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
              'September', 'October', 'November', 'December']
    match = re.fullmatch(r'(' + '|'.join(months) + r') ([0-9]{4})', release['period'])
    if not match:
        raise ValueError('RELEASE_IDENTITY_CONFLICT')
    month, year = months.index(match[1]) + 1, int(match[2])
    reference_end = dt.date(year, month, calendar.monthrange(year, month)[1])
    root = ('https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/'
            'consumer-price-index-australia/' + match[1][:3].lower() + '-' + match[2])
    if (release['evidence_url'] != root or release['workbook_url'] != root + '/64010Appendix1a.xlsx'):
        raise ValueError('RELEASE_IDENTITY_CONFLICT')
    capture.official_url(release['evidence_url'], 'ABS')
    capture.official_url(release['workbook_url'], 'ABS')
    if date < reference_end:
        raise ValueError('RELEASE_CHRONOLOGY_CONFLICT')
    return date, reference_end


def check_workbook_structure(archive):
    ns = workbook_reader.NS
    root = ET.fromstring(archive.read('xl/workbook.xml'))
    relationships = list(ET.fromstring(archive.read('xl/_rels/workbook.xml.rels')))
    rel_ids = [r.get('Id') for r in relationships]
    if None in rel_ids or len(set(rel_ids)) != len(rel_ids):
        raise ValueError('AMBIGUOUS_WORKBOOK_STRUCTURE')
    rels = {r.get('Id'): r for r in relationships}
    sheets = root.findall('m:sheets/m:sheet', ns)
    names, ids, refs, targets = [], [], [], []
    for sheet in sheets:
        name, sid, rid = sheet.get('name'), sheet.get('sheetId'), sheet.get('{' + workbook_reader.REL + '}id')
        if not name or not sid or not re.fullmatch(r'[1-9][0-9]*', sid) or rid not in rels:
            raise ValueError('AMBIGUOUS_WORKBOOK_STRUCTURE')
        rel = rels[rid]
        target = rel.get('Target', '')
        if rel.get('TargetMode') == 'External' or not target or '\\' in target:
            raise ValueError('AMBIGUOUS_WORKBOOK_STRUCTURE')
        target = posixpath.normpath(target.lstrip('/') if target.startswith('/') else 'xl/' + target)
        if not target.startswith('xl/') or target not in archive.namelist():
            raise ValueError('AMBIGUOUS_WORKBOOK_STRUCTURE')
        names.append(name.casefold()); ids.append(int(sid)); refs.append(rid); targets.append(target)
    if (any(len(set(values)) != len(values) for values in (names, ids, refs, targets))
            or not {'index', 'data1'}.issubset(names)):
        raise ValueError('AMBIGUOUS_WORKBOOK_STRUCTURE')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def binding(value):
    return digest(provenance.canonical(value))


def safe_binding(value):
    """Null records a rejected binding, never permission to continue evaluation."""
    try:
        return binding(value)
    except (ValueError, TypeError, RecursionError, OverflowError):
        return None


def quarter(period):
    if not isinstance(period, str) or not re.fullmatch(r'[0-9]{4}-Q[1-4]', period) or period[:4] == '0000':
        raise ValueError('Noncanonical quarter')
    return provenance.period_index(period, 'quarterly')


class MemoryWorkbook:
    def __init__(self, raw):
        self.raw = raw

    def read_bytes(self):
        return self.raw

    def __str__(self):
        return '<offline-bytes>'


def extract(raw, identity, policy):
    """Exact Decimal source tokens; no rounding or float normalisation of values."""
    if not isinstance(raw, bytes) or len(raw) > policy['maximum_bytes']:
        raise ValueError('Workbook size/type')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        if (len(members) > policy['maximum_zip_members']
                or len({m.filename for m in members}) != len(members)
                or sum(m.file_size for m in members) > policy['maximum_expanded_bytes']):
            raise ValueError('Workbook archive limits')
        if any(m.flag_bits & 1 or m.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) for m in members):
            raise ValueError('UNSUPPORTED_WORKBOOK_ARCHIVE')
        check_workbook_structure(archive)
    book = workbook_reader.read_workbook(MemoryWorkbook(raw))
    cells = book['sheets'].get('Data1', {})
    if book['sheets'].get('Index', {}).get('B6') != identity['table']:
        raise ValueError('Table mismatch')
    if any(cells.get(f'A{r}') != text for r, text in e12.LABELS.items()):
        raise ValueError('Metadata labels mismatch')
    columns = [a[:-2] for a, text in cells.items()
               if re.fullmatch(r'[A-Z]+10', a) and text == identity['series_id']]
    if len(columns) != 1:
        raise ValueError('Missing or duplicate Series ID')
    col = columns[0]
    expected = {1: identity['description'], 2: identity['unit'], 3: identity['seasonal_adjustment'],
                4: identity['data_type'], 5: 'Quarter', 6: '3'}
    for r, value in expected.items():
        if cells.get(f'{col}{r}') != value:
            raise ValueError(f'WORKBOOK_METADATA_ROW_{r}_MISMATCH')
    numbers = sorted({int(re.search(r'\d+$', a).group()) for a, value in cells.items()
                      if value and re.fullmatch(r'(?:A|' + col + r')\d+', a)
                      and int(re.search(r'\d+$', a).group()) > 10})
    rows, indices, issues = {}, [], []
    for row in numbers:
        _, _, period = e12.parse_date(cells.get(f'A{row}'), {'frequency': 'Quarter'})
        index = quarter(period)
        if period in rows:
            raise ValueError('Duplicate quarter')
        if indices and index != indices[-1] + 1:
            issues.append('GRID_NOT_CONSECUTIVE')
        indices.append(index)
        rows[period] = revision.number(cells.get(f'{col}{row}', ''))
    valid = {p: v for p, v in rows.items() if v is not None}
    if not valid:
        raise ValueError('No valid observations')
    first, last = min(valid), max(valid)
    internal = [p for p, value in rows.items() if first <= p <= last and value is None]
    if internal:
        issues.append('INTERNAL_MISSING_VALUES')
    declared_first = e12.parse_date(cells.get(col + '7'), {'frequency': 'Quarter'})[2]
    declared_last = e12.parse_date(cells.get(col + '8'), {'frequency': 'Quarter'})[2]
    if not re.fullmatch(r'[0-9]+', cells.get(col + '9', '')):
        raise ValueError('Invalid declared count')
    if (declared_first, declared_last, int(cells[col + '9'])) != (first, last, len(valid)):
        issues.append('DECLARED_COVERAGE_MISMATCH')
    return {'rows': rows, 'valid': valid, 'issues': sorted(set(issues)),
            'coverage': {'first_period': first, 'last_period': last, 'observation_count': len(valid),
                         'grid_first': min(rows), 'grid_last': max(rows),
                         'leading_missing_count': sum(p < first for p, v in rows.items() if v is None),
                         'trailing_missing_count': sum(p > last for p, v in rows.items() if v is None),
                         'internal_missing_count': len(internal)}}


def compare_values(baseline, candidate, first, last):
    """Reuse Phase 2C classifications/decimal rendering, not its synthetic loader.

    Future boundary placeholders are not observations. A filled future placeholder
    is NEW_OBSERVATION; a missing existing observation is MISSINGNESS_CHANGED.
    """
    old = baseline['valid']
    new = {p: v for p, v in candidate['rows'].items()
           if first <= p <= last and (v is not None or p in old)}
    counts, rows = dict.fromkeys(revision.CLASSES, 0), []
    with localcontext(Context(prec=256, rounding=ROUND_HALF_EVEN)):
        for p in sorted(old.keys() | new.keys(), key=quarter):
            x, y = old.get(p), new.get(p)
            if p not in old:
                state = 'NEW_OBSERVATION'
            elif p not in new:
                state = 'REMOVED_OBSERVATION'
            elif (x is None) != (y is None):
                state = 'MISSINGNESS_CHANGED'
            else:
                state = 'UNCHANGED' if x == y else 'REVISED'
            change = y - x if x is not None and y is not None else None
            counts[state] += 1
            rows.append({'period': p, 'classification': state,
                         'old_present': p in old, 'new_present': p in new,
                         'old_value': revision.decimal_text(x), 'new_value': revision.decimal_text(y),
                         'signed_change_pp': revision.decimal_text(change),
                         'absolute_change_pp': revision.decimal_text(abs(change)) if change is not None else None})
    return {'counts': counts, 'observations': rows}


def evaluate(policy, profile, baseline_evidence, baseline_bytes, candidate_evidence, candidate_bytes):
    """All evidence declarations are hash-bound attestations, not authenticated approvals."""
    report = {'report_version': '0.1.1',
              'policy_id': policy.get('policy_id') if type(policy) is dict and type(policy.get('policy_id')) is str else None,
              'policy_version': policy.get('policy_version') if type(policy) is dict and type(policy.get('policy_version')) is str else None,
              'policy_sha256': safe_binding(policy),
              'profile_sha256': safe_binding(profile), 'baseline_evidence_sha256': safe_binding(baseline_evidence),
              'candidate_evidence_sha256': safe_binding(candidate_evidence),
              'implementation_sha256': digest(Path(__file__).read_bytes().replace(b'\r\n', b'\n')),
              'dependency_sha256': {name: digest(Path(module.__file__).read_bytes().replace(b'\r\n', b'\n'))
                                    for name, module in [('phase2a', provenance), ('phase2b', capture), ('phase2c', revision),
                                                         ('workbook_reader', workbook_reader), ('e12_importer', e12)]},
              'status': 'FAIL', 'fail_reasons': [], 'manual_review_reasons': [], 'comparison': None,
              'candidate_status': e12.STATUS, 'publication_approved': False, 'point_in_time_eligible': False,
              'historical_classification': 'latest_revised_data_research',
              'composite_release_statuses': dict(provenance.HOLD),
              'composite_scores': dict.fromkeys(provenance.HOLD),
              'release_verification': 'OPERATOR_ATTESTATION_NOT_AUTOMATED_VERIFICATION'}
    report['comparison_is_diagnostic_only'] = True
    report['canonical_bindings_valid'] = all(report[key] is not None for key in
        ('policy_sha256', 'profile_sha256', 'baseline_evidence_sha256', 'candidate_evidence_sha256'))
    fail, manual = report['fail_reasons'], report['manual_review_reasons']
    try:
        # Includes direct API inputs bypassing the strict JSON decoder. Do not
        # inspect sources, classify methodology or append manual-only gates when
        # any input cannot be canonically hashed (NaN, infinity, cycles, sets...).
        if not report['canonical_bindings_valid']:
            raise ValueError('CANONICAL_BINDING_FAILED')
        # The public CLI reads only this reviewed policy file; no approval override.
        validate_policy(policy)
        if any(type(value) is not dict for value in (profile, baseline_evidence, candidate_evidence)):
            raise ValueError('INPUT_OBJECT_REQUIRED')
        manual.append('C05_UNRESOLVED')
        identity = policy['identity']
        c = e12.CONTRACTS['A']
        fixed = {'indicator': 'E12', 'methodological_variant': 'A', 'source_role': 'track_A',
                 'provider': 'ABS', 'adapter': 'ABS_XLSX', 'series_id': c['series_id'],
                 'frequency': 'quarterly', 'unit': 'Percent', 'seasonal_adjustment': 'Seasonally Adjusted',
                 'data_type': 'PERCENT', 'description': c['description'], 'table': c['table']}
        if identity != fixed or profile['identity'] != identity:
            raise ValueError('IDENTITY_PROFILE_MISMATCH')
        if (set(profile) != {'policy_sha256', 'identity', 'reviewed_by', 'review_reference', 'expected_last_period', 'reviewed_releases'}
                or profile['policy_sha256'] != binding(policy)
                or any(not isinstance(profile[k], str) or not profile[k].strip()
                       or profile[k].strip().upper() in UNKNOWN for k in ('reviewed_by', 'review_reference'))):
            raise ValueError('EXPLICIT_REVIEW_PROFILE_REQUIRED')
        baseline_contract = policy['baseline']
        first, old_last = baseline_contract['first_period'], baseline_contract['last_period']
        expected = profile['expected_last_period']
        if ((first, old_last, baseline_contract['observation_count']) != ('1983-Q1', '2026-Q2', 174)
                or quarter(expected) < quarter(old_last)):
            raise ValueError('EXPECTED_COVERAGE_INVALID')
        for label, raw, evidence in [('baseline', baseline_bytes, baseline_evidence),
                                     ('candidate', candidate_bytes, candidate_evidence)]:
            if (set(evidence) != {'identity', 'sha256', 'byte_count', 'methodology', 'release'}
                    or evidence['identity'] != identity):
                raise ValueError(label.upper() + '_IDENTITY_EVIDENCE')
            if (not isinstance(raw, bytes) or evidence['sha256'] != digest(raw)
                    or type(evidence['byte_count']) is not int or evidence['byte_count'] != len(raw)):
                raise ValueError(label.upper() + '_INTEGRITY')
            report[label + '_sha256'] = digest(raw)
            if label == 'baseline' and (digest(raw), len(raw)) != (baseline_contract['sha256'], baseline_contract['byte_count']):
                raise ValueError('BASELINE_PIN_MISMATCH')
        baseline = extract(baseline_bytes, identity, policy)
        candidate = extract(candidate_bytes, identity, policy)
        if baseline['issues'] or any(baseline['coverage'][key] != baseline_contract[key] for key in baseline['coverage'] if key != 'internal_missing_count'):
            raise ValueError('BASELINE_COVERAGE_INVALID')
        report['baseline_coverage'], report['candidate_coverage'] = baseline['coverage'], candidate['coverage']
        fail.extend(candidate['issues'])
        required = set()
        for index in range(quarter(first), quarter(expected) + 1):
            required.add(f'{(index - 1) // 4}-Q{(index - 1) % 4 + 1}')
        absent = sorted(required - candidate['valid'].keys())
        if absent:
            fail.append('INCOMPLETE_REQUIRED_HISTORY')
            report['missing_required_periods'] = absent
        if (set(candidate['valid']) != required or candidate['coverage']['first_period'] != first
                or candidate['coverage']['last_period'] != expected):
            fail.append('UNEXPECTED_COVERAGE_ENDPOINT_OR_COUNT')
        if any(candidate['coverage'][k] != baseline['coverage'][k] for k in
               ('grid_first', 'grid_last', 'leading_missing_count', 'trailing_missing_count')):
            manual.append('BOUNDARY_GRID_CHANGED')
        methods = []
        compatible = True
        valid_releases = {}
        reviewed = profile['reviewed_releases']
        if type(reviewed) is not dict or set(reviewed) != {'baseline', 'candidate'}:
            raise ValueError('EXPLICIT_RELEASE_REVIEW_REQUIRED')
        for label, evidence in [('baseline', baseline_evidence), ('candidate', candidate_evidence)]:
            method = evidence['methodology']
            if (not isinstance(method, dict) or set(method) != set(policy['methodology_declaration_fields'])
                    or any(not isinstance(v, str) or not v.strip() or v.strip().upper() in UNKNOWN for v in method.values())):
                manual.append(label.upper() + '_METHODOLOGY_UNKNOWN')
                compatible = False
            methods.append(method)
            release = evidence['release']
            try:
                date, reference_end = release_identity(release)
                keys = {'date', 'period', 'evidence_url', 'workbook_url'}
                if type(reviewed[label]) is not dict or set(reviewed[label]) != keys:
                    raise ValueError('RELEASE_REVIEW_BINDING_CONFLICT')
                if reviewed[label] != {k: release[k] for k in keys}:
                    raise ValueError('RELEASE_REVIEW_BINDING_CONFLICT')
                endpoint = old_last if label == 'baseline' else expected
                year, q = int(endpoint[:4]), int(endpoint[-1])
                end = dt.date(year, q * 3, calendar.monthrange(year, q * 3)[1])
                if end > date or end > reference_end:
                    raise ValueError('RELEASE_CHRONOLOGY_CONFLICT')
                valid_releases[label] = date
            except (ValueError, TypeError, KeyError, AttributeError) as error:
                manual.append(label.upper() + '_RELEASE_EVIDENCE_UNKNOWN')
                # Preserve dedicated conflict diagnostics instead of hiding them behind C05.
                code = str(error)
                if code in {'RELEASE_IDENTITY_CONFLICT', 'RELEASE_REVIEW_BINDING_CONFLICT', 'RELEASE_CHRONOLOGY_CONFLICT'}:
                    manual.append(label.upper() + '_' + code)
        if methods[0] != methods[1]:
            manual.append('METHODOLOGY_CHANGED')
            compatible = False
        report['methodological_compatibility'] = 'DECLARED_COMPATIBLE' if compatible else 'NOT_ESTABLISHED'
        if compatible:
            report['comparison'] = compare_values(baseline, candidate, first, max(expected, candidate['coverage']['last_period']))
            if report['comparison']['counts']['REVISED']:
                manual.append('HISTORICAL_REVISION')
        else:
            report['comparison_suppression_reason'] = 'METHODOLOGY_CHANGED_OR_UNKNOWN'
        if set(valid_releases) == {'baseline', 'candidate'}:
            if valid_releases['candidate'] < valid_releases['baseline']:
                manual.append('RELEASE_DATE_REGRESSION')
        report['byte_identity'] = 'IDENTICAL' if baseline_bytes == candidate_bytes else 'DIFFERENT'
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError, IndexError, OSError,
            RecursionError, RuntimeError, NotImplementedError, ET.ParseError, zipfile.BadZipFile, zlib.error) as error:
        # Stable codes only; never leak local paths or raw parse exception text.
        known = {'POLICY_RESTRICTIONS', 'IDENTITY_PROFILE_MISMATCH', 'EXPLICIT_REVIEW_PROFILE_REQUIRED',
                 'EXPECTED_COVERAGE_INVALID', 'BASELINE_IDENTITY_EVIDENCE', 'CANDIDATE_IDENTITY_EVIDENCE',
                 'BASELINE_INTEGRITY', 'CANDIDATE_INTEGRITY', 'BASELINE_PIN_MISMATCH', 'BASELINE_COVERAGE_INVALID',
                 'INPUT_OBJECT_REQUIRED', 'EXPLICIT_RELEASE_REVIEW_REQUIRED', 'AMBIGUOUS_WORKBOOK_STRUCTURE',
                 'UNSUPPORTED_WORKBOOK_ARCHIVE', 'CANONICAL_BINDING_FAILED'}
        code = str(error)
        fail.append(code if code in known or re.fullmatch(r'WORKBOOK_METADATA_ROW_[1-6]_MISMATCH', code)
                    else 'INVALID_WORKBOOK_OR_EVIDENCE')
    report['fail_reasons'] = sorted(set(fail))
    report['manual_review_reasons'] = sorted(set(manual))
    report['status'] = ('FAIL' if fail else 'MANUAL_REVIEW_REQUIRED' if manual else 'PASS_RESEARCH_CHECKS')
    report['structural_checks_passed'] = not bool(fail)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('profile', 'baseline-evidence', 'baseline-workbook', 'candidate-evidence', 'candidate-workbook'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    try:
        policy = read_json_bounded(POLICY_PATH)
        validate_policy(policy)
        profile = read_json_bounded(args.profile)
        old = read_json_bounded(args.baseline_evidence)
        new = read_json_bounded(args.candidate_evidence)
        report = evaluate(policy, profile, old, read_bounded(args.baseline_workbook, policy['maximum_bytes']),
                          new, read_bounded(args.candidate_workbook, policy['maximum_bytes']))
    except (ValueError, TypeError, OSError, UnicodeError, RecursionError, OverflowError) as error:
        report = evaluate({}, {}, {}, b'', {}, b'')
        report['fail_reasons'] = ['NONFINITE_JSON_NUMBER' if str(error) == 'NONFINITE_JSON_NUMBER'
                                  else 'INVALID_OR_UNREADABLE_BOUNDED_INPUT']
        report['canonical_bindings_valid'] = False
        for key in ('policy_sha256', 'profile_sha256', 'baseline_evidence_sha256', 'candidate_evidence_sha256'):
            report[key] = None  # Loading failed: no substitute empty-object evidence hashes.
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return {'PASS_RESEARCH_CHECKS': 0, 'MANUAL_REVIEW_REQUIRED': 2, 'FAIL': 1}[report['status']]


if __name__ == '__main__':
    raise SystemExit(main())
