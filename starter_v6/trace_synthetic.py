"""CLI for stage-by-stage synthetic E04 traces; never loads match assets."""

import argparse
import json
import sys
from pathlib import Path

from starter_v6.synthetic import fixture_catalog, trace_all, trace_fixture


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", choices=[fixture.name for fixture in fixture_catalog()])
    parser.add_argument("--all", action="store_true", help="emit every fixture trace")
    parser.add_argument("--output", type=Path, help="optional local JSON path")
    args = parser.parse_args(argv)
    if bool(args.fixture) == bool(args.all):
        parser.error("choose exactly one of --fixture or --all")
    payload = (
        trace_fixture(next(item for item in fixture_catalog() if item.name == args.fixture)).as_dict()
        if args.fixture else {"fixtures": trace_all()}
    )
    encoded = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is None:
        sys.stdout.write(encoded)
        return 0
    target = args.output.resolve()
    if target.exists():
        raise ValueError("refusing to overwrite existing synthetic trace: {}".format(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(encoded, encoding="utf-8")
    print("synthetic trace written: {}".format(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
