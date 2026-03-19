#!/usr/bin/env bash
# Run tests for all plugins that have a tools/tests/ directory.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
failed=0
passed=0

for plugin_dir in "$REPO_ROOT"/plugins/*/; do
  test_dir="$plugin_dir/tools/tests"
  [ -d "$test_dir" ] || continue

  name=$(basename "$plugin_dir")
  echo "=== Testing $name ==="

  if (cd "$plugin_dir/tools" && bun test --timeout 15000); then
    echo "  PASS"
    ((passed++))
  else
    echo "  FAIL"
    ((failed++))
  fi
  echo ""
done

echo "Results: $passed passed, $failed failed"
[ "$failed" -eq 0 ] || exit 1
