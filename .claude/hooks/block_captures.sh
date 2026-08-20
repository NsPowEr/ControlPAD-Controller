#!/usr/bin/env bash
# PreToolUse hook: the USB captures (.pcapng) and the "ControlPAD - CATTURA"
# directory are the only source of the device protocol — new ones cannot be
# recorded on macOS. They are read-only: any write is refused.
set -uo pipefail

path="$(jq -r '.tool_input.file_path // empty' 2>/dev/null)"
[ -n "$path" ] || exit 0

case "$path" in
    *.pcapng|*"ControlPAD - CATTURA"/*)
        jq -n --arg p "$path" '{
            hookSpecificOutput: {
                hookEventName: "PreToolUse",
                permissionDecision: "deny",
                permissionDecisionReason: ("Write refused on \($p): the USB captures are read-only. They are the irreplaceable source of the device protocol and cannot be re-recorded on macOS.")
            }
        }'
        ;;
esac
exit 0
