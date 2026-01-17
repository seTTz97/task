# Git Test Suite

A comprehensive test suite for testing Git software, with a focus on client-server communication.

## Overview

This test suite validates Git's core functionality and client-server communication using multiple transport protocols. It is designed to be run in CI/CD environments and supports both local testing and distributed testing scenarios.

## Test Structure

```
task/
├── conftest.py              # Pytest fixtures and helpers
├── pytest.ini               # Pytest configuration
├── requirements.txt         # Python dependencies
├── README.md                # This documentation
└── git_tests/
    ├── test_basic_operations.py # Core Git command tests
    ├── test_client_server.py    # Client-server communication tests
    ├── test_protocols.py        # Protocol-specific tests (file, SSH, HTTP, git://)
    └── test_error_handling.py   # Error handling and edge cases
```

## Test Categories

### 1. Basic Operations (`test_basic_operations.py`)
Tests fundamental Git commands:
- `git init` - Repository initialization
- `git add` - Staging files
- `git commit` - Creating commits
- `git status` - Working tree status
- `git branch` - Branch operations

### 2. Client-Server Communication (`test_client_server.py`)
Tests communication between Git clients and servers:
- **Clone** - Initial repository download and handshake
- **Push** - Sending commits to remote
- **Fetch** - Downloading commits from remote
- **Pull** - Fetch + merge operations
- **Remote** - Remote configuration

### 3. Protocol-Specific Tests (`test_protocols.py`)
Tests different Git transport protocols:
- `file://` - Local filesystem protocol
- `ssh://` - Secure Shell protocol
- `http://` / `https://` - HTTP protocols
- `git://` - Native Git daemon protocol

### 4. Error Handling (`test_error_handling.py`)
Tests error conditions and edge cases:
- Connection errors
- Merge conflicts
- Edge cases (empty repos, large files, special characters)

## Installation

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Running Tests

### Run All Tests
```bash
pytest git_tests/ -v
```

### Run Specific Test Files
```bash
pytest git_tests/test_basic_operations.py
pytest git_tests/test_client_server.py
```

### Run Tests by Category
```bash
# Skip slow tests
pytest -m "not slow"

# Skip network-dependent tests
pytest -m "not network"

# Skip SSH tests (require SSH setup)
pytest -m "not ssh"
```

### Run with Coverage
```bash
pytest --cov=. --cov-report=html
```

### Run in Parallel
```bash
pytest -n auto  # Requires pytest-xdist
```

### Generate HTML Report
```bash
pytest --html=report.html  # Requires pytest-html
```

## Shortcuts Taken

Due to time constraints, the following shortcuts were implemented:

### 1. SSH Protocol Tests
**Current:** Tests check for SSH availability and skip if not configured.

**Full Implementation Would:**
- Spin up an SSH server in a Docker container
- Auto-generate and configure SSH keys
- Create test repositories accessible via SSH
- Test authentication scenarios (key-based, password, failure cases)

### 2. HTTP/HTTPS Protocol Tests
**Current:** Uses Python's simple HTTP server (dumb protocol only, read-only).

**Full Implementation Would:**
- Deploy `git-http-backend` or GitLab/Gitea in Docker
- Test smart HTTP protocol with push support
- Test authentication (Basic, OAuth, tokens)
- Test certificate validation and TLS versions


### 3. Network Failure Simulation
**Current:** Tests basic unreachable host scenarios.

**Full Implementation Would:**
- Use network namespaces or iptables to simulate:
  - Packet loss
  - Connection timeouts
  - Partial transfers
  - DNS failures

### 4. Performance Testing
**Current:** Not implemented.

**Full Implementation Would:**
- Benchmark clone/push/pull times
- Test with varying repository sizes
- Test concurrent client connections
- Memory usage profiling

## CI/CD Requirements

### Minimum Requirements

| Component | Requirement |
|-----------|-------------|
| **OS** | Linux (Ubuntu 20.04+), macOS 11+, or Windows Server 2019+ |
| **Git** | Version 2.30+ |
| **Python** | Version 3.8+ |
| **Memory** | 4GB RAM minimum |
| **Disk** | 10GB free space |
| **Network** | Outbound access for HTTP tests |

### Recommended CI Configuration

#### GitHub Actions Example
```yaml
name: Git Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        git-version: ['2.30', '2.40', 'latest']
        python-version: ['3.9', '3.11']

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install Git version
        run: |
          sudo add-apt-repository ppa:git-core/ppa -y
          sudo apt-get update
          sudo apt-get install git -y

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run tests
        run: pytest -v --tb=short -m "not ssh"

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```