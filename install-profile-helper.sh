#!/bin/bash
set -euo pipefail

if [[ "$EUID" -ne 0 ]]; then
  echo "Run this installer with sudo: sudo ./install-profile-helper.sh" >&2
  exit 1
fi

install -d -o root -g root -m 0755 /usr/local/libexec
install -o root -g root -m 0755 predator-control-set-profile /usr/local/libexec/predator-control-set-profile

echo "Installed /usr/local/libexec/predator-control-set-profile"
echo "The helper only accepts profiles advertised by the kernel and writes only platform_profile."
echo "The app will invoke it via pkexec when you press Apply profile."
