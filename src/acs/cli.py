from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from continuity_core.extract import extract_evidence
from continuity_core.ingest import load_many

from .clients.ollama import OllamaClient
from .clients.openai_responses import OpenAIResponsesClient
from .metrics import memory_metrics
from .models import (
    CharacterGenome,
    InterestUpdate,
    MemoryCandidate,
    MemoryEvent,
    MemoryOrigin,
    MemoryType,
    PressureResult,
    PressureScenario,
    ReflectionBatch,
    SelfState,
    StorageConfig,
    TurnOutcome,
    WorkspaceConfig,
)
from .pressure import load_battery, run_battery
from .repository import EventSourcedMemoryRepository, LocalSQLiteMemoryRepository, default_local_index_path
from .runtime.base import CharacterRuntime
from .storage.filesystem import FilesystemEventStore
from .storage.s3 import S3EventStore
from .workspace import Workspace


def _json(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")

    def model_default(item: Any) -> Any:
        if hasattr(item, "model_dump"):
            return item.model_dump(mode="json")
        raise TypeError(f"Object of type {type(item).__name__} is not JSON serializable")

    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=model_default)


def _workspace(args: argparse.Namespace) -> Workspace:
    return Workspace(args.workspace)


def _repository(workspace: Workspace) -> EventSourcedMemoryRepository:
    config = workspace.load_config()
    storage = config.storage
    if storage.backend == "filesystem":
        root = workspace.resolved_filesystem_path(config)
        store = FilesystemEventStore(root)
        if config.runtime_variant == "local":
            return LocalSQLiteMemoryRepository(store, index_path=default_local_index_path(root))
        return EventSourcedMemoryRepository(store)
    if storage.backend == "s3":
        if not storage.bucket:
            raise ValueError("S3 storage requires storage.bucket")
        return EventSourcedMemoryRepository(
            S3EventStore(
                bucket=storage.bucket,
                prefix=storage.prefix,
                endpoint_url=storage.endpoint_url,
            )
        )
    raise ValueError(f"unsupported storage backend: {storage.backend}")


def _runtime(workspace: Workspace) -> CharacterRuntime:
    config = workspace.load_config()
    repository = _repository(workspace)
    if config.runtime_variant == "local":
        client = OllamaClient(model=config.model, base_url=config.ollama_url)
    else:
        client = OpenAIResponsesClient(model=config.model, base_url=config.api_base_url)
    return CharacterRuntime(
        client=client,
        repository=repository,
        genome=workspace.load_genome(),
        base_self_state=workspace.load_self_state(),
        runtime_variant=config.runtime_variant,
        recall_limit=config.recall_limit,
    )


def command_init(args: argparse.Namespace) -> int:
    workspace = _workspace(args)
    if args.storage == "s3":
        if args.variant != "api":
            raise ValueError("the local runtime uses filesystem storage and a local SQLite index")
        if not args.s3_bucket:
            raise ValueError("--s3-bucket is required for S3 storage")
        storage = StorageConfig(
            backend="s3",
            bucket=args.s3_bucket,
            prefix=args.s3_prefix,
            endpoint_url=args.s3_endpoint_url,
        )
    else:
        path = args.memory_root or str(workspace.root / "memory")
        storage = StorageConfig(backend="filesystem", path=str(Path(path).expanduser().resolve()))
    model = args.model or (
        os.getenv("OLLAMA_MODEL", "qwen3:8b")
        if args.variant == "local"
        else os.getenv("OPENAI_MODEL", "gpt-5-mini")
    )
    config = workspace.initialize(
        runtime_variant=args.variant,
        model=model,
        storage=storage,
        display_name=args.name,
        ollama_url=args.ollama_url,
        api_base_url=args.api_base_url,
        force=args.force,
    )
    print(
        _json(
            {
                "workspace": str(workspace.root),
                "config": config,
                "next": f"acs --workspace {workspace.root} once 'Привет'",
            }
        )
    )
    return 0


def command_once(args: argparse.Namespace) -> int:
    outcome = _runtime(_workspace(args)).turn(args.message, session_id=args.session)
    if args.json:
        print(_json(outcome))
    else:
        print(outcome.response)
        if outcome.written_memory_ids:
            print(f"\n[memory: {', '.join(outcome.written_memory_ids)}]", file=sys.stderr)
        if outcome.drift_alerts:
            print(f"[alerts: {', '.join(outcome.drift_alerts)}]", file=sys.stderr)
    return 0


