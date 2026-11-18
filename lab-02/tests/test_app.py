import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
import app as catshop_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Ізольований тестовий клієнт Flask із тимчасовим файлом замість /data/visits.txt."""
    temp_counter = tmp_path / "visits.txt"
    monkeypatch.setattr(catshop_app, "COUNTER_FILE", temp_counter)
    monkeypatch.setattr(catshop_app, "DATABASE_URL", None)
    catshop_app.app.config["TESTING"] = True

    with catshop_app.app.test_client() as test_client:
        yield test_client


def test_health_returns_ok(client):
    """Перевіряє, що /health відповідає 200 OK і текстом 'ok'."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.data.decode("utf-8").strip() == "ok"


def test_ready_reports_file_store(client, tmp_path):
    """Перевіряє, що /ready підтверджує готовність і вказує правильний шлях до сховища."""
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.get_json() == {
        "ready": True,
        "store": f"file:{tmp_path / 'visits.txt'}",
    }


def test_visits_increments_sequentially(client):
    """Перевіряє, що кожен запит до /visits збільшує лічильник на 1."""
    first = client.get("/visits")
    assert first.status_code == 200
    assert first.get_json() == {"visits": 1, "store": "file"}

    second = client.get("/visits")
    assert second.status_code == 200
    assert second.get_json() == {"visits": 2, "store": "file"}


def test_visits_persists_state_to_file(client, tmp_path):
    """Перевіряє, що лічильник реально записується у файл на диску, а не висить у пам'яті."""
    client.get("/visits")
    client.get("/visits")
    client.get("/visits")

    counter_file = tmp_path / "visits.txt"
    assert counter_file.exists()
    assert counter_file.read_text(encoding="utf-8").strip() == "3"


def test_ready_returns_503_when_database_unreachable(client, monkeypatch):
    """Перевіряє, що при налаштованій, але недоступній БД, /ready чесно віддає 503."""
    monkeypatch.setattr(
        catshop_app,
        "DATABASE_URL",
        "postgresql://user:pass@127.0.0.1:1/nonexistent",
    )
    response = client.get("/ready")
    assert response.status_code == 503
    payload = response.get_json()
    assert payload["ready"] is False
    assert "error" in payload