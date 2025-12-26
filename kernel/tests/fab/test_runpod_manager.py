"""
Tests for RunPod manager.

Tests focus on:
- API key handling (not exposed in URLs)
- SSH key validation
- Tunnel verification
- Error handling
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from cyntra.fab.runpod_manager import (
    RunPodConfig,
    RunPodManager,
    RunPodError,
    RunPodAuthError,
    RunPodAPIError,
    PodStatus,
    PodPort,
    TunnelInfo,
)


class TestRunPodConfig:
    """Tests for RunPodConfig dataclass."""

    def test_default_values(self) -> None:
        config = RunPodConfig(api_key="test-key")
        assert config.api_key == "test-key"
        assert config.default_gpu_type == "NVIDIA GeForce RTX 4090"
        assert config.default_volume_gb == 100
        assert config.comfyui_port == 8188

    def test_from_env_missing_key(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="RUNPOD_API_KEY"):
                RunPodConfig.from_env()

    def test_from_env_with_key(self) -> None:
        with patch.dict("os.environ", {"RUNPOD_API_KEY": "my-api-key"}):
            config = RunPodConfig.from_env()
            assert config.api_key == "my-api-key"


class TestPodStatus:
    """Tests for PodStatus dataclass."""

    def test_is_running(self) -> None:
        running = PodStatus(id="1", name="test", status="running")
        stopped = PodStatus(id="2", name="test", status="stopped")

        assert running.is_running is True
        assert stopped.is_running is False

    def test_is_stopped(self) -> None:
        running = PodStatus(id="1", name="test", status="running")
        stopped = PodStatus(id="2", name="test", status="stopped")
        exited = PodStatus(id="3", name="test", status="exited")

        assert running.is_stopped is False
        assert stopped.is_stopped is True
        assert exited.is_stopped is True


class TestTunnelInfo:
    """Tests for TunnelInfo dataclass."""

    def test_local_url(self) -> None:
        tunnel = TunnelInfo(
            local_port=8188,
            remote_host="localhost",
            remote_port=8188,
            ssh_host="192.168.1.1",
            ssh_port=22,
        )
        assert tunnel.local_url == "http://localhost:8188"


class TestRunPodManagerAPIKey:
    """Tests for API key handling in RunPodManager."""

    @pytest.mark.asyncio
    async def test_api_key_in_header_not_url(self) -> None:
        """Verify API key is sent in Authorization header, not in URL query string."""
        config = RunPodConfig(api_key="secret-api-key")

        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"myself": {"pods": []}}}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.is_closed = False
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            async with RunPodManager(config) as manager:
                await manager.list_pods()

            # Verify the API call
            call_args = mock_client.post.call_args

            # Check URL does NOT contain API key
            url = call_args.args[0] if call_args.args else call_args.kwargs.get("url", "")
            assert "api_key" not in url
            assert "secret-api-key" not in url

            # Check headers DOES contain API key
            headers = call_args.kwargs.get("headers", {})
            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer secret-api-key"


class TestRunPodManagerSSHValidation:
    """Tests for SSH key validation in RunPodManager."""

    @pytest.mark.asyncio
    async def test_ssh_key_not_found_raises(self, tmp_path: Path) -> None:
        """SSH key file not found should raise error."""
        config = RunPodConfig(
            api_key="test",
            ssh_key_path=str(tmp_path / "nonexistent_key"),
        )

        # Mock list_pods to return a running pod
        mock_pod = PodStatus(
            id="pod-123",
            name="test",
            status="running",
            ports=[PodPort(ip="1.2.3.4", private_port=22, public_port=12345, port_type="tcp")],
        )

        with patch.object(RunPodManager, "list_pods", return_value=[mock_pod]):
            with patch.object(RunPodManager, "get_pod", return_value=mock_pod):
                manager = RunPodManager(config)
                manager._client = AsyncMock()
                manager._client.is_closed = False

                with pytest.raises(RunPodAPIError, match="SSH key not found"):
                    await manager.create_tunnel("pod-123")

    @pytest.mark.asyncio
    async def test_ssh_key_is_directory_raises(self, tmp_path: Path) -> None:
        """SSH key path is a directory should raise error."""
        ssh_dir = tmp_path / "ssh_dir"
        ssh_dir.mkdir()

        config = RunPodConfig(api_key="test", ssh_key_path=str(ssh_dir))

        mock_pod = PodStatus(
            id="pod-123",
            name="test",
            status="running",
            ports=[PodPort(ip="1.2.3.4", private_port=22, public_port=12345, port_type="tcp")],
        )

        with patch.object(RunPodManager, "get_pod", return_value=mock_pod):
            manager = RunPodManager(config)
            manager._client = AsyncMock()
            manager._client.is_closed = False

            with pytest.raises(RunPodAPIError, match="SSH key is not a file"):
                await manager.create_tunnel("pod-123")

    @pytest.mark.asyncio
    async def test_ssh_key_permissive_logs_warning(self, tmp_path: Path) -> None:
        """Permissive SSH key permissions should log a warning."""
        ssh_key = tmp_path / "id_rsa"
        ssh_key.touch()
        ssh_key.chmod(0o644)  # Permissive (should be 600)

        config = RunPodConfig(api_key="test", ssh_key_path=str(ssh_key))

        mock_pod = PodStatus(
            id="pod-123",
            name="test",
            status="running",
            ports=[PodPort(ip="1.2.3.4", private_port=22, public_port=12345, port_type="tcp")],
        )

        with patch.object(RunPodManager, "get_pod", return_value=mock_pod):
            with patch("subprocess.Popen") as mock_popen:
                # Mock subprocess to fail so we don't actually try to SSH
                mock_process = MagicMock()
                mock_process.poll.return_value = 1
                mock_process.communicate.return_value = (b"", b"Connection refused")
                mock_popen.return_value = mock_process

                with patch("structlog.get_logger") as mock_logger:
                    mock_log = MagicMock()
                    mock_logger.return_value = mock_log

                    manager = RunPodManager(config)
                    manager._client = AsyncMock()
                    manager._client.is_closed = False

                    # This will fail, but should have logged the warning
                    with pytest.raises(RunPodAPIError):
                        await manager.create_tunnel("pod-123")


class TestRunPodManagerTunnelVerification:
    """Tests for tunnel verification in RunPodManager."""

    @pytest.mark.asyncio
    async def test_verify_tunnel_success(self) -> None:
        """Test tunnel verification succeeds when endpoint responds."""
        config = RunPodConfig(api_key="test")
        manager = RunPodManager(config)

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get = AsyncMock(return_value=mock_response)
        manager._client = mock_client

        tunnel = TunnelInfo(
            local_port=8188,
            remote_host="localhost",
            remote_port=8188,
            ssh_host="1.2.3.4",
            ssh_port=22,
        )

        result = await manager._verify_tunnel(tunnel, retries=1)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_tunnel_retry_on_failure(self) -> None:
        """Test tunnel verification retries on connection failure."""
        config = RunPodConfig(api_key="test")
        manager = RunPodManager(config)

        # First two calls fail, third succeeds
        call_count = 0

        async def mock_get(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("Connection failed")
            response = MagicMock()
            response.status_code = 200
            return response

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get = mock_get
        manager._client = mock_client

        tunnel = TunnelInfo(
            local_port=8188,
            remote_host="localhost",
            remote_port=8188,
            ssh_host="1.2.3.4",
            ssh_port=22,
        )

        result = await manager._verify_tunnel(tunnel, retries=5, delay=0.01)
        assert result is True
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_verify_tunnel_all_retries_fail(self) -> None:
        """Test tunnel verification returns False after all retries fail."""
        config = RunPodConfig(api_key="test")
        manager = RunPodManager(config)

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Failed"))
        manager._client = mock_client

        tunnel = TunnelInfo(
            local_port=8188,
            remote_host="localhost",
            remote_port=8188,
            ssh_host="1.2.3.4",
            ssh_port=22,
        )

        result = await manager._verify_tunnel(tunnel, retries=3, delay=0.01)
        assert result is False


class TestRunPodManagerErrorHandling:
    """Tests for error handling in RunPodManager."""

    @pytest.mark.asyncio
    async def test_graphql_auth_error(self) -> None:
        """Test 401 response raises RunPodAuthError."""
        config = RunPodConfig(api_key="bad-key")

        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.is_closed = False
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            manager = RunPodManager(config)
            await manager._ensure_client()

            with pytest.raises(RunPodAuthError, match="Invalid API key"):
                await manager._graphql("query { test }")

    @pytest.mark.asyncio
    async def test_graphql_error_response(self) -> None:
        """Test GraphQL error in response raises RunPodAPIError."""
        config = RunPodConfig(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [{"message": "Rate limit exceeded"}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.is_closed = False
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            manager = RunPodManager(config)
            await manager._ensure_client()

            with pytest.raises(RunPodAPIError, match="Rate limit exceeded"):
                await manager._graphql("query { test }")

    @pytest.mark.asyncio
    async def test_pod_not_running_for_tunnel(self) -> None:
        """Test creating tunnel for stopped pod raises error."""
        config = RunPodConfig(api_key="test")

        stopped_pod = PodStatus(id="pod-123", name="test", status="stopped")

        with patch.object(RunPodManager, "get_pod", return_value=stopped_pod):
            manager = RunPodManager(config)
            manager._client = AsyncMock()
            manager._client.is_closed = False

            with pytest.raises(RunPodAPIError, match="not running"):
                await manager.create_tunnel("pod-123")

    @pytest.mark.asyncio
    async def test_pod_no_ssh_port(self) -> None:
        """Test creating tunnel for pod without SSH port raises error."""
        config = RunPodConfig(api_key="test")

        # Pod with ComfyUI port but no SSH port
        pod = PodStatus(
            id="pod-123",
            name="test",
            status="running",
            ports=[PodPort(ip="1.2.3.4", private_port=8188, public_port=8188, port_type="http")],
        )

        with patch.object(RunPodManager, "get_pod", return_value=pod):
            manager = RunPodManager(config)
            manager._client = AsyncMock()
            manager._client.is_closed = False

            with pytest.raises(RunPodAPIError, match="no SSH port"):
                await manager.create_tunnel("pod-123")


class TestRunPodManagerCleanup:
    """Tests for cleanup behavior in RunPodManager."""

    @pytest.mark.asyncio
    async def test_close_terminates_tunnels(self) -> None:
        """Test close() terminates all tunnel processes."""
        config = RunPodConfig(api_key="test")
        manager = RunPodManager(config)
        manager._client = AsyncMock()
        manager._client.is_closed = False
        manager._client.aclose = AsyncMock()

        # Create mock tunnel processes
        mock_process1 = MagicMock()
        mock_process1.poll.return_value = None  # Process is running
        mock_process1.wait = MagicMock()

        mock_process2 = MagicMock()
        mock_process2.poll.return_value = None
        mock_process2.wait = MagicMock()

        manager._tunnels = {
            "pod-1": TunnelInfo(
                local_port=8188, remote_host="localhost", remote_port=8188,
                ssh_host="1.1.1.1", ssh_port=22, process=mock_process1
            ),
            "pod-2": TunnelInfo(
                local_port=8189, remote_host="localhost", remote_port=8188,
                ssh_host="2.2.2.2", ssh_port=22, process=mock_process2
            ),
        }

        await manager.close()

        mock_process1.terminate.assert_called_once()
        mock_process2.terminate.assert_called_once()
        assert len(manager._tunnels) == 0

    @pytest.mark.asyncio
    async def test_stop_pod_kills_tunnel(self) -> None:
        """Test stop_pod() kills associated tunnel."""
        config = RunPodConfig(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"podStop": {"id": "pod-123", "desiredStatus": "EXITED"}}}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.is_closed = False
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock list_pods for get_pod call
            with patch.object(RunPodManager, "get_pod", return_value=PodStatus(id="pod-123", name="test", status="stopped")):
                manager = RunPodManager(config)
                await manager._ensure_client()

                # Add a tunnel
                mock_process = MagicMock()
                mock_process.poll.return_value = None
                manager._tunnels["pod-123"] = TunnelInfo(
                    local_port=8188, remote_host="localhost", remote_port=8188,
                    ssh_host="1.1.1.1", ssh_port=22, process=mock_process
                )

                await manager.stop_pod("pod-123")

                mock_process.terminate.assert_called_once()
                assert "pod-123" not in manager._tunnels
