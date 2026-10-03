"""AIS command entry point; the ACS implementation remains compatible."""

from acs.cli import build_parser, main

__all__ = ["build_parser", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
