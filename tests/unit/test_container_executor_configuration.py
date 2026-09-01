import pytest

from packages.replay.src.executor import ContainerReplayExecutor


@pytest.mark.parametrize(
    "image",
    [
        "",
        "driftguard-sandbox:latest",
        "python:3.11-slim",
        "registry.example/replay@sha256:not-a-digest",
    ],
)
def test_container_executor_rejects_mutable_or_invalid_images(image: str) -> None:
    with pytest.raises(ValueError, match="pinned"):
        ContainerReplayExecutor(image=image)
