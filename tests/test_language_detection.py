import pytest
from engine.language import detect_script, detect_language, identify_dialect

@pytest.mark.parametrize(
    "text,expected",
    [
        ("\u0C15\u0C4D\u0C37\u0C3F", "telugu"),  # "క్షి" Telugu characters
        ("Hello world", "latin"),
        ("Hello \u0C15\u0C4D\u0C37\u0C3F", "mixed"),
        ("!@#$%^&*()", "none"),
        ("1234567890", "none"),
        ("", "none"),
    ],
)
def test_detect_script(text, expected):
    assert detect_script(text) == expected

@pytest.mark.parametrize(
    "text,expected",
    [
        ("\u0C15\u0C4D\u0C37\u0C3F", "telugu"),
        ("Hello world", "english"),
        ("Hello \u0C15\u0C4D\u0C37\u0C3F", "mixed"),
        ("!@#$%^&*()", "unknown"),
        ("1234567890", "unknown"),
        ("", "unknown"),
        ("naaku em cheppali?", "mixed"),  # Romanized Telugu is NOT assumed to be English
    ],
)
def test_detect_language(text, expected):
    assert detect_language(text) == expected

def test_identify_dialect_romanized():
    # romanized pattern includes word 'naaku'
    text = "naaku em cheppali?"
    assert identify_dialect(text) == "romanized"

def test_identify_dialect_classical():
    text = "ఇది దుర్గాపురాణ గ్రంథము"
    assert identify_dialect(text) == "classical"

def test_identify_dialect_vyavaharika():
    text = "మనం చెప్పుద్దాం"
    assert identify_dialect(text) == "vyavaharika"

def test_identify_dialect_none():
    assert identify_dialect("some random English text") is None
