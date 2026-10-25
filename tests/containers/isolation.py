"""Validate Docker inspection metadata before sending any destructive test request."""


def test_instance_url(metadata: dict, project: str) -> str:
    labels = metadata["Config"]["Labels"]
    if (
        labels.get("io.pax0r.listkeeper.test-instance") != "true"
        or labels.get("com.docker.compose.project") != project
        or labels.get("com.docker.compose.service") != "homeassistant"
    ):
        raise ValueError("Refusing a container not owned by this test project")
    bindings = metadata["NetworkSettings"]["Ports"]["8123/tcp"]
    if len(bindings) != 1 or bindings[0]["HostIp"] != "127.0.0.1":
        raise ValueError("Test HA must be exposed only on loopback")
    port = int(bindings[0]["HostPort"])
    if not 1 <= port <= 65535:
        raise ValueError("Invalid container port")
    return f"http://127.0.0.1:{port}"
