"""
Demo 16: Container & Remote Plugin Isolation

Demonstrates Phase 3 container/remote plugin isolation:
  - Docker/Podman container configuration and command generation
  - Remote plugin registration and configuration
  - Factory pattern for isolation mode selection

Run: python3 demo/16_container_isolation.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.container_isolation import (
    ContainerPluginConfig, RemotePlugin, ContainerIsolationFactory,
)


def main():
    print("=" * 60)
    print("  DEMO 16: Container & Remote Plugin Isolation")
    print("=" * 60)

    # ── 1. Docker Container Configuration ──
    print("\n🐳 1. Docker Container Plugin")

    docker_config = ContainerPluginConfig(
        plugin_id="code-agent",
        image="zelos/python-agent:3.12",
        runtime="docker",
        command=["python", "-m", "zelos_agent", "--mode", "worker"],
        env={
            "ZELOS_API_KEY": "zelos_***",
            "LOG_LEVEL": "info",
            "MAX_CONCURRENT_TASKS": "5",
        },
        mounts={
            "/var/run/docker.sock": "/var/run/docker.sock",
            "/data/output": "/app/output",
        },
        ports={8080: 8080},
        cpu_limit=2.0,
        memory_limit_mb=1024,
        network_mode="host",
        labels={"app": "zelos", "component": "code-agent"},
    )

    print(f"   Plugin: {docker_config.plugin_id}")
    print(f"   Image: {docker_config.image}")
    print(f"   CPU: {docker_config.cpu_limit} cores")
    print(f"   Memory: {docker_config.memory_limit_mb} MB")
    print(f"   Network: {docker_config.network_mode}")
    print(f"   Env vars: {list(docker_config.env.keys())}")
    print(f"   Mounts: {list(docker_config.mounts.keys())}")

    # Generate docker run command
    docker_cmd = docker_config.to_docker_command()
    print(f"\n   Equivalent command ({len(docker_cmd)} args):")
    print(f"   {' '.join(docker_cmd[:8])}...")

    # ── 2. Podman Configuration ──
    print("\n📦 2. Podman Container Plugin")
    podman_config = ContainerPluginConfig(
        plugin_id="browser-agent",
        image="zelos/browser-agent:latest",
        runtime="podman",
        env={"DISPLAY": ":99"},
        memory_limit_mb=2048,
        network_mode="slirp4netns",
    )
    print(f"   Plugin: {podman_config.plugin_id}")
    print(f"   Runtime: {podman_config.runtime}")
    print(f"   Image: {podman_config.image}")

    # ── 3. Remote Plugin Configuration ──
    print("\n🌐 3. Remote Plugin (HTTP-based)")

    remote1 = RemotePlugin(
        plugin_id="remote-codex-1",
        endpoint="https://agent-fleet.internal:8443",
        health_endpoint="/api/health",
        task_endpoint="/api/v1/execute",
        callback_url="https://zelos.internal:9876/api/callback",
        timeout_seconds=30.0,
        max_retries=3,
        retry_backoff_ms=2000,
    )

    print(f"   Plugin ID: {remote1.plugin_id}")
    print(f"   Endpoint: {remote1.endpoint}")
    print(f"   Health URL: {remote1.health_url}")
    print(f"   Task URL: {remote1.task_url}")
    print(f"   Timeout: {remote1.timeout_seconds}s")
    print(f"   Max retries: {remote1.max_retries}")
    print(f"   Retry backoff: {remote1.retry_backoff_ms}ms")

    remote2 = RemotePlugin(
        plugin_id="remote-data-analyst",
        endpoint="http://data-cluster:9090",
        timeout_seconds=120.0,
        max_retries=1,
    )
    print(f"\n   Plugin ID: {remote2.plugin_id}")
    print(f"   Endpoint: {remote2.endpoint}")
    print(f"   Timeout: {remote2.timeout_seconds}s (data analysis takes longer)")

    # ── 4. Factory Pattern ──
    print("\n🏭 4. Isolation Mode Factory")

    modes = ContainerIsolationFactory.list_modes()
    print(f"   Available modes: {', '.join(modes)}")

    # Create different isolation types
    docker_instance = ContainerIsolationFactory.create("docker", docker_config)
    print(f"   docker → {type(docker_instance).__name__} (runtime={docker_instance.runtime})")

    podman_instance = ContainerIsolationFactory.create("podman", podman_config)
    print(f"   podman → {type(podman_instance).__name__} (runtime={podman_instance.runtime})")

    remote_instance = ContainerIsolationFactory.create("remote", remote1)
    print(f"   remote → {type(remote_instance).__name__} (plugin_id={remote_instance.plugin_id})")

    print(f"\n{'=' * 60}")
    print(f"  Demo complete. Container isolation primitives working.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
