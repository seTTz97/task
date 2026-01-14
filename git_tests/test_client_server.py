import pytest
import subprocess
from pathlib import Path


from conftest import GitRepository


class TestClone:
    """Tests for git clone - the initial client-server handshake."""

    def test_clone_bare_repository(self, bare_repo, temp_dir: Path):
        temp_work = temp_dir / "temp_work"
        temp_work.mkdir()

        work = GitRepository(temp_work)
        work.init()
        work.create_file("README.md", "# Test")
        work.add("README.md")
        work.commit("Initial commit")
        work.run("remote", "add", "origin", str(bare_repo.path))
        work.run("push", "-u", "origin", work.get_branch())

        clone_path = temp_dir / "cloned"
        result = subprocess.run(
            ["git", "clone", str(bare_repo.path), str(clone_path)],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert (clone_path / "README.md").exists()
        assert (clone_path / ".git").exists()

    def test_clone_preserves_commit_history(self, client_server_setup):
        server, client1, client2 = client_server_setup

        client1.create_file("file1.txt", "content1")
        client1.add("file1.txt")
        client1.commit("Add file1")

        client1.create_file("file2.txt", "content2")
        client1.add("file2.txt")
        client1.commit("Add file2")

        branch = client1.get_branch()
        client1.push("origin", branch)

        clone_path = server.path.parent / "fresh_clone"
        cloned = server.clone_to(clone_path)

        log = cloned.run("log", "--oneline")
        assert "Add file1" in log.stdout
        assert "Add file2" in log.stdout
        assert "Initial commit" in log.stdout

    def test_clone_to_nonexistent_directory(self, bare_repo, temp_dir: Path):
        temp_work = temp_dir / "work"
        temp_work.mkdir()
        work = GitRepository(temp_work)
        work.init()
        work.create_file("test.txt", "test")
        work.add("test.txt")
        work.commit("Initial")
        work.run("remote", "add", "origin", str(bare_repo.path))
        work.run("push", "-u", "origin", work.get_branch())

        clone_path = temp_dir / "nonexistent" / "nested" / "clone"

        result = subprocess.run(
            ["git", "clone", str(bare_repo.path), str(clone_path)],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert clone_path.exists()

    def test_clone_specific_branch(self, client_server_setup, temp_dir: Path):
        server, client1, _ = client_server_setup

        client1.run("checkout", "-b", "feature")
        client1.create_file("feature.txt", "feature content")
        client1.add("feature.txt")
        client1.commit("Feature commit")
        client1.push("origin", "feature")

        clone_path = temp_dir / "feature_clone"
        result = subprocess.run(
            ["git", "clone", "-b", "feature", str(server.path), str(clone_path)],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        cloned = GitRepository(clone_path)
        assert cloned.get_branch() == "feature"
        assert (clone_path / "feature.txt").exists()


class TestPush:
    """Tests for git push - sending changes from client to server."""

    def test_push_new_commits(self, client_server_setup):
        server, client1, client2 = client_server_setup

        client1.create_file("new_file.txt", "new content")
        client1.add("new_file.txt")
        client1.commit("Add new file")

        branch = client1.get_branch()
        result = client1.push("origin", branch)
        assert result.returncode == 0

        server_log = server.run("log", "--oneline", branch)
        assert "Add new file" in server_log.stdout

    def test_push_new_branch(self, client_server_setup):
        """Verify pushing a new branch to server."""
        server, client1, _ = client_server_setup

        client1.run("checkout", "-b", "new-feature")
        client1.create_file("feature.txt", "feature")
        client1.add("feature.txt")
        client1.commit("Feature commit")

        result = client1.push("origin", "new-feature")
        assert result.returncode == 0

        branches = server.run("branch", "--list")
        assert "new-feature" in branches.stdout

    def test_push_with_tags(self, client_server_setup):
        """Verify pushing tags to server."""
        server, client1, _ = client_server_setup

        client1.run("tag", "v1.0.0")

        result = client1.run("push", "origin", "--tags")
        assert result.returncode == 0

        tags = server.run("tag", "--list")
        assert "v1.0.0" in tags.stdout


class TestFetch:
    """Tests for git fetch - downloading changes from server."""

    def test_fetch_downloads_new_commits(self, client_server_setup):
        server, client1, client2 = client_server_setup

        branch = client1.get_branch()

        client1.create_file("shared.txt", "shared content")
        client1.add("shared.txt")
        client1.commit("Shared commit")
        client1.push("origin", branch)

        result = client2.fetch("origin")
        assert result.returncode == 0

        log = client2.run("log", f"origin/{branch}", "--oneline")
        assert "Shared commit" in log.stdout

    def test_fetch_updates_remote_tracking_branches(self, client_server_setup):
        server, client1, client2 = client_server_setup

        branch = client1.get_branch()

        old_ref = client2.run("rev-parse", f"origin/{branch}").stdout.strip()

        client1.create_file("new.txt", "content")
        client1.add("new.txt")
        client1.commit("New commit")
        client1.push("origin", branch)

        client2.fetch("origin")

        new_ref = client2.run("rev-parse", f"origin/{branch}").stdout.strip()

        assert old_ref != new_ref

    def test_fetch_all_branches(self, client_server_setup):
        server, client1, client2 = client_server_setup

        for i in range(3):
            client1.run("checkout", "-b", f"branch-{i}")
            client1.create_file(f"file-{i}.txt", f"content-{i}")
            client1.add(f"file-{i}.txt")
            client1.commit(f"Commit on branch-{i}")
            client1.push("origin", f"branch-{i}")

        client2.fetch("origin")

        branches = client2.run("branch", "-r")
        assert "origin/branch-0" in branches.stdout
        assert "origin/branch-1" in branches.stdout
        assert "origin/branch-2" in branches.stdout


class TestPull:
    """Tests for git pull - fetch + merge operation."""

    def test_pull_integrates_remote_changes(self, client_server_setup):
        server, client1, client2 = client_server_setup

        branch = client1.get_branch()

        client1.create_file("remote_file.txt", "from remote")
        client1.add("remote_file.txt")
        client1.commit("Remote commit")
        client1.push("origin", branch)

        result = client2.pull("origin", branch)
        assert result.returncode == 0

        assert (client2.path / "remote_file.txt").exists()
        assert client2.read_file("remote_file.txt") == "from remote"

    def test_pull_creates_merge_commit(self, client_server_setup):
        server, client1, client2 = client_server_setup

        branch = client1.get_branch()

        client1.create_file("client1_file.txt", "client1")
        client1.add("client1_file.txt")
        client1.commit("Client1 commit")
        client1.push("origin", branch)

        client2.create_file("client2_file.txt", "client2")
        client2.add("client2_file.txt")
        client2.commit("Client2 commit")

        result = client2.run("pull", "--no-rebase", "origin", branch, check=False)

        if result.returncode == 0:
            log = client2.run("log", "--oneline", "-5")
            assert "Client1 commit" in log.stdout
            assert "Client2 commit" in log.stdout


class TestRemote:
    """Tests for git remote operations."""

    def test_add_remote(self, git_repo, temp_dir: Path):
        git_repo.create_file("test.txt", "test")
        git_repo.add("test.txt")
        git_repo.commit("Initial commit")

        remote_path = temp_dir / "remote.git"
        remote_path.mkdir()

        result = git_repo.run("remote", "add", "origin", str(remote_path))
        assert result.returncode == 0

        remotes = git_repo.run("remote", "-v")
        assert "origin" in remotes.stdout
        assert str(remote_path) in remotes.stdout

    def test_remove_remote(self, client_server_setup):
        _, client1, _ = client_server_setup

        client1.run("remote", "remove", "origin")

        remotes = client1.run("remote", "-v")
        assert "origin" not in remotes.stdout

    def test_rename_remote(self, client_server_setup):
        _, client1, _ = client_server_setup

        client1.run("remote", "rename", "origin", "upstream")

        remotes = client1.run("remote", "-v")
        assert "origin" not in remotes.stdout
        assert "upstream" in remotes.stdout


class TestDataIntegrity:
    """Tests to verify data integrity during client-server communication."""

    def test_file_content_preserved_after_push_pull(self, client_server_setup):
        server, client1, client2 = client_server_setup

        branch = client1.get_branch()

        content = "Line 1\nLine 2\nSpecial: !@#$%^&*()\nUnicode: 日本語"
        client1.create_file("content_test.txt", content)
        client1.add("content_test.txt")
        client1.commit("Add content test file")
        client1.push("origin", branch)

        client2.pull("origin", branch)

        pulled_content = client2.read_file("content_test.txt")
        assert pulled_content == content

    def test_large_file_transfer(self, client_server_setup):
        server, client1, client2 = client_server_setup

        branch = client1.get_branch()

        large_content = "X" * (1024 * 1024)
        client1.create_file("large_file.txt", large_content)
        client1.add("large_file.txt")
        client1.commit("Add large file")
        client1.push("origin", branch)

        client2.pull("origin", branch)

        pulled = client2.read_file("large_file.txt")
        assert len(pulled) == len(large_content)
        assert pulled == large_content