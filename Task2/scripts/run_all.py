from __future__ import annotations

from build_site import build_site
from calculate_indicators import run


def main() -> None:
    run()
    print(f"Task2 website: {build_site()}")


if __name__ == "__main__":
    main()
