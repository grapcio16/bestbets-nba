"""Read the latest public, official NBA injury-report PDF (availability facts).

The NBA report is independent of ESPN. Parse strictly bounded PDF column
positions and keep only the selected game date / matchup / named teams.
Ambiguous extraction returns no statuses rather than inventing an injury.
No raw NBA PDF, logos, notes or detailed reasons are redistributed to clients.
Access/redistribution rights must be reviewed before paid commercial scale.
"""
from __future__ import annotations

import io
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from teams import TEAM_MAP

REPORT_PAGE = "https://www.nba.com/players/injury-report"
PDF_HOST = "https://ak-static.cms.nba.com/referee/injury/"
REPORT_PATTERN = re.compile(
    r"Injury-Report_(\d{4}-\d{2}-\d{2})_(\d{2})_(\d{2})(AM|PM)\.pdf",
    re.I)
URL_PATTERN = re.compile(
    r"(?:https?:)?//ak-static\.cms\.nba\.com/referee/injury/"
    r"Injury-Report_\d{4}-\d{2}-\d{2}_\d{2}_\d{2}(?:AM|PM)\.pdf",
    re.I)
GAME_PATTERN = re.compile(r"\b[A-Z]{2,3}@[A-Z]{2,3}\b")
DATE_PATTERN = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
VALID_STATUSES = frozenset({"Out", "Doubtful", "Questionable",
                            "Probable", "Available"})
US_EAST = ZoneInfo("America/New_York")


def latest_report_url(html: str, *, now=None):
    """Latest published PDF, based on its own ET timestamp, never download time."""
    moment = (pd.to_datetime(now, utc=True, errors="coerce") if now is not None
              else pd.Timestamp.now(tz="UTC"))
    if pd.isna(moment) or not isinstance(html, str):
        return None
    best = None
    for raw in URL_PATTERN.findall(html.replace("&amp;", "&")):
        url = "https:" + raw if raw.startswith("//") else raw
        m = REPORT_PATTERN.search(url)
        if not m:
            continue
        try:
            reported = datetime.strptime(
                f"{m.group(1)} {m.group(2)}:{m.group(3)}{m.group(4).upper()}",
                "%Y-%m-%d %I:%M%p").replace(tzinfo=US_EAST)
            stamp = pd.Timestamp(reported).tz_convert("UTC")
        except (ValueError, TypeError):
            continue
        age = (moment - stamp).total_seconds()
        # The NBA updates roughly every fifteen minutes. An older PDF can
        # contain outdated medical decisions. Do not trust it after 2h.
        if age < 0 or age > 90 * 60:
            continue
        if best is None or stamp > best[0]:
            best = (stamp, url)
    return best


def _line_groups(words):
    """Group PDF words by physical baseline before splitting into columns."""
    groups = []
    for word in sorted(words, key=lambda w: (float(w.get("top", 0)),
                                              float(w.get("x0", 0)))):
        try:
            top = float(word["top"])
            x = float(word["x0"])
            label = str(word["text"])
        except (TypeError, ValueError, KeyError):
            continue
        if not label.strip():
            continue
        if not groups or abs(groups[-1][0] - top) > 2.8:
            groups.append((top, [(x, label)]))
        else:
            groups[-1][1].append((x, label))
    for _, row in groups:
        yield sorted(row, key=lambda w: w[0])


def _column(row, width, low, high):
    return " ".join(token for x, token in row
                    if low <= x / width < high).strip()


