"""Offline Phase 2C synthetic-vintage comparison. No capture or publication path."""
import argparse
import csv
from decimal import Context, Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
import io
import json
from pathlib import Path
import re

import aesm_capture as capture
import aesm_provenance as provenance

CLASSES = ('UNCHANGED', 'REVISED', 'NEW_OBSERVATION', 'REMOVED_OBSERVATION', 'MISSINGNESS_CHANGED')
METHOD_FIELDS = {'definition_version', 'methodology', 'reference_year', 'price_basis', 'percentage_point_applicable'}
UNKNOWN_DECLARATIONS = {'UNKNOWN', 'UNVERIFIED', 'UNSPECIFIED', 'PENDING', 'TBD'}
PERCENT_UNITS = {'percent', 'per cent', '%'}


def number(value):
    if value.strip() in ('', '..', 'NA', 'na', 'n.a.', '-', '*'):
        return None
    if len(value) > 100 or not re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?', value):
        raise ValueError('Expected bounded plain decimal source value')
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError('Invalid decimal') from error
    if not result.is_finite():
        raise ValueError('Nonfinite value')
    return result


def decimal_text(value):
    if value is None:
        return None
    if value == 0:
        return '0'
    return format(value, 'f').rstrip('0').rstrip('.') if '.' in format(value, 'f') else format(value, 'f')


def load_bundle(bundle):
    if set(bundle) != {'synthetic_only', 'start', 'record', 'source_text', 'methodology'} or bundle['synthetic_only'] is not True:
        raise ValueError('Only explicitly synthetic vintage bundles are supported')
    start, record = bundle['start'], bundle['record']
    capture.validate_record(start)
    capture.validate_record(record)
    if start['outcome'] != 'STARTED' or record['outcome'] != 'VALIDATED':
        raise ValueError('Only complete VALIDATED captures can be compared')
    expected_filename_bases = {'LOCAL_BASENAME'} if record['transport'] == 'LOCAL_IMPORT' else {'URL_PATH', 'CONTENT_DISPOSITION'}
    if record['source']['filename_basis'] not in expected_filename_bases:
        raise ValueError('Filename provenance conflicts with capture transport')
    if record['validation']['error_type'] is not None:
        raise ValueError('Successful capture cannot carry a validation error')
    if (record['start_record_id'] != start['record_id'] or
            any(record[k] != start[k] for k in ('capture_id', 'request', 'started_at_utc', 'transport', 'implementation_sha256', 'record_schema_sha256'))):
        raise ValueError('Capture/start linkage conflict')
    if record['record_schema_sha256'] != capture.text_digest(capture.RECORD_SCHEMA):
        raise ValueError('Unsupported capture schema evidence')
    raw = bundle['source_text'].encode('utf-8')
    if len(raw) > record['request']['maximum_bytes']:
        raise ValueError('Source exceeds capture size contract')
    if len(raw) != record['source']['byte_count'] or capture.digest(raw) != record['source']['sha256']:
        raise ValueError('Source bytes do not match capture hash/count')
    method = bundle['methodology']
    if set(method) != METHOD_FIELDS or type(method['percentage_point_applicable']) is not bool:
        raise ValueError('Explicit methodology declaration required')
    if any(not isinstance(method[k], str) or not method[k].strip() for k in METHOD_FIELDS - {'percentage_point_applicable'}):
        raise ValueError('Unknown methodology/reference basis requires manual review before input')
    req = record['request']
    c = req['validation_contract']
    if c['seasonal_adjustment'] is None:
        raise ValueError('Explicit adjustment basis required')
    if method['percentage_point_applicable'] and c['unit'].lower() not in PERCENT_UNITS:
        raise ValueError('Percentage points require percentage units')
    if c['adapter'] != 'ABS_SDMX_CSV':
        raise ValueError('Synthetic Phase 2C supports SDMX CSV fixtures only; no live adapter approval')
    if c['dimensions'].get('SERIES') != c['series_id']:
        raise ValueError('Synthetic source SERIES dimension must bind the declared series ID')
    if 'UNIT_MEASURE' not in c['dimensions'] or ((c['unit'].lower() in PERCENT_UNITS) != (c['dimensions']['UNIT_MEASURE'] == 'PCT')):
        raise ValueError('Synthetic source UNIT_MEASURE conflicts with percentage unit declaration')
    reader = csv.DictReader(io.StringIO(bundle['source_text']), strict=True)
    if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError('Missing or duplicate CSV columns')
    if not {'TIME_PERIOD', 'OBS_VALUE', *c['dimensions']}.issubset(reader.fieldnames):
        raise ValueError('Required source columns missing')
    rows = []
    try:
        for row in reader:
            if None in row or any(v is None for v in row.values()) or any(row[k] != v for k, v in c['dimensions'].items()):
                raise ValueError('Invalid source row/dimensions')
            period = row['TIME_PERIOD']
            pattern = r'[0-9]{4}-Q[1-4]' if c['frequency'] == 'quarterly' else r'[0-9]{4}-(?:0[1-9]|1[0-2])'
            if not re.fullmatch(pattern, period) or period[:4] == '0000':
                raise ValueError('Expected canonical ASCII calendar period with year 0001-9999')
            rows.append((period, number(row['OBS_VALUE'])))
    except csv.Error as error:
        raise ValueError('Malformed synthetic source CSV') from error
    coverage = capture.coverage(rows, c['frequency'], c['minimum_observations'])
    if coverage != record['validation']['coverage']:
        raise ValueError('Extracted coverage differs from capture record')
    return record, dict(rows), coverage


