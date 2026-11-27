import unittest
from unittest.mock import Mock
from admin_source_monitor import assess_payload, probe

class SourceMonitorTest(unittest.TestCase):
    def test_valid_and_empty(self):
        self.assertEqual(assess_payload("ESPN scoreboard", {"events":[]}), ("empty_response",0))
        self.assertEqual(assess_payload("NBA scoreboard", {"scoreboard":{"games":[{"gameId":"1","homeTeam":{},"awayTeam":{}}]}}), ("schema_ok",1))
        self.assertEqual(assess_payload("ESPN injuries", {"injuries":[{"injuries":[{"athlete":{"id":"1"},"status":"Out"}]}]}), ("schema_ok",1))

    def test_schema_errors(self):
        for name, payload in (("ESPN scoreboard", {}), ("NBA scoreboard", {"scoreboard":{}}),
                              ("ESPN injuries", {"injuries":[{}]})):
            self.assertEqual(assess_payload(name,payload), ("invalid_schema",None))

    def test_failure_does_not_leak_details(self):
        result = probe("NBA scoreboard", get=Mock(side_effect=RuntimeError("private detail")))
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("private detail", str(result))
        self.assertIsNone(result["rows"])

    def test_http_failure(self):
        get = Mock(return_value=Mock(status_code=503))
        result = probe("ESPN scoreboard", get=get)
        self.assertEqual(result["status"], "http_error")
        self.assertEqual(result["http_status"],503)
        self.assertFalse(get.call_args.kwargs["allow_redirects"])

if __name__ == "__main__":
    unittest.main()
