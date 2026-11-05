"""Run the real Streamlit script without a browser or backend."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_home_page_renders():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run(timeout=15)

    assert not app.exception
    assert app.title[0].value == "🎓 CampusAgent"
    assert "工程初始化" in app.info[0].value
