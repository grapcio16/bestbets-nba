import unittest
from unittest.mock import MagicMock, Mock
from admin_performance import database_probe, summarize_sources

class PerformanceTest(unittest.TestCase):
    def test_missing_configuration(self):
        self.assertEqual(database_probe("")["status"], "setup_required")

    def test_success(self):
        connect = MagicMock()
        cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (1,)
        result = database_probe("test", connect=connect, clock=Mock(side_effect=[0,0.1,0.12,0.13]))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["connect_ms"], 100.0)
        self.assertEqual(result["query_ms"], 20.0)
        self.assertEqual(result["total_ms"], 130.0)
        self.assertEqual([item.args[0] for item in cursor.execute.call_args_list], [
            "SET TRANSACTION READ ONLY", "SET LOCAL statement_timeout = '3000ms'", "SELECT 1"])
        self.assertEqual(connect.call_args.kwargs["connect_timeout"], 5)
        self.assertNotIn("options", connect.call_args.kwargs)

    def test_failure_sanitized(self):
        result = database_probe("test", connect=Mock(side_effect=RuntimeError("sensitive")),
                                clock=Mock(side_effect=[0,0.1]))
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("sensitive", str(result))
        self.assertIsNone(result["query_ms"])

    def test_only_successful_sources_ranked(self):
        rows = [{"status":"schema_ok","elapsed_ms":100},
                {"status":"unavailable","elapsed_ms":9000},
                {"status":"empty_response","elapsed_ms":200}]
        self.assertEqual([r["elapsed_ms"] for r in summarize_sources(rows)], [200,100])

if __name__ == "__main__":
    unittest.main()
