"""Screenshot-matched Player Simulations, real-history semantics, guest gate.

All player names/statistics here are synthetic and never displayed live.
"""
from pathlib import Path
from shutil import which

from playwright.sync_api import sync_playwright

PAGE = (Path(__file__).parent / "bestbets_reference_frontend" / "index.html").as_uri()
OUT = Path("test-results/hoopzaro-responsive")
OUT.mkdir(parents=True, exist_ok=True)


def main():
    with sync_playwright() as p:
        executable = which("chromium") or which("google-chrome")
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"],
                                    **({"executable_path": executable} if executable else {}))
        for width, height in ((1672, 941), (390, 844)):
            page = browser.new_page(viewport={"width": width, "height": height},
                                    device_scale_factor=1)
            page.clock.set_fixed_time("2026-11-21T12:00:00Z")
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(PAGE, wait_until="load")
            mobile = page.locator('#hz-mobile-nav [data-page="simulations"]')
            if mobile.is_visible():
                mobile.click()
            else:
                page.locator('.nav-btn[data-page="simulations"]').click()
            day, game_id = "2026-11-23", "401999600"
            history = [
                {"date": "2026-11-%02d" % (i + 3),
                 "pts": float(18+i), "reb": float(3+i%2),
                 "ast": float(5+i%3), "pra": float(26+i+i%2+i%3),
                 "min": float(29+i%4)}
                for i in range(15)
            ]
            phi_logo = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGN8ZhPFwMDAxMDAwMDAAAAShgGAryh2VAAAAABJRU5ErkJggg=="
            mil_logo = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGOU29nAwMDAxMDAwMDAAAAP3AFbBNdn1AAAAABJRU5ErkJggg=="
            payload = {
                "brand": "", "auth": {"role": "premium"},
                "home": {"calendar_today": day, "calendar_loaded_days": [day],
                         "team_logos": {"PHI": phi_logo, "MIL": mil_logo},
                         "calendar_games": [
                             {"id": game_id, "day": day, "away": "MIL",
                              "home": "PHI", "state": "scheduled",
                              "away_logo": "team-logo:MIL",
                              "home_logo": "team-logo:PHI",
                              "start": "2026-11-23T02:00:00Z"}]},
                "premium_simulation": {
                    "entitled": True,
                    "game": {
                        "date": day, "game_id": game_id, "model_id": "research_form_v74",
                        "away_points": 111.0, "home_points": 120.0,
                        "total_points": 231.0, "away_win_pct": 28.6,
                        "home_win_pct": 71.4, "distributions": {},
                        "n_sims": 5000,
                        "model_context": {
                            "score_sd_samples": [19, 20],
                            "score_sd_points": [11.6, 12.9],
                            "rest_days": [1, 0],
                            "team_comparison": {},
                        },
                    },
                    "players": {
                        "date": day, "game_id": game_id, "model_id": "research_form_v74",
                        "home": "PHI", "players": [
                            {"name": "Test Guard Alpha", "team": "PHI",
                             "pts": 20, "reb": 2.4, "ast": 6.5,
                             "position": "PG", "espn_id": "",
                             "history": history,
                             "season_team_mean": {"pts": 25.0, "reb": 3.47,
                                                  "ast": 5.93, "pra": 34.4},
                             "season_team_games": 15},
                            {"name": "Test Forward Beta", "team": "MIL",
                             "pts": 17, "reb": 7.5, "ast": 3.2,
                             "espn_id": "", "history": []},
                        ],
                    },
                },
            }
            def push():
                page.evaluate(
                    "d => window.postMessage({type:'streamlit:render',args:{payload:d}}, '*')",
                    payload)
            push()
            page.locator("#hzm-day-input").fill(day)
            page.locator("#hzm-day-input").dispatch_event("change")
            page.locator("#hzm-lab-tab-players").click()
            assert page.locator("#hzm-detail-grid").is_hidden()
            panel = page.locator("#hzv3")
            assert panel.is_visible()
            assert page.locator("#hzv3-roster").is_visible()
            assert page.locator("#hzv3-inspector").is_visible()
            assert page.locator("#hzv3-analytics").count() == 0  # semantic section uses a class
            assert page.locator("#hzv3 .hzv3-analytics").is_visible()
            assert page.locator("#hzv3-version").inner_text() == "V7.4"
            assert page.locator("#hzv3-roster .hzv3-player").count() == 2
            assert "Test Guard Alpha" in page.locator("#hzv3-inspector").inner_text()
            assert page.locator("#hzv3-hist svg").count() == 1
            # Badge behind the portrait follows the selected player's REAL
            # game team, reusing verified home.team_logos (no separate URL).
            watermark = page.locator("#hzv3-inspector .hzv3-team-watermark")
            assert watermark.count() == 1
            assert watermark.locator("img").get_attribute("src") == phi_logo
            assert watermark.locator(".hzv3-team-watermark-label").inner_text() == "PHI"
            assert page.locator("#hzv3-inspector .hzv3-headshot").count() == 0
            color_style = page.evaluate("""() => {
                const inspector = document.querySelector("#hzv3-inspector");
                const mark = document.querySelector(".hzv3-team-watermark");
                const card = document.querySelector(".hzv3-hist-card");
                return {
                    background: getComputedStyle(inspector).backgroundImage,
                    border: getComputedStyle(inspector).borderTopColor,
                    watermarkOpacity: Number(getComputedStyle(mark).opacity),
                    chart: getComputedStyle(card).backgroundImage,
                };
            }""")
            assert "radial-gradient" in color_style["background"], color_style
            assert "radial-gradient" in color_style["chart"], color_style
            assert .20 <= color_style["watermarkOpacity"] <= .45, color_style
            assert page.locator("#hzv3-trend svg").count() == 1
            assert page.locator("#hzv3-hist svg rect").count() >= 24
            assert "15 meczów" in page.locator("#hzv3-rates-note").inner_text()
            averages = page.locator("#hzv3-averages").inner_text()
            assert "Sezon · PHI" in averages, averages
            assert "25,0" in averages, averages
            assert "—" not in averages, averages
            assert "Minuty (ESPN L5)" in page.locator("#hzv3-inspector").inner_text()
            assert "30,6" in page.locator("#hzv3-inspector").inner_text()
            assert "Model SD" in page.locator("#hzv3-pace").inner_text()
            assert "12,3" in page.locator("#hzv3-pace").inner_text()
            assert page.locator("#hzv3-rates>div").count() == 4
            # All four historical threshold rows and history buttons must
            # actually fit the desktop visual reference, not be clipped.
            if width >= 1600:
                positions = page.evaluate("""() => {
                    const area=document.querySelector('.hzv3-rates-card').getBoundingClientRect();
                    const rows=[...document.querySelectorAll('#hzv3-rates>div')];
                    const card=document.querySelector('#hzv3-inspector').getBoundingClientRect();
                    const buttons=[...document.querySelectorAll('#hzv3-inspector [data-hzv3-props]')];
                    return {
                      lastRate:rows[rows.length-1].getBoundingClientRect().bottom,
                      rateBottom:area.bottom,
                      lastButton:buttons[buttons.length-1].getBoundingClientRect().bottom,
                      inspectorBottom:card.bottom,
                    }
                }""")
                assert positions["lastRate"] <= positions["rateBottom"]+1, positions
                assert positions["lastButton"] <= positions["inspectorBottom"]+1, positions
            assert "20,0" in page.locator('#hzv3-inspector [data-hzv3-metric="PTS"]').inner_text()
            assert page.locator("[data-hzv3-market]").count() == 4
            if width >= 1600:
                bounds = page.evaluate("""() => {
                    const rect = q => {
                        const r=document.querySelector(q).getBoundingClientRect();
                        return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom};
                    };
                    const row=document.querySelector('.hzv3-player');
                    const cells=[...row.querySelectorAll('.hzv3-player-stat')];
                    const values=cells.map(el=>{
                        const r=el.getBoundingClientRect();
                        return {left:r.left,right:r.right,width:r.width,scroll:el.scrollWidth,client:el.clientWidth};
                    });
                    return {
                        card:rect('#hzv3-inspector'),
                        roster:rect('.hzv3-roster-card'),
                        analytics:rect('.hzv3-analytics'),
                        summary:rect('.hzv3-summary'),
                        cells:values
                    };
                }""")
                assert abs(bounds["card"]["width"]-278) < 2, bounds
                assert abs(bounds["roster"]["width"]-390) < 2, bounds
                assert abs(bounds["card"]["y"]-bounds["roster"]["y"]) < 2, bounds
                assert abs(bounds["analytics"]["y"]-bounds["roster"]["y"]) < 2, bounds
                assert bounds["summary"]["x"] >= bounds["roster"]["x"]-2, bounds
                assert abs(bounds["summary"]["bottom"]-bounds["card"]["bottom"]) < 3, bounds
                assert all(v["width"] >= 44 for v in bounds["cells"]), bounds
                assert all(v["scroll"] <= v["client"]+2 for v in bounds["cells"]), bounds
                assert all(l["right"] <= r["left"]+1 for l,r in zip(bounds["cells"],bounds["cells"][1:])),bounds
            page.locator('[data-hzv3-market="REB"]').click()
            assert page.locator("#hzv3-rates-title").inner_text() == "Historyczne over (REB)"
            assert "2,4" in page.locator('#hzv3-inspector [data-hzv3-metric="REB"]').inner_text()
            assert page.locator('[data-hzv3-market="REB"]').get_attribute("aria-pressed") == "true"
            page.locator('[data-hzv3-window="10"]').click()
            assert page.locator('[data-hzv3-window="10"]').get_attribute("aria-pressed") == "true"
            assert page.locator("#hzv3-trend svg").count() == 1

            # Select a different athlete: logo must switch PHI -> MIL
            # without stale watermark or previous-team background.
            page.locator('#hzv3-roster [data-hzv3-pick="1"]').click()
            assert "Test Forward Beta" in page.locator("#hzv3-inspector").inner_text()
            assert page.locator("#hzv3-inspector .hzv3-team-watermark img").get_attribute("src") == mil_logo
            assert page.locator("#hzv3-inspector .hzv3-team-watermark-label").inner_text() == "MIL"
            page.locator('#hzv3-roster [data-hzv3-pick="0"]').click()
            assert page.locator("#hzv3-inspector .hzv3-team-watermark img").get_attribute("src") == phi_logo
            page.screenshot(path=str(OUT / f"player-simulations-neon-{width}x{height}.png"))
            payload["premium_simulation"] = {"entitled": False, "game": None, "players": None}
            payload["auth"] = {"role": "free"}
            push()
            assert page.locator("#hzv3-roster .hzv3-player").count() == 0
            assert "Test Guard Alpha" not in page.locator("#hzv3-inspector").inner_text()
            assert page.locator("#hzv3-hist svg").count() == 0
            assert "Premium" in page.locator("#hzv3-roster").inner_text()
            assert not errors, (width, height, errors)
            page.close()
        browser.close()
    print("Player Simulations neon parity, real L5, PTS/REB toggle, responsive and guest isolation OK")


if __name__ == "__main__":
    main()
