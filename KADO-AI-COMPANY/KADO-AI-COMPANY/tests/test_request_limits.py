from fastapi.testclient import TestClient

from company.api import create_app
from company.config import Settings


def test_declared_and_streamed_body_limits(tmp_path):
    app = create_app(Settings(project_root=tmp_path, api_token="local-test-token-with-at-least-24-characters", max_retries=0, task_timeout=7))
    with TestClient(app) as client:
        url = "/api/tasks"
        auth = {"Authorization": "Bearer " + app.state.settings.api_token}
        assert client.post(url, content=b"{}", headers={**auth, "content-length": "invalid"}).status_code == 400
        assert client.post(url, content=b"{}", headers={**auth, "content-length": "1000001"}).status_code == 413
        assert client.post(url, content=iter([b"x" * 600000, b"x" * 600000]), headers=auth).status_code == 413
        # A following valid body remains readable by FastAPI after middleware accounting.
        created = client.post(url, json={"title": "Gerçek sınırlı görev"}, headers=auth)
        assert created.status_code == 201
        assert created.json()["max_retries"] == 0
        assert created.json()["timeout_seconds"] == 7
