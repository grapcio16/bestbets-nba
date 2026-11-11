"""Real browser/HTTP/SQL/crypto, explicitly synthetic external providers."""
import os
from pathlib import Path
import socket
import threading
import time
import httpx
import pytest
import uvicorn
from playwright.sync_api import sync_playwright
from billing_demo.testing.runner import build


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


@pytest.fixture(scope='session')
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def site(tmp_path):
    port, provider_port = free_port(), free_port()
    database = os.getenv('TEST_DEMO_DATABASE_URL') or 'sqlite:////tmp/bestbets-demo-'+tmp_path.name+'.sqlite3'
    app, hosted = build(database, port, provider_port)
    servers, threads = [], []
    for asgi, number in [(hosted, provider_port), (app, port)]:
        server = uvicorn.Server(uvicorn.Config(asgi, host='127.0.0.1', port=number,
            access_log=False, proxy_headers=False, log_level='warning'))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        servers.append(server)
        threads.append(thread)
    origin = f'http://localhost:{port}'
    for _ in range(100):
        try:
            if httpx.get(origin+'/healthz', trust_env=False).status_code == 200:
                break
        except httpx.TransportError:
            pass
        time.sleep(.05)
    else:
        pytest.fail('Local demo failed to start')
    yield origin, app, f'http://localhost:{provider_port}'
    for server in servers:
        server.should_exit = True
    for thread in threads:
        thread.join(timeout=5)
    app.state.billing.db.engine.dispose()


@pytest.fixture
def page(browser, request):
    context = browser.new_context(viewport={'width':1440, 'height':1000})
    trace_folder = os.getenv('DEMO_TRACE_DIR')
    if trace_folder:
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
    page = context.new_page()
    yield page
    if trace_folder:
        Path(trace_folder).mkdir(parents=True, exist_ok=True)
        context.tracing.stop(path=str(Path(trace_folder)/(request.node.name+'.zip')))
    context.close()


def register(page, origin, alias='alice'):
    page.goto(origin)
    page.get_by_role('button', name='Załóż konto', exact=True).click()
    page.locator('input[name=alias]').fill(alias)
    page.get_by_role('button', name='Utwórz syntetyczne konto').click()
    page.wait_for_url(origin+'/account')
