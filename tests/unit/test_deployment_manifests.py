import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SHA256_IMAGE = re.compile(r"^.+@sha256:([0-9a-f]{64})$")


def _documents(name: str) -> list[dict]:
    path = ROOT / "deploy" / "k8s" / name
    return [document for document in yaml.safe_load_all(path.read_text()) if document]


def _pod_spec(document: dict) -> dict:
    if document["kind"] == "Job":
        return document["spec"]["template"]["spec"]
    return document["spec"]["template"]["spec"]


def test_application_images_are_digest_pinned_and_security_hardened():
    for filename in (
        "api-deployment.yaml",
        "worker-deployment.yaml",
        "web-deployment.yaml",
        "migration-job.yaml",
    ):
        workload = _documents(filename)[0]
        pod = _pod_spec(workload)
        assert pod["securityContext"]["runAsNonRoot"] is True
        assert pod["securityContext"]["seccompProfile"]["type"] == "RuntimeDefault"
        container = pod["containers"][0]
        assert SHA256_IMAGE.fullmatch(container["image"])
        assert container["securityContext"]["allowPrivilegeEscalation"] is False
        assert container["securityContext"]["capabilities"]["drop"] == ["ALL"]


def test_runtime_ids_match_container_users_and_api_records_image_identity():
    api = _pod_spec(_documents("api-deployment.yaml")[0])
    worker = _pod_spec(_documents("worker-deployment.yaml")[0])
    migration = _pod_spec(_documents("migration-job.yaml")[0])
    web = _pod_spec(_documents("web-deployment.yaml")[0])

    for pod in (api, worker, migration):
        assert pod["securityContext"]["runAsUser"] == 10001
        assert pod["securityContext"]["runAsGroup"] == 10001
    assert web["securityContext"]["runAsUser"] == 1001
    assert web["securityContext"]["runAsGroup"] == 1001

    api_container = api["containers"][0]
    image_digest = api_container["image"].rsplit("@", 1)[1]
    digest_env = {item["name"]: item["value"] for item in api_container["env"]}
    assert digest_env["DGX_CONTAINER_IMAGE_DIGEST"] == image_digest


def test_worker_and_api_have_real_readiness_and_liveness_probes():
    api_container = _pod_spec(_documents("api-deployment.yaml")[0])["containers"][0]
    worker_container = _pod_spec(_documents("worker-deployment.yaml")[0])["containers"][0]

    assert api_container["readinessProbe"]["httpGet"]["path"] == "/ready"
    assert api_container["livenessProbe"]["httpGet"]["path"] == "/health"
    assert "startupProbe" in worker_container
    assert "readinessProbe" in worker_container
    assert "livenessProbe" in worker_container


def test_postgres_major_version_matches_compose():
    postgres = _documents("postgres.yaml")[0]
    image = _pod_spec(postgres)["containers"][0]["image"]
    assert image == "postgres:16-alpine"
