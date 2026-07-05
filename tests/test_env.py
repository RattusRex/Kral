import os
import subprocess
import sys
from pathlib import Path

from app.core.env import load_env, parse_env


def test_parse_env_basic_and_quotes_and_comments():
    content = "\n".join([
        "# a comment",
        "",
        "DATABASE_URL=postgresql://postgres:pw@localhost:5432/EpohaTruda",
        'QUOTED="value with spaces"',
        "SINGLE='single quoted'",
        "export EXPORTED=exported-value",
        "WITH_COMMENT=plain # trailing comment",
    ])

    parsed = parse_env(content)

    assert parsed["DATABASE_URL"] == "postgresql://postgres:pw@localhost:5432/EpohaTruda"
    assert parsed["QUOTED"] == "value with spaces"
    assert parsed["SINGLE"] == "single quoted"
    assert parsed["EXPORTED"] == "exported-value"
    assert parsed["WITH_COMMENT"] == "plain"
    assert "# a comment" not in parsed


def test_load_env_sets_missing_and_preserves_existing(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "KRAL_TEST_MISSING=from-file\nKRAL_TEST_EXISTING=from-file\n",
        encoding="utf-8",
    )

    os.environ.pop("KRAL_TEST_MISSING", None)
    os.environ["KRAL_TEST_EXISTING"] = "from-shell"
    try:
        applied = load_env(start=tmp_path)

        # A variable absent from the environment is loaded from the file.
        assert os.environ["KRAL_TEST_MISSING"] == "from-file"
        assert applied["KRAL_TEST_MISSING"] == "from-file"
        # Pre-existing variables are never overwritten.
        assert os.environ["KRAL_TEST_EXISTING"] == "from-shell"
        assert "KRAL_TEST_EXISTING" not in applied
    finally:
        os.environ.pop("KRAL_TEST_MISSING", None)
        os.environ.pop("KRAL_TEST_EXISTING", None)


def test_load_env_missing_file_returns_empty(tmp_path):
    assert load_env(start=tmp_path) == {}


def test_database_config_requires_explicit_database_url_without_env_file():
    repo_root = Path(__file__).resolve().parents[1]
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"DATABASE_URL", "PYTHONPATH"}
    }
    env["PYTHONPATH"] = str(repo_root)

    result = subprocess.run(
        [sys.executable, "-c", "import app.db.database"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "DATABASE_URL is not set" in result.stderr
