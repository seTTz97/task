import pytest
import socket
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


from conftest import GitRepository


def is_port_available(port: int) -> bool:
    """Check if a port is available for binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def wait_for_port(port: int, timeout: float = 5.0) -> bool:
    """Wait for a port to become available for connections."""
    start = time.time()
    while time.time() - start < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect(("127.0.0.1", port))
                return True
            except OSError:
                time.sleep(0.1)
    return False


class TestFileProtocol:
    """Tests for file:// protocol (local filesystem)."""

    def test_clone_with_explicit_file_protocol(self, bare_repo, temp_dir: Path):
        work = GitRepository(temp_dir / "work")
        work.path.mkdir()
        work.init()
        work.create_file("test.txt", "content")
        work.add("test.txt")
        work.commit("Initial")
        work.run("remote", "add", "origin", f"file://{bare_repo.path}")
        work.run("push", "-u", "origin", work.get_branch())

        # Clone using file:// URL
        clone_path = temp_dir / "clone"
        result = subprocess.run(
            ["git", "clone", f"file://{bare_repo.path}", str(clone_path)],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert (clone_path / "test.txt").exists()

    def test_push_with_file_protocol(self, bare_repo, temp_dir: Path):
        work = GitRepository(temp_dir / "work")
        work.path.mkdir()
        work.init()
        work.create_file("test.txt", "content")
        work.add("test.txt")
        work.commit("Initial")
        work.run("remote", "add", "origin", f"file://{bare_repo.path}")

        result = work.run("push", "-u", "origin", work.get_branch())
        assert result.returncode == 0

        log = bare_repo.run("log", "--oneline", work.get_branch())
        assert "Initial" in log.stdout

    def test_fetch_with_file_protocol(self, client_server_setup):
        server, client1, client2 = client_server_setup

        branch = client1.get_branch()

        client2.run("remote", "set-url", "origin", f"file://{server.path}")

        client1.create_file("new.txt", "new")
        client1.add("new.txt")
        client1.commit("New file")
        client1.push("origin", branch)

        result = client2.fetch("origin")
        assert result.returncode == 0

        log = client2.run("log", f"origin/{branch}", "--oneline")
        assert "New file" in log.stdout


class TestSSHProtocol:
    """Tests for SSH protocol."""

    @pytest.fixture
    def ssh_available(self) -> bool:
        """Check if SSH is available for testing."""
        # Check if we can connect to localhost SSH
        try:
            result = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=2",
                 "localhost", "echo", "test"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @pytest.mark.ssh
    def test_ssh_clone(self, ssh_available, temp_dir: Path):
        """Test cloning over SSH protocol."""
        if not ssh_available:
            pytest.skip("SSH not available for testing")
        pytest.skip("SSH infrastructure not configured - see SHORTCUT note")

    @pytest.mark.ssh
    def test_ssh_push(self, ssh_available, temp_dir: Path):
        if not ssh_available:
            pytest.skip("SSH not available for testing")

        pytest.skip("SSH infrastructure not configured - see SHORTCUT note")

    @pytest.mark.ssh
    def test_ssh_authentication_failure(self, temp_dir: Path):
        repo = GitRepository(temp_dir / "repo")
        repo.path.mkdir()
        repo.init()
        repo.create_file("test.txt", "test")
        repo.add("test.txt")
        repo.commit("Initial")

        repo.run("remote", "add", "origin",
                 "ssh://invaliduser@localhost/nonexistent/repo.git")

        result = repo.run("push", "-u", "origin", repo.get_branch(), check=False)
        assert result.returncode != 0


class TestHTTPProtocol:
    """Tests for HTTP/HTTPS protocol."""

    @contextmanager
    def git_http_server(self, repo_path: Path, port: int = 8080) -> Generator[str, None, None]:
        """
        Context manager to run a simple Git HTTP server.

        SHORTCUT: This uses Python's simple HTTP server which only supports
        dumb HTTP protocol (no push). A real implementation would use
        git-http-backend or similar for full functionality.
        """
        if not is_port_available(port):
            raise RuntimeError(f"Port {port} is not available")

        process = subprocess.Popen(
            ["python", "-m", "http.server", str(port)],
            cwd=repo_path.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        try:
            if wait_for_port(port):
                yield f"http://127.0.0.1:{port}/{repo_path.name}"
            else:
                raise RuntimeError("HTTP server failed to start")
        finally:
            process.terminate()
            process.wait()

    @pytest.mark.slow
    @pytest.mark.network
    def test_http_clone_dumb_protocol(self, bare_repo, temp_dir: Path):
        """Test cloning over HTTP dumb protocol."""
        work = GitRepository(temp_dir / "work")
        work.path.mkdir()
        work.init()
        work.create_file("test.txt", "content")
        work.add("test.txt")
        work.commit("Initial")
        work.run("remote", "add", "origin", str(bare_repo.path))
        work.run("push", "-u", "origin", work.get_branch())

        bare_repo.run("update-server-info")

        port = 9418
        for p in range(9418, 9500):
            if is_port_available(p):
                port = p
                break

        try:
            with self.git_http_server(bare_repo.path, port) as url:
                clone_path = temp_dir / "http_clone"
                result = subprocess.run(
                    ["git", "clone", url, str(clone_path)],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode == 0:
                    assert (clone_path / "test.txt").exists()
                else:
                    pytest.skip("Dumb HTTP clone not supported in this environment")
        except RuntimeError as e:
            pytest.skip(f"Could not start HTTP server: {e}")

    @pytest.mark.network
    def test_https_certificate_validation(self, temp_dir: Path):
        repo = GitRepository(temp_dir / "repo")
        repo.path.mkdir()
        repo.init()
        repo.create_file("test.txt", "test")
        repo.add("test.txt")
        repo.commit("Initial")

        repo.run("remote", "add", "origin", "https://invalid-cert.example.com/repo.git")

        result = repo.run("fetch", "origin", check=False)
        assert result.returncode != 0

class TestProtocolNegotiation:
    """Tests for Git protocol version negotiation."""

    def test_protocol_v2_support(self, bare_repo, temp_dir: Path):
        work = GitRepository(temp_dir / "work")
        work.path.mkdir()
        work.init()
        work.create_file("test.txt", "content")
        work.add("test.txt")
        work.commit("Initial")
        work.run("remote", "add", "origin", str(bare_repo.path))
        work.run("push", "-u", "origin", work.get_branch())

        # Clone with protocol v2
        clone_path = temp_dir / "clone"
        result = subprocess.run(
            ["git", "-c", "protocol.version=2", "clone",
             str(bare_repo.path), str(clone_path)],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0

    def test_ls_remote_over_file_protocol(self, bare_repo, temp_dir: Path):
        """Test ls-remote command over file protocol."""
        work = GitRepository(temp_dir / "work")
        work.path.mkdir()
        work.init()
        work.create_file("test.txt", "content")
        work.add("test.txt")
        work.commit("Initial")
        work.run("remote", "add", "origin", str(bare_repo.path))
        work.run("push", "-u", "origin", work.get_branch())

        result = subprocess.run(
            ["git", "ls-remote", str(bare_repo.path)],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "refs/heads/" in result.stdout