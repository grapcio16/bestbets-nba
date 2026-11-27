"""Disposable local SQLite archive for research forecasts, never production Neon."""
from hashlib import sha256
import json
import sqlite3
import pandas as pd

from player_intelligence.rotation import LEAD, _time

SCHEMA = """
CREATE TABLE IF NOT EXISTS player_research_forecast (
  model_id TEXT NOT NULL,
  game_id TEXT NOT NULL,
  team TEXT NOT NULL,
  scenario_id TEXT NOT NULL,
  issued_at TEXT NOT NULL,
  record_sha256 TEXT NOT NULL,
  payload TEXT NOT NULL,
  PRIMARY KEY(model_id, game_id, team)
);
CREATE TRIGGER IF NOT EXISTS player_research_no_update
BEFORE UPDATE ON player_research_forecast
BEGIN SELECT RAISE(ABORT, 'immutable forecast'); END;
CREATE TRIGGER IF NOT EXISTS player_research_no_delete
BEFORE DELETE ON player_research_forecast
BEGIN SELECT RAISE(ABORT, 'immutable forecast'); END;
"""


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)


class ResearchArchive:
    """Explicit local path or :memory:, immutable first team/model/game.

    No production connector, remote URL, schema migration or settlement write.
    Clock injection is for isolated tests; live archive time is current UTC.
    """
    def __init__(self,path=":memory:",*,clock=None):
        if not isinstance(path,str) or not path or "://" in path or path.startswith("file:"):
            raise ValueError("local SQLite file only")
        self.db=sqlite3.connect(path)
        self.db.executescript(SCHEMA)
        self.clock=clock or (lambda:pd.Timestamp.now(tz="UTC"))

    def close(self):
        self.db.close()

    def append_batch(self,records):
        records=list(records)
        now=_time(self.clock())
        prepared=[]
        keys=set()
        for record in records:
            payload=dict(record)
            digest=payload.pop("record_sha256",None)
            if digest!=sha256(_canonical(payload).encode()).hexdigest():
                raise ValueError("record integrity mismatch")
            if payload.get("evidence_mode")!="prospective":
                raise ValueError("only prospective forecasts may be archived")
            p=payload["projection"]
            issued,tip,model_clock=(_time(payload["issued_at"]),_time(payload["start_utc"]),_time(p["asof"]))
            if not model_clock<=issued<=now<tip-LEAD or now-issued>pd.Timedelta(minutes=2):
                raise ValueError("expired or backdated archive")
            if p.get("status")!="shadow_conditional":
                raise ValueError("unresolved projection cannot be archived")
            key=(p["model_id"],p["game_id"],p["team"])
            if any(not isinstance(k,str) or not k for k in key) or key in keys:
                raise ValueError("duplicate or invalid batch identity")
            keys.add(key)
            scenario=payload["scenario_id"]
            if not isinstance(scenario,str) or not scenario:
                raise ValueError("scenario identity required")
            prepared.append((*key,scenario,issued.isoformat(),digest,_canonical(record)))
        inserted=0
        # Check real clock again inside the transaction, before each insert.
        with self.db:
            for row,record in zip(prepared,records):
                current=_time(self.clock())
                if not _time(record["issued_at"])<=current<_time(record["start_utc"])-LEAD or current-_time(record["issued_at"])>pd.Timedelta(minutes=2):
                    raise ValueError("archive deadline passed during batch")
                cur=self.db.execute(
                    "INSERT INTO player_research_forecast VALUES (?,?,?,?,?,?,?) ON CONFLICT(model_id,game_id,team) DO NOTHING",row)
                inserted+=cur.rowcount
        return inserted

    def records(self):
        result=[]
        for digest,payload in self.db.execute(
                "SELECT record_sha256,payload FROM player_research_forecast ORDER BY game_id,team,model_id"):
            r=json.loads(payload)
            body=dict(r)
            if body.pop("record_sha256",None)!=digest or sha256(_canonical(body).encode()).hexdigest()!=digest:
                raise ValueError("stored record integrity mismatch")
            result.append(r)
        return result
