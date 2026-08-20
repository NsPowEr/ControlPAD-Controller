# Contributing to ControlPAD Controller

Thank you for your interest in contributing to **ControlPAD Controller**! 

## Development Setup

### 1. Requirements
- **Python 3.11+** with `hidapi` installed (`pip install -r ControlPadEngine/requirements.txt`).
- **macOS with Xcode 15+ / Swift 6+** (for building and testing `ControlPadGUI`).
- Optional: USB packet capture tools (Wireshark) for protocol research.

### 2. Running Tests
Before submitting a pull request, ensure all test suites pass:

**Python Engine Tests:**
```bash
python3 -m unittest discover ControlPadEngine/tests
```

**Swift GUI Tests:**
```bash
cd ControlPadGUI
swift test
```

## Pull Request Guidelines

1. **Semantic PR Titles**: Follow the Conventional Commits format (e.g., `feat: add breathing animation mode`, `fix: handle USB disconnect gracefully`).
2. **Atomic Changes**: Keep PRs focused on a single responsibility.
3. **Update Docs**: If modifying protocol handling or adding new endpoints, update [`ControlPAD - CATTURA/PROTOCOL.md`](ControlPAD%20-%20CATTURA/PROTOCOL.md) and [`CHANGES.md`](CHANGES.md).
4. **Issue Tracking**: Reference any related GitHub issues in your PR description.
