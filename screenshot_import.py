"""Local screenshot-to-batch NBA props intake (BETA).

OCR is one bounded Tesseract invocation. Never persist images, odds or user
account information; never invent unreadable prices or player identities.
A screenshot is NOT a verified current market. Every parsed row requires manual
review before running an experimental, uncalibrated player-props model.
"""
from __future__ import annotations

import math
import re
import unicodedata

import pandas as pd

from core import STAT_NAMES, calc_projection, norm_name, prop_probability
from prediction_engine_v2 import forecast_v2


EDIT_COLUMNS = ["Zawodnik", "Rynek", "Linia", "Kurs OVER", "Kurs UNDER", "Weryfikacja OCR"]
RESULT_COLUMNS = [
    "Zawodnik", "Rynek", "Linia", "Kurs OVER", "Kurs UNDER",
    "Prognoza", "P(OVER) model %", "P(UNDER) model %",
    "Prognoza v2", "P(OVER) v2 %", "P(UNDER) v2 %",
    "Minuty v2", "Próg OVER %", "Próg UNDER %",
    "Rynek bez marży OVER %", "Ostatnie 10 OVER", "Próba",
    "Status", "Uwaga", "Wariant v2",
]
MAX_IMAGE_BYTES = 8_000_000
MAX_IMAGE_PIXELS = 12_000_000
MARKERS = {"powyzej":"OVER", "ponizej":"UNDER", "over":"OVER",
           "under":"UNDER", "above":"OVER", "below":"UNDER"}


def ascii_word(word):
    v=unicodedata.normalize("NFKD", str(word or ""))
    return "".join(c for c in v if not unicodedata.combining(c)).lower().strip(" :!.")


def side_word(word):
    return MARKERS.get(ascii_word(word))


def parse_price(value):
    """Parse only recognizable decimal odds; don't treat a lone digit as odds."""
    s=str(value or "").replace(" ", "").replace(",", ".").strip(".,:")
    if re.fullmatch(r"[12]\d{2}", s):
        s=s[0]+"."+s[1:]
    if not re.fullmatch(r"\d{1,2}\.\d{2}",s):
        return None
    v=float(s)
    return round(v,2) if 1.01<=v<=15 else None


def parse_line(value):
    s=str(value or "").strip().replace(",", ".")
    if not re.fullmatch(r"\d{1,3}(?:\.\d{1,2})?",s):
        return None
    v=float(s)
    return v if 0.5<=v<=150 else None


def market_from_header(words, default="PTS"):
    header=ascii_word(" ".join(str(x) for x in words[:40]))
    if "pra" in header or (("punkty" in header or "point" in header) and
                            ("zbiork" in header or "rebound" in header) and
                            ("asyst" in header or "assist" in header)):
        return "PRA"
    if "zbiork" in header or "rebound" in header:
        return "REB"
    if "asyst" in header or "assist" in header:
        return "AST"
    if any(x in header for x in (
            "trojk","3-point","three point","3pt","3pm",
            "celnych rzutow za 3","rzutow za trzy",
            "3-punktowe","3 punkty","three pointers","triple made")):
        return "FG3M"
    return default if default in STAT_NAMES else "PTS"


