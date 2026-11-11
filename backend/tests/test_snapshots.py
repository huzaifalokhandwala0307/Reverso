from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def test_create_snapshot_success(client: TestClient):
    repo_res = client.post(
        "/api/repositories",
        json={"url": "https://github.com/sqlalchemy/sqlalchemy"},
    )
    repo_id = repo_res.json()["id"]

    snap_payload = {
        "ref": "v2.0.0",
        "commit_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
    }
    response = client.post(f"/api/repositories/{repo_id}/snapshots", json=snap_payload)
    assert response.status_code == 201
    data = response.json()

    assert data["repository_id"] == repo_id
    assert data["ref"] == "v2.0.0"
    assert data["commit_sha"] == "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
    assert data["status"] == "created"
    assert "id" in data
    assert "created_at" in data


def test_create_snapshot_duplicate_commit_409(client: TestClient):
    repo_res = client.post(
        "/api/repositories",
        json={"url": "https://github.com/encode/uvicorn"},
    )
    repo_id = repo_res.json()["id"]

    commit_sha = "1234567890abcdef1234567890abcdef12345678"
    snap_payload = {"ref": "main", "commit_sha": commit_sha}

    res1 = client.post(f"/api/repositories/{repo_id}/snapshots", json=snap_payload)
    assert res1.status_code == 201

    # Second creation with identical commit_sha on same repo MUST return 409
    res2 = client.post(f"/api/repositories/{repo_id}/snapshots", json=snap_payload)
    assert res2.status_code == 409
    data = res2.json()
    assert "error" in data
    assert data["error"]["code"] == "duplicate_snapshot"


def test_create_snapshot_same_commit_different_repo_allowed(client: TestClient):
    repo1 = client.post("/api/repositories", json={"url": "https://github.com/user1/repo"}).json()[
        "id"
    ]
    repo2 = client.post("/api/repositories", json={"url": "https://github.com/user2/repo"}).json()[
        "id"
    ]

    commit_sha = "abcdef1234567890abcdef1234567890abcdef12"

    res1 = client.post(f"/api/repositories/{repo1}/snapshots", json={"commit_sha": commit_sha})
    assert res1.status_code == 201

    # Different repo with same commit_sha is valid and properly partitioned
    res2 = client.post(f"/api/repositories/{repo2}/snapshots", json={"commit_sha": commit_sha})
    assert res2.status_code == 201
    assert res1.json()["id"] != res2.json()["id"]


def test_create_snapshot_nonexistent_repo(client: TestClient):
    random_id = uuid.uuid4()
    response = client.post(
        f"/api/repositories/{random_id}/snapshots",
        json={"ref": "main"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "repository_not_found"


def test_get_snapshot_by_id(client: TestClient):
    repo_id = client.post(
        "/api/repositories", json={"url": "https://github.com/pydantic/pydantic"}
    ).json()["id"]
    snap_id = client.post(f"/api/repositories/{repo_id}/snapshots", json={"ref": "main"}).json()[
        "id"
    ]

    response = client.get(f"/api/snapshots/{snap_id}")
    assert response.status_code == 200
    assert response.json()["id"] == snap_id
    assert response.json()["repository_id"] == repo_id
    assert response.json()["status"] == "created"


def test_get_snapshot_not_found(client: TestClient):
    random_id = uuid.uuid4()
    response = client.get(f"/api/snapshots/{random_id}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "snapshot_not_found"


def test_list_snapshots_for_repository(client: TestClient):
    repo_url = "https://github.com/django/django"
    repo_id = client.post("/api/repositories", json={"url": repo_url}).json()["id"]
    sha1 = "aaaa1111bbbb2222cccc3333dddd4444eeee5555"
    sha2 = "ffff1111bbbb2222cccc3333dddd4444eeee5555"
    client.post(f"/api/repositories/{repo_id}/snapshots", json={"ref": "main", "commit_sha": sha1})
    client.post(f"/api/repositories/{repo_id}/snapshots", json={"ref": "v5.0", "commit_sha": sha2})

    response = client.get(f"/api/repositories/{repo_id}/snapshots")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    assert {s["ref"] for s in items} == {"main", "v5.0"}
