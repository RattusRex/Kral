import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_database_import(database_url_marker: str | None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if database_url_marker is None:
        env.pop("DATABASE_URL", None)
    else:
        env["DATABASE_URL"] = database_url_marker

    script = """
import app.core.env

app.core.env.load_env = lambda *args, **kwargs: {}

try:
    import app.db.database as database
except RuntimeError as exc:
    print(str(exc))
    raise SystemExit(10)

print(database.DATABASE_URL)
"""
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )


def test_database_url_is_required_when_env_and_dotenv_are_missing():
    result = run_database_import(None)

    assert result.returncode == 10, result.stdout + result.stderr
    assert "DATABASE_URL is not set" in result.stdout


def test_database_url_from_environment_is_accepted():
    result = run_database_import("sqlite://")

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "sqlite://"


def test_committed_files_do_not_contain_previous_database_password():
    previous_password = "Gal" + "U5TA1"

    result = subprocess.run(
        ["git", "grep", "-n", previous_password, "--", "."],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 1, result.stdout
