from pathlib import Path

from valuepulse.helptext import HELP_MARKDOWN


def test_hilfe_erklaert_den_ersten_start():
    text = HELP_MARKDOWN
    assert "run.bat" in text
    assert "run.sh" in text
    assert "run.command" in text
    assert "Demo-Modus" in text
    assert "localhost:8501" in text
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "run.bat" in readme
    assert "Hilfe" in readme
