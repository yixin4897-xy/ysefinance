#!/usr/bin/env python3
"""Offline security/quality checks for review-only AEHI ABS API importer."""
import importlib.util
from pathlib import Path
import unittest

module_path=Path(__file__).resolve().parents[1]/"scripts"/"aehi_abs_api_import.py"
spec=importlib.util.spec_from_file_location("aehi_abs_api_import",module_path)
api=importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)

class APIImportChecks(unittest.TestCase):
    def test_no_untrusted_hosts(self):
        for url in (
            "http://data.api.abs.gov.au/rest/data/ABS,CPI,2.0.0/a.b?format=csv",
            "https://data.api.abs.gov.au.evil.com/rest/data/ABS,CPI,2.0.0/a.b?format=csv",
            "https://data.api.abs.gov.au/rest/data/ABS,CPI,2.0.0/all?format=csv",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                api.validate_url(url)
    def test_official_explicit_key_allowed(self):
        url="https://data.api.abs.gov.au/rest/data/ABS,CPI,2.0.0/1.10001.10.50.M?format=csv"
        self.assertEqual(api.validate_url(url),url)
    def test_unapproved_series_rejected(self):
        with self.assertRaises(ValueError):
            api.parse({"code":"E06","approved_series_metadata":False},[], "abc")
    def test_wrong_population_rejected(self):
        cfg={"code":"E06","approved_series_metadata":True,"expected_dimensions":{"REGION":"AUS"},
             "frequency":"monthly","verified_metric_definition":"National seasonally adjusted unemployment rate",
             "value_transform":"identity","series_id":"a test-only key","url":"https://data.api.abs.gov.au/rest/data/test"}
        with self.assertRaisesRegex(ValueError,"unexpected ABS series dimensions"):
            api.parse(cfg,[{"REGION":"NSW","TIME_PERIOD":"2026-09","OBS_VALUE":"4.3"}],"abc")

if __name__=="__main__":
    unittest.main()
