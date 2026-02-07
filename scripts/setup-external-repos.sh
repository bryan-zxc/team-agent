#!/bin/bash
#
# Setup External Repositories
#
# This script clones or updates external repositories used for reference
# and development in the team-agent project.
#
# Usage:
#   ./scripts/setup-external-repos.sh           # Clone repositories
#   ./scripts/setup-external-repos.sh --update  # Update existing repositories
#   ./scripts/setup-external-repos.sh --help    # Show help

set -e

# Colour codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Colour

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
EXTERNAL_DIR="${PROJECT_ROOT}/external"

# Repository configuration
# Format: "name|url|branch"
REPOS=(
    "claude-agent-sdk-python|https://github.com/anthropics/claude-agent-sdk-python.git|main"
    # Add more repositories here:
    # "repo-name|https://github.com/org/repo.git|main"
)

print_header() {
    echo -e "${BLUE}===================================${NC}"
    echo -e "${BLUE}  External Repository Manager${NC}"
    echo -e "${BLUE}===================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

show_help() {
    cat << EOF
Setup External Repositories

This script manages external repositories in the external/ directory.

Usage:
    $0 [OPTIONS]

Options:
    --update    Update existing repositories instead of cloning
    --help      Show this help message

Examples:
    # Initial setup - clone all repositories
    $0

    # Update all repositories
    $0 --update

Managed Repositories:
EOF
    for repo in "${REPOS[@]}"; do
        IFS='|' read -r name url branch <<< "$repo"
        echo "    - ${name} (${branch})"
    done
    echo ""
}

clone_repo() {
    local name=$1
    local url=$2
    local branch=$3
    local repo_path="${EXTERNAL_DIR}/${name}"

    if [ -d "${repo_path}" ]; then
        print_info "Repository ${name} already exists, skipping..."
        return 0
    fi

    echo -e "${BLUE}Cloning ${name}...${NC}"
    if git clone --branch "${branch}" "${url}" "${repo_path}"; then
        print_success "Successfully cloned ${name}"
    else
        print_error "Failed to clone ${name}"
        return 1
    fi
}

update_repo() {
    local name=$1
    local url=$2
    local branch=$3
    local repo_path="${EXTERNAL_DIR}/${name}"

    if [ ! -d "${repo_path}" ]; then
        print_info "Repository ${name} not found, cloning instead..."
        clone_repo "${name}" "${url}" "${branch}"
        return $?
    fi

    echo -e "${BLUE}Updating ${name}...${NC}"
    cd "${repo_path}"

    # Check if there are uncommitted changes
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        print_error "${name} has uncommitted changes, skipping..."
        cd "${PROJECT_ROOT}"
        return 1
    fi

    if git pull origin "${branch}"; then
        print_success "Successfully updated ${name}"
    else
        print_error "Failed to update ${name}"
        cd "${PROJECT_ROOT}"
        return 1
    fi

    cd "${PROJECT_ROOT}"
}

main() {
    local update_mode=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --update)
                update_mode=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done

    print_header

    # Create external directory if it doesn't exist
    if [ ! -d "${EXTERNAL_DIR}" ]; then
        echo "Creating external directory..."
        mkdir -p "${EXTERNAL_DIR}"
    fi

    # Process each repository
    local success_count=0
    local total_count=${#REPOS[@]}

    for repo in "${REPOS[@]}"; do
        IFS='|' read -r name url branch <<< "$repo"

        if [ "${update_mode}" = true ]; then
            update_repo "${name}" "${url}" "${branch}"
        else
            clone_repo "${name}" "${url}" "${branch}"
        fi

        if [ $? -eq 0 ]; then
            ((success_count++))
        fi
    done

    echo ""
    echo -e "${BLUE}===================================${NC}"
    if [ "${update_mode}" = true ]; then
        echo -e "Updated ${success_count}/${total_count} repositories"
    else
        echo -e "Cloned ${success_count}/${total_count} repositories"
    fi
    echo -e "${BLUE}===================================${NC}"

    if [ ${success_count} -eq ${total_count} ]; then
        exit 0
    else
        exit 1
    fi
}

main "$@"
