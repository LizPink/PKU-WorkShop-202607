from __future__ import annotations

import argparse

from build_site import build_site
from fetch_data import main as fetch_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Task1 data and rebuild the website.")
    parser.add_argument("--skip-fetch", action="store_true", help="Only rebuild the website from existing CSV.")
    args, rest = parser.parse_known_args()

    if args.skip_fetch:
        html = build_site()
    else:
        # Forward date/token arguments to fetch_data.py's parser.
        import sys

        sys.argv = [sys.argv[0], *rest]
        outputs = fetch_data()
        html = build_site(outputs["combined"])
    print(f"Task1 website: {html}")


if __name__ == "__main__":
    main()
