"""E03 entry point; retain E01/E02 compatibility modes from the forked runner."""

from starter_v5.run_e01 import main


if __name__ == "__main__":
    raise SystemExit(main())
