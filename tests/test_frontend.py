"""
The Streamlit script must import and run on the installed Streamlit version.

streamlit-cookies-manager 0.2.0 calls st.cache, which current Streamlit removed,
so the app crashed on start until frontend/app.py added a compatibility line.
This runs the script in Streamlit's headless test runner. It does not render a
browser page and does not talk to the API.
"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parent.parent / "frontend" / "app.py"


def test_app_script_runs_without_exceptions():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert [str(e.value) for e in app.exception] == []
