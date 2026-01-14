import pytest
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple


class GitRepository:
    """Helper class to manage Git repository operations."""

    def __init__(self, path: Path, is_bare: bool = False):
        self.path = path
        self.is_bare = is_bare

    def run(self, *args: str, check: bool = True, capture_output: bool = True) -> subprocess.CompletedProcess:
        """Run a git command in this repository."""
        cmd = ["git"] + list(args)
        return subprocess.run(
            cmd,
            cwd=self.path,
            check=check,
            capture_output=capture_output,
            text=True
        )

    def init(self, bare: bool = False) -> None:
        """Initialize the repository."""
        args = ["init"]
        if bare:
            args.append("--bare")
        self.run(*args)

        # Configure user for commits (required for non-bare repos)
        if not bare:
            self.run("config", "user.email", "test@example.com")
            self.run("config", "user.name", "Test User")

    def add(self, *files: str) -> subprocess.CompletedProcess:
        """Stage files."""
        return self.run("add", *files)

    def commit(self, message: str) -> subprocess.CompletedProcess:
        """Create a commit."""
        return self.run("commit", "-m", message)

    def push(self, remote: str = "origin", branch: str = "main", **kwargs) -> subprocess.CompletedProcess:
        """Push to remote."""
        return self.run("push", remote, branch, **kwargs)

    def pull(self, remote: str = "origin", branch: str = "main", **kwargs) -> subprocess.CompletedProcess:
        """Pull from remote."""
        return self.run("pull", remote, branch, **kwargs)

    def fetch(self, remote: str = "origin", **kwargs) -> subprocess.CompletedProcess:
        """Fetch from remote."""
        return self.run("fetch", remote, **kwargs)

    def clone_to(self, dest: Path) -> "GitRepository":
        """Clone this repository to a new location."""
        subprocess.run(
            ["git", "clone", str(self.path), str(dest)],
            check=True,
            capture_output=True,
            text=True
        )
        cloned = GitRepository(dest)
        cloned.run("config", "user.email", "test@example.com")
        cloned.run("config", "user.name", "Test User")
        return cloned

    def get_head_commit(self) -> str:
        """Get the current HEAD commit hash."""
        result = self.run("rev-parse", "HEAD")
        return result.stdout.strip()

    def get_branch(self) -> str:
        """Get current branch name."""
        result = self.run("branch", "--show-current")
        return result.stdout.strip()

    def create_file(self, name: str, content: str) -> Path:
        """Create a file in the repository."""
        file_path = self.path / name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        return file_path

    def read_file(self, name: str) -> str:
        """Read a file from the repository."""
        return (self.path / name).read_text()


@pytest.fixture
def temp_dir() -> Path:
    """Provide a temporary directory that is cleaned up after the test."""
    tmp = Path(tempfile.mkdtemp())
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def git_repo(temp_dir: Path) -> GitRepository:
    """Provide an initialized (non-bare) Git repository."""
    repo_path = temp_dir / "repo"
    repo_path.mkdir()
    repo = GitRepository(repo_path)
    repo.init()
    return repo


@pytest.fixture
def bare_repo(temp_dir: Path) -> GitRepository:
    """Provide an initialized bare Git repository."""
    repo_path = temp_dir / "bare_repo.git"
    repo_path.mkdir()
    repo = GitRepository(repo_path, is_bare=True)
    repo.init(bare=True)
    return repo


@pytest.fixture
def client_server_setup(temp_dir: Path) -> Tuple[GitRepository, GitRepository, GitRepository]:
    """
    Provide a server (bare repo) and two clients with an initial commit.

    Returns:
        Tuple of (server, client1, client2) GitRepository instances.
        - server: bare repository acting as the remote
        - client1: first client clone with origin pointing to server
        - client2: second client clone with origin pointing to server
    """
    server_path = temp_dir / "server.git"
    server_path.mkdir()
    server = GitRepository(server_path, is_bare=True)
    server.init(bare=True)

    client1_path = temp_dir / "client1"
    client1_path.mkdir()
    client1 = GitRepository(client1_path)
    client1.init()
    client1.create_file("initial.txt", "initial content")
    client1.add("initial.txt")
    client1.commit("Initial commit")
    client1.run("remote", "add", "origin", str(server.path))
    branch = client1.get_branch()
    client1.run("push", "-u", "origin", branch)

    client2_path = temp_dir / "client2"
    client2 = server.clone_to(client2_path)

    return server, client1, client2
