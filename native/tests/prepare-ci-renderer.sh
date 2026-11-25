#!/bin/bash
# A software buffer device for stock KWin 6.8 on a disposable GitHub runner.
# Never run this against a workstation or a self-hosted runner.
set -euo pipefail
test "${GITHUB_ACTIONS:-}" = true
test "${RUNNER_ENVIRONMENT:-}" = github-hosted
mkdir -p work
exec > >(tee work/renderer-setup.log) 2>&1
trap 'status=$?; if [ "$status" -ne 0 ]; then python3 scripts/report-ci-failure.py work/renderer-setup.log; fi; exit "$status"' EXIT
kernel_release=$(uname -r)
printf '::notice title=Runner kernel::%s\n' "$kernel_release"
dpkg-query -W "linux-image-$kernel_release" "linux-modules-$kernel_release" || true
if [ -f "/boot/config-$kernel_release" ]; then
    grep -E 'CONFIG_(UDMABUF|MEMFD_CREATE|DMA_SHARED_BUFFER|DRM_VKMS|DRM_VGEM)' "/boot/config-$kernel_release" | sed 's/^/::notice title=Kernel configuration::/' || true
fi
for module in udmabuf vgem vkms; do
    if path=$(modinfo -F filename "$module" 2>&1); then
        printf '::notice title=Available software renderer module::%s %s\n' "$module" "$path"
    else
        printf '::notice title=Unavailable software renderer module::%s\n' "$module"
    fi
done
ls -ld /dev/udmabuf /dev/dri /sys/class/misc/udmabuf 2>/dev/null || true
# Hosted images can omit modules for their running Azure kernel. Install only
# that kernel's distribution package; never substitute a different kernel.
if ! modinfo udmabuf; then
    sudo apt-get update
    sudo apt-get install --yes --reinstall "linux-modules-$kernel_release"
fi
sudo modprobe udmabuf
test -c /dev/udmabuf
sudo chgrp 1000 /dev/udmabuf
sudo chmod 0660 /dev/udmabuf
ls -l /dev/udmabuf
