"""Explicit operator commands; no automatic schema changes or deployment."""
import argparse
from .api import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['reconcile'])
    args = parser.parse_args()
    if args.command == 'reconcile':
        result = create_app().state.billing.reconcile()
        print(f"checked={result['checked']} failed={result['failed']}")
        raise SystemExit(1 if result['failed'] else 0)


if __name__ == '__main__':
    main()