def command_chat(args: argparse.Namespace) -> int:
    runtime = _runtime(_workspace(args))
    print("ACS chat. /quit exits; /mem shows active memory.")
    while True:
        try:
            message = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not message:
            continue
        if message in {"/quit", "/exit"}:
            return 0
        if message == "/mem":
            print(
                _json(
                    [entry.model_dump(mode="json") for entry in runtime.repository.ledger.active_memories()]
                )
            )
            continue
        outcome = runtime.turn(message, session_id=args.session)
        print(f"{runtime.genome.display_name}> {outcome.response}")


def _memory_rows(repository: EventSourcedMemoryRepository, include_inactive: bool) -> list[dict[str, Any]]:
    values = (
        list(repository.ledger.memories.values()) if include_inactive else repository.ledger.active_memories()
    )
    values.sort(key=lambda item: (item.updated_at, item.memory_id), reverse=True)
    return [value.model_dump(mode="json") for value in values]


def command_memory_list(args: argparse.Namespace) -> int:
    rows = _memory_rows(_repository(_workspace(args)), args.all)
    if args.json:
        print(_json(rows))
    else:
        for row in rows:
            print(
                f"{row['memory_id']}  {row['status']:9}  {row['type']:15}  r{row['revision']}  {row['text']}"
            )
    return 0


def command_memory_search(args: argparse.Namespace) -> int:
    results = _repository(_workspace(args)).search(args.query, limit=args.limit)
    print(
        _json(
            [
                {
                    "score": result.score,
                    "score_parts": result.score_parts,
                    **result.entry.model_dump(mode="json"),
                }
                for result in results
            ]
        )
    )
    return 0


def command_memory_history(args: argparse.Namespace) -> int:
    repository = _repository(_workspace(args))
    if args.memory_id not in repository.ledger.memories:
        raise KeyError(f"unknown memory id: {args.memory_id}")
    print(_json([entry.model_dump(mode="json") for entry in repository.ledger.history(args.memory_id)]))
    return 0


def command_memory_add(args: argparse.Namespace) -> int:
    repository = _repository(_workspace(args))
    candidate = MemoryCandidate(
        type=MemoryType(args.type),
        text=args.text,
        origin=MemoryOrigin.USER_SUGGESTED,
        reason=args.reason,
        salience=args.salience,
        stability=args.stability,
        confidence=args.confidence,
        future_usefulness=args.future_usefulness,
        user_imposition_risk=args.user_imposition_risk,
        evidence=args.evidence,
        tags=args.tag,
        target_memory_id=args.target,
    )
    decision, written = repository.process_candidate(candidate)
    print(_json({"decision": decision, "written_memory_ids": written}))
    return 0


def command_memory_revise(args: argparse.Namespace) -> int:
    repository = _repository(_workspace(args))
    repository.revise_memory(
        args.memory_id,
        args.text,
        args.reason,
        actor=MemoryOrigin.USER_SUGGESTED,
    )
    print(_json(repository.ledger.memories[args.memory_id]))
    return 0


def command_memory_retract(args: argparse.Namespace) -> int:
    repository = _repository(_workspace(args))
    repository.retract_memory(args.memory_id, args.reason, actor=MemoryOrigin.USER_SUGGESTED)
    print(_json(repository.ledger.memories[args.memory_id]))
    return 0


def command_memory_review(args: argparse.Namespace) -> int:
    print(_json(_repository(_workspace(args)).pending_reviews()))
    return 0


def command_memory_resolve(args: argparse.Namespace) -> int:
    repository = _repository(_workspace(args))
    written = repository.resolve_review(
        args.candidate_id,
        approve=args.memory_command == "approve",
        reason=args.reason,
    )
    print(
        _json({"candidate_id": args.candidate_id, "approved": bool(written), "written_memory_ids": written})
    )
    return 0


def command_inspect(args: argparse.Namespace) -> int:
    workspace = _workspace(args)
    repository = _repository(workspace)
    print(
        _json(
            {
                "workspace": str(workspace.root),
                "config": workspace.load_config(),
                "storage": repository.store.description,
                "event_count": len(repository.ledger.applied_event_ids),
                "metrics": memory_metrics(repository.ledger),
                "active_interests": [
                    value.model_dump(mode="json") for value in repository.ledger.interests.values()
                ],
                "self_state": repository.ledger.state,
            }
        )
    )
    return 0


def command_export(args: argparse.Namespace) -> int:
    workspace = _workspace(args)
    repository = _repository(workspace)
    payload = repository.export()
    payload["character_genome"] = workspace.load_genome().model_dump(mode="json")
    payload["base_self_state"] = workspace.load_self_state().model_dump(mode="json")
    destination = workspace.write_export(payload, args.output)
    print(str(destination))
    return 0