def parse_ocr_tokens(raw, image_width, default_market="PTS"):
    """Rows from Tesseract image_to_data or synthetic tests.

    Each side has directional anchor text. Words are attached by bounding-box
    position, never by global OCR reading order alone. Unreadable odds stay NaN.
    """
    tokens=[]
    for item in raw:
        value=str(item.get("text") or "").strip()
        try:
            left=float(item["left"]); top=float(item["top"])
            width=float(item["width"]); height=float(item["height"])
            conf=float(item.get("conf",0))
        except (KeyError,TypeError,ValueError):
            continue
        if value and conf>=18 and width>0 and height>0:
            tokens.append({"text":value, "x":left+width/2,
                           "left":left,"y":top+height/2,
                           "conf":conf})
    markers=[t for t in tokens if side_word(t["text"])]
    if not markers:
        return pd.DataFrame(columns=EDIT_COLUMNS),{
            "detected":0,"unreadable_odds":0,
            "warning":"Nie znaleziono rozpoznawalnych linii Over/Under."}
    has_two_cols=(any(t["x"]<image_width*.48 for t in markers)
                  and any(t["x"]>image_width*.52 for t in markers))
    bounds=[(0.0,image_width*.5),(image_width*.5,float(image_width))] if has_two_cols else [(0.0,float(image_width))]
    market=market_from_header([t["text"] for t in sorted(tokens,key=lambda x:(x["y"],x["x"])) if t["y"]<min(m["y"] for m in markers)-18],default_market)
    extracted=[]
    for lo,hi in bounds:
        col=[t for t in tokens if lo<=t["x"]<hi]
        for anchor in [m for m in col if side_word(m["text"])]:
            # Keep an intentionally narrow vertical tolerance to avoid crossing
            # two bookmaker rows; odds sit above the text in common table layouts.
            near=[t for t in col if abs(t["y"]-anchor["y"])<=25]
            left_words=sorted([t for t in near if t["x"]<anchor["left"] and t["x"]<hi-100],
                              key=lambda t:t["x"])
            name=" ".join(t["text"] for t in left_words).strip()
            if not name or len(name)>85 or len(left_words)>8:
                continue
            trailing=sorted([t for t in near
                             if t["left"]>=anchor["left"] and t["x"]>anchor["x"]
                             and t["x"]<hi-(hi-lo)*.15],key=lambda t:t["x"])
            line=next((v for x in trailing if (v:=parse_line(x["text"])) is not None),None)
            if line is None:
                continue
            price_candidates=sorted(
                [t for t in near if t["x"]>hi-(hi-lo)*.2],
                key=lambda t:(abs(t["y"]-anchor["y"]),-t["conf"]))
            odds=next((o for x in price_candidates if (o:=parse_price(x["text"])) is not None),None)
            # Different props on the same screenshot are common. Prefer
            # market words on this VERY row over the general page header.
            # An unrecognized market inherits user-selected default and
            # still requires explicit review in the editing table.
            row_market=market_from_header(
                [t["text"] for t in sorted(near,key=lambda t:t["x"])],
                default=market)
            extracted.append({"name":name,"market":row_market,"line":line,
                              "side":side_word(anchor["text"]),"price":odds})
    combined={}
    for r in extracted:
        key=(norm_name(r["name"]),r["market"],r["line"])
        if not key[0]:
            continue
        if key not in combined:
            combined[key]={"Zawodnik":r["name"],"Rynek":r["market"],
                           "Linia":r["line"],"Kurs OVER":None,
                           "Kurs UNDER":None,"Weryfikacja OCR":"WYMAGA SPRAWDZENIA"}
        field="Kurs "+r["side"]
        if combined[key][field] is None:
            combined[key][field]=r["price"]
    df=pd.DataFrame(list(combined.values()),columns=EDIT_COLUMNS)
    missing=0 if df.empty else int(df[["Kurs OVER","Kurs UNDER"]].isna().sum().sum())
    return df,{"detected":len(df),"unreadable_odds":missing,
               "warning":("Rozpoznanie OCR jest orientacyjne. Sprawdź każdą nazwę, linię i kurs "
                          "na oryginalnym screenie; brakujący kurs uzupełnij ręcznie.")}


def read_screenshot(image_bytes, default_market="PTS"):
    """ONE local OCR call after explicit upload; no cloud vision/API requests."""
    if len(image_bytes)>MAX_IMAGE_BYTES:
        raise ValueError("Obraz jest za duży (limit 8 MB).")
    try:
        from io import BytesIO
        from PIL import Image
        import pytesseract
        with Image.open(BytesIO(image_bytes)) as im:
            if im.width*im.height>MAX_IMAGE_PIXELS:
                raise ValueError("Zbyt duża rozdzielczość obrazu (limit 12 MP).")
            picture=im.convert("RGB")
        picture.thumbnail((2200,2200))
        # Run Tesseract once, not once per player or each yellow quote badge.
        data=pytesseract.image_to_data(
            picture, lang="pol+eng", config="--psm 6",
            output_type=pytesseract.Output.DICT, timeout=18)
        items=[{k:data[k][idx] for k in ("text","conf","left","top","width","height")}
               for idx in range(len(data["text"]))]
        return parse_ocr_tokens(items,picture.width,default_market)
    except ImportError as exc:
        raise RuntimeError("Brak modułu OCR na serwerze. Wpisz wiersze ręcznie.") from exc
    except Exception as exc:
        if isinstance(exc,ValueError):
            raise
        raise RuntimeError("Rozpoznawanie tekstu niedostępne: "+str(exc)[:125]) from exc


def _valid_decimal(value):
    try:
        v=float(str(value).replace(",","."))
        return v if math.isfinite(v) else None
    except (TypeError,ValueError):
        return None


