"""Prospective capture simulations only: no live network or production writes."""
import copy
import datetime as dt
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import aesm_capture as capture
import aesm_provenance as provenance


def request():
    result = provenance.read_json(ROOT / "docs/examples/aesm-capture-rba-household.json")
    result["validation_contract"]["minimum_observations"] = 2
    return result


def rba_bytes(values=(1, 2), missing=False):
    lines = ["Title,Household debt to income", "Units,Per cent", "Frequency,Quarterly", "Type,Original", "Series ID,BHFDDIT"]
    for i, value in enumerate(values):
        lines.append(f"{2025 + i // 4}-{(i % 4 + 1) * 3:02}-01," + ("" if missing and i == 1 else str(value)))
    return ("\n".join(lines) + "\n").encode()


class Response(io.BytesIO):
    def __init__(self, data, **headers):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data)), **headers}

    def geturl(self):
        return "https://www.rba.gov.au/statistics/tables/csv/e2-data.csv"


def workbook(path, count=2):
    """Synthetic two/three-quarter ABS workbook, not official observations."""
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    req = provenance.read_json(ROOT / "docs/examples/aesm-capture-e12-quarterly.json")
    contract = req["validation_contract"]
    dates = [(dt.date(2026, q * 3, 1) - dt.date(1899, 12, 30)).days for q in range(1, count + 1)]
    cells = {"B1": contract["description"], "B2": contract["unit"], "B3": contract["seasonal_adjustment"],
             "B4": contract["data_type"], "B5": "Quarter", "B6": "3", "B7": str(dates[0]),
             "B8": str(dates[-1]), "B9": str(count), "B10": contract["series_id"]}
    cells.update({f"A{k}": v for k, v in capture.e12.LABELS.items()})
    for i, date in enumerate(dates, 11):
        cells[f"A{i}"] = str(date)
        cells[f"B{i}"] = str(i - 10)
    def sheet(mapping):
        root = ET.Element("worksheet", xmlns=ns)
        rows = ET.SubElement(root, "sheetData")
        for address, text in mapping.items():
            row = ET.SubElement(rows, "row")
            cell = ET.SubElement(row, "c", r=address, t="inlineStr")
            ET.SubElement(ET.SubElement(cell, "is"), "t").text = text
        return ET.tostring(root)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", '<workbook xmlns="' + ns + '" xmlns:r="' + capture.e04.REL + '"><sheets><sheet name="Index" sheetId="1" r:id="r1"/><sheet name="Data1" sheetId="2" r:id="r2"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/><Relationship Id="r2" Target="worksheets/sheet2.xml"/></Relationships>')
        archive.writestr("xl/worksheets/sheet1.xml", sheet({"B6": contract["table"]}))
        archive.writestr("xl/worksheets/sheet2.xml", sheet(cells))


class CaptureChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive = self.root / "archive"
        self.fixture = self.root / "fixture.csv"
        self.fixture.write_bytes(rba_bytes())

    def test_dry_run_does_not_create_or_fetch(self):
        with patch.object(capture, "open_official", side_effect=AssertionError("No download allowed")):
            report = capture.capture(request(), self.archive, dry_run=True)
        self.assertTrue(report["dry_run"])
        self.assertFalse(self.archive.exists())
        self.assertIsNone(report["retrieved_at_utc"])
        self.assertIsNone(report["snapshot_sha256"])

    def test_recovery_cannot_silently_ignore_dry_run_flag(self):
        args = ["aesm_capture.py", "recover", "--archive-dir", str(self.archive),
                "--capture-id", "a" * 32, "--confirm-stopped", "--dry-run"]
        with patch.object(sys, "argv", args), patch.object(sys, "stderr", io.StringIO()), self.assertRaises(SystemExit) as error:
            capture.main()
        self.assertEqual(error.exception.code, 2)
        self.assertFalse(self.archive.exists())

    def test_local_import_never_invents_retrieval_or_release(self):
        record = capture.capture(request(), self.archive, self.fixture)
        self.assertEqual(record["outcome"], "VALIDATED")
        self.assertIsNone(record["retrieved_at_utc"])
        self.assertIsNone(record["request"]["release"]["date"])
        self.assertEqual(record["source"]["filename_basis"], "LOCAL_BASENAME")
        self.assertEqual(record["source"]["sha256"], capture.digest(self.fixture.read_bytes()))
        self.assertEqual(record["validation"]["coverage"]["observation_count"], 2)
        self.assertEqual(capture.inspect_archive(self.archive)["pending_capture_ids"], [])

    def test_https_download_records_actual_utc_completion_and_original_filename(self):
        times = ["2026-10-24T00:00:00+00:00", "2026-10-24T00:00:01+00:00", "2026-10-24T00:00:02+00:00"]
        with patch.object(capture, "now", side_effect=times), patch.object(capture, "open_official", return_value=Response(rba_bytes(), **{"Content-Disposition": 'attachment; filename="e2-original.csv"'})):
            record = capture.capture(request(), self.archive)
        self.assertEqual(record["retrieved_at_utc"], times[1])
        self.assertEqual(record["source"]["original_filename"], "e2-original.csv")
        self.assertEqual(record["source"]["filename_basis"], "CONTENT_DISPOSITION")
        self.assertEqual(record["outcome"], "VALIDATED")

    def test_validation_failure_is_quarantined_and_audited(self):
        self.fixture.write_bytes(b"not an RBA CSV\n")
        record = capture.capture(request(), self.archive, self.fixture)
        self.assertEqual(record["outcome"], "VALIDATION_FAILED")
        self.assertTrue(record["source"]["snapshot_path"].startswith("quarantine/"))
        self.assertIsNone(record["validation"]["coverage"])
        self.assertTrue(all(v is False for v in record["approval"].values()))
        self.assertEqual(len(capture.inspect_archive(self.archive)["outcomes"]), 1)

    def test_network_failure_records_terminal_audit_without_snapshot(self):
        with patch.object(capture, "open_official", side_effect=OSError("Simulated outage")):
            record = capture.capture(request(), self.archive)
        self.assertEqual(record["outcome"], "TRANSFER_FAILED")
        self.assertIsNone(record["source"]["snapshot_id"])
        self.assertFalse(list(self.archive.glob("snapshots/**/*")))
        self.assertEqual(capture.inspect_archive(self.archive)["terminal_manifests"], 1)

    def test_interrupted_stream_and_length_mismatch_never_publish_partial_bytes(self):
        class Broken(Response):
            def read(self, size=-1):
                if self.tell():
                    raise OSError("Connection interrupted")
                return super().read(4)
        responses = [Broken(rba_bytes()), Response(rba_bytes(), **{"Content-Length": str(len(rba_bytes()) + 10)})]
        for response in responses:
            with patch.object(capture, "open_official", return_value=response):
                record = capture.capture(request(), self.archive)
            self.assertEqual(record["outcome"], "TRANSFER_FAILED")
            self.assertIsNone(record["source"]["sha256"])
        self.assertEqual(list((self.archive / ".staging").glob("*.part")), [])

    def test_response_size_limit_failure_is_audited(self):
        req = request()
        req["maximum_bytes"] = 4
        record = capture.capture(req, self.archive, self.fixture)
        self.assertEqual(record["outcome"], "TRANSFER_FAILED")

    def test_identical_downloads_reuse_bytes_but_append_distinct_capture_manifests(self):
        first = capture.capture(request(), self.archive, self.fixture)
        blob = self.archive / first["source"]["snapshot_path"]
        stamp, data = blob.stat().st_mtime_ns, blob.read_bytes()
        second = capture.capture(request(), self.archive, self.fixture)
        self.assertNotEqual(first["capture_id"], second["capture_id"])
        self.assertEqual(first["source"]["snapshot_id"], second["source"]["snapshot_id"])
        self.assertEqual((blob.stat().st_mtime_ns, blob.read_bytes()), (stamp, data))
        self.assertEqual(capture.inspect_archive(self.archive)["terminal_manifests"], 2)

    def test_future_release_changes_snapshot_without_overwriting_prior(self):
        first = capture.capture(request(), self.archive, self.fixture)
        original = (self.archive / first["source"]["snapshot_path"]).read_bytes()
        self.fixture.write_bytes(rba_bytes((1, 2, 3)))
        second = capture.capture(request(), self.archive, self.fixture)
        self.assertNotEqual(first["source"]["snapshot_id"], second["source"]["snapshot_id"])
        self.assertEqual(second["validation"]["coverage"]["observation_count"], 3)
        self.assertEqual((self.archive / first["source"]["snapshot_path"]).read_bytes(), original)

    def test_reused_capture_id_is_rejected(self):
        first = capture.capture(request(), self.archive, self.fixture, capture_id="a" * 32)
        before = (self.archive / "manifests" / (first["capture_id"] + ".json")).read_bytes()
        with self.assertRaisesRegex(ValueError, "already used"):
            capture.capture(request(), self.archive, self.fixture, capture_id="a" * 32)
        self.assertEqual((self.archive / "manifests" / (first["capture_id"] + ".json")).read_bytes(), before)

    def test_preexisting_staging_bytes_are_never_deleted(self):
        path = self.archive / ".staging" / ("c" * 32 + ".part")
        path.parent.mkdir(parents=True)
        path.write_bytes(b"preexisting bytes owned by another operation")
        record = capture.capture(request(), self.archive, self.fixture, capture_id="c" * 32)
        self.assertEqual(record["outcome"], "TRANSFER_FAILED")
        self.assertEqual(path.read_bytes(), b"preexisting bytes owned by another operation")

    def test_changed_staging_source_cannot_be_published_under_wrong_hash(self):
        original = capture.validate_source
        def changed(path, req):
            result = original(path, req)
            path.write_bytes(b"changed during validation")
            return result
        with patch.object(capture, "validate_source", side_effect=changed), self.assertRaisesRegex(ValueError, "changed during validation"):
            capture.capture(request(), self.archive, self.fixture)
        self.assertEqual(capture.inspect_archive(self.archive)["terminal_manifests"], 0)

    def test_conflicting_snapshot_identifier_is_never_replaced(self):
        checksum = capture.digest(self.fixture.read_bytes())
        target = self.archive / "snapshots/sha256" / checksum
        target.parent.mkdir(parents=True)
        target.write_bytes(b"conflicting bytes")
        with self.assertRaisesRegex(ValueError, "Conflicting existing"):
            capture.capture(request(), self.archive, self.fixture)
        self.assertEqual(target.read_bytes(), b"conflicting bytes")
        self.assertEqual(len(capture.inspect_archive(self.archive)["pending_capture_ids"]), 1)

    def test_crash_after_snapshot_publish_leaves_pending_not_a_success_manifest(self):
        original_writer = capture.write_record
        def crash(root, record, final=False):
            if final:
                raise KeyboardInterrupt("Simulated process interruption")
            return original_writer(root, record, final)
        with patch.object(capture, "write_record", side_effect=crash), self.assertRaises(KeyboardInterrupt):
            capture.capture(request(), self.archive, self.fixture, capture_id="b" * 32)
        report = capture.inspect_archive(self.archive)
        self.assertEqual(report["pending_capture_ids"], ["b" * 32])
        self.assertEqual(report["terminal_manifests"], 0)
        with self.assertRaises(ValueError):
            capture.recover(self.archive, "b" * 32)
        result = capture.recover(self.archive, "b" * 32, confirm_stopped=True)
        self.assertEqual(result["outcome"], "INTERRUPTED")
        self.assertIsNone(result["source"]["snapshot_id"])
        self.assertTrue((self.archive / ".staging" / ("b" * 32 + ".part")).exists())

    def test_partial_atomic_record_publication_is_not_a_final_manifest(self):
        original = capture.atomic_publish
        def crash(temp, target, allow_identical=False):
            if target.parent.name == "manifests":
                raise OSError("Simulated filesystem failure")
            return original(temp, target, allow_identical)
        with patch.object(capture, "atomic_publish", side_effect=crash), self.assertRaises(OSError):
            capture.capture(request(), self.archive, self.fixture)
        report = capture.inspect_archive(self.archive)
        self.assertEqual(report["terminal_manifests"], 0)
        self.assertEqual(len(report["pending_capture_ids"]), 1)

    def test_archive_cannot_be_in_repo_or_any_other_git_worktree(self):
        for path in (ROOT / "research-inputs/capture", Path("relative/archive")):
            with self.assertRaises(ValueError):
                capture.archive_root(path)
        (self.root / ".git").mkdir()
        with self.assertRaisesRegex(ValueError, "Git worktree"):
            capture.archive_root(self.archive)

    def test_official_hosts_redirects_and_filename_guards(self):
        for url in ("http://www.rba.gov.au/a", "https://www.rba.gov.au.evil.example/a", "https://user:pass@www.rba.gov.au/a", "https://www.rba.gov.au/a?token=secret"):
            with self.assertRaises(ValueError):
                capture.official_url(url, "RBA")
        with self.assertRaises(ValueError):
            capture.OfficialRedirect("ABS").redirect_request(None, None, 302, "", {}, "https://unofficial.example/file")
        for value in ("../data.csv", "C:\\private.csv", "bad\x00.csv"):
            with self.assertRaises(ValueError):
                capture.filename(value)

    def test_operator_release_claim_requires_evidence_not_inference(self):
        req = request()
        req["release"]["date"] = "2026-10-01"
        with self.assertRaises(ValueError):
            capture.validate_request(req)
        req["release"].update(evidence_url="https://www.rba.gov.au/statistics/tables/", verification_note="Synthetic operator attestation for test only")
        result = capture.capture(req, self.archive, self.fixture)
        self.assertEqual(result["release_verification_basis"], "OPERATOR_ATTESTATION_NOT_AUTOMATED_VERIFICATION")
        self.assertIsNone(result["retrieved_at_utc"])

    def test_source_internal_gap_and_wrong_metadata_are_validation_failures(self):
        self.fixture.write_bytes(rba_bytes((1, 2, 3), missing=True))
        result = capture.capture(request(), self.archive, self.fixture)
        self.assertEqual(result["outcome"], "VALIDATION_FAILED")
        self.fixture.write_bytes(rba_bytes().replace(b"Per cent", b"Index"))
        result = capture.capture(request(), self.archive, self.fixture)
        self.assertEqual(result["outcome"], "VALIDATION_FAILED")

    def test_future_abs_workbook_coverage_not_locked_to_phase2a_endpoint(self):
        path = self.root / "fixture.xlsx"
        req = provenance.read_json(ROOT / "docs/examples/aesm-capture-e12-quarterly.json")
        req["validation_contract"]["minimum_observations"] = 2
        workbook(path, 2)
        first = capture.capture(req, self.archive, path)
        self.assertEqual(first["outcome"], "VALIDATED")
        workbook(path, 3)
        second = capture.capture(req, self.archive, path)
        self.assertEqual(second["validation"]["coverage"]["last_period"], "2026-Q3")
        self.assertEqual(second["validation"]["coverage"]["observation_count"], 3)
        self.assertNotEqual(first["source"]["snapshot_id"], second["source"]["snapshot_id"])

    def test_sdmx_dimensions_and_frequency_checked_with_operator_metadata_caveat(self):
        req = request()
        req.update(provider="ABS", indicator="E06", official_source_url="https://data.api.abs.gov.au/rest/data/test")
        req["validation_contract"].update(adapter="ABS_SDMX_CSV", frequency="monthly", dimensions={"MEASURE": "M13"})
        self.fixture.write_text("MEASURE,TIME_PERIOD,OBS_VALUE\nM13,2026-01,4.0\nM13,2026-02,4.1\n", encoding="utf-8")
        result = capture.capture(req, self.archive, self.fixture)
        self.assertEqual(result["outcome"], "VALIDATED")
        self.assertIn("pending independent DSD review", result["validation"]["note"])
        self.fixture.write_text("MEASURE,TIME_PERIOD,OBS_VALUE\nWRONG,2026-01,4.0\n", encoding="utf-8")
        self.assertEqual(capture.capture(req, self.archive, self.fixture)["outcome"], "VALIDATION_FAILED")

    def test_approval_score_and_timestamp_tampering_rejected(self):
        record = capture.capture(request(), self.archive, self.fixture)
        for change in (lambda d: d["approval"].update(publication_approved=True),
                       lambda d: d["composite_scores"].update(AEHI=0),
                       lambda d: d.update(retrieved_at_utc=d["completed_at_utc"])):
            changed = copy.deepcopy(record)
            change(changed)
            with self.assertRaises(ValueError):
                capture.validate_record(capture.record_seal(changed))

    def test_restore_verification_detects_tampered_snapshot_and_manifest(self):
        record = capture.capture(request(), self.archive, self.fixture)
        blob = self.archive / record["source"]["snapshot_path"]
        blob.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "immutable snapshot"):
            capture.inspect_archive(self.archive)
        blob.write_bytes(self.fixture.read_bytes())
        path = self.archive / "manifests" / (record["capture_id"] + ".json")
        data = json.loads(path.read_text())
        data["request"]["source_role"] = "changed"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(ValueError):
            capture.inspect_archive(self.archive)


if __name__ == "__main__":
    unittest.main()
