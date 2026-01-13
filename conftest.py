import pytest
import subprocess
from pathlib import Path



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

