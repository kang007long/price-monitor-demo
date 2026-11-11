from __future__ import annotations

import json

from price_monitor.cli import main
from price_monitor import db


def test_export_command_writes_files(tmp_path) -> None:
    database = tmp_path / "cli.db"
    connection = db.connect(database)
    db.initialize(connection)
    connection.close()
    web = tmp_path / "web"
    assert main(["export", "--db", str(database), "--web-dir", str(web)]) == 0
    payload = json.loads((web / "public" / "data" / "dashboard.json").read_text())
    assert payload["items"] == []
    assert (web / "public" / "exports" / "price-monitor-latest.xlsx").exists()


def test_max_pages_zero_is_rejected_not_treated_as_default(tmp_path, capsys) -> None:
    code = main(["scrape", "--db", str(tmp_path / "cli.db"), "--max-pages", "0"])
    assert code == 2
    assert "between 1 and 50" in capsys.readouterr().err


def test_negative_ensure_history_is_rejected(tmp_path, capsys) -> None:
    code = main(
        [
            "scrape",
            "--db",
            str(tmp_path / "cli.db"),
            "--simulate",
            "--ensure-history",
            "-1",
        ]
    )
    assert code == 2
    assert "must be >= 0" in capsys.readouterr().err


def test_ensure_history_without_simulate_is_rejected(tmp_path, capsys) -> None:
    code = main(
        [
            "scrape",
            "--db",
            str(tmp_path / "cli.db"),
            "--ensure-history",
            "3",
        ]
    )
    assert code == 2
    assert "requires --simulate" in capsys.readouterr().err


def test_max_pages_is_capped_to_the_source_limit(tmp_path, capsys) -> None:
    code = main(["scrape", "--db", str(tmp_path / "cli.db"), "--max-pages", "999"])
    assert code == 2
    assert "between 1 and 50" in capsys.readouterr().err


def test_min_interval_cannot_go_below_one_second(tmp_path, capsys) -> None:
    code = main(
        ["scrape", "--db", str(tmp_path / "cli.db"), "--min-interval", "0.2"]
    )
    assert code == 2
    assert "at least 1.0 second" in capsys.readouterr().err


def test_invalid_timeout_and_retries_are_rejected(tmp_path, capsys) -> None:
    assert main(["scrape", "--db", str(tmp_path / "a.db"), "--timeout", "0"]) == 2
    assert "must be > 0" in capsys.readouterr().err
    assert main(["scrape", "--db", str(tmp_path / "a.db"), "--retries", "-1"]) == 2
    assert "must be >= 0" in capsys.readouterr().err
