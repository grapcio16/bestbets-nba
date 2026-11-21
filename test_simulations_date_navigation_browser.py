"""Regression: Simulation Lab dates must survive Streamlit iframe remounts.

Synthetic basketball fixtures only; no production requests or credentials.
Exercises 1672px desktop UI on the actual frontend, including the originally
reported right-hand date arrows, native date field and server round-trip.
"""
from pathlib import Path
from shutil import which

from playwright.sync_api import sync_playwright

PAGE = (Path(__file__).parent / "bestbets_reference_frontend" / "index.html").as_uri()


def fixture(day, game_id, away, home):
    return {
        "id": game_id, "day": day, "away": away, "home": home,
        "state": "scheduled", "start": day + "T23:00:00Z"
    }


def main():
    with sync_playwright() as tool:
        path = which("chromium") or which("google-chrome")
        browser = tool.chromium.launch(
            headless=True, args=["--no-sandbox"],
            **({"executable_path": path} if path else {})
        )
        for width, height in ((1672, 941), (1231, 691)):
            page = browser.new_page(
                viewport={"width": width, "height": height}, device_scale_factor=1
            )
            page.clock.set_fixed_time("2026-11-21T15:00:00Z")
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(PAGE, wait_until="load")
            page.locator('.nav-btn[data-page="simulations"]').click()
            page.evaluate("""() => {
                window.__calendarRequests = [];
                window.addEventListener("message", event => {
                    const data = event.data || {};
                    if(data.type === "streamlit:setComponentValue" &&
                        data.value?.type === "home_date")
                        window.__calendarRequests.push(data.value.date);
                });
            }""")
            today = "2026-11-21"
            next_day = "2026-11-22"
            chosen = "2026-11-24"
            home = {
                "calendar_today": today,
                "calendar_loaded_days": [today],
                "calendar_games": [fixture(today, "401888000", "CHA", "ATL")],
                "calendar_extras": {},
                "calendar_requested_day": None
            }
            payload = {
                "brand": "", "auth": {"role": "guest"},
                "home": home,
                "premium_simulation": {
                    "entitled": False, "game": None, "players": None
                }
            }

            def push():
                page.evaluate(
                    "d => window.postMessage({type:'streamlit:render',args:{payload:d}}, '*')",
                    payload
                )
                page.wait_for_timeout(90)

            push()
            assert page.locator("#hzm-day-input").input_value() == today
            assert "CHA" in page.locator("#hzm-match-picker-label").inner_text()

            # Arrow updates the input immediately, even without Premium.
            page.locator("#hzm-day-next").click()
            assert page.locator("#hzm-day-input").input_value() == next_day
            assert "22 LISTOPADA" in page.locator("#hzm-day-title").inner_text()
            page.wait_for_function(
                "window.__calendarRequests.includes('2026-11-22')"
            )
            assert page.locator("#hzm-match-picker-label").inner_text() == "Wybierz mecz"

            # Simulate verified server's response to home_date.
            home["calendar_extras"] = {
                next_day: {
                    "date": next_day,
                    "games": [fixture(next_day, "401888001", "BOS", "MIA")],
                    "complete": True
                }
            }
            home["calendar_requested_day"] = next_day
            push()
            assert page.locator("#hzm-day-input").input_value() == next_day
            assert "BOS" in page.locator("#hzm-match-picker-label").inner_text()

            # On Streamlit rerun the iframe is often remounted; the selected
            # day MUST be restored from calendar_requested_day, not today.
            page.goto(PAGE, wait_until="load")
            page.locator('.nav-btn[data-page="simulations"]').click()
            push()
            assert page.locator("#hzm-day-input").input_value() == next_day
            assert "BOS" in page.locator("#hzm-match-picker-label").inner_text()

            # Previous arrow and arbitrary manual date entry both work.
            page.locator("#hzm-day-prev").click()
            assert page.locator("#hzm-day-input").input_value() == today
            assert "CHA" in page.locator("#hzm-match-picker-label").inner_text()
            page.locator("#hzm-day-input").fill(chosen)
            page.locator("#hzm-day-input").dispatch_event("change")
            assert page.locator("#hzm-day-input").input_value() == chosen
            assert "24 LISTOPADA" in page.locator("#hzm-day-title").inner_text()
            assert page.locator("#hzm-match-picker-label").inner_text() == "Wybierz mecz"

            # Server acknowledgment persists an arbitrary selected date.
            home["calendar_requested_day"] = chosen
            home["calendar_extras"][chosen] = {
                "date": chosen, "games": [fixture(chosen, "401888002", "NYK", "IND")],
                "complete": True
            }
            page.goto(PAGE, wait_until="load")
            page.locator('.nav-btn[data-page="simulations"]').click()
            push()
            assert page.locator("#hzm-day-input").input_value() == chosen
            assert "NYK" in page.locator("#hzm-match-picker-label").inner_text()
            assert not errors, (width, errors)
            page.close()
        browser.close()
    print("Simulation date arrows, manual date and Streamlit remount: OK")


if __name__ == "__main__":
    main()
