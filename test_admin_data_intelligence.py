import unittest
from datetime import datetime, timezone, timedelta
from admin_data_intelligence import classify_worker, read_snapshot, read_scorecard

class DataIntelligenceTest(unittest.TestCase):
    def test_worker_status(self):
        now = datetime(2026,11,25,20,tzinfo=timezone.utc)
        row = {"run_utc":now, "trainable_examples":100, "minimum_examples":80}
        self.assertEqual(classify_worker(row, now), "recent_evidence")
        self.assertEqual(classify_worker(None, now), "no_evidence")
        self.assertEqual(classify_worker({**row,"run_utc":now-timedelta(hours=7)},now),"stale")
        self.assertEqual(classify_worker({**row,"run_utc":now+timedelta(hours=1)},now),"invalid_timestamp")
        self.assertEqual(classify_worker({**row,"trainable_examples":79},now),"insufficient_training")

    def test_missing_database(self):
        self.assertEqual(read_snapshot("", "2026-27"), {"status":"setup_required"})
        self.assertEqual(read_scorecard("", "2026-27"), {"status":"setup_required"})

if __name__ == "__main__":
    unittest.main()
