"""One-page, model-grounded HOOPZARO Flow report. No external feed or request."""
from __future__ import annotations

from io import BytesIO
import math
import unicodedata


def _label(value, limit=145):
    # Portable PDF standard fonts require WinAnsi-safe text. The UI retains
    # original Polish text; only the downloadable printable document uses
    # ASCII transliteration rather than displaying missing-glyph squares.
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if ord(ch) < 128 and ch.isprintable())[:limit]


def _num(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def build_flow_pdf(*, day: str, game_id: str, model_id: str,
                   away: str, home: str, stats: dict, flow: dict,
                   variant: str) -> bytes:
    """Create an export only from server-held, entitlement-checked snapshots."""
    if not isinstance(flow, dict) or flow.get("available") is not True or flow.get("n_sims") != 5000:
        raise ValueError("No verified 5000-result flow")
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.pagesizes import landscape, A4

    buf = BytesIO()
    w, h = landscape(A4)
    c = Canvas(buf, pagesize=(w, h), pageCompression=1)
    navy, blue, cyan, violet = "#08172f", "#10244b", "#34edf7", "#c277f8"
    white, muted = "#f0faff", "#b4c7e6"
    c.setFillColor(navy);c.rect(0, 0, w, h, fill=1, stroke=0)
    c.setFillColor(blue);c.roundRect(28, h-104, w-56, 78, 12, fill=1, stroke=0)
    c.setFillColor(cyan);c.setFont("Helvetica-Bold", 23)
    c.drawString(44, h-57, "HOOPZARO  /  FLOW MECZU")
    c.setFillColor(white);c.setFont("Helvetica-Bold", 13)
    c.drawString(44, h-82, _label(f"{away} vs {home}  |  {day}  |  {model_id}", 98))
    c.setFillColor(violet);c.setFont("Helvetica-Bold", 10)
    c.drawRightString(w-44, h-58, _label(variant.upper()))
    c.setFillColor(muted);c.setFont("Helvetica", 9)
    c.drawRightString(w-44, h-82, "5 000 losowan koncowego wyniku")
    c.setFillColor(white);c.setFont("Helvetica-Bold", 15)
    aw, ho = _num(stats.get("away_points")), _num(stats.get("home_points"))
    c.drawString(45, h-133, "Srednia koncowa:")
    c.setFillColor(cyan);c.drawString(190, h-133, f"{away} {aw:.1f}" if aw is not None else "--")
    c.setFillColor(violet);c.drawString(292, h-133, f"{home} {ho:.1f}" if ho is not None else "--")
    c.setFillColor(muted);c.setFont("Helvetica", 8)
    c.drawString(45, h-150, "Nie jest to wynik na zywo, prognoza kwart ani rzeczywiste play-by-play.")

    # Plot the conditional mean differential with clearly separated period ticks.
    area = (54, 221, 466, 177)
    x0, y0, pw, ph = area
    c.setFillColor(blue);c.roundRect(x0-12, y0-14, pw+24, ph+25, 10, fill=1, stroke=0)
    c.setFillColor(white);c.setFont("Helvetica-Bold", 12)
    c.drawString(x0, y0+ph-2, "Warunkowy przebieg przewagi")
    rows = flow.get("timeline", [])
    values = [_num(r.get("margin_mean")) for r in rows if isinstance(r, dict)]
    values = [v for v in values if v is not None]
    limit = max(5, max([abs(v) for v in values]+[0])*1.25)
    graph_y = y0+19;graph_h=ph-48
    c.setStrokeColor("#415e88");c.setLineWidth(.6)
    for i in range(5):
        y=graph_y+graph_h*i/4
        c.line(x0,y,x0+pw,y)
    c.setStrokeColor("#8098ba")
    for minute in (0,12,24,36,48):
        x=x0+pw*minute/48
        c.line(x,graph_y,x,graph_y+graph_h)
        c.setFont("Helvetica", 8);c.setFillColor(muted)
        c.drawCentredString(x,graph_y-12,str(minute)+"m")
    quarter_proof = isinstance(flow.get("quarter_model"), dict) and (
        flow["quarter_model"].get("available") is True)
    if quarter_proof and len(rows)==9 and len(values)==9:
        c.setStrokeColor(cyan);c.setLineWidth(2.5)
        def pt(i):
            return (x0+pw*i/8, graph_y+graph_h/2 + float(values[i])/(2*limit)*graph_h)
        for i in range(8):c.line(*pt(i),*pt(i+1))
    c.setFillColor(muted);c.setFont("Helvetica", 8)
    c.drawString(x0, y0-29, _label(
        "Srednia przewaga 5000 wynikow i historyczne Q1-Q4 ESPN; bez PBP."
        if quarter_proof else "Brak historycznych Q1-Q4 ESPN. Brak prognozy kwart."
    ))

    # Four conditional quarter summaries: outscoring, not final-game win odds.
    qx=548
    c.setFillColor(white);c.setFont("Helvetica-Bold", 12)
    c.drawString(qx, y0+ph-2, "Kwartalne udzialy (%)")
    c.setFont("Helvetica", 9)
    for i,row in enumerate((flow.get("quarters") or [])[:4]):
        if not isinstance(row,dict):continue
        y=y0+ph-29-i*30
        a,b,t=(_num(row.get(k)) for k in
               ("away_outscores_pct","home_outscores_pct","tie_pct"))
        if a is None or b is None or t is None:continue
        c.setFillColor(cyan);c.drawString(qx,y,f"Q{i+1}  {away}: {a:.1f}%")
        c.setFillColor(violet);c.drawString(qx+130,y,f"{home}: {b:.1f}%")
        c.setFillColor(muted);c.drawString(qx,y-12,f"Remis kwarty: {t:.1f}%")
    c.setFillColor(blue);c.roundRect(43, 59, w-86, 118, 10, fill=1, stroke=0)
    c.setFillColor(cyan);c.setFont("Helvetica-Bold", 11)
    c.drawString(58, 153, "METODOLOGIA I OGRANICZENIA")
    c.setFillColor(white);c.setFont("Helvetica", 9)
    descriptions = [
        "Rekonstrukcja warunkowa z tych samych 5000 koncowych losowan Monte Carlo.",
        ("Q1-Q4 bazuja na historycznych zdobytych i straconych punktach ESPN."
         if quarter_proof else
         "Brak danych ESPN Q1-Q4. Nie przedstawiamy sztucznych wynikow kwart."),
        "Model kwart eksperymentalny, niekalibrowany. Odcinki 6-min sa ilustracyjne.",
        "Brak zweryfikowanych rotacji, scoring runs, historycznych kursow i przewidywania wyniku live.",
        "Ewentualna dogrywka z koncowego wyniku jest umownie rozlozona na 48 minut.",
    ]
    for i,line in enumerate(descriptions):
        c.drawString(58, 135-i*15, _label(line))
    c.setFillColor(muted);c.setFont("Helvetica", 8)
    c.drawString(45, 30, _label("HOOPZARO | wynik symulacji, nie rekomendacja bukmacherska"))
    c.drawRightString(w-45, 30, _label("Game ID "+game_id))
    c.showPage();c.save()
    return buf.getvalue()
