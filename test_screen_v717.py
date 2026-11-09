"""BestBets v7.17 screenshot import regression tests — no bookmaker OCR service."""
import unittest

import pandas as pd

from screenshot_import import (
    parse_ocr_tokens, parse_price, parse_line, market_from_header,
    batch_analyze, EDIT_COLUMNS,
)


def token(text,x,y,width=38,conf=92):
    return {"text":text,"left":x,"top":y,"width":width,
            "height":18,"conf":conf}


class ScreenshotIntakeTests(unittest.TestCase):
    def test_15_pairs_from_two_columns_and_missing_odds_kept_blank(self):
        # Synthetic OCR geometry resembles two-col sportsbook listings; no
        # private screen/photo is checked into public GitHub.
        words=[token("Łączne",30,8),token("punkty",102,8),token("gracza",173,8)]
        names=[("Aaron","Wiggins"),("Austin","Reaves"),("CJ","McCollum"),
               ("Dyson","Daniels"),("Jake","LaRavia"),("Jalen","Johnson"),
               ("Kingston","Flemings"),("Luguentz","Dort"),("Luka","Doncic"),
               ("Matisse","Thybulle"),("Nickeil","Walker"),("Onyeka","Okongwu"),
               ("S.","Mamukelashvili"),("Walker","Kessler"),("Ziaire","Williams")]
        for n,(first,last) in enumerate(names):
            y=55+44*n
            for shift,direction,odds in (
                (0,"Powyżej","176" if n!=3 else "??"),
                (500,"Poniżej","1,88" if n!=6 else "??")):
                words+=[token(first,30+shift,y,width=len(first)*8),
                        token(last,110+shift,y,width=len(last)*7),
                        token(direction,220+shift,y),
                        token("12,5",290+shift,y),
                        token(odds,435+shift,y-10)]
        frame,meta=parse_ocr_tokens(words,1000)
        self.assertEqual(len(frame),15)
        self.assertEqual(meta["detected"],15)
        self.assertEqual(set(frame["Rynek"]),{"PTS"})
        self.assertEqual(frame.loc[frame["Zawodnik"]=="Aaron Wiggins",
                                   "Kurs OVER"].iloc[0],1.76)
        self.assertEqual(frame.loc[frame["Zawodnik"]=="Aaron Wiggins",
                                   "Kurs UNDER"].iloc[0],1.88)
        self.assertEqual(meta["unreadable_odds"],2)
        self.assertTrue((frame["Weryfikacja OCR"]=="WYMAGA SPRAWDZENIA").all())

    def test_pra_header_not_misidentified_as_rebounds(self):
        self.assertEqual(market_from_header(
            ["Łączne","punkty","i","zbiórki","i","asysty"]),"PRA")
        self.assertEqual(market_from_header(["Rebounds","player"]),"REB")
        self.assertEqual(market_from_header(["Player","points"]),"PTS")

    def test_number_parsing_is_strict(self):
        self.assertEqual(parse_price("176"),1.76)
        self.assertEqual(parse_price("1,89"),1.89)
        self.assertIsNone(parse_price("6"))
        self.assertIsNone(parse_price("wa"))
        self.assertIsNone(parse_price("17.8"))
        self.assertEqual(parse_line("36,5"),36.5)
        self.assertIsNone(parse_line("AA"))


class BatchResearchTests(unittest.TestCase):
    def setUp(self):
        base=pd.Timestamp("2026-10-22T00:00:00Z")
        self.logs=pd.DataFrame(
            [{"PLAYER_NAME":"Aaron Wiggins","TEAM_ABBREVIATION":"OKC",
              "GAME_DATE":base+pd.Timedelta(days=k),"MIN":24+k%3,
              "PTS":12+k%9,"REB":5+k%3,"AST":4+k%2,"FG3M":1+k%3,
              "PRA":21+k%9} for k in range(12)]
            +[{"PLAYER_NAME":"Other Player","TEAM_ABBREVIATION":"LAL",
              "GAME_DATE":base+pd.Timedelta(days=k),"MIN":29,
              "PTS":16,"REB":3,"AST":6,"FG3M":2,"PRA":25}
              for k in range(4)])
        self.line=pd.DataFrame([{
            "Zawodnik":"Aaron Wiggins","Rynek":"PTS","Linia":12.5,
            "Kurs OVER":1.76,"Kurs UNDER":1.88,
            "Weryfikacja OCR":"WYMAGA SPRAWDZENIA",
        }],columns=EDIT_COLUMNS)
        self.cutoff="2026-11-09T20:00:00Z"

    def test_probability_is_model_labelled_and_two_sided(self):
        result=batch_analyze(self.line,self.logs,self.cutoff)
        self.assertEqual(len(result),1)
        v=result.iloc[0]
        self.assertEqual(v["Status"],"MODEL TESTOWY")
        self.assertEqual(v["Próba"],12)
        self.assertAlmostEqual(v["P(OVER) model %"]+v["P(UNDER) model %"],100,places=1)
        self.assertAlmostEqual(v["Próg OVER %"],round(100/1.76,1))
        self.assertIn("Niezweryfikowane",v["Uwaga"])
        self.assertTrue(0<=v["Rynek bez marży OVER %"]<=100)

    def test_missing_player_low_sample_and_integer_lines_fail_closed(self):
        frame=self.line.copy()
        frame.loc[0,"Zawodnik"]="Luka Doncie"
        self.assertEqual(batch_analyze(frame,self.logs,self.cutoff).iloc[0]["Status"],"WSTRZYMAJ")
        frame.loc[0,"Zawodnik"]="Other Player"
        self.assertEqual(batch_analyze(frame,self.logs,self.cutoff).iloc[0]["Status"],"WSTRZYMAJ")
        frame.loc[0,"Zawodnik"]="Aaron Wiggins"
        frame.loc[0,"Linia"]=13
        self.assertIn("Całkowita",batch_analyze(frame,self.logs,self.cutoff).iloc[0]["Uwaga"])
        frame.loc[0,"Linia"]=12.5
        frame.loc[0,"Kurs OVER"]=None
        frame.loc[0,"Kurs UNDER"]=None
        self.assertEqual(batch_analyze(frame,self.logs,self.cutoff).iloc[0]["Status"],"WSTRZYMAJ")

    def test_future_boxscore_never_changes_pregame_prediction(self):
        original=batch_analyze(self.line,self.logs,self.cutoff)
        extra=self.logs.iloc[[0]].copy()
        extra.loc[:,"GAME_DATE"]=pd.Timestamp("2026-11-11T01:00:00Z")
        extra.loc[:,"PTS"]=65
        later=pd.concat([self.logs,extra],ignore_index=True)
        after=batch_analyze(self.line,later,self.cutoff)
        self.assertEqual(original["Prognoza"].tolist(),after["Prognoza"].tolist())
        self.assertEqual(original["P(OVER) model %"].tolist(),
                         after["P(OVER) model %"].tolist())

    def test_missing_market_column_never_calculates(self):
        logs=self.logs.drop(columns=["PRA"])
        variant=self.line.copy()
        variant.loc[0,"Rynek"]="PRA"
        self.assertEqual(batch_analyze(variant,logs,self.cutoff).iloc[0]["Status"],
                         "WSTRZYMAJ")


if __name__=="__main__":
    unittest.main()