def identity(record):
    req = record['request']
    c = req['validation_contract']
    return {**{k: req[k] for k in ('provider', 'indicator', 'methodological_variant', 'source_role')},
            **{k: c[k] for k in ('series_id', 'frequency', 'unit', 'seasonal_adjustment', 'adapter', 'dimensions')}}


def vintage(record, bundle):
    return {**{k: record[k] for k in ('capture_id', 'record_id', 'started_at_utc', 'retrieved_at_utc', 'completed_at_utc', 'transport', 'implementation_sha256', 'record_schema_sha256')},
            'source': record['source'], 'identity': identity(record),
            'official_source_url': record['request']['official_source_url'],
            'release': record['request']['release'], 'release_verification_basis': record['release_verification_basis'],
            'methodology_declaration': bundle['methodology'],
            'bundle_sha256': capture.digest(provenance.canonical(bundle))}


def compare(old, new):
    a, av, ac = load_bundle(old)
    b, bv, bc = load_bundle(new)
    if identity(a) != identity(b):
        raise ValueError('Incompatible provider/series/indicator/frequency/unit/adjustment/variant/source identity')
    if a['capture_id'] == b['capture_id']:
        raise ValueError('Distinct capture events required')
    if capture.utc(b['started_at_utc']) <= capture.utc(a['completed_at_utc']):
        raise ValueError('New vintage must start after old vintage completes')
    reasons = [k for k in sorted(METHOD_FIELDS) if old['methodology'][k] != new['methodology'][k]]
    for label, bundle in (('old', old), ('new', new)):
        for key in sorted(METHOD_FIELDS - {'percentage_point_applicable'}):
            if bundle['methodology'][key].strip().upper() in UNKNOWN_DECLARATIONS:
                reasons.append(f'{label}.{key}_unknown')
    for k in ('description', 'data_type', 'table'):
        if a['request']['validation_contract'][k] != b['request']['validation_contract'][k]:
            reasons.append(k)
    report = {'schema_version': '0.1.0', 'status': 'MANUAL_REVIEW_REQUIRED' if reasons else 'RESEARCH_COMPARISON_COMPLETE',
              'synthetic_only': True, 'manual_review_reasons': reasons,
              'old_vintage': vintage(a, old), 'new_vintage': vintage(b, new),
              'coverage': {'old': ac, 'new': bc}, 'observations': [], 'summary': None,
              'candidate_status': 'CANDIDATE_ONLY_PENDING_VALIDATION',
              'composite_release_statuses': dict(provenance.HOLD), 'composite_scores': dict.fromkeys(provenance.HOLD),
              'point_in_time_eligible': False, 'publication_approved': False,
              'implementation_sha256': capture.text_digest(__file__)}
    if reasons:
        return report
    counts = dict.fromkeys(CLASSES, 0)
    changes = []
    # Each input has <=100 decimal characters. 256 digits preserves subtraction
    # and aggregates exactly; division uses fixed precision, independent of caller.
    with localcontext(Context(prec=256, rounding=ROUND_HALF_EVEN)):
        for period in sorted(av.keys() | bv.keys(), key=lambda p: provenance.period_index(p, identity(a)['frequency'])):
            x, y = av.get(period), bv.get(period)
            if period not in av:
                state = 'NEW_OBSERVATION'
            elif period not in bv:
                state = 'REMOVED_OBSERVATION'
            elif (x is None) != (y is None):
                state = 'MISSINGNESS_CHANGED'
            else:
                state = 'UNCHANGED' if x == y else 'REVISED'
            delta = y - x if x is not None and y is not None else None
            if delta is not None:
                changes.append(delta)
            counts[state] += 1
            report['observations'].append({'period': period, 'classification': state,
                'old_present': period in av, 'new_present': period in bv,
                'old_value': decimal_text(x), 'new_value': decimal_text(y),
                'signed_change': decimal_text(delta), 'absolute_change': decimal_text(abs(delta)) if delta is not None else None,
                'percentage_point_change': decimal_text(delta) if old['methodology']['percentage_point_applicable'] else None})
        report['summary'] = {'counts': counts, 'union_period_count': len(av.keys() | bv.keys()),
            'overlap_period_count': len(av.keys() & bv.keys()), 'numeric_pair_count': len(changes),
            'mean_signed_change': decimal_text(sum(changes) / Decimal(len(changes))) if changes else None,
            'mean_absolute_change': decimal_text(sum(map(abs, changes)) / Decimal(len(changes))) if changes else None,
            'maximum_absolute_change': decimal_text(max(map(abs, changes))) if changes else None,
            'arithmetic_precision': 256}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old', type=Path, required=True)
    parser.add_argument('--new', type=Path, required=True)
    args = parser.parse_args()
    result = compare(provenance.read_json(args.old), provenance.read_json(args.new))
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 2 if result['status'] == 'MANUAL_REVIEW_REQUIRED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
