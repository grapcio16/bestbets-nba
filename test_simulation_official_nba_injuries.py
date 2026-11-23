"""Offline parser tests for the independent official NBA injury-report PDFs.

Synthetic test PDFs; no official document is stored in the repository.
"""
import io
import unittest

from reportlab.pdfgen.canvas import Canvas

from simulation_official_nba_injuries import (
    latest_report_url, parse_official_word_pages, selected_official_injury_rows,
)

PDF_URL = ("https://ak-static.cms.nba.com/referee/injury/"
           "Injury-Report_2026-11-23_03_00PM.pdf")
NOW = "2026-11-23T20:20:00Z"


def sample_pdf():
    """Minimal NBA-column-layout PDF from synthetic text only."""
    buf = io.BytesIO()
    pdf = Canvas(buf, pagesize=(1000, 800))
    def line(y, date="", matchup="", team="", player="", status=""):
        for x, txt in ((27,date),(239,matchup),(314,team),(507,player),(695,status)):
            if txt:
                pdf.drawString(x,y,txt)
    line(725,"11/23/2026","POR@PHI","Portland Trail Blazers",
         "Krejci, Vit","Out")
    line(704,player="Morant, Ja",status="Out")
    line(683,team="Philadelphia 76ers",player="Brown, Jaylen",
         status="Probable")
    line(657,"11/23/2026","NYK@BOS","New York Knicks",
         "Risk, Jane","Questionable")
    line(640,team="Boston Celtics",player="Healthy, John",status="Available")
    pdf.showPage()
    pdf.save()
    return buf.getvalue()


class MockResponse:
    def __init__(self, *, text="", content=b""):
        self.text, self.content = text, content
    def raise_for_status(self):
        pass


class OfficialSourceTests(unittest.TestCase):
    def test_latest_document_timestamp_from_nba_html(self):
        html = '<a href="'+PDF_URL+'">Latest</a>'
        found = latest_report_url(html, now=NOW)
        self.assertIsNotNone(found)
        self.assertEqual(found[1], PDF_URL)
        self.assertEqual(found[0].isoformat(), "2026-11-23T20:00:00+00:00")
        self.assertIsNone(latest_report_url(html, now="2026-11-24T04:10:00Z"))

    def test_real_pdf_column_extraction_with_matchup_boundaries(self):
        import pdfplumber
        with pdfplumber.open(io.BytesIO(sample_pdf())) as doc:
            extracted = parse_official_word_pages(
                [(p.width, p.extract_words()) for p in doc.pages])
        self.assertEqual(len(extracted), 5, extracted)
        por = [r for r in extracted if r["team"] == "POR"]
        phi = [r for r in extracted if r["team"] == "PHI"]
        self.assertEqual({x["player"] for x in por},
                         {"Vit Krejci", "Ja Morant"})
        self.assertEqual(phi[0]["player"], "Jaylen Brown")
        self.assertEqual(phi[0]["status"], "Probable")
        self.assertEqual(
            [r["status"] for r in extracted if r["team"] == "BOS"],
            ["Available"])

    def test_fixture_and_game_date_prevents_other_team_injuries(self):
        html = '<a href="'+PDF_URL+'">Report</a>'
        def get(url, **_kwargs):
            return (MockResponse(text=html) if "nba.com/players" in url
                    else MockResponse(content=sample_pdf()))
        rows, meta = selected_official_injury_rows(
            "POR", "PHI", "2026-11-24T00:00:00Z",
            now=NOW, get=get)
        self.assertTrue(meta["available"], meta)
        self.assertEqual(meta["source"], "NBA oficjalny raport")
        self.assertEqual(len(rows), 3)
        self.assertEqual(set(rows["team"]), {"POR","PHI"})
        self.assertIn("Vit Krejci", set(rows["player"]))
        other, meta2 = selected_official_injury_rows(
            "POR", "PHI", "2026-11-25T00:00:00Z",
            now=NOW, get=get)
        self.assertFalse(meta2["available"])
        self.assertTrue(other.empty)

    def test_no_current_pdf_yields_explicit_unknown_not_healthy(self):
        html = '<a href="'+PDF_URL+'">Old report</a>'
        rows, meta = selected_official_injury_rows(
            "POR", "PHI", "2026-11-24T00:00:00Z",
            now="2026-11-24T05:10:00Z",
            get=lambda *_a, **_kw: MockResponse(text=html))
        self.assertTrue(rows.empty)
        self.assertFalse(meta["available"])


if __name__ == "__main__":
    unittest.main()
