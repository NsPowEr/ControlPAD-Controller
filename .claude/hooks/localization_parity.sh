#!/usr/bin/env bash
# PostToolUse hook: after any edit to a Localizable.strings file, compare the
# keys in it.lproj and en.lproj and report the ones present on only one side.
# Non-blocking: it prints a warning that is fed back into the model's context.
set -uo pipefail

path="$(jq -r '.tool_input.file_path // .tool_response.filePath // empty' 2>/dev/null)"
case "$path" in
    *Localizable.strings) ;;
    *) exit 0 ;;
esac

resources="$(cd "$(dirname "$path")/.." 2>/dev/null && pwd)" || exit 0
it="$resources/it.lproj/Localizable.strings"
en="$resources/en.lproj/Localizable.strings"
[ -f "$it" ] && [ -f "$en" ] || exit 0

keys() { grep -oE '^[[:space:]]*"[^"]+"[[:space:]]*=' "$1" | grep -oE '"[^"]+"' | sort -u; }

only_it="$(comm -23 <(keys "$it") <(keys "$en"))"
only_en="$(comm -13 <(keys "$it") <(keys "$en"))"
[ -z "$only_it" ] && [ -z "$only_en" ] && exit 0

message="Localizations out of sync."
[ -n "$only_it" ] && message="$message Only in it.lproj: $(echo "$only_it" | tr '\n' ' ')."
[ -n "$only_en" ] && message="$message Only in en.lproj: $(echo "$only_en" | tr '\n' ' ')."

jq -n --arg m "$message" \
    '{systemMessage: $m, hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $m}}'