def batch_analyze(offers, logs, cutoff_utc=None, min_games=10):
    """Batch experimental PTS/REB/AST/3PM/PRA model, no new API calls.

    No probabilistic score if player cannot be matched EXACTLY, samples are
    insufficient, or a line is not a half-point (integer may cause refunds).
    Never claim a screenshot price is still current. One row per market/line.
    """
    if offers is None or offers.empty:
        return pd.DataFrame(columns=RESULT_COLUMNS)
    history=logs if isinstance(logs,pd.DataFrame) else pd.DataFrame()
    time=pd.to_datetime(cutoff_utc,errors="coerce",utc=True)
    if pd.isna(time):
        time=pd.Timestamp.now(tz="UTC")
    if not history.empty:
        expected={"PLAYER_NAME","TEAM_ABBREVIATION","GAME_DATE","MIN","PTS","REB","AST","FG3M"}
        if not expected.issubset(history.columns):
            history=pd.DataFrame()
        else:
            history=history.copy()
            history["GAME_DATE"]=pd.to_datetime(history["GAME_DATE"],errors="coerce",utc=True)
            history=history[history["GAME_DATE"]<time].sort_values("GAME_DATE")
    by_name={}
    if not history.empty:
        for name,g in history.groupby("PLAYER_NAME",sort=False):
            key=norm_name(name)
            by_name.setdefault(key,[]).append((str(name),g))
    output=[]
    for row in offers.to_dict("records"):
        name=str(row.get("Zawodnik") or "").strip()
        market=str(row.get("Rynek") or "PTS").upper().strip()
        line=parse_line(row.get("Linia"))
        over=_valid_decimal(row.get("Kurs OVER"))
        under=_valid_decimal(row.get("Kurs UNDER"))
        for odds in (over,under):
            if odds is not None and not 1.01<=odds<=15:
                raise ValueError("Kurs poza dozwolonym zakresem 1.01–15.")
        result={"Zawodnik":name,"Rynek":market,"Linia":line,
                "Kurs OVER":over,"Kurs UNDER":under,
                "Prognoza":None,"P(OVER) model %":None,
                "P(UNDER) model %":None,
                "Prognoza v2":None,"P(OVER) v2 %":None,
                "P(UNDER) v2 %":None,"Minuty v2":None,
                "Wariant v2":"BRAK DANYCH",
                "Próg OVER %":round(100/over,1) if over else None,
                "Próg UNDER %":round(100/under,1) if under else None,
                "Rynek bez marży OVER %":round(100*(1/over)/((1/over)+(1/under)),1)
                                          if over and under else None,
                "Ostatnie 10 OVER":None,"Próba":0,
                "Status":"WSTRZYMAJ","Uwaga":""}
        if not name or market not in STAT_NAMES or line is None:
            result["Uwaga"]="Nieprawidłowa nazwa, rynek albo linia.";output.append(result);continue
        if abs(line-round(line))<1e-9:
            result["Uwaga"]="Całkowita linia może dawać zwrot; model dwustanowy jej nie obsługuje."
            output.append(result);continue
        if over is None and under is None:
            result["Uwaga"]="Brak rozpoznanych kursów — popraw OCR."
            output.append(result);continue
        matches=by_name.get(norm_name(name),[])
        if len(matches)!=1:
            result["Uwaga"]="Brak dokładnego dopasowania zawodnika; popraw nazwę." if not matches else "Niejednoznaczny zawodnik."
            output.append(result);continue
        _,g=matches[0]
        # A traded player's old-team games should not be mixed with a new
        # team's role unless a validated transfer-aware model is available.
        team=str(g.iloc[-1]["TEAM_ABBREVIATION"])
        sub=g[g["TEAM_ABBREVIATION"]==team].copy()
        if market not in sub:
            result["Uwaga"]="Brak kolumny statystyk dla tego rynku."
            output.append(result);continue
        sub=sub[(pd.to_numeric(sub["MIN"],errors="coerce")>2) &
                pd.to_numeric(sub[market],errors="coerce").notna()]
        n=len(sub)
        result["Próba"]=n
        if n<min_games:
            result["Uwaga"]=f"Tylko {n} występów aktualnego klubu (minimum {min_games})."
            output.append(result);continue
        last=sub["GAME_DATE"].max()
        if pd.notna(last) and (time-last).days>30:
            result["Uwaga"]="Dane zawodnika starsze niż 30 dni."
            output.append(result);continue
        try:
            pred=calc_projection(sub,market)
            p=prop_probability(pred,line,"OVER")
            result.update({"Prognoza":round(float(pred["prediction"]),1),
                           "P(OVER) model %":round(100*p,1),
                           "P(UNDER) model %":round(100*(1-p),1),
                           "Ostatnie 10 OVER":f"{int((sub[market].tail(10)>line).sum())}/{min(10,n)}",
                           "Status":"MODEL TESTOWY",
                           "Uwaga":"Niezweryfikowane prawdopodobieństwo; brak matchupu i potwierdzenia daty/aktywności."})
            # Candidate 2.0 is displayed side-by-side, NEVER substituted for
            # the current production percentage unless later validated.
            try:
                v2=forecast_v2(sub,market,line,time,min_games=max(10,min_games),
                               draws=2048)
                result.update({"Prognoza v2":round(v2["mean"],1),
                               "P(OVER) v2 %":round(100*v2["p_over"],1),
                               "P(UNDER) v2 %":round(100*v2["p_under"],1),
                               "Minuty v2":v2["minutes"],
                               "Wariant v2":"BADAWCZY, NIEKALIBROWANY"})
            except (ValueError,TypeError,KeyError,OverflowError) as exc:
                result["Wariant v2"]="WSTRZYMANY: "+str(exc)[:90]
        except (ValueError,TypeError,KeyError,ZeroDivisionError) as exc:
            result["Uwaga"]="Brak możliwej do zweryfikowania projekcji: "+str(exc)[:100]
        output.append(result)
    return pd.DataFrame(output,columns=RESULT_COLUMNS)
