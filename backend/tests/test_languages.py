from app.utils.languages import detect_language


def test_language_detection_supports_common_extensions() -> None:
    assert detect_language("backend/main.py") == "Python"
    assert detect_language("src/App.tsx") == "TypeScript"
    assert detect_language("styles/main.scss") == "SCSS"
    assert detect_language("README.md") == "Markdown"
    assert detect_language("unknown.data") is None