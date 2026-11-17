#!/usr/bin/env bash

set -Eeuo pipefail

# Resolve project paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST_DIR="$(dirname "$SCRIPT_DIR")"
REPO_DIR="$(dirname "$HOST_DIR")"
PACKAGE_DIR="$HOST_DIR/tui/lerobot_tui"

# Installation paths
INSTALL_DIR="$HOME/.local/share/lerobot-setup"
VENV_DIR="$INSTALL_DIR/venv"
BIN_DIR="$HOME/.local/bin"
LAUNCHER="$BIN_DIR/lerobot-setup"

# Logging
LOG_DIR="$HOME/.local/state/lerobot-setup"
LOG_FILE="$LOG_DIR/install.log"

mkdir -p "$LOG_DIR"
: > "$LOG_FILE"

# Terminal colors
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    RED='\033[0;31m'
    BLUE='\033[0;34m'
    RESET='\033[0m'
else
    GREEN=''
    YELLOW=''
    RED=''
    BLUE=''
    RESET=''
fi

# Logging helpers
info() {
    printf "${BLUE}  →${RESET} %s\n" "$1"
}

success() {
    printf "${GREEN}  ✓${RESET} %s\n" "$1"
}

warning() {
    printf "${YELLOW}  !${RESET} %s\n" "$1"
}

error() {
    printf "${RED}  ✗${RESET} %s\n" "$1" >&2
}

# Execute a command and redirect output to the log file
run_step() {
    local description="$1"
    shift

    info "$description"

    if "$@" >> "$LOG_FILE" 2>&1; then
        success "$description"
    else
        error "$description"
        echo ""
        echo "Last 30 log lines:"
        tail -n 30 "$LOG_FILE" >&2
        echo ""
        echo "Full log: $LOG_FILE"
        exit 1
    fi
}

echo ""
printf "${BLUE}LeRobot Setup${RESET}\n"
echo "────────────────────────────────────────"

# Validate environment
if ! command -v apt-get >/dev/null 2>&1; then
    error "Unsupported operating system (APT required)"
    exit 1
fi

if [[ ! -f "$PACKAGE_DIR/setup.py" ]]; then
    error "Python package not found: $PACKAGE_DIR"
    exit 1
fi

# Install system dependencies
run_step "Installing system dependencies" \
    sudo apt-get update -qq

run_step "Installing Python packages" \
    sudo apt-get install -y -qq \
        python3 \
        python3-venv \
        python3-pip

# Check Docker
info "Checking Docker installation"

if ! command -v docker >/dev/null 2>&1; then
    warning "Docker CLI not found"
elif ! docker compose version >/dev/null 2>&1; then
    warning "Docker Compose plugin not found"
else
    success "Docker and Docker Compose available"
fi

# Create virtual environment
run_step "Creating Python environment" \
    python3 -m venv "$VENV_DIR"

# Install application and dependencies
run_step "Installing LeRobot TUI" \
    "$VENV_DIR/bin/python" -m pip install \
        --disable-pip-version-check \
        --no-input \
        -e "$PACKAGE_DIR"

# Create launcher
info "Creating launcher"

mkdir -p "$BIN_DIR"

{
    printf '#!/usr/bin/env bash\n'
    printf 'export LEROBOT_COMPOSE_FILE=%q\n' \
        "$REPO_DIR/docker/deploy/compose.yaml"
    printf 'exec %q -m lerobot_tui.main "$@"\n' "$VENV_DIR/bin/python"
} > "$LAUNCHER"

chmod +x "$LAUNCHER"

success "Launcher created"

echo ""
echo "────────────────────────────────────────"
printf "${GREEN}Installation completed successfully!${RESET}\n"
echo ""
echo "  Command: lerobot-setup"
echo "  Logs:    $LOG_FILE"
echo ""
