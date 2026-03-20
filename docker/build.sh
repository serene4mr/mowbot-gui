#!/usr/bin/env bash

set -e

# Function to print help message
print_help() {
    echo "Usage: build.sh [OPTIONS]"
    echo "Options:"
    echo "  --help          Display this help message"
    echo "  -h              Display this help message"
    echo "  --platform      Specify the platform (default: current platform)"
    echo ""
    echo "Note: The --platform option should be one of 'linux/amd64' or 'linux/arm64'."
}

SCRIPT_DIR=$(readlink -f "$(dirname "$0")")
WORKSPACE_ROOT="$SCRIPT_DIR/.."

# Parse arguments
parse_arguments() {
    while [ "$1" != "" ]; do
        case "$1" in
        --help | -h)
            print_help
            exit 1
            ;;
        --platform)
            option_platform="$2"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            print_help
            exit 1
            ;;
        esac
        shift
    done
}

# Set platform
set_platform() {
    if [ -n "$option_platform" ]; then
        platform="$option_platform"
    else
        platform="linux/amd64"
        if [ "$(uname -m)" = "aarch64" ]; then
            platform="linux/arm64"
        fi
    fi
}

# Set arch lib dir
set_arch_lib_dir() {
    if [ "$platform" = "linux/arm64" ]; then
        lib_dir="aarch64"
    elif [ "$platform" = "linux/amd64" ]; then
        lib_dir="x86_64"
    else
        echo "Unsupported platform: $platform"
        exit 1
    fi
}

# Install some necessary apt packages (Optimized)
install_packages() {
    # Ensure ~/.local/bin is in PATH for user-installed Python scripts
    export PATH="$HOME/.local/bin:$PATH"
    if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' ~/.bashrc; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    fi

    # Only run apt-get if docker buildx is not installed
    if ! docker buildx version > /dev/null 2>&1; then
        echo "Installing Docker Buildx and dependencies..."
        sudo apt-get update
        sudo apt-get install -y \
            git \
            python3 \
            python3-pip \
            ca-certificates \
            curl \
            gnupg

        # Add Docker's official GPG key and repository if not already present
        if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
            sudo install -m 0755 -d /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            sudo chmod a+r /etc/apt/keyrings/docker.gpg
        fi

        if [ ! -f /etc/apt/sources.list.d/docker.list ]; then
            echo \
              "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
              $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
              sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        fi

        sudo apt-get update
        sudo apt-get install -y docker-buildx-plugin
    fi

    # Install vcstool only if it's missing
    if ! command -v vcs > /dev/null 2>&1; then
        echo "Installing vcstool..."
        python3 -m pip install --user --upgrade vcstool
    fi
}

# Build images
build_images() {
    # https://github.com/docker/buildx/issues/484
    export BUILDKIT_STEP_LOG_MAX_SIZE=10000000

    echo "Building images for platform: $platform"
    echo "Lib dir: $lib_dir"

    set -x
    docker buildx build \
        --load \
        --progress=plain \
        --platform="$platform" \
        --build-arg LIB_DIR="$lib_dir" \
        -f "$SCRIPT_DIR/Dockerfile" \
        -t "ghcr.io/serene4mr/mowbot-gui:latest" \
        "$WORKSPACE_ROOT"
    set +x
}

# Remove dangling images
remove_dangling_images() {
    docker image prune -f
}

# Main script execution
parse_arguments "$@"
set_platform
set_arch_lib_dir
install_packages
build_images
remove_dangling_images