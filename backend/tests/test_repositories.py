from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def test_create_repository_success(client: TestClient):
    payload = {
        "url": "https://github.com/fastapi/fastapi",
        "default_branch": "master",
    }
    response = client.post("/api/repositories", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["url"] == "https://github.com/fastapi/fastapi"
    assert data["name"] == "fastapi/fastapi"
    assert data["default_branch"] == "master"
    assert data["source"] == "github"
    assert data["owner_id"] is None
    # Privacy flags must default to false
    assert data["allow_external_embeddings"] is False
    assert data["allow_external_llm"] is False
    assert "id" in data
    assert "created_at" in data


def test_create_repository_custom_name_and_flags(client: TestClient):
    payload = {
        "url": "https://github.com/tiangolo/typer.git",
        "name": "Custom Typer Name",
        "allow_external_embeddings": True,
        "allow_external_llm": True,
    }
    response = client.post("/api/repositories", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["name"] == "Custom Typer Name"
    assert data["url"] == "https://github.com/tiangolo/typer"
    assert data["allow_external_embeddings"] is True
    assert data["allow_external_llm"] is True


def test_create_repository_bad_urls(client: TestClient):
    bad_urls = [
        "https://gitlab.com/owner/repo",
        "https://google.com",
        "https://github.com/onlyowner",
        "https://github.com/owner/repo/extra/path",
        "not-a-url",
        "https://github.com/invalid name/repo",
    ]

    for bad_url in bad_urls:
        response = client.post("/api/repositories", json={"url": bad_url})
        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "validation_error"


def test_get_repository_by_id(client: TestClient):
    create_res = client.post(
        "/api/repositories",
        json={"url": "https://github.com/pallets/flask"},
    )
    repo_id = create_res.json()["id"]

    get_res = client.get(f"/api/repositories/{repo_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == repo_id
    assert get_res.json()["name"] == "pallets/flask"


def test_get_repository_not_found(client: TestClient):
    random_id = uuid.uuid4()
    response = client.get(f"/api/repositories/{random_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "repository_not_found"


def test_patch_repository(client: TestClient):
    create_res = client.post(
        "/api/repositories",
        json={"url": "https://github.com/psf/requests"},
    )
    repo_id = create_res.json()["id"]

    patch_payload = {
        "default_branch": "develop",
        "allow_external_embeddings": True,
        "allow_external_llm": True,
    }
    patch_res = client.patch(f"/api/repositories/{repo_id}", json=patch_payload)
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["default_branch"] == "develop"
    assert data["allow_external_embeddings"] is True
    assert data["allow_external_llm"] is True

    # Check non-existent repository patch
    random_id = uuid.uuid4()
    patch_404 = client.patch(f"/api/repositories/{random_id}", json=patch_payload)
    assert patch_404.status_code == 404
    assert patch_404.json()["error"]["code"] == "repository_not_found"


def test_list_repositories_pagination(client: TestClient):
    # Create 3 repositories
    client.post("/api/repositories", json={"url": "https://github.com/org/repo-1"})
    client.post("/api/repositories", json={"url": "https://github.com/org/repo-2"})
    client.post("/api/repositories", json={"url": "https://github.com/org/repo-3"})

    # Page 1 with limit 2
    res_page1 = client.get("/api/repositories?limit=2")
    assert res_page1.status_code == 200
    page1_data = res_page1.json()
    assert len(page1_data["items"]) == 2
    assert page1_data["next_cursor"] is not None

    # Page 2 using cursor
    cursor = page1_data["next_cursor"]
    res_page2 = client.get(f"/api/repositories?limit=2&cursor={cursor}")
    assert res_page2.status_code == 200
    page2_data = res_page2.json()
    assert len(page2_data["items"]) >= 1

    # Ensure items on page 2 do not overlap with page 1
    page1_ids = {item["id"] for item in page1_data["items"]}
    page2_ids = {item["id"] for item in page2_data["items"]}
    assert page1_ids.isdisjoint(page2_ids)
