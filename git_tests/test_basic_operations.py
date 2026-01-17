import random
import string

import pytest
import subprocess
from pathlib import Path


class TestGitInit:
    """Tests for git init command."""

    def test_init_creates_git_directory(self, temp_dir: Path):
        repo_path = temp_dir / "new_repo"
        repo_path.mkdir()

        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)

        assert (repo_path / ".git").exists()
        assert (repo_path / ".git").is_dir()

    def test_init_creates_required_subdirectories(self, temp_dir: Path):
        repo_path = temp_dir / "new_repo"
        repo_path.mkdir()

        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)

        git_dir = repo_path / ".git"
        assert (git_dir / "objects").is_dir()
        assert (git_dir / "refs").is_dir()
        assert (git_dir / "refs" / "heads").is_dir()
        assert (git_dir / "HEAD").is_file()

    def test_init_bare_repository(self, temp_dir: Path):
        repo_path = temp_dir / "bare_repo.git"
        repo_path.mkdir()

        subprocess.run(
            ["git", "init", "--bare"],
            cwd=repo_path,
            check=True,
            capture_output=True
        )

        assert (repo_path / "objects").is_dir()
        assert (repo_path / "refs").is_dir()
        assert (repo_path / "HEAD").is_file()
        assert not (repo_path / ".git").exists()


class TestGitAdd:
    """Tests for git add command."""

    def test_add_single_file(self, git_repo):
        git_repo.create_file("test.txt", "Hello, World!")

        result = git_repo.add("test.txt")
        assert result.returncode == 0

        status = git_repo.run("status", "--porcelain")
        assert "A  test.txt" in status.stdout

    def test_add_single_file_with_special_chars(self, git_repo):
        file_name = "+)'?$>%!.txt"

        git_repo.create_file(file_name, "Hello, World!")

        result = git_repo.add(file_name)
        assert result.returncode == 0

        status = git_repo.run("status", "--porcelain")
        assert file_name in status.stdout

    def test_add_multiple_files(self, git_repo):
        git_repo.create_file("file1.txt", "Content 1")
        git_repo.create_file("file2.txt", "Content 2")
        git_repo.create_file("file3.txt", "Content 3")

        result = git_repo.add("file1.txt", "file2.txt", "file3.txt")
        assert result.returncode == 0

        status = git_repo.run("status", "--porcelain")
        assert "A  file1.txt" in status.stdout
        assert "A  file2.txt" in status.stdout
        assert "A  file3.txt" in status.stdout

    def test_add_all_with_dot(self, git_repo):
        git_repo.create_file("file1.txt", "1")
        git_repo.create_file("dir/file2.txt", "2")

        result = git_repo.add(".")
        assert result.returncode == 0

        status = git_repo.run("status", "--porcelain")
        assert "A  file1.txt" in status.stdout
        assert "A  dir/file2.txt" in status.stdout

    def test_add_nonexistent_file_fails(self, git_repo):
        result = git_repo.run("add", "nonexistent.txt", check=False)
        assert result.returncode != 0


class TestGitCommit:
    """Tests for git commit command."""

    def test_commit_creates_commit_object(self, git_repo):
        git_repo.create_file("test.txt", "Hello")
        git_repo.add("test.txt")

        result = git_repo.commit("Initial commit")
        assert result.returncode == 0

        log = git_repo.run("log", "--oneline")
        assert "Initial commit" in log.stdout

    def test_commit_without_staged_changes_fails(self, git_repo):
        git_repo.create_file("init.txt", "init")
        git_repo.add("init.txt")
        git_repo.commit("Initial commit")

        result = git_repo.run("commit", "-m", "Empty commit", check=False)
        assert result.returncode != 0

    def test_commit_message_stored_correctly(self, git_repo):
        git_repo.create_file("test.txt", "content")
        git_repo.add("test.txt")

        message = "Test commit with specific message"
        git_repo.commit(message)

        log = git_repo.run("log", "-1", "--format=%s")
        assert log.stdout.strip() == message


class TestGitStatus:
    """Tests for git status command."""

    def test_status_shows_untracked_files(self, git_repo):
        git_repo.create_file("untracked.txt", "content")

        result = git_repo.run("status")
        assert "untracked.txt" in result.stdout
        assert "Untracked files" in result.stdout

    def test_status_shows_staged_files(self, git_repo):
        git_repo.create_file("staged.txt", "content")
        git_repo.add("staged.txt")

        result = git_repo.run("status")
        assert "staged.txt" in result.stdout
        assert "Changes to be committed" in result.stdout

    def test_status_shows_modified_files(self, git_repo):
        git_repo.create_file("file.txt", "original")
        git_repo.add("file.txt")
        git_repo.commit("Add file")

        git_repo.create_file("file.txt", "modified")

        result = git_repo.run("status")
        assert "modified:" in result.stdout
        assert "file.txt" in result.stdout


class TestGitBranch:
    """Tests for git branch operations."""

    def test_default_branch_exists(self, git_repo):
        git_repo.create_file("test.txt", "content")
        git_repo.add("test.txt")
        git_repo.commit("Initial commit")

        branch = git_repo.get_branch()
        assert branch in ["main", "master", "develop"]

    def test_create_new_branch(self, git_repo):
        git_repo.create_file("test.txt", "content")
        git_repo.add("test.txt")
        git_repo.commit("Initial commit")

        result = git_repo.run("branch", "feature")
        assert result.returncode == 0

        branches = git_repo.run("branch", "--list")
        assert "feature" in branches.stdout

    def test_switch_branch(self, git_repo):
        git_repo.create_file("test.txt", "content")
        git_repo.add("test.txt")
        git_repo.commit("Initial commit")

        git_repo.run("branch", "feature")
        git_repo.run("checkout", "feature")

        current = git_repo.get_branch()
        assert current == "feature"