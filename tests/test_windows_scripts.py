import os
import stat
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _paren_issues(text: str, needles: tuple[str, ...]) -> list[str]:
    """Meldet Variablen, die in demselben Klammerblock gelesen werden.

    cmd erweitert Prozent-Variablen, bevor die Zeilen im Block laufen.
    Ein Pfad, der erst in der Klammer gesetzt wird, ist dann leer.
    """
    depth = 0
    issues = []
    for number, raw in enumerate(text.splitlines(), 1):
        code, _, _ = raw.partition("REM")
        if depth > 0:
            for needle in needles:
                if needle in code:
                    issues.append(f"{number}:{needle}")
        depth += _paren_delta(code)
        if depth < 0:
            depth = 0
    return issues


def _paren_delta(line: str) -> int:
    depth = 0
    quote = False
    for char in line:
        if char == '"':
            quote = not quote
        elif not quote and char == "(":
            depth += 1
        elif not quote and char == ")":
            depth -= 1
    return depth


def test_altes_klammermuster_wird_erkannt():
    sample = """
if not errorlevel 1 (
  set "VP_PYTHON=C:\\Python\\python.exe"
  "%VP_PYTHON%" -c "print(1)"
)
"""
    assert _paren_issues(sample, ("%VP_PYTHON%",))


def test_findpython_liest_den_pfad_nicht_in_derselben_klammer():
    path = ROOT / "findpython.bat"
    data = path.read_bytes()
    assert data.count(b"\n") == data.count(b"\r\n")
    text = data.decode("ascii")
    assert _paren_issues(text, ("%VP_PYTHON%", "%ERRORLEVEL%")) == []
    assert "3.13" in text
    assert "WindowsApps" in text
    assert "py -%1" in text


def test_update_bat_laedt_zip_und_behaelt_eigene_dateien():
    path = ROOT / "update.bat"
    data = path.read_bytes()
    assert data.count(b"\n") == data.count(b"\r\n")
    text = data.decode("ascii")
    assert "archive/refs/heads/main.zip" in text
    assert "/XF .env" in text
    assert "valuepulse.sqlite3" in text
    assert "ValuePulse wurde erfolgreich aktualisiert!" in text
    assert "Dieser Ordner ist kein Git-Projekt" not in text
    assert _paren_issues(text, ("%VP_PYTHON%", "%ERRORLEVEL%", "%VP_SRC%")) == []


def test_update_sh_zip_behaelt_env_und_datenbank(tmp_path: Path):
    project = tmp_path / "ValuePulse"
    project.mkdir()
    (project / ".env").write_text("ODDS_API_KEY=geheim\n", encoding="utf-8")
    (project / "valuepulse.sqlite3").write_bytes(b"alte-datenbank")
    (project / "run.bat").write_text("alt\n", encoding="utf-8")
    (project / ".venv").mkdir()
    (project / ".venv" / "marker").write_text("bleiben", encoding="utf-8")

    packed = tmp_path / "packed" / "ValuePulse-main"
    (packed / "valuepulse").mkdir(parents=True)
    (packed / "run.bat").write_text("neu\n", encoding="utf-8")
    (packed / "valuepulse" / "app.py").write_text("print('neu')\n", encoding="utf-8")
    (packed / ".env").write_text("ODDS_API_KEY=aus-dem-zip\n", encoding="utf-8")
    (packed / "valuepulse.sqlite3").write_bytes(b"zip-datenbank")
    (packed / ".venv").mkdir()
    (packed / ".venv" / "marker").write_text("zip-venv", encoding="utf-8")

    archive = tmp_path / "main.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        for item in packed.rglob("*"):
            handle.write(item, item.relative_to(packed.parent))

    script = ROOT / "update.sh"
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    env = os.environ.copy()
    env["VALUEPULSE_MAIN_ZIP"] = str(archive)
    env["VALUEPULSE_UPDATE_FILES_ONLY"] = "1"
    result = subprocess.run(
        ["bash", str(script)],
        cwd=project,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "ValuePulse wurde erfolgreich aktualisiert!" in result.stdout
    assert (project / ".env").read_text(encoding="utf-8") == "ODDS_API_KEY=geheim\n"
    assert (project / "valuepulse.sqlite3").read_bytes() == b"alte-datenbank"
    assert (project / "run.bat").read_text(encoding="utf-8") == "neu\n"
    assert (project / "valuepulse" / "app.py").read_text(encoding="utf-8") == "print('neu')\n"
    assert (project / ".venv" / "marker").read_text(encoding="utf-8") == "bleiben"
