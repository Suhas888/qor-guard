"""QoR Guard: UP5K checks that run only where private evaluation data exists.
That data is not distributed, so these tests skip in the public suite.
Run (from the project root): python -I -B -m unittest discover -s tests -t . -v"""
import os
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
CASES = os.path.join(ROOT, 'tests', 'private_evaluation', 'cases.py')
REASON = 'requires private UP5K evaluation data, which is not distributed'


class TestPrivateUp5kEvaluation(unittest.TestCase):
    def check(self, name):
        if not os.path.isfile(CASES):
            self.skipTest(REASON)
        from tests.private_evaluation.cases import Cases
        result = unittest.TestResult()
        Cases(name).run(result)
        self.assertEqual((result.testsRun, result.failures, result.errors), (1, [], []))

    def test_values_match_raw_files_and_reference(self):
        self.check('test_values_match_raw_files_and_reference')

    def test_deltas_utilisation_headroom(self):
        self.check('test_deltas_utilisation_headroom')

    def test_report_framing(self):
        self.check('test_report_framing')


if __name__ == '__main__':
    unittest.main()
