import json

import pytest

from siegesense_engine.protocol import (
    ProtocolError,
    StatusPayload,
    error_response,
    make,
    parse,
)


def test_all_fixtures_parse(protocol_fixtures):
    files = sorted(protocol_fixtures.glob("*.json"))
    assert len(files) >= 5
    for f in files:
        env = parse(f.read_text())
        assert env.type


def test_status_fixture_matches_model(protocol_fixtures):
    env = parse((protocol_fixtures / "status.json").read_text())
    status = StatusPayload.model_validate(env.payload)
    assert len(status.lights) == 6


def test_make_roundtrip():
    env = parse(make("status", {"a": 1}, id="7"))
    assert env.type == "status"
    assert env.id == "7"
    assert env.payload == {"a": 1}
    assert env.ts >= 0


def test_error_response_shape():
    env = parse(error_response("9", "bad", "m"))
    assert env.type == "response"
    assert env.id == "9"
    assert env.payload == {"ok": False, "error": {"code": "bad", "message": "m"}}


@pytest.mark.parametrize(
    "text", ["not json", '{"ts":1}', "[1,2]", json.dumps({"type": 5, "ts": 1})]
)
def test_parse_rejects_garbage(text):
    with pytest.raises(ProtocolError):
        parse(text)


def test_new_fixtures_validate(protocol_fixtures):
    from siegesense_engine.calibration import CalibrationState
    from siegesense_engine.warmup import FlickOut, WarmupMetrics, WarmupSummary

    def payload(name):
        return parse((protocol_fixtures / name).read_text()).payload

    assert WarmupMetrics.model_validate(payload("metrics.json")).flicks == 12
    assert FlickOut.model_validate(payload("flick.json")).id == 1
    assert CalibrationState.model_validate(payload("calibration.json")).phase == "measuring"
    summary = WarmupSummary.model_validate(payload("warmup_summary.json")["data"])
    assert summary.drill is not None
