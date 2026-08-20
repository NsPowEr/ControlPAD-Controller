# Changelog

All notable changes to **ControlPAD Controller** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Complete `.github` infrastructure (CI/CD workflows for Engine and GUI, PR checks, Release pipelines).
- GitHub Issue & Pull Request templates.
- Native SwiftUI interface (`ControlPadGUI`) with preset management, key mapping, and hardware bank pickers.
- Python engine daemon (`ControlPadEngine`) with USB HID communication, macro generation, and lighting effects.
- Full suite of 130+ unit tests across Python engine and Swift GUI.
- Reverse engineering documentation and protocol specifications (`PROTOCOL.md`).

## [0.1.0] - 2026-08-20

### Added
- Initial setup of ControlPAD controller protocol decoder and bridge.
- Interactive LED effects manipulation (breathing, static, animations).
- Macro recording and key layout mapping.
- Swift GUI test suite and Python engine unit tests.
