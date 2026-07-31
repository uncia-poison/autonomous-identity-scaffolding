from __future__ import annotations

import argparse
import json
from pathlib import Path

from .compiler import build_identity_bundle, bundle_from_dict, compile_profile
from .drift import evaluate_drift
from .ingest import load_many


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_command(args: argparse.Namespace) -> int:
    turns = load_many(args.inputs)
    bundle = build_identity_bundle(
        turns,
        subject_name=args.subject,
        max_per_kind=args.max_per_kind,
        voice_role=args.voice_role,
    )
    _write_json(Path(args.output), bundle.to_dict())
    print(f"Wrote {args.output}: {len(turns)} turns, anchor={len(bundle.anchor)} chars")
    return 0


def compile_command(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    profile = compile_profile(bundle_from_dict(data), target=args.target)
    Path(args.output).write_text(profile, encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


def drift_command(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    response = Path(args.response).read_text(encoding="utf-8")
    result = evaluate_drift(bundle_from_dict(data), response)
    if args.output:
        _write_json(Path(args.output), result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="continuity", description="Build portable AI identity continuity bundles")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Extract an evidence-backed identity bundle from transcript files")
    build.add_argument("inputs", nargs="+", help="JSON, TXT or Markdown transcript files")
    build.add_argument("--subject", required=True, help="Name of the AI/persona whose continuity is being compiled")
    build.add_argument("--output", default="identity.bundle.json")
    build.add_argument("--voice-role", choices=["assistant", "user"], default="assistant")
    build.add_argument("--max-per-kind", type=int, default=20)
    build.set_defaults(func=build_command)

    compile_p = sub.add_parser("compile", help="Compile a bundle into a target-specific continuity prompt")
    compile_p.add_argument("bundle")
    compile_p.add_argument("--target", choices=["generic", "openai", "anthropic", "gemini"], default="generic")
    compile_p.add_argument("--output", default="continuity-profile.txt")
    compile_p.set_defaults(func=compile_command)

    drift = sub.add_parser("drift", help="Evaluate a candidate response against the bundle")
    drift.add_argument("bundle")
    drift.add_argument("response")
    drift.add_argument("--output")
    drift.set_defaults(func=drift_command)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
