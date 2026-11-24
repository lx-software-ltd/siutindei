#!/usr/bin/env bash
set -euo pipefail
os=linux
arch=x64
case "$(uname -m)" in
  aarch64|arm64) arch=arm64 ;;
  x86_64|amd64) arch=x64 ;;
  *) echo "unsupported arch $(uname -m)" >&2; exit 1 ;;
esac
version="${CURSOR_CLI_VERSION}"
dest="${HOME}/.local/share/cursor-agent/versions/${version}"
mkdir -p "${dest}" "${HOME}/.local/bin"
curl -fsSL \
  "https://downloads.cursor.com/lab/${version}/${os}/${arch}/agent-cli-package.tar.gz" \
  | tar --strip-components=1 -xzf - -C "${dest}"
ln -sfn "${dest}/cursor-agent" "${HOME}/.local/bin/agent"
ln -sfn "${dest}/cursor-agent" "${HOME}/.local/bin/cursor-agent"
echo "${HOME}/.local/bin" >> "${GITHUB_PATH}"
echo "${HOME}/.cursor/bin" >> "${GITHUB_PATH}"
"${HOME}/.local/bin/cursor-agent" --version
