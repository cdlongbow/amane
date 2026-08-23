#!/usr/bin/env bash
# 按 tests/.fixtures-rev 检出 amane-testdata → tests/crawlers/cases/ (gitignored).
# 无权限时警告并成功退出, 爬虫 TOML 用例 skip、不阻断 just setup/check.
#
# Env:
#   AMANE_FIXTURES_URL     覆盖仓库 URL
#   FIXTURES_DEPLOY_KEY    CI deploy key (PEM); 有则走 SSH
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

rev="$(tr -d '[:space:]' < tests/.fixtures-rev)"
repo="${AMANE_FIXTURES_URL:-https://github.com/sqzw-x/amane-testdata.git}"
target="tests/crawlers/cases"
key=""

cleanup() {
  if [[ -n "$key" && -f "$key" ]]; then
    rm -f "$key"
  fi
}
trap cleanup EXIT

if [[ -n "${FIXTURES_DEPLOY_KEY:-}" ]]; then
  key="$(mktemp)"
  printf '%s\n' "$FIXTURES_DEPLOY_KEY" > "$key"
  chmod 600 "$key"
  export GIT_SSH_COMMAND="ssh -i $key -o StrictHostKeyChecking=accept-new"
  repo="${AMANE_FIXTURES_URL:-git@github.com:sqzw-x/amane-testdata.git}"
fi

fetch() {
  if [[ -d "$target/.git" ]]; then
    git -C "$target" fetch --quiet origin "$rev"
    git -C "$target" checkout --quiet --force "$rev"
  else
    rm -rf "$target"
    git clone --quiet "$repo" "$target"
    git -C "$target" checkout --quiet --force "$rev"
  fi
}

if ! fetch; then
  echo "warning: could not fetch fixtures, crawler cases will be skipped" >&2
fi
