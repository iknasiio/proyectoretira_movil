#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IOS_BUILD_DIR="${HOME}/Rama-ios-build"
IOS_SOURCE_DIR="${IOS_BUILD_DIR}/source"
IOS_PROJECT_DIR="${IOS_BUILD_DIR}/Rama-ios"
VENV_DIR="${IOS_BUILD_DIR}/venv"

if [[ "$(uname -s)" != "Darwin" ]]; then
    printf 'iOS packaging requires macOS and Xcode.\n' >&2
    exit 1
fi

if ! command -v xcodebuild >/dev/null 2>&1; then
    printf 'Install Xcode and its command line tools before continuing.\n' >&2
    exit 1
fi

mkdir -p "$IOS_BUILD_DIR"
python3 -m venv "$VENV_DIR"
source "${VENV_DIR}/bin/activate"
python -m pip install --upgrade pip
python -m pip install "Cython==3.0.11" kivy-ios

mkdir -p "${IOS_SOURCE_DIR}/app" "${IOS_SOURCE_DIR}/assets"
rsync -a --delete --delete-excluded \
    --exclude='/config/email_settings.json' \
    "${ROOT_DIR}/app/" "${IOS_SOURCE_DIR}/app/"
rsync -a --delete "${ROOT_DIR}/assets/" "${IOS_SOURCE_DIR}/assets/"
cp "${ROOT_DIR}/main.py" "${IOS_SOURCE_DIR}/main.py"

cd "$IOS_BUILD_DIR"
toolchain build python3 kivy pillow
toolchain pip install -r "${ROOT_DIR}/requirements-ios.txt"

if [[ ! -d "$IOS_PROJECT_DIR" ]]; then
    toolchain create Rama "$IOS_SOURCE_DIR"
else
    toolchain update Rama-ios
fi

printf 'Open %s/Rama.xcodeproj in Xcode.\n' "$IOS_PROJECT_DIR"
printf 'Add NSCameraUsageDescription to the app target before testing the camera.\n'
