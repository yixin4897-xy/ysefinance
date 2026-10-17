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


    def test_e01_documented_abs_example_qoq_growth(self):
        cfg={"code":"E01","approved_series_metadata":True,
             "expected_dimensions":{"MEASURE":"M1","DATA_ITEM":"GPM_PCA",
                 "TSEST":"20","REGION":"AUS","FREQ":"Q"},
             "frequency":"quarterly",
             "verified_metric_definition":"Real seasonally adjusted GDP per capita, QoQ growth",
             "value_transform":"qoq_pct_change",
             "series_id":"ABS:ANA_AGG(1.1.0)/M1.GPM_PCA.20.AUS.Q",
             "url":"https://data.api.abs.gov.au/rest/data/ABS,ANA_AGG,1.1.0/M1.GPM_PCA.20.AUS.Q?format=csv"}
        from datetime import date
        # Synthetic values are test inputs, NOT official ABS observations.
        rows=[]
        for i in range(16):
            yr=2022+i//4
            q=i%4+1
            rows.append({"MEASURE":"M1","DATA_ITEM":"GPM_PCA","TSEST":"20",
               "REGION":"AUS","FREQ":"Q","TIME_PERIOD":f"{yr}-Q{q}",
               "OBS_VALUE":str(19000+100*i)})
        parsed=api.parse(cfg,rows,"a"*64)
        self.assertEqual(len(parsed["observations"]),15)
        self.assertEqual(parsed["observations"][0]["period"],"2022 Q2")
        self.assertAlmostEqual(parsed["observations"][0]["value"],(19100/19000-1)*100,4)
        self.assertEqual(parsed["growth_convention"],"quarter_on_quarter_percent")

    def test_e01_reject_gap(self):
        cfg={"code":"E01","approved_series_metadata":True,
             "expected_dimensions":{"MEASURE":"M1"},
             "frequency":"quarterly","verified_metric_definition":"GDP per capita, QoQ",
             "value_transform":"qoq_pct_change","series_id":"TEST","url":"https://data.api.abs.gov.au/rest/data/test"}
        rows=[{"MEASURE":"M1","TIME_PERIOD":f"{2020+i//4}-Q{i%4+1}","OBS_VALUE":"20000"} for i in range(16)]
        rows[10]["TIME_PERIOD"]="2022-Q4"
        with self.assertRaises(ValueError):
            api.parse(cfg,rows,"a"*64)

if __name__=="__main__":
    unittest.main()
