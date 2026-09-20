import importlib.util
from pathlib import Path
import unittest


class ReportSelectionTests(unittest.TestCase):
    def test_newest_attempt_wins_even_when_its_id_is_lower(self):
        path=Path(__file__).resolve().parents[1]/'Scripts/collect_reports.py'
        spec=importlib.util.spec_from_file_location('collect',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        artifacts=[{'id':90,'name':'SimulatorRuntimeReports','created_at':'2026-09-20T01:00:00Z','expired':False},
                   {'id':80,'name':'SimulatorRuntimeReports','created_at':'2026-09-20T22:00:00Z','expired':False},
                   {'id':100,'name':'BO2CS-Validation-Reports','created_at':'2026-09-20T23:00:00Z','expired':False}]
        result=module.latest_reports(artifacts)
        self.assertEqual(result['SimulatorRuntimeReports']['id'],80)
        self.assertNotIn('BO2CS-Validation-Reports',result)


if __name__=='__main__':unittest.main()
