from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "protocol" / "fixtures"
TEST_FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def protocol_fixtures() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def ocr():
    from siegesense_engine.hud.ocr import RapidOcrEngine

    engine = RapidOcrEngine()
    engine.warm_up()
    return engine