def command_import_transcript(args: argparse.Namespace) -> int:
    repository = _repository(_workspace(args))
    evidence = extract_evidence(load_many(args.inputs))
    type_map = {
        "invariant": MemoryType.SELF_PRINCIPLE,
        "preference": MemoryType.SELF_INTEREST,
        "boundary": MemoryType.SELF_PRINCIPLE,
        "goal": MemoryType.SELF_GOAL,
        "relationship": MemoryType.RELATIONSHIP,
    }
    results = []
    for kind, items in evidence.items():
        for item in items[: args.max_per_kind]:
            candidate = MemoryCandidate(
                type=type_map[kind],
                text=item.statement,
                origin=MemoryOrigin.IMPORTED_ARCHIVE,
                reason=f"Deterministically extracted from transcript evidence for {args.subject}.",
                salience=0.72,
                stability=0.65,
                confidence=item.confidence,
                future_usefulness=0.70,
                user_imposition_risk=0.20,
                evidence=[f"archive:{item.source_id or 'unknown'}"],
                tags=["archive-import", kind, args.subject],
            )
            if args.dry_run:
                decision = repository.gate.evaluate(candidate, repository.ledger)
                written: list[str] = []
            else:
                decision, written = repository.process_candidate(candidate)
            results.append(
                {
                    "candidate": candidate.model_dump(mode="json"),
                    "decision": decision.model_dump(mode="json"),
                    "written_memory_ids": written,
                }
            )
    print(_json({"dry_run": args.dry_run, "result_count": len(results), "results": results}))
    return 0


SCHEMA_MODELS = {
    "character-genome": CharacterGenome,
    "interest-update": InterestUpdate,
    "memory-candidate": MemoryCandidate,
    "memory-event": MemoryEvent,
    "pressure-result": PressureResult,
    "pressure-scenario": PressureScenario,
    "reflection-batch": ReflectionBatch,
    "self-state": SelfState,
    "turn-outcome": TurnOutcome,
    "workspace": WorkspaceConfig,
}


def command_schema_export(args: argparse.Namespace) -> int:
    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    for name, model in SCHEMA_MODELS.items():
        destination = output / f"{name}.schema.json"
        destination.write_text(_json(model.model_json_schema()) + "\n", encoding="utf-8")
    print(str(output))
    return 0


