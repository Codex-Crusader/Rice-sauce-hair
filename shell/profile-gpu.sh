# shellcheck shell=bash  # sourced by zprofile
# GPU selection for Hyprland on a hybrid laptop (optional, see docs/INSTALL.md, "Hybrid GPU").
# Hyprland uses only the iGPU when the udev rule made /dev/dri/amd-igpu. Start apps on the dGPU with prime-run.
[[ -e /dev/dri/amd-igpu ]] && export AQ_DRM_DEVICES=/dev/dri/amd-igpu
