from pathlib import Path


REQUIREMENTS_PATH = Path(__file__).parents[1] / "requirements.txt"


def _requirements() -> dict[str, str]:
    raw_requirements = REQUIREMENTS_PATH.read_bytes()
    assert not raw_requirements.startswith((b"\xff\xfe", b"\xfe\xff")), (
        "requirements.txt must be UTF-8 so pip can install it on every platform"
    )

    requirements = {}
    for line in raw_requirements.decode("utf-8").splitlines():
        requirement = line.strip()
        if not requirement or requirement.startswith("#"):
            continue
        name, version = requirement.split("==", maxsplit=1)
        requirements[name.casefold()] = version
    return requirements


def test_fastapi_stack_remains_compatible_without_fastapi_mail():
    requirements = _requirements()

    assert requirements["fastapi"] == "0.115.6"
    assert requirements["starlette"] == "0.41.3"
    assert requirements["pydantic"] == "2.12.5"
    assert requirements["httpx"] == "0.28.1"
    assert "fastapi-mail" not in requirements
