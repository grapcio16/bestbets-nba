import unittest
import pandas as pd
from player_intelligence.availability_calibration import calibrate_availability

NOW=pd.Timestamp("2026-11-27T12:00:00Z")

def observation(i):
    tip=NOW-pd.Timedelta(days=i+1)
    return {"game_id":f"nba:00226{i:05d}","player_id":"nba:100",
            "evidence_mode":"prospective","verified":True,"status":"questionable",
            "start_utc":tip,"forecast_asof":tip-pd.Timedelta(hours=1),
            "published_at":tip-pd.Timedelta(hours=2),"captured_at":tip-pd.Timedelta(hours=1),
            "final_observed_at":tip+pd.Timedelta(hours=5),"played":i%2==0}

class AvailabilityCalibrationTests(unittest.TestCase):
    def test_insufficient_samples_have_no_probability(self):
        result=calibrate_availability(observations=[observation(i) for i in range(49)],asof=NOW)
        self.assertIsNone(result["groups"]["questionable"]["historical_play_rate"])
        self.assertFalse(result["apply_to_live_model"])

    def test_descriptive_frequency_requires_sample_and_games(self):
        result=calibrate_availability(observations=[observation(i) for i in range(50)],asof=NOW)
        q=result["groups"]["questionable"]
        self.assertEqual(q["historical_play_rate"],.5)
        self.assertEqual(q["distinct_games"],50)
        self.assertLess(q["wilson_95_descriptive"][0],.5)
        self.assertGreater(q["wilson_95_descriptive"][1],.5)
        self.assertFalse(result["apply_to_live_model"])

    def test_replay_future_and_unknown_rejected(self):
        rows=[dict(observation(0),evidence_mode="captured_replay"),
              dict(observation(1),final_observed_at=NOW+pd.Timedelta(seconds=1)),
              dict(observation(2),status="unknown")]
        result=calibrate_availability(observations=rows,asof=NOW)
        self.assertEqual(sum(result["rejected"].values()),3)
        self.assertEqual(result["groups"]["questionable"]["n"],0)

    def test_duplicate_not_counted_twice(self):
        with self.assertRaisesRegex(ValueError,"duplicate"):
            calibrate_availability(observations=[observation(0),observation(0)],asof=NOW)

if __name__=="__main__":
    unittest.main()
