import pytest
import subprocess
from pathlib import Path


class TestConnectionErrors:
    """Tests for connection-related errors."""

    def test_clone_nonexistent_repository(self, temp_dir: Path):
        clone_path = temp_dir / "clone"

        result = subprocess.run(
            ["git", "clone", "/nonexistent/path/to/repo.git", str(clone_path)],
            capture_output=True,
            text=True
        )

        assert result.returncode != 0
        stderr = result.stderr.lower()
        assert "not found" in stderr or "does not exist" in stderr or "fatal" in stderr

    def test_push_to_nonexistent_remote(self, git_repo):
        git_repo.create_file("test.txt", "content")
        git_repo.add("test.txt")
        git_repo.commit("Initial")

        git_repo.run("remote", "add", "origin", "/nonexistent/repo.git")

        result = git_repo.run("push", "origin", git_repo.get_branch(), check=False)
        assert result.returncode != 0

    def test_push_when_remote_removed(self, client_server_setup, temp_dir: Path):
        server, client1, _ = client_server_setup

        import shutil
        shutil.rmtree(server.path)

        client1.create_file("new.txt", "content")
        client1.add("new.txt")
        client1.commit("New commit")

        result = client1.run("push", "origin", client1.get_branch(), check=False)
        assert result.returncode != 0


class TestConflictScenarios:
    """Tests for merge conflict scenarios."""

    def test_merge_conflict_detection(self, client_server_setup):
        server, client1, client2 = client_server_setup

        branch = client1.get_branch()

        client1.create_file("shared.txt", "client1 content")
        client1.add("shared.txt")
        client1.commit("Client1 changes")
        client1.push("origin", branch)

        client2.create_file("shared.txt", "client2 content")
        client2.add("shared.txt")
        client2.commit("Client2 changes")

        result = client2.run("pull", "--no-rebase", "origin", branch, check=False)

        status = client2.run("status")
        has_conflict = (
            "CONFLICT" in result.stdout or
            "CONFLICT" in result.stderr or
            "Unmerged" in status.stdout or
            "both modified" in status.stdout.lower()
        )
        assert has_conflict or result.returncode != 0

    def test_conflict_markers_present(self, client_server_setup):
        """Verify conflict markers are added to conflicting files."""
        server, client1, client2 = client_server_setup

        branch = client1.get_branch()

        client1.create_file("conflict.txt", "line1\noriginal\nline3")
        client1.add("conflict.txt")
        client1.commit("Client1 version")
        client1.push("origin", branch)

        client2.create_file("conflict.txt", "line1\nmodified\nline3")
        client2.add("conflict.txt")
        client2.commit("Client2 version")

        client2.run("pull", "--no-rebase", "origin", branch, check=False)

        content = client2.read_file("conflict.txt")

        assert "<<<<<<" in content, "Expected conflict markers in file"
        assert "=======" in content
        assert ">>>>>>>" in content


class TestEdgeCases:
    """Tests for edge cases and unusual scenarios."""

    def test_empty_repository_clone(self, temp_dir: Path):
        empty_bare = temp_dir / "empty.git"
        empty_bare.mkdir()
        subprocess.run(["git", "init", "--bare"], cwd=empty_bare, check=True, capture_output=True)

        clone_path = temp_dir / "empty_clone"
        result = subprocess.run(
            ["git", "clone", str(empty_bare), str(clone_path)],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert (clone_path / ".git").exists()
        assert "empty" in result.stderr.lower() or "warning" in result.stderr.lower() or result.returncode == 0

    def test_large_commit_message(self, client_server_setup):
        server, client1, client2 = client_server_setup

        branch = client1.get_branch()

        large_message = "A" * 10000
        client1.create_file("large_msg.txt", "content")
        client1.add("large_msg.txt")
        client1.commit(large_message)
        client1.push("origin", branch)

        client2.pull("origin", branch)
        log = client2.run("log", "-1", "--format=%B")
        assert large_message in log.stdout

    def test_special_characters_in_filenames(self, client_server_setup):
        server, client1, client2 = client_server_setup

        branch = client1.get_branch()

        special_files = [
            "file with spaces.txt",
            "file-with-dashes.txt",
            "file_with_underscores.txt",
            "file.multiple.dots.txt",
        ]

        for fname in special_files:
            client1.create_file(fname, f"content of {fname}")
            client1.add(fname)

        client1.commit("Add special files")
        client1.push("origin", branch)

        client2.pull("origin", branch)

        for fname in special_files:
            assert (client2.path / fname).exists(), f"File {fname} should exist"

    def test_deeply_nested_directories(self, client_server_setup):
        server, client1, client2 = client_server_setup

        branch = client1.get_branch()

        deep_path = "a/b/c/d/e/f/g/h/i/j/file.txt"
        client1.create_file(deep_path, "deep content")
        client1.add(deep_path)
        client1.commit("Add deep file")
        client1.push("origin", branch)

        client2.pull("origin", branch)
        assert (client2.path / deep_path).exists()
        assert client2.read_file(deep_path) == "deep content"

    def test_empty_file(self, client_server_setup):
        """Verify empty files transfer correctly."""
        server, client1, client2 = client_server_setup

        branch = client1.get_branch()

        # Create empty file
        client1.create_file("empty.txt", "")
        client1.add("empty.txt")
        client1.commit("Add empty file")
        client1.push("origin", branch)

        # Pull and verify
        client2.pull("origin", branch)
        assert (client2.path / "empty.txt").exists()
        assert client2.read_file("empty.txt") == ""
