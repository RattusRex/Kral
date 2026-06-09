import os

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
