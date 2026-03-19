#!/bin/bash

#
# Deploy draw.io diagrams to Lucidchart
# Uses the Lucid Import Document API to push .drawio files to Lucidchart
#

# Configuration
LUCID_API_ENDPOINT="https://api.lucid.co/documents"
LUCID_TOKEN="${LUCID_TOKEN:-}"
MAPPINGS_FILE="${MAPPINGS_FILE:-.github/lucidchart-mappings.txt}"
HASH_DIR=".github/.deployment-hashes/lucidchart"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if required tools are installed
check_dependencies() {
    local missing_deps=()

    if ! command -v curl &> /dev/null; then
        missing_deps+=("curl")
    fi

    if ! command -v jq &> /dev/null; then
        missing_deps+=("jq")
    fi

    if [ ${#missing_deps[@]} -ne 0 ]; then
        error "Missing required dependencies: ${missing_deps[*]}"
        error "Please install them before running this script"
        exit 1
    fi

    if [ ! -f "$MAPPINGS_FILE" ]; then
        warning "Mappings file not found: $MAPPINGS_FILE"
        warning "No draw.io files are configured for deployment"
        warning "Create $MAPPINGS_FILE to enable Lucidchart deployment"
        return 0
    fi

    # Check if mappings file is empty or only has comments
    if ! grep -q '^[^#]' "$MAPPINGS_FILE" 2>/dev/null; then
        warning "Mappings file exists but contains no active mappings"
        warning "Add mappings to $MAPPINGS_FILE to enable deployment"
        return 0
    fi
}

# Get the configured Lucid destination ID from mappings file
get_lucidchart_id() {
    local file_path="$1"
    local lucid_id

    lucid_id=$(grep "^${file_path}=" "$MAPPINGS_FILE" | cut -d'=' -f2)

    if [ -z "$lucid_id" ]; then
        warning "No mapping found for: $file_path"
        return 1
    fi

    echo "$lucid_id"
}

# Validate environment
check_environment() {
    if [ -z "$LUCID_TOKEN" ]; then
        error "LUCID_TOKEN environment variable is not set"
        error "Please set your Lucidchart OAuth token"
        exit 1
    fi
}

# Calculate file hash
get_file_hash() {
    local file_path="$1"
    shasum -a 256 "$file_path" | cut -d' ' -f1
}

# Check if file has changed since last deployment
has_file_changed() {
    local file_path="$1"
    local hash_file="$HASH_DIR/$(echo "$file_path" | tr '/' '_').sha256"

    # If hash file doesn't exist, file has "changed" (never deployed)
    if [ ! -f "$hash_file" ]; then
        return 0
    fi

    local current_hash
    local stored_hash

    current_hash=$(get_file_hash "$file_path")
    stored_hash=$(cat "$hash_file")

    [ "$current_hash" != "$stored_hash" ]
}

# Store file hash after successful deployment
store_file_hash() {
    local file_path="$1"
    local hash_file="$HASH_DIR/$(echo "$file_path" | tr '/' '_').sha256"

    mkdir -p "$HASH_DIR"
    get_file_hash "$file_path" > "$hash_file"
}

# Import draw.io file to Lucidchart.
# Lucid's import endpoint creates a new document; placement in team folders is handled manually.
import_to_lucidchart() {
    local file_path="$1"
    local destination_id="$2"
    local title="${3:-$(basename "$file_path" .drawio)}"

    log "Importing $file_path to Lucidchart..."
    log "Configured destination ID: $destination_id (manual move to team folder may still be required)"

    # The Lucid API supports importing draw.io files directly
    # Using multipart/form-data with the draw.io MIME type
    local response
    local http_code

    response=$(curl -s -w "\n%{http_code}" \
        -X POST "$LUCID_API_ENDPOINT" \
        -H "Authorization: Bearer $LUCID_TOKEN" \
        -H "Lucid-Api-Version: 1" \
        -F "file=@${file_path};type=x-application/vnd.lucid.drawio" \
        -F "title=${title}" \
        -F "product=lucidchart")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        success "Successfully imported $file_path"

        # Try to extract the document URL from response
        local doc_url
        doc_url=$(echo "$body" | jq -r '.url // empty' 2>/dev/null)

        if [ -n "$doc_url" ]; then
            log "Document URL: $doc_url"
        fi

        # Store the hash to mark successful deployment
        store_file_hash "$file_path"

        return 0
    else
        error "Failed to import $file_path (HTTP $http_code)"

        # Try to extract error message
        local error_msg
        error_msg=$(echo "$body" | jq -r '.message // .error // empty' 2>/dev/null)

        if [ -n "$error_msg" ]; then
            error "API Error: $error_msg"
        else
            error "Response: $body"
        fi

        return 1
    fi
}

# Deploy a single file
deploy_file() {
    local file_path="$1"
    local force="${2:-false}"

    if [ ! -f "$file_path" ]; then
        error "File not found: $file_path"
        return 1
    fi

    # Check if file has changed (unless force deploy)
    if [ "$force" = "false" ] && ! has_file_changed "$file_path"; then
        log "Skipping $file_path (no changes detected)"
        return 0
    fi

    local lucid_id
    lucid_id=$(get_lucidchart_id "$file_path")

    if [ -z "$lucid_id" ]; then
        error "No Lucidchart document ID found for: $file_path"
        return 1
    fi

    import_to_lucidchart "$file_path" "$lucid_id"
}

# Deploy changed files from comma-separated list or "all"
deploy_changed_files() {
    local changed_files="$1"

    if [ "$changed_files" = "all" ]; then
        log "Deploying all mapped files..."

        while IFS='=' read -r file_path lucid_id; do
            # Skip empty lines and comments
            [[ -z "$file_path" || "$file_path" =~ ^# ]] && continue

            deploy_file "$file_path" "true"
        done < "$MAPPINGS_FILE"
    else
        # Split comma-separated list
        IFS=',' read -ra FILES <<< "$changed_files"

        for file_path in "${FILES[@]}"; do
            # Trim whitespace
            file_path=$(echo "$file_path" | xargs)

            # Only process .drawio files that are in mappings
            if [[ "$file_path" == *.drawio ]] && grep -q "^${file_path}=" "$MAPPINGS_FILE"; then
                deploy_file "$file_path" "false"
            fi
        done
    fi
}

# Main script
main() {
    check_dependencies
    check_environment

    case "${1:-}" in
        --deploy-changed)
            if [ -z "${CHANGED_FILES:-}" ]; then
                error "CHANGED_FILES environment variable is not set"
                exit 1
            fi
            deploy_changed_files "$CHANGED_FILES"
            ;;
        --force)
            deploy_changed_files "all"
            ;;
        --deploy-file)
            if [ -z "${2:-}" ]; then
                error "Please specify a file path"
                exit 1
            fi
            deploy_file "$2" "false"
            ;;
        --help|*)
            cat << EOF
Usage: $0 [OPTIONS]

Deploy draw.io diagrams to Lucidchart using the Lucid Import Document API.

Options:
    --deploy-changed    Deploy files listed in CHANGED_FILES environment variable
    --force             Force deploy all mapped files (ignore change detection)
    --deploy-file FILE  Deploy a specific file
    --help              Show this help message

Environment Variables:
    LUCID_TOKEN         OAuth token for Lucid API authentication (required)
    CHANGED_FILES       Comma-separated list of changed files (for --deploy-changed)

Configuration:
    Mappings file: $MAPPINGS_FILE
    Format: path/to/diagram.drawio=lucidchart_folder_id

Examples:
    # Deploy specific file
    $0 --deploy-file programs/diagram.drawio

    # Deploy all files (force)
    $0 --force

    # Deploy changed files (typically used in CI/CD)
    CHANGED_FILES="file1.drawio,file2.drawio" $0 --deploy-changed

Notes:
    - The script uses SHA-256 hashing to detect file changes
    - Hashes are stored in $HASH_DIR
    - The Lucid API requires OAuth 2.0 authentication
    - Contact Lucid support to request API access
EOF
            [ "${1:-}" = "--help" ] && exit 0 || exit 1
            ;;
    esac
}

main "$@"
