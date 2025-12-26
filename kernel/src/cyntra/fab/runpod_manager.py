"""
RunPod Manager - Manage on-demand GPU pods for ComfyUI.

Provides pod lifecycle management (start/stop/status) and
SSH tunnel management for secure ComfyUI access.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

RUNPOD_GRAPHQL_URL = "https://api.runpod.io/graphql"


@dataclass
class RunPodConfig:
    """Configuration for RunPod manager."""

    api_key: str
    default_gpu_type: str = "NVIDIA GeForce RTX 4090"
    default_volume_gb: int = 100
    default_container_disk_gb: int = 20
    default_image: str = "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"
    ssh_key_path: str = "~/.ssh/id_ed25519"
    comfyui_port: int = 8188
    idle_timeout_minutes: int = 30

    @classmethod
    def from_env(cls) -> "RunPodConfig":
        """Create config from environment variables."""
        api_key = os.environ.get("RUNPOD_API_KEY", "")
        if not api_key:
            raise ValueError("RUNPOD_API_KEY environment variable not set")
        return cls(api_key=api_key)


@dataclass
class PodPort:
    """Port mapping for a RunPod pod."""

    ip: str
    private_port: int
    public_port: int
    port_type: str
    is_public: bool = False


@dataclass
class PodStatus:
    """Status of a RunPod pod."""

    id: str
    name: str
    status: str  # "running", "stopped", "starting", "unknown"
    gpu_type: str | None = None
    gpu_utilization: int | None = None
    memory_utilization: int | None = None
    uptime_seconds: int = 0
    ports: list[PodPort] = field(default_factory=list)
    ssh_command: str | None = None
    comfyui_url: str | None = None
    cost_per_hour: float = 0.0

    @property
    def is_running(self) -> bool:
        return self.status == "running"

    @property
    def is_stopped(self) -> bool:
        return self.status in ("stopped", "exited")


@dataclass
class TunnelInfo:
    """SSH tunnel information."""

    local_port: int
    remote_host: str
    remote_port: int
    ssh_host: str
    ssh_port: int
    process: subprocess.Popen | None = None
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def local_url(self) -> str:
        return f"http://localhost:{self.local_port}"


class RunPodError(Exception):
    """Base exception for RunPod errors."""

    pass


class RunPodAuthError(RunPodError):
    """Authentication failed."""

    pass


class RunPodAPIError(RunPodError):
    """API request failed."""

    pass


class RunPodManager:
    """
    Manage RunPod GPU pods for ComfyUI workflows.

    Supports:
    - Listing pods and their status
    - Starting/stopping pods
    - Creating new pods with ComfyUI setup
    - SSH tunnel management for secure access

    Example:
        config = RunPodConfig.from_env()
        manager = RunPodManager(config)

        pods = await manager.list_pods()
        if not pods:
            pod = await manager.create_pod("comfyui-server")

        tunnel = await manager.create_tunnel(pod.id)
        # ComfyUI now accessible at tunnel.local_url
    """

    # ComfyUI Docker image with CUDA support
    COMFYUI_IMAGE = "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"

    def __init__(self, config: RunPodConfig) -> None:
        self.config = config
        self._client: httpx.AsyncClient | None = None
        self._tunnels: dict[str, TunnelInfo] = {}

    async def __aenter__(self) -> "RunPodManager":
        await self._ensure_client()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        """Close manager and cleanup tunnels."""
        # Kill all tunnels
        for tunnel in self._tunnels.values():
            if tunnel.process and tunnel.process.poll() is None:
                tunnel.process.terminate()
                try:
                    tunnel.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    tunnel.process.kill()

        self._tunnels.clear()

        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _graphql(
        self, query: str, variables: dict | None = None, timeout: float | None = None
    ) -> dict[str, Any]:
        """Execute a GraphQL query.

        Args:
            query: GraphQL query string
            variables: Optional query variables
            timeout: Optional timeout override (default: 30s, pod creation: 120s)
        """
        client = await self._ensure_client()

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        # Use longer timeout for pod creation operations
        if timeout is None:
            timeout = 120.0 if "podFindAndDeployOnDemand" in query else 30.0

        # Use Authorization header instead of query string to avoid key exposure in logs
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }

        try:
            response = await client.post(
                RUNPOD_GRAPHQL_URL,
                json=payload,
                headers=headers,
                timeout=timeout,
            )

            if response.status_code == 401:
                raise RunPodAuthError("Invalid API key")

            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                errors = data["errors"]
                error_msg = errors[0].get("message", "Unknown error") if errors else "Unknown error"
                raise RunPodAPIError(f"GraphQL error: {error_msg}")

            return data.get("data", {})

        except httpx.RequestError as e:
            raise RunPodAPIError(f"Request failed: {e}") from e

    async def list_pods(self) -> list[PodStatus]:
        """List all pods in your account."""
        query = """
        query Pods {
            myself {
                pods {
                    id
                    name
                    desiredStatus
                    runtime {
                        uptimeInSeconds
                        ports {
                            ip
                            isIpPublic
                            privatePort
                            publicPort
                            type
                        }
                        gpus {
                            id
                            gpuUtilPercent
                            memoryUtilPercent
                        }
                    }
                    machine {
                        gpuDisplayName
                    }
                    costPerHr
                }
            }
        }
        """

        data = await self._graphql(query)
        pods_data = data.get("myself", {}).get("pods", [])

        pods = []
        for pod in pods_data:
            runtime = pod.get("runtime") or {}
            ports = []

            for port in runtime.get("ports") or []:
                ports.append(
                    PodPort(
                        ip=port.get("ip", ""),
                        private_port=port.get("privatePort", 0),
                        public_port=port.get("publicPort", 0),
                        port_type=port.get("type", ""),
                        is_public=port.get("isIpPublic", False),
                    )
                )

            # Determine status
            desired = pod.get("desiredStatus", "").lower()
            if runtime and runtime.get("uptimeInSeconds", 0) > 0:
                status = "running"
            elif desired == "running":
                status = "starting"
            elif desired == "exited":
                status = "stopped"
            else:
                status = "unknown"

            # Get GPU utilization
            gpus = runtime.get("gpus") or []
            gpu_util = gpus[0].get("gpuUtilPercent") if gpus else None
            mem_util = gpus[0].get("memoryUtilPercent") if gpus else None

            # Build SSH command if we have SSH port
            ssh_port = None
            for port in ports:
                if port.private_port == 22:
                    ssh_port = port

            ssh_command = None
            if ssh_port:
                ssh_command = f"ssh root@{ssh_port.ip} -p {ssh_port.public_port} -i {self.config.ssh_key_path}"

            # Check for ComfyUI port
            comfyui_url = None
            for port in ports:
                if port.private_port == self.config.comfyui_port:
                    comfyui_url = f"http://{port.ip}:{port.public_port}"

            pods.append(
                PodStatus(
                    id=pod.get("id", ""),
                    name=pod.get("name", ""),
                    status=status,
                    gpu_type=pod.get("machine", {}).get("gpuDisplayName"),
                    gpu_utilization=gpu_util,
                    memory_utilization=mem_util,
                    uptime_seconds=runtime.get("uptimeInSeconds", 0),
                    ports=ports,
                    ssh_command=ssh_command,
                    comfyui_url=comfyui_url,
                    cost_per_hour=pod.get("costPerHr", 0.0),
                )
            )

        return pods

    async def get_pod(self, pod_id: str) -> PodStatus | None:
        """Get status of a specific pod."""
        pods = await self.list_pods()
        for pod in pods:
            if pod.id == pod_id:
                return pod
        return None

    async def start_pod(self, pod_id: str, gpu_count: int = 1) -> PodStatus:
        """Start a stopped pod."""
        query = """
        mutation PodResume($podId: String!, $gpuCount: Int!) {
            podResume(input: {podId: $podId, gpuCount: $gpuCount}) {
                id
                desiredStatus
            }
        }
        """

        data = await self._graphql(query, {"podId": pod_id, "gpuCount": gpu_count})
        result = data.get("podResume", {})

        if not result.get("id"):
            raise RunPodAPIError(f"Failed to start pod {pod_id}")

        logger.info("Started pod", pod_id=pod_id)

        # Poll until running
        return await self._wait_for_status(pod_id, "running", timeout=300)

    async def stop_pod(self, pod_id: str) -> PodStatus:
        """Stop a running pod."""
        # Kill any tunnels first
        if pod_id in self._tunnels:
            tunnel = self._tunnels[pod_id]
            if tunnel.process and tunnel.process.poll() is None:
                tunnel.process.terminate()
            del self._tunnels[pod_id]

        query = """
        mutation PodStop($podId: String!) {
            podStop(input: {podId: $podId}) {
                id
                desiredStatus
            }
        }
        """

        data = await self._graphql(query, {"podId": pod_id})
        result = data.get("podStop", {})

        if not result.get("id"):
            raise RunPodAPIError(f"Failed to stop pod {pod_id}")

        logger.info("Stopped pod", pod_id=pod_id)

        # Return current status
        pod = await self.get_pod(pod_id)
        if pod:
            return pod

        return PodStatus(id=pod_id, name="", status="stopped")

    async def create_pod(
        self,
        name: str,
        gpu_type: str | None = None,
        volume_gb: int | None = None,
        image: str | None = None,
        env: dict[str, str] | None = None,
    ) -> PodStatus:
        """
        Create a new pod with ComfyUI pre-installed.

        Args:
            name: Pod name
            gpu_type: GPU type ID (default: RTX 4090)
            volume_gb: Volume size in GB
            image: Docker image
            env: Environment variables
        """
        gpu_type = gpu_type or self.config.default_gpu_type
        volume_gb = volume_gb or self.config.default_volume_gb
        image = image or self.config.default_image

        # Build environment variables
        env_list = []
        if env:
            for key, value in env.items():
                env_list.append({"key": key, "value": value})

        query = """
        mutation CreatePod($input: PodFindAndDeployOnDemandInput!) {
            podFindAndDeployOnDemand(input: $input) {
                id
                name
                imageName
                machineId
            }
        }
        """

        variables = {
            "input": {
                "cloudType": "ALL",
                "gpuCount": 1,
                "volumeInGb": volume_gb,
                "containerDiskInGb": self.config.default_container_disk_gb,
                "minVcpuCount": 4,
                "minMemoryInGb": 16,
                "gpuTypeId": gpu_type,
                "name": name,
                "imageName": image,
                "ports": "22/tcp,8188/http,8888/http",
                "volumeMountPath": "/workspace",
                "env": env_list,
            }
        }

        data = await self._graphql(query, variables)
        result = data.get("podFindAndDeployOnDemand", {})

        if not result.get("id"):
            raise RunPodAPIError("Failed to create pod")

        pod_id = result["id"]
        logger.info("Created pod", pod_id=pod_id, name=name, gpu_type=gpu_type)

        # Wait for pod to be ready
        return await self._wait_for_status(pod_id, "running", timeout=600)

    async def _wait_for_status(
        self, pod_id: str, target_status: str, timeout: int = 300
    ) -> PodStatus:
        """Wait for pod to reach target status."""
        start = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed >= timeout:
                raise RunPodAPIError(
                    f"Timeout waiting for pod {pod_id} to reach {target_status}"
                )

            pod = await self.get_pod(pod_id)
            if pod and pod.status == target_status:
                return pod

            await asyncio.sleep(5)

    async def create_tunnel(
        self,
        pod_id: str,
        local_port: int = 8188,
        remote_port: int = 8188,
    ) -> TunnelInfo:
        """
        Create an SSH tunnel to a pod.

        Args:
            pod_id: Pod ID
            local_port: Local port to forward to
            remote_port: Remote port on pod (ComfyUI default: 8188)

        Returns:
            TunnelInfo with connection details
        """
        # Check if tunnel already exists
        if pod_id in self._tunnels:
            tunnel = self._tunnels[pod_id]
            if tunnel.process and tunnel.process.poll() is None:
                return tunnel
            # Tunnel died, clean up
            del self._tunnels[pod_id]

        # Get pod info
        pod = await self.get_pod(pod_id)
        if not pod or not pod.is_running:
            raise RunPodAPIError(f"Pod {pod_id} is not running")

        # Find SSH port
        ssh_port = None
        for port in pod.ports:
            if port.private_port == 22:
                ssh_port = port
                break

        if not ssh_port:
            raise RunPodAPIError(f"Pod {pod_id} has no SSH port exposed")

        # Validate and expand SSH key path
        ssh_key = Path(self.config.ssh_key_path).expanduser()
        if not ssh_key.exists():
            raise RunPodAPIError(f"SSH key not found: {ssh_key}")
        if not ssh_key.is_file():
            raise RunPodAPIError(f"SSH key is not a file: {ssh_key}")
        # Check for overly permissive key permissions (security warning)
        try:
            stat_info = ssh_key.stat()
            if stat_info.st_mode & 0o077:  # Check if group/other have any permissions
                logger.warning(
                    "SSH key has permissive permissions",
                    path=str(ssh_key),
                    mode=oct(stat_info.st_mode),
                    hint="Run: chmod 600 " + str(ssh_key),
                )
        except OSError:
            pass  # Skip permission check on platforms that don't support it

        # Build SSH command
        cmd = [
            "ssh",
            "-f",  # Background
            "-N",  # No command
            "-L", f"{local_port}:localhost:{remote_port}",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ServerAliveInterval=60",
            "-i", str(ssh_key),
            "-p", str(ssh_port.public_port),
            f"root@{ssh_port.ip}",
        ]

        logger.info(
            "Creating SSH tunnel",
            pod_id=pod_id,
            local_port=local_port,
            remote_port=remote_port,
            ssh_host=ssh_port.ip,
            ssh_port=ssh_port.public_port,
        )

        # Start tunnel
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Wait a moment for connection
            await asyncio.sleep(2)

            exit_code = process.poll()
            if exit_code is not None:
                # Process exited - check if it's an error
                _, stderr = process.communicate()
                stderr_text = stderr.decode()

                # Check for errors in stderr (even with exit code 0)
                error_indicators = [
                    "Address already in use",
                    "Could not request local forwarding",
                    "Connection refused",
                    "Permission denied",
                    "Host key verification failed",
                ]

                has_error = any(ind in stderr_text for ind in error_indicators)

                if has_error or exit_code != 0:
                    # Filter out non-error messages for error reporting
                    error_lines = [
                        line for line in stderr_text.strip().split('\n')
                        if line and not line.startswith('Warning:')
                    ]

                    if error_lines:
                        raise RunPodAPIError(f"SSH tunnel failed: {' '.join(error_lines)}")

                # SSH with -f backgrounds itself - exit code 0 with no errors is success
                if exit_code == 0:
                    logger.debug("SSH process exited after backgrounding")

            tunnel = TunnelInfo(
                local_port=local_port,
                remote_host="localhost",
                remote_port=remote_port,
                ssh_host=ssh_port.ip,
                ssh_port=ssh_port.public_port,
                process=process,
            )

            # Verify tunnel works by testing connection to ComfyUI
            tunnel_verified = await self._verify_tunnel(tunnel, retries=5, delay=1.0)

            if not tunnel_verified:
                # Cleanup failed tunnel
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                raise RunPodAPIError(
                    f"SSH tunnel created but ComfyUI unreachable at localhost:{local_port}. "
                    "Check if ComfyUI is running on the pod."
                )

            self._tunnels[pod_id] = tunnel

            logger.info(
                "SSH tunnel created and verified",
                pod_id=pod_id,
                local_url=tunnel.local_url,
            )

            return tunnel

        except RunPodAPIError:
            raise
        except Exception as e:
            raise RunPodAPIError(f"Failed to create tunnel: {e}") from e

    async def _verify_tunnel(
        self, tunnel: TunnelInfo, retries: int = 5, delay: float = 1.0
    ) -> bool:
        """Verify tunnel is working by checking ComfyUI endpoint.

        Args:
            tunnel: Tunnel info to verify
            retries: Number of retry attempts
            delay: Delay between retries in seconds

        Returns:
            True if tunnel is verified working, False otherwise
        """
        client = await self._ensure_client()

        for attempt in range(retries):
            try:
                response = await client.get(
                    f"http://localhost:{tunnel.local_port}/system_stats",
                    timeout=2.0,
                )
                if response.status_code == 200:
                    logger.debug(
                        "Tunnel verified",
                        local_port=tunnel.local_port,
                        attempt=attempt + 1,
                    )
                    return True
            except Exception:
                pass

            if attempt < retries - 1:
                await asyncio.sleep(delay)

        return False

    def get_tunnel(self, pod_id: str) -> TunnelInfo | None:
        """Get existing tunnel for a pod."""
        tunnel = self._tunnels.get(pod_id)
        if tunnel and tunnel.process and tunnel.process.poll() is None:
            return tunnel
        return None

    async def ensure_tunnel(self, pod_id: str) -> TunnelInfo:
        """Ensure a tunnel exists for a pod, creating one if needed."""
        tunnel = self.get_tunnel(pod_id)
        if tunnel:
            return tunnel
        return await self.create_tunnel(pod_id)

    async def get_available_gpus(self) -> list[dict[str, Any]]:
        """Get list of available GPU types with pricing."""
        query = """
        query GpuTypes {
            gpuTypes {
                id
                displayName
                memoryInGb
                secureCloud
                communityCloud
                lowestPrice(input: {gpuCount: 1}) {
                    minimumBidPrice
                    uninterruptablePrice
                    stockStatus
                }
            }
        }
        """

        data = await self._graphql(query)
        gpu_types = data.get("gpuTypes", [])

        # Filter to available GPUs
        available = []
        for gpu in gpu_types:
            price = gpu.get("lowestPrice", {})
            if price.get("stockStatus") in ("High", "Medium", "Low"):
                available.append(
                    {
                        "id": gpu.get("id"),
                        "name": gpu.get("displayName"),
                        "memory_gb": gpu.get("memoryInGb"),
                        "on_demand_price": price.get("uninterruptablePrice"),
                        "spot_price": price.get("minimumBidPrice"),
                        "stock": price.get("stockStatus"),
                        "secure_cloud": gpu.get("secureCloud"),
                    }
                )

        return sorted(available, key=lambda x: x.get("on_demand_price", 999))

    def get_reconnect_command(self, pod_id: str) -> str | None:
        """Get command to manually reconnect SSH tunnel."""
        tunnel = self._tunnels.get(pod_id)
        if not tunnel:
            return None

        ssh_key = Path(self.config.ssh_key_path).expanduser()
        return (
            f"ssh -f -N -L {tunnel.local_port}:localhost:{tunnel.remote_port} "
            f"-i {ssh_key} -p {tunnel.ssh_port} root@{tunnel.ssh_host}"
        )
