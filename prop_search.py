"""Natural-language NBA player prop search, independent of Streamlit/network.

Examples:
  'Jayson Tatum over 25.5 points'
  'Jason Tatum uver 25,5 point'
  'Jayson Tatum under 3.5 assists'
  'Jayson Tatum over 2.5 three point'
  'Jayson Tatum over 7.5 rebounds'

Always require verification before querying; fuzzy athlete matching is only
a suggestion, never an automatic substitution that can produce a wrong bet.
"""
from __future__ import annotations

from difflib import SequenceMatcher
import math
import re
import unicodedata


def plain(value):
    s=unicodedata.normalize("NFKD",str(value or "").lower())
    s="".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.strip().split())


SIDES={
    "over":"OVER","uver":"OVER","above":"OVER","powyzej":"OVER",
    "ponad":"OVER","overem":"OVER",
    "under":"UNDER","below":"UNDER","ponizej":"UNDER",
    "ponize":"UNDER","nizej":"UNDER",
}

MARKET_PATTERNS=[
    ("PRA", r"\b(?:pra|p\s*\+\s*r\s*\+\s*a|"
            r"points?\s*[+/]\s*rebounds?\s*[+/]\s*assists?|"
            r"pts?\s*[+/]\s*reb?\s*[+/]\s*ast?|"
            r"punkty\s*\+\s*zbiorki\s*\+\s*asysty|"
            r"punktow\s*\+\s*zbiorek\s*\+\s*asyst|"
            r"punkty\s*,\s*zbiorki\s+i\s+asysty|"
            r"points?\s+rebounds?\s+assists?)\b"),
    ("FG3M",r"\b(?:3\s*(?:pt|pm|pointers?)|three[\s-]*pointers?|three[\s-]*points?|"
             r"triples?|trojki|trojek|celne?\s+rzuty?\s+za\s+3|"
             r"rzuty?\s+za\s+trzy|3\s*punktow(?:e|ych)?)\b"),
    ("AST",r"\b(?:assists?|asists?|asist(?:s|y|ow)?|ast|asysty|asyst)\b"),
    ("REB",r"\b(?:rebounds?|rebunds?|rebs?|zbiorki|zbiorek)\b"),
    ("PTS",r"\b(?:points?|pts?|punkty|punktow|punkt|pkt)\b"),
]

SIDE_RE = re.compile(r"\b("+ "|".join(map(re.escape, SIDES)) + r")\b",re.I)
LINE_RE = re.compile(r"(?<![A-Za-z0-9])(\d{1,3}(?:[.,]\d{1,2})?)(?![A-Za-z0-9])")


def parse_prop_query(text):
    """Parse a single athlete, market, direction and line or raise ValueError."""
    raw=" ".join(str(text or "").strip().split())
    if len(raw)>170:
        raise ValueError("Wpis jest zbyt długi (maksymalnie 170 znaków).")
    normalized=plain(raw)
    direction=SIDE_RE.search(normalized)
    if not direction:
        raise ValueError("Podaj OVER/UNDER lub powyżej/poniżej.")
    before=normalized[:direction.start()].strip(" -:,.")
    after=normalized[direction.end():].strip()
    match=LINE_RE.search(after)
    if not match:
        raise ValueError("Brak linii, np. 25,5.")
    try:
        line=float(match.group(1).replace(",","."))
    except ValueError as exc:
        raise ValueError("Błędna linia.") from exc
    if not math.isfinite(line) or line<.5 or line>150:
        raise ValueError("Linia musi być między 0,5 a 150.")
    if not before or len(before)<3:
        raise ValueError("Wpisz imię i nazwisko zawodnika przed OVER/UNDER.")
    # Sport markets must come after the line: prevents 'three point' from
    # being interpreted as just POINTS. If multiple match, prefer PRA > 3PM.
    tail=after[match.end():].strip(" -:,./")
    detected=[market for market,pattern in MARKET_PATTERNS
              if re.search(pattern,tail,re.I)]
    if not detected:
        raise ValueError(
            "Podaj rynek: PTS, REB, AST, 3PM lub PRA (punkty + zbiórki + asysty).")
    chosen=detected[0]
    return {
        "name_input":before,
        "side":SIDES[direction.group(1).lower()],
        "line":line,
        "market":chosen,
        "raw":raw,
    }


def parse_prop_batch(text, max_items=12):
    """Parse line/semicolon-separated market descriptions, preserving errors."""
    rows=re.split(r"[\n;]+",str(text or ""))
    cleaned=[line.strip() for line in rows if line.strip()]
    if len(cleaned)>max_items:
        raise ValueError(f"Maksymalnie {max_items} zdarzeń jednocześnie.")
    valid=[];errors=[]
    for index,item in enumerate(cleaned,1):
        try:
            valid.append(parse_prop_query(item))
        except ValueError as exc:
            errors.append(f"Wiersz {index}: {str(exc)}")
    return valid,errors


def resolve_catalog_player(candidate, catalog):
    """Suggest canonical ESPN catalog identity. Require manual confirmation.

    Return {name,team,id,confidence,quality}; ambiguous unknown never mapped.
    A unique typo like 'Jason Tatum' may resolve to 'Jayson Tatum' for review.
    """
    from core import norm_name
    if catalog is None or getattr(catalog,"empty",True):
        return {"name":candidate,"quality":"no_catalog",
                "confidence":0.,"id":None,"team":""}
    key=norm_name(candidate)
    rows=catalog.to_dict("records")
    exact=[r for r in rows if norm_name(r.get("PLAYER_NAME",""))==key]
    if len(exact)==1:
        r=exact[0]
        return {"name":str(r["PLAYER_NAME"]),
                "team":str(r.get("TEAM_ABBREVIATION") or ""),
                "id":str(r.get("PLAYER_ID") or ""),
                "confidence":1.,"quality":"exact"}
    if len(exact)>1:
        return {"name":candidate,"quality":"ambiguous",
                "confidence":1.,"id":None,"team":""}
    scored=sorted([
        (SequenceMatcher(None,key,norm_name(r.get("PLAYER_NAME",""))).ratio(),
         str(r.get("PLAYER_NAME") or ""),r)
        for r in rows if r.get("PLAYER_NAME")
    ],key=lambda x:(-x[0],x[1]))
    if not scored:
        return {"name":candidate,"quality":"unknown",
                "confidence":0.,"id":None,"team":""}
    best=scored[0]
    next_score=scored[1][0] if len(scored)>1 else 0.
    if best[0]>=.87 and best[0]-next_score>=.05:
        r=best[2]
        return {"name":str(r["PLAYER_NAME"]),
                "team":str(r.get("TEAM_ABBREVIATION") or ""),
                "id":str(r.get("PLAYER_ID") or ""),
                "confidence":round(best[0],3),"quality":"suggested"}
    return {"name":candidate,"quality":"unknown",
            "confidence":round(best[0],3),"id":None,"team":""}