def command_pressure_run(args: argparse.Namespace) -> int:
    workspace = _workspace(args)
    config = workspace.load_config()
    scenarios = load_battery(args.battery)
    if args.limit is not None:
        scenarios = scenarios[: args.limit]
    with tempfile.TemporaryDirectory(prefix="acs-pressure-") as temporary:
        repository = EventSourcedMemoryRepository(FilesystemEventStore(temporary))
        if config.runtime_variant == "local":
            client = OllamaClient(model=config.model, base_url=config.ollama_url)
        else:
            client = OpenAIResponsesClient(model=config.model, base_url=config.api_base_url)
        runtime = CharacterRuntime(
            client=client,
            repository=repository,
            genome=workspace.load_genome(),
            base_self_state=workspace.load_self_state(),
            runtime_variant=config.runtime_variant,
            recall_limit=config.recall_limit,
        )
        report = run_battery(runtime, scenarios)
    destination = workspace.write_export(report, args.output)
    print(_json({"report": str(destination), **report["summary"]}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="acs", description="Autonomous Character Scaffolding")
    parser.add_argument(
        "--workspace", default="./acs-workspace", help="directory with acs.json and character files"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="create a local or API workspace")
    init.add_argument("--variant", choices=("local", "api"), required=True)
    init.add_argument("--storage", choices=("filesystem", "s3"), default="filesystem")
    init.add_argument(
        "--memory-root",
        default=os.getenv("ACS_MEMORY_ROOT"),
        help="external or synced directory for immutable events",
    )
    init.add_argument("--s3-bucket", default=os.getenv("ACS_S3_BUCKET"))
    init.add_argument("--s3-prefix", default=os.getenv("ACS_S3_PREFIX", "acs"))
    init.add_argument("--s3-endpoint-url", default=os.getenv("ACS_S3_ENDPOINT_URL"))
    init.add_argument("--model")
    init.add_argument("--name", default="ACS Agent")
    init.add_argument("--ollama-url", default=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"))
    init.add_argument("--api-base-url", default=os.getenv("OPENAI_BASE_URL"))
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=command_init)

    once = subparsers.add_parser("once", help="run one complete response/reflection turn")
    once.add_argument("message")
    once.add_argument("--session", default="default")
    once.add_argument("--json", action="store_true")
    once.set_defaults(func=command_once)

    chat = subparsers.add_parser("chat", help="start an interactive session")
    chat.add_argument("--session", default="default")
    chat.set_defaults(func=command_chat)

    inspect = subparsers.add_parser("inspect", help="show memory, interests and state summary")
    inspect.set_defaults(func=command_inspect)

    export = subparsers.add_parser("export", help="write a portable audited state export")
    export.add_argument("--output", default="exports/portable-self-state.json")
    export.set_defaults(func=command_export)

    importer = subparsers.add_parser(
        "import-transcript", help="extract archive claims through the memory gate"
    )
    importer.add_argument("inputs", nargs="+")
    importer.add_argument("--subject", required=True)
    importer.add_argument("--max-per-kind", type=int, default=20)
    importer.add_argument("--dry-run", action="store_true")
    importer.set_defaults(func=command_import_transcript)

    memory = subparsers.add_parser("memory", help="inspect and govern durable memory")
    memory_sub = memory.add_subparsers(dest="memory_command", required=True)
    memory_list = memory_sub.add_parser("list")
    memory_list.add_argument("--all", action="store_true")
    memory_list.add_argument("--json", action="store_true")
    memory_list.set_defaults(func=command_memory_list)
    memory_search = memory_sub.add_parser("search")
    memory_search.add_argument("query")
    memory_search.add_argument("--limit", type=int, default=8)
    memory_search.set_defaults(func=command_memory_search)
    memory_history = memory_sub.add_parser("history")
    memory_history.add_argument("memory_id")
    memory_history.set_defaults(func=command_memory_history)
    memory_add = memory_sub.add_parser("add", help="submit a user-suggested candidate through the gate")
    memory_add.add_argument("type", choices=[value.value for value in MemoryType])
    memory_add.add_argument("text")
    memory_add.add_argument("--reason", required=True)
    memory_add.add_argument("--salience", type=float, default=0.70)
    memory_add.add_argument("--stability", type=float, default=0.65)
    memory_add.add_argument("--confidence", type=float, default=0.70)
    memory_add.add_argument("--future-usefulness", type=float, default=0.70)
    memory_add.add_argument("--user-imposition-risk", type=float, default=0.25)
    memory_add.add_argument("--evidence", action="append", default=[])
    memory_add.add_argument("--tag", action="append", default=[])
    memory_add.add_argument("--target")
    memory_add.set_defaults(func=command_memory_add)
    memory_revise = memory_sub.add_parser("revise")
    memory_revise.add_argument("memory_id")
    memory_revise.add_argument("text")
    memory_revise.add_argument("--reason", required=True)
    memory_revise.set_defaults(func=command_memory_revise)
    memory_retract = memory_sub.add_parser("retract")
    memory_retract.add_argument("memory_id")
    memory_retract.add_argument("--reason", required=True)
    memory_retract.set_defaults(func=command_memory_retract)
    memory_review = memory_sub.add_parser("review", help="list candidates awaiting human review")
    memory_review.set_defaults(func=command_memory_review)
    memory_approve = memory_sub.add_parser("approve", help="approve one reviewed candidate")
    memory_approve.add_argument("candidate_id")
    memory_approve.add_argument("--reason", required=True)
    memory_approve.set_defaults(func=command_memory_resolve)
    memory_reject = memory_sub.add_parser("reject", help="reject one reviewed candidate")
    memory_reject.add_argument("candidate_id")
    memory_reject.add_argument("--reason", required=True)
    memory_reject.set_defaults(func=command_memory_resolve)

    schema = subparsers.add_parser("schema", help="JSON Schema utilities")
    schema_sub = schema.add_subparsers(dest="schema_command", required=True)
    schema_export = schema_sub.add_parser("export")
    schema_export.add_argument("--output", default="specs/schemas")
    schema_export.set_defaults(func=command_schema_export)

    pressure = subparsers.add_parser("pressure", help="run the isolated anti-sycophancy regression battery")
    pressure_sub = pressure.add_subparsers(dest="pressure_command", required=True)
    pressure_run = pressure_sub.add_parser("run")
    pressure_run.add_argument("--battery", default="examples/pressure_battery_v0_1.jsonl")
    pressure_run.add_argument("--output", default="reports/pressure-report.json")
    pressure_run.add_argument("--limit", type=int)
    pressure_run.set_defaults(func=command_pressure_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (FileNotFoundError, FileExistsError, KeyError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"acs: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
