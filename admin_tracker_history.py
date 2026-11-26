"""Read-only detailed tracker archive for the private administrator dashboard."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from math import isfinite
from collections import Counter, defaultdict
from admin_live_data import _read

TZ = ZoneInfo("Europe/Warsaw")
MAX_ROWS = 5000
MAX_DAYS = 31
KINDS = {"games":"Mecze", "players":"Zawodnicy", "quarters":"Kwarty"}
STATS = {"PTS":("pts_pred","pts_actual"), "REB":("reb_pred","reb_actual"),
         "AST":("ast_pred","ast_actual"), "3PM":("fg3m_pred","fg3m_actual"),
         "MIN":("minutes_pred","minutes_actual")}

# Fixed SQL only, bound parameters. Source rows are preserved, not recalculated.
SQL = {
    "games": """SELECT * FROM (
        SELECT game_id,model_id,start_utc,forecast_time_utc AS issued,settled_at_utc AS settled,
        away,home,away_points AS pred_away,home_points AS pred_home,
        away_score AS actual_away,home_score AS actual_home,home_win_pct,
        NULL::integer AS scenario_away,NULL::integer AS scenario_home
        FROM bestbets_forecasts_by_model WHERE season=%s AND start_utc >= %s AND start_utc < %s
        UNION ALL
        SELECT game_id,model_id,start_utc,issued_at AS issued,settled_at AS settled,
        away,home,mean_away AS pred_away,mean_home AS pred_home,
        actual_away,actual_home,home_win_pct,scenario_away,scenario_home
        FROM hoopzaro_v8_shadow_forecasts WHERE season=%s AND start_utc >= %s AND start_utc < %s
    ) AS forecasts ORDER BY start_utc DESC,game_id,model_id LIMIT 5001""",
    "players": """SELECT game_id,model_id,start_utc,forecast_time_utc AS issued,settled_at_utc AS settled,
        player_id,player_name,team,pts_pred,pts_actual,reb_pred,reb_actual,ast_pred,ast_actual,
        fg3m_pred,fg3m_actual,minutes_pred,minutes_actual
        FROM bestbets_player_forecasts WHERE season=%s AND start_utc >= %s AND start_utc < %s
        ORDER BY start_utc DESC,game_id,player_name,player_id,model_id LIMIT 5001""",
    "quarters": """SELECT game_id,model_id,start_utc,forecast_time_utc AS issued,settled_at_utc AS settled,
        away,home,quarter,away_points AS pred_away,home_points AS pred_home,
        away_actual AS actual_away,home_actual AS actual_home,home_win_pct
        FROM bestbets_quarter_forecasts WHERE season=%s AND start_utc >= %s AND start_utc < %s
        ORDER BY start_utc DESC,game_id,quarter,model_id LIMIT 5001""",
}

def read_history(url, season, kind, start, end):
    from access_control import current_role
    if current_role() != "admin":
        return {"status":"denied"}
    if (kind not in SQL or type(start) is not date or type(end) is not date
            or not 0 <= (end-start).days < MAX_DAYS):
        return {"status":"invalid_range"}
    lower = datetime.combine(start,time.min,TZ).astimezone(timezone.utc)
    upper = datetime.combine(end+timedelta(days=1),time.min,TZ).astimezone(timezone.utc)
    params = (season,lower,upper)
    result = _read(url,[("rows",SQL[kind],params*2 if kind=="games" else params)])
    if result.get("status") == "ok" and len(result["rows"]) > MAX_ROWS:
        return {"status":"too_many"}
    return result

def finite(value):
    try:
        return isfinite(float(value))
    except (TypeError,ValueError,OverflowError):
        return False

def values(row,kind,stat="PTS"):
    if kind=="players":
        pred,actual=STATS[stat]
        return (row.get(pred),),(row.get(actual),)
    return (row.get("pred_away"),row.get("pred_home")),(row.get("actual_away"),row.get("actual_home"))

def classify(row,kind,stat="PTS",now=None):
    now=now or datetime.now(timezone.utc)
    issued,start,settled=row.get("issued"),row.get("start_utc"),row.get("settled")
    # Match the prospective evaluation cutoff for games; other archives
    # use the existing tracker pre-tipoff criterion.
    cutoff=timedelta(minutes=15) if kind=="games" else timedelta(0)
    if not issued or not start or issued>=start-cutoff:
        return "excluded"
    predicted,actual=values(row,kind,stat)
    if not all(finite(v) and float(v)>=0 for v in predicted):
        return "excluded"
    if not settled:
        return "upcoming" if start>now else "waiting"
    if settled<start or not all(finite(v) and float(v)>=0 for v in actual):
        return "excluded"
    if kind=="games" and (actual[0]==actual[1] or not all(50<=float(v)<=200 for v in (*predicted,*actual))):
        return "excluded"
    return "settled"

def error_value(row,kind,stat="PTS"):
    p,a=values(row,kind,stat)
    return sum(abs(float(x)-float(y)) for x,y in zip(p,a))/len(p)

def summarize(rows,kind,stat="PTS",now=None):
    counts=Counter()
    errors=[]
    daily=defaultdict(list)
    for row in rows:
        state=classify(row,kind,stat,now)
        counts[state]+=1
        if state=="settled":
            err=error_value(row,kind,stat)
            errors.append(err)
            daily[row["start_utc"].astimezone(TZ).date()].append(err)
    return {"total":len(rows),"settled":counts["settled"],"waiting":counts["waiting"],
            "upcoming":counts["upcoming"],"excluded":counts["excluded"],
            "mae":sum(errors)/len(errors) if errors else None,
            "daily":[{"Data":d,"Średni błąd":sum(v)/len(v),"Prognozy":len(v)} for d,v in sorted(daily.items())]}