def parse_official_word_pages(pages):
    """Yield named injury rows from (page_width, extract_words()) tuples.

    NBA PDF has stable column boundaries: matchup x=.235, team=.313,
    player=.504, status=.697 of page width. Check both team and matchup on
    every row; never assign a player across a changed game.
    """
    current_date, matchup, team = "", "", ""
    rows = []
    for width, words in pages:
        if not isinstance(width, (int, float)) or width <= 0:
            continue
        for row in _line_groups(words):
            text = " ".join(w for _, w in row)
            if "Game Date" in text or "Injury Report:" in text:
                continue
            day = DATE_PATTERN.search(_column(row, width, 0, .14))
            match = GAME_PATTERN.search(_column(row, width, .225, .315))
            named_team = _column(row, width, .31, .502)
            if day:
                current_date = day.group(0)
            if match:
                matchup = match.group(0)
                team = ""  # Never carry old team across fixture boundaries.
            code = TEAM_MAP.get(named_team)
            if code:
                team = code
            player_name = _column(row, width, .5, .69)
            status_field = _column(row, width, .69, .79)
            status = next((s for s in VALID_STATUSES
                           if re.search(r"(?<![A-Za-z])"+s+r"(?![A-Za-z])",
                                        status_field, flags=re.I)), "")
            if not player_name or not status or not team or not matchup or not current_date:
                continue
            # Official PDF writes "Lastname, Firstname"; ESPN projections use
            # "Firstname Lastname". Do not infer identities from team alone.
            if "," not in player_name:
                continue
            surname, given = player_name.split(",", 1)
            given, surname = given.strip(), surname.strip()
            if not given or not surname or len(given)+len(surname) > 75:
                continue
            rows.append({"game_date": current_date, "matchup": matchup,
                         "team": team, "player": given+" "+surname,
                         "status": status, "athlete_id": "", "note": "",
                         "source": "NBA oficjalny raport"})
    return rows


def selected_official_injury_rows(away: str, home: str, tipoff, *,
                                  now=None, get=None):
    """(DataFrame, metadata) for a single verified future matchup.

    Any HTML/PDF parser ambiguity is a recoverable provider failure. Never
    use an old report for tomorrow's game or a different opponent.
    """
    if get is None:
        get = requests.get
    start = pd.to_datetime(tipoff, utc=True, errors="coerce")
    now_time = (pd.to_datetime(now, utc=True, errors="coerce") if now is not None
                else pd.Timestamp.now(tz="UTC"))
    if pd.isna(start) or pd.isna(now_time) or start <= now_time:
        return pd.DataFrame(), {"available": False, "source": "NBA",
                                "reason": "Mecz już rozpoczęty lub brak terminu"}
    wanted = f"{str(away).upper()}@{str(home).upper()}"
    game_date = start.tz_convert(US_EAST).strftime("%m/%d/%Y")
    try:
        page = get(REPORT_PAGE, timeout=7,
                   headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"})
        page.raise_for_status()
        found = latest_report_url(page.text, now=now_time)
        if found is None:
            raise ValueError("No recent official NBA injury PDF")
        stamp, url = found
        binary = get(url, timeout=9, headers={"User-Agent": "Mozilla/5.0",
                                              "Accept": "application/pdf"})
        binary.raise_for_status()
        content = binary.content
        if not content.startswith(b"%PDF") or len(content) > 9_000_000:
            raise ValueError("Not a bounded NBA PDF")
        import pdfplumber
        with pdfplumber.open(io.BytesIO(content)) as document:
            if not (1 <= len(document.pages) <= 20):
                raise ValueError("Unexpected number of NBA PDF pages")
            pages = [(float(p.width), p.extract_words()) for p in document.pages]
        rows = parse_official_word_pages(pages)
        selected = [r for r in rows if r["matchup"] == wanted
                    and r["game_date"] == game_date
                    and r["team"] in {away, home}]
        # A PDF without selected fixture statuses may still be valid, but
        # cannot certify any athlete as healthy. Keep ESPN / conditional UX.
        if not selected:
            return pd.DataFrame(), {"available": False, "source": "NBA",
                                    "timestamp": stamp.isoformat(),
                                    "reason": "Brak wpisów dla wybranego meczu"}
        frame = pd.DataFrame(selected)
        return frame, {"available": True, "stale": False,
                       "source": "NBA oficjalny raport",
                       "timestamp": stamp.isoformat(),
                       "coverage_teams": sorted(set(frame["team"]))}
    except (OSError, RuntimeError, ValueError, TypeError, KeyError,
            requests.RequestException, ImportError) as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Official NBA injury source unavailable: %s", type(exc).__name__)
        return pd.DataFrame(), {"available": False, "source": "NBA",
                                "reason": "Nie udało się zweryfikować raportu NBA"}
