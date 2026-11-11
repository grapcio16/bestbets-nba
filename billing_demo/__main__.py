"""Explicit local operator commands; no deployment, live mode or secret output."""
import argparse
import time
from dotenv import load_dotenv
from sqlalchemy import delete
from .models import WebSession, LoginFlow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', required=True)
    parser.add_argument('command', choices=['serve', 'migrate', 'reconcile', 'cleanup'])
    args = parser.parse_args()
    load_dotenv(args.env_file, override=False)
    if args.command == 'migrate':
        from alembic import command
        from alembic.config import Config
        command.upgrade(Config('alembic-billing.ini'), 'head')
        return
    from .app import create_app
    app = create_app()
    service = app.state.billing
    if args.command == 'serve':
        import uvicorn
        uvicorn.run(app, host='127.0.0.1', port=8810, proxy_headers=False, access_log=False)
    elif args.command == 'reconcile':
        service.reconcile()
    else:
        with service.db.transaction() as s:
            s.execute(delete(LoginFlow).where(LoginFlow.expires_at <= int(time.time())))
            s.execute(delete(WebSession).where(WebSession.expires_at <= int(time.time())))
    service.db.engine.dispose()


if __name__ == '__main__':
    main()
