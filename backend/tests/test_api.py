import httpx
import pytest

from main import app


@pytest.fixture
def client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_list_turns_builds_query_params(client, monkeypatch):
    async def fake_query(sql, params=None):
        assert params["device_id"] == "d1"
        assert params["q"] == "你好"
        assert params["limit"] == 20
        return [{"turn_id": "t1", "utc_start_ms": 1000}]

    monkeypatch.setattr("routers.turns.query", fake_query)
    res = await client.get("/api/turns", params={"device_id": "d1", "q": "你好", "limit": 20})
    assert res.status_code == 200
    data = res.json()
    assert data["rows"][0]["turn_id"] == "t1"
    assert data["limit"] == 20


async def test_turn_not_found_404(client, monkeypatch):
    async def fake_query(sql, params=None):
        return []

    monkeypatch.setattr("routers.turns.query", fake_query)
    res = await client.get("/api/turns/missing")
    assert res.status_code == 404


async def test_audio_invalid_kind_400(client):
    res = await client.get("/api/turns/x/audio/zzz")
    assert res.status_code == 400


async def test_audio_s3_not_configured_503(client, monkeypatch):
    async def fake_query(sql, params=None):
        return [{"s3_input_wav": "s3://bucket/key.wav", "s3_tts_wav": ""}]

    monkeypatch.setattr("routers.turns.query", fake_query)
    monkeypatch.setattr("routers.turns.settings.audio_s3_bucket", "")
    res = await client.get("/api/turns/x/audio/input")
    assert res.status_code == 503


async def test_audio_presigned_url(client, monkeypatch):
    async def fake_query(sql, params=None):
        return [{"s3_input_wav": "s3://audio-bucket/turn/input.wav", "s3_tts_wav": ""}]

    class FakeClient:
        def generate_presigned_url(self, op, Params=None, ExpiresIn=None):
            assert op == "get_object"
            assert Params == {"Bucket": "audio-bucket", "Key": "turn/input.wav"}
            return f"https://presigned.example/{Params['Key']}?x={ExpiresIn}"

    monkeypatch.setattr("routers.turns.query", fake_query)
    monkeypatch.setattr("routers.turns.settings.audio_s3_bucket", "audio-bucket")
    monkeypatch.setattr("routers.turns.boto3.client", lambda *a, **k: FakeClient())
    res = await client.get("/api/turns/t1/audio/input")
    assert res.status_code == 200
    data = res.json()
    assert data["bucket"] == "audio-bucket"
    assert data["key"] == "turn/input.wav"
    assert data["url"].startswith("https://presigned.example/")


async def test_health(client, monkeypatch):
    async def fake_query(sql, params=None):
        return [{"1": 1}]

    monkeypatch.setattr("core.clickhouse.query", fake_query)
    res = await client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "clickhouse": "ok"}
