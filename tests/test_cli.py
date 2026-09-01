from __future__ import annotations

import json
from pathlib import Path

from acs.cli import main


def test_cli_init_inspect_schema_and_archive_dry_run(tmp_path: Path, capsys: object) -> None:
    workspace = tmp_path / "workspace"
    memory = tmp_path / "external"
    assert (
        main(
            [
                "--workspace",
                str(workspace),
                "init",
                "--variant",
                "local",
                "--memory-root",
                str(memory),
                "--model",
                "fake-model",
            ]
        )
        == 0
    )
    assert main(["--workspace", str(workspace), "inspect"]) == 0
    schemas = tmp_path / "schemas"
    assert main(["--workspace", str(workspace), "schema", "export", "--output", str(schemas)]) == 0
    assert (schemas / "memory-event.schema.json").exists()

    transcript = tmp_path / "chat.json"
    transcript.write_text(
        json.dumps(
            [
                {
                    "role": "assistant",
                    "content": "Я люблю проверяемые выводы и хочу хранить причины ревизий.",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "--workspace",
                str(workspace),
                "import-transcript",
                str(transcript),
                "--subject",
                "Test",
                "--dry-run",
            ]
        )
        == 0
    )
