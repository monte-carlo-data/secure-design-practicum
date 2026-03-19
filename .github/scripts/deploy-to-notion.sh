#!/bin/bash

# Deploy Markdown files to Notion
# Monitors changes to markdown files and updates corresponding Notion pages

set -e

# Configuration
NOTION_API_URL="https://api.notion.com/v1"
NOTION_TOKEN="${NOTION_TOKEN:-}"      # Set as environment variable
MAPPINGS_FILE="${MAPPINGS_FILE:-.github/notion-mappings.txt}"
LAST_HASH_FILE=".notion-deploy-hash"
CHANGED_FILES="${CHANGED_FILES:-}"    # Comma-separated list from workflow

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to log messages
log() {
    printf "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} %s\n" "$1"
}

error() {
    printf "${RED}[ERROR]${NC} %s\n" "$1" >&2
}

success() {
    printf "${GREEN}[SUCCESS]${NC} %s\n" "$1"
}

warning() {
    printf "${YELLOW}[WARNING]${NC} %s\n" "$1"
}

# Check dependencies
check_dependencies() {
    log "Checking dependencies..."

    if ! command -v curl &> /dev/null; then
        error "curl is required but not installed"
        exit 1
    fi

    if ! command -v jq &> /dev/null; then
        error "jq is required but not installed (brew install jq)"
        exit 1
    fi

    if [ ! -f "$MAPPINGS_FILE" ]; then
        warning "Mappings file not found: $MAPPINGS_FILE"
        warning "No markdown files are configured for deployment"
        warning "Create $MAPPINGS_FILE to enable Notion deployment"
        return 0
    fi

    # Check if mappings file is empty or only has comments
    if ! grep -q '^[^#]' "$MAPPINGS_FILE" 2>/dev/null; then
        warning "Mappings file exists but contains no active mappings"
        warning "Add mappings to $MAPPINGS_FILE to enable deployment"
        return 0
    fi
}

# Format Notion page ID with dashes (UUID format)
format_notion_page_id() {
    local page_id="$1"

    # Remove any existing dashes
    page_id=$(echo "$page_id" | tr -d '-')

    # Check if it's a 32-character hex string
    if [[ ! "$page_id" =~ ^[0-9a-fA-F]{32}$ ]]; then
        error "Invalid Notion page ID format: $page_id"
        error "Expected 32 hexadecimal characters"
        exit 1
    fi

    # Format as UUID: 8-4-4-4-12
    echo "${page_id:0:8}-${page_id:8:4}-${page_id:12:4}-${page_id:16:4}-${page_id:20:12}"
}

# Get Notion page ID from mappings file
get_notion_page_id() {
    local file_path="$1"

    # Look for the file path in the mappings file
    local page_id=$(grep -v "^#" "$MAPPINGS_FILE" | grep "^$file_path=" | cut -d'=' -f2 | tr -d ' \t\n\r')

    if [ -z "$page_id" ]; then
        error "No Notion page ID found for file: $file_path"
        error "Add mapping to: $MAPPINGS_FILE"
        error "Format: $file_path=your_notion_page_id"
        exit 1
    fi

    # Format the page ID with dashes
    format_notion_page_id "$page_id"
}

# Check environment variables
check_environment() {
    log "Checking environment variables..."
    
    if [ -z "$NOTION_TOKEN" ]; then
        error "NOTION_TOKEN environment variable is required"
        error "Get your token from: https://www.notion.so/my-integrations"
        exit 1
    fi
}

# Calculate file hash
get_file_hash() {
    local file_path="$1"
    if command -v shasum &> /dev/null; then
        shasum -a 256 "$file_path" | cut -d' ' -f1
    elif command -v sha256sum &> /dev/null; then
        sha256sum "$file_path" | cut -d' ' -f1
    else
        # Fallback to basic checksum
        cksum "$file_path" | cut -d' ' -f1
    fi
}

# Check if file has changed
has_file_changed() {
    local file_path="$1"
    local hash_file="${LAST_HASH_FILE}.$(echo "$file_path" | tr '/' '_')"
    local current_hash=$(get_file_hash "$file_path")
    local last_hash=""

    if [ -f "$hash_file" ]; then
        last_hash=$(cat "$hash_file")
    fi

    if [ "$current_hash" != "$last_hash" ]; then
        echo "$current_hash" > "$hash_file"
        return 0  # File has changed
    else
        return 1  # File hasn't changed
    fi
}

# Convert markdown to Notion blocks
convert_markdown_to_notion_blocks() {
    local markdown_file="$1"
    local temp_json=$(mktemp)
    
    log "Converting markdown file: $markdown_file" >&2
    if [ -f "$markdown_file" ]; then
        local file_size=$(wc -c < "$markdown_file")
        log "File size: $file_size bytes" >&2
    else
        error "Markdown file not found: $markdown_file"
        exit 1
    fi
    
    # Basic markdown to Notion blocks conversion
    # This is a simplified version - you might want to use a more sophisticated converter
    python3 -c "
import json
import re

def parse_inline_formatting(text):
    \"\"\"Parse inline markdown formatting (bold, italic, code, links) into Notion rich_text\"\"\"
    rich_text = []

    # Pattern to match [text](url), **bold**, *italic*, and \`code\`
    pattern = r'(\[.*?\]\(.*?\)|\*\*.*?\*\*|\`.*?\`|\*.*?\*)'
    parts = re.split(pattern, text)

    for part in parts:
        if not part:
            continue

        # Markdown links [text](url)
        link_match = re.match(r'^\[(.*?)\]\((.*?)\)$', part)
        if link_match:
            link_text = link_match.group(1)
            link_url = link_match.group(2)
            if link_text:
                # Only create Notion links for absolute URLs - relative paths and anchors are invalid
                if link_url.startswith('http://') or link_url.startswith('https://'):
                    rich_text.append({
                        'type': 'text',
                        'text': {'content': link_text, 'link': {'url': link_url}}
                    })
                else:
                    rich_text.append({
                        'type': 'text',
                        'text': {'content': link_text}
                    })
        elif part.startswith('**') and part.endswith('**'):
            # Bold text
            content = part[2:-2]
            if content:
                rich_text.append({
                    'type': 'text',
                    'text': {'content': content},
                    'annotations': {'bold': True}
                })
        elif part.startswith('\`') and part.endswith('\`'):
            # Inline code
            content = part[1:-1]
            if content:
                rich_text.append({
                    'type': 'text',
                    'text': {'content': content},
                    'annotations': {'code': True}
                })
        elif part.startswith('*') and part.endswith('*') and not part.startswith('**'):
            # Italic text
            content = part[1:-1]
            if content:
                rich_text.append({
                    'type': 'text',
                    'text': {'content': content},
                    'annotations': {'italic': True}
                })
        else:
            # Plain text - check for bare URLs
            if part:
                url_pattern = r'(https?://[^\s<>\"]+)'
                url_parts = re.split(url_pattern, part)
                for up in url_parts:
                    if not up:
                        continue
                    if re.match(r'^https?://', up):
                        rich_text.append({
                            'type': 'text',
                            'text': {'content': up, 'link': {'url': up}}
                        })
                    else:
                        rich_text.append({
                            'type': 'text',
                            'text': {'content': up}
                        })

    return rich_text if rich_text else [{'type': 'text', 'text': {'content': text}}]

def markdown_to_notion_blocks(markdown_content):
    blocks = []
    list_stack = []
    lines = markdown_content.split('\n')
    i = 0

    def get_indent_level(raw_line):
        # Treat tabs as 4 spaces and map indentation to list nesting depth.
        leading_ws = re.match(r'^\s*', raw_line).group(0).replace('\t', '    ')
        return len(leading_ws) // 2

    def add_list_block(block, indent_level):
        # Pop list items at this depth or deeper; attach to nearest shallower parent.
        while list_stack and list_stack[-1][0] >= indent_level:
            list_stack.pop()

        if list_stack:
            parent_block = list_stack[-1][1]
            parent_type = parent_block['type']
            parent_block[parent_type].setdefault('children', []).append(block)
        else:
            blocks.append(block)

        list_stack.append((indent_level, block))

    while i < len(lines):
        raw_line = lines[i].rstrip('\r')
        line = raw_line.strip()
        if not line:
            # Empty lines end list context.
            list_stack = []
            i += 1
            continue

        # Code blocks (must check before headers)
        if line.startswith('\`\`\`'):
            list_stack = []
            # Extract language if specified
            language = line[3:].strip() if len(line) > 3 else 'plain text'

            # Map common language aliases to Notion-supported languages
            language_map = {
                'text': 'plain text',
                'txt': 'plain text',
                'sh': 'shell',
                'zsh': 'shell',
                'js': 'javascript',
                'ts': 'typescript',
                'py': 'python',
                'rb': 'ruby',
                'yml': 'yaml'
            }
            language = language_map.get(language.lower(), language)

            # Collect code block content
            code_lines = []
            i += 1
            while i < len(lines):
                if lines[i].strip().startswith('\`\`\`'):
                    break
                code_lines.append(lines[i])
                i += 1

            # Create code block, splitting into 2000-char chunks for Notion API limit
            code_content = '\\n'.join(code_lines)
            rich_text = []
            for j in range(0, max(1, len(code_content)), 2000):
                rich_text.append({'type': 'text', 'text': {'content': code_content[j:j+2000]}})
            blocks.append({
                'object': 'block',
                'type': 'code',
                'code': {
                    'rich_text': rich_text,
                    'language': language if language else 'plain text'
                }
            })
        # Headers
        elif line.startswith('# '):
            list_stack = []
            blocks.append({
                'object': 'block',
                'type': 'heading_1',
                'heading_1': {
                    'rich_text': parse_inline_formatting(line[2:])
                }
            })
        elif line.startswith('## '):
            list_stack = []
            blocks.append({
                'object': 'block',
                'type': 'heading_2',
                'heading_2': {
                    'rich_text': parse_inline_formatting(line[3:])
                }
            })
        elif line.startswith('### '):
            list_stack = []
            blocks.append({
                'object': 'block',
                'type': 'heading_3',
                'heading_3': {
                    'rich_text': parse_inline_formatting(line[4:])
                }
            })
        # Table detection
        elif '|' in line and i + 1 < len(lines) and '---' in lines[i + 1]:
            list_stack = []
            # Found table header, process entire table
            table_rows = []
            header_row = [cell.strip() for cell in line.split('|') if cell.strip()]
            table_width = len(header_row)
            table_rows.append(header_row)
            
            # Skip separator line
            i += 2
            
            # Process table rows
            table_end = i
            while table_end < len(lines):
                current_line = lines[table_end].strip()
                if not current_line or '|' not in current_line:
                    break
                    
                row = [cell.strip() for cell in current_line.split('|') if cell.strip()]
                
                # Ensure row has exactly the same number of cells as header
                while len(row) < table_width:
                    row.append('')  # Add empty cells
                while len(row) > table_width:
                    row.pop()  # Remove extra cells
                
                if row:  # Only add non-empty rows
                    table_rows.append(row)
                table_end += 1
            
            # Update i to skip processed table rows
            i = table_end - 1
            
            # Create table block with children
            if table_rows:
                table_children = []
                
                # Create table rows as children
                for row in table_rows:
                    table_row_cells = []
                    for cell in row:
                        rich_text = parse_inline_formatting(cell)
                        table_row_cells.append(rich_text)
                    
                    table_children.append({
                        'object': 'block',
                        'type': 'table_row',
                        'table_row': {
                            'cells': table_row_cells
                        }
                    })
                
                # Notion requires at least one child row when creating a table.
                # Include only the header row inline; remaining rows go into a
                # _deferred_children sentinel so the upload loop can append them
                # to the table block after it has been created.
                blocks.append({
                    'object': 'block',
                    'type': 'table',
                    'table': {
                        'table_width': len(table_rows[0]) if table_rows else 1,
                        'has_column_header': True,
                        'has_row_header': False,
                        'children': table_children[:1]
                    }
                })
                if len(table_children) > 1:
                    blocks.append({
                        'object': 'block',
                        'type': '_deferred_children',
                        '_deferred_children': {
                            'children': table_children[1:]
                        }
                    })
            
        # Images ![alt](url) - only external URLs work in Notion
        elif re.match(r'^!\[.*?\]\(.*?\)$', line):
            img_match = re.match(r'^!\[(.*?)\]\((.*?)\)$', line)
            if img_match:
                img_url = img_match.group(2)
                # Skip local/relative paths - Notion only supports external URLs
                if img_url.startswith('http://') or img_url.startswith('https://'):
                    blocks.append({
                        'object': 'block',
                        'type': 'image',
                        'image': {
                            'type': 'external',
                            'external': {'url': img_url}
                        }
                    })
                else:
                    # Render as a note that the image is local-only
                    blocks.append({
                        'object': 'block',
                        'type': 'callout',
                        'callout': {
                            'rich_text': [{'type': 'text', 'text': {'content': 'Image: ' + (img_match.group(1) or img_url) + ' (local file - not available in Notion)'}}],
                            'icon': {'type': 'emoji', 'emoji': '\U0001f5bc'}
                        }
                    })
        # Checkbox items (to-do list)
        elif re.match(r'^\s*-\s\[\s\]\s+', raw_line):
            todo_match = re.match(r'^(\s*)-\s\[\s\]\s+(.*)$', raw_line)
            indent_level = get_indent_level(todo_match.group(1))
            todo_block = {
                'object': 'block',
                'type': 'to_do',
                'to_do': {
                    'rich_text': parse_inline_formatting(todo_match.group(2)),
                    'checked': False
                }
            }
            add_list_block(todo_block, indent_level)
        elif re.match(r'^\s*-\s\[[xX]\]\s+', raw_line):
            todo_match = re.match(r'^(\s*)-\s\[[xX]\]\s+(.*)$', raw_line)
            indent_level = get_indent_level(todo_match.group(1))
            todo_block = {
                'object': 'block',
                'type': 'to_do',
                'to_do': {
                    'rich_text': parse_inline_formatting(todo_match.group(2)),
                    'checked': True
                }
            }
            add_list_block(todo_block, indent_level)
        # Bullet points
        elif re.match(r'^\s*-\s+', raw_line):
            bullet_match = re.match(r'^(\s*)-\s+(.*)$', raw_line)
            indent_level = get_indent_level(bullet_match.group(1))
            bullet_block = {
                'object': 'block',
                'type': 'bulleted_list_item',
                'bulleted_list_item': {
                    'rich_text': parse_inline_formatting(bullet_match.group(2))
                }
            }
            add_list_block(bullet_block, indent_level)
        # Horizontal rule
        elif line.startswith('---') and not ('|' in line):
            list_stack = []
            blocks.append({
                'object': 'block',
                'type': 'divider',
                'divider': {}
            })
        # Regular paragraph
        else:
            list_stack = []
            blocks.append({
                'object': 'block',
                'type': 'paragraph',
                'paragraph': {
                    'rich_text': parse_inline_formatting(line)
                }
            })
        
        i += 1
    
    return blocks

# Read markdown file
with open('$markdown_file', 'r', encoding='utf-8') as f:
    content = f.read()

blocks = markdown_to_notion_blocks(content)
print(json.dumps({'children': blocks}))
" > "$temp_json" 2>&1
    
    local python_exit_code=$?
    if [ $python_exit_code -ne 0 ]; then
        error "Python conversion failed with exit code: $python_exit_code"
        if [ -f "$temp_json" ]; then
            error "Python error output:"
            cat "$temp_json"
        fi
        rm -f "$temp_json"
        exit 1
    fi
    
    # Check if temp file actually exists and has content
    if [ ! -f "$temp_json" ]; then
        error "Conversion failed - temp file does not exist: $temp_json"
        exit 1
    elif [ ! -s "$temp_json" ]; then
        error "Conversion failed - temp file is empty: $temp_json"
        if [ -f "$temp_json" ]; then
            error "File contents:"
            cat "$temp_json"
        fi
        exit 1
    fi
    
    log "Conversion completed. Output file: $temp_json" >&2
    echo "$temp_json"
}

# Update Notion page
update_notion_page() {
    local markdown_file="$1"
    local notion_page_id="$2"

    log "Converting markdown to Notion blocks for: $markdown_file"
    local blocks_file=$(convert_markdown_to_notion_blocks "$markdown_file")
    
    log "Clearing existing page content..."
    # First, get existing blocks to delete them
    local existing_blocks=$(curl -s \
        -H "Authorization: Bearer $NOTION_TOKEN" \
        -H "Notion-Version: 2022-06-28" \
        -H "Content-Type: application/json" \
        "$NOTION_API_URL/blocks/$notion_page_id/children" | jq -r '.results[].id' 2>/dev/null)
    
    # Delete existing blocks
    if [ -n "$existing_blocks" ]; then
        echo "$existing_blocks" | while read -r block_id; do
            if [ -n "$block_id" ] && [ "$block_id" != "null" ]; then
                curl -s -X DELETE \
                    -H "Authorization: Bearer $NOTION_TOKEN" \
                    -H "Notion-Version: 2022-06-28" \
                    "$NOTION_API_URL/blocks/$block_id" >/dev/null
            fi
        done
    fi
    
    log "Uploading new content to Notion..."
    if [ -f "$blocks_file" ]; then
        local file_size=$(wc -c < "$blocks_file")
        log "JSON payload size: $file_size bytes"
    else
        error "Blocks file not found: $blocks_file"
        exit 1
    fi

    # Notion API limits blocks to 100 per request and ~500KB per request body.
    # Build batches block-by-block, flushing when either limit is reached.
    local total_blocks=$(jq '.children | length' "$blocks_file")
    log "Total blocks to upload: $total_blocks"

    local max_blocks_per_batch=100
    local max_bytes_per_batch=400000  # 400KB, well under Notion's ~500KB limit
    local batch_num=0


    # flush_batch uploads blocks [batch_start, batch_start+batch_count) to target_id.
    flush_batch() {
        local start="$1"
        local count="$2"
        local target_id="$3"
        batch_num=$((batch_num + 1))
        log "Uploading batch $batch_num (blocks $start to $((start + count - 1)))..."
        local batch_file
        batch_file=$(mktemp)
        jq "{children: .children[$start:$((start + count))]}" "$blocks_file" > "$batch_file"

        local response
        response=$(curl -s -X PATCH \
            -H "Authorization: Bearer $NOTION_TOKEN" \
            -H "Notion-Version: 2022-06-28" \
            -H "Content-Type: application/json" \
            -d "@$batch_file" \
            "$NOTION_API_URL/blocks/$target_id/children")
        local curl_exit_code=$?
        rm -f "$batch_file"

        if [ $curl_exit_code -ne 0 ]; then
            error "Curl failed with exit code: $curl_exit_code"
            rm -f "$blocks_file"
            exit 1
        fi

        local error_msg
        error_msg=$(echo "$response" | jq -r '.message // empty' 2>/dev/null)
        if [ -n "$error_msg" ]; then
            error "Notion API error: $error_msg"
            local error_code
            error_code=$(echo "$response" | jq -r '.code // empty' 2>/dev/null)
            [ -n "$error_code" ] && error "Error code: $error_code"
            rm -f "$blocks_file"
            exit 1
        fi

    }

    local batch_start=0
    local batch_count=0
    local batch_bytes=0
    local i=0

    while [ $i -lt $total_blocks ]; do
        local block_type
        block_type=$(jq -r ".children[$i].type" "$blocks_file")

        # _deferred_children: append rows to the previously created table block
        if [ "$block_type" = "_deferred_children" ]; then
            # Flush any pending regular blocks first
            if [ $batch_count -gt 0 ]; then
                flush_batch "$batch_start" "$batch_count" "$notion_page_id"
                sleep 0.5
                batch_start=$((batch_start + batch_count))
                batch_count=0
                batch_bytes=0
            fi

            # The table block was the last one uploaded; get its ID from the API
            local table_block_id
            table_block_id=$(curl -s \
                -H "Authorization: Bearer $NOTION_TOKEN" \
                -H "Notion-Version: 2022-06-28" \
                "$NOTION_API_URL/blocks/$notion_page_id/children?page_size=100" \
                | jq -r '.results[-1].id // empty' 2>/dev/null)

            if [ -z "$table_block_id" ]; then
                error "Could not retrieve table block ID to append rows"
                rm -f "$blocks_file"
                exit 1
            fi

            log "Appending deferred children to block $table_block_id..."

            local child_count
            child_count=$(jq ".children[$i]._deferred_children.children | length" "$blocks_file")
            # Table rows are ~600 bytes each; 50 per batch is well under 400KB
            local row_batch_size=50
            local child_offset=0

            while [ $child_offset -lt $child_count ]; do
                batch_num=$((batch_num + 1))
                local end=$((child_offset + row_batch_size))
                [ $end -gt $child_count ] && end=$child_count
                log "Uploading batch $batch_num (rows $child_offset to $((end - 1)) of $child_count)..."
                local child_batch_file
                child_batch_file=$(mktemp)
                jq "{children: .children[$i]._deferred_children.children[$child_offset:$end]}" "$blocks_file" > "$child_batch_file"
                local child_response
                child_response=$(curl -s -X PATCH \
                    -H "Authorization: Bearer $NOTION_TOKEN" \
                    -H "Notion-Version: 2022-06-28" \
                    -H "Content-Type: application/json" \
                    -d "@$child_batch_file" \
                    "$NOTION_API_URL/blocks/$table_block_id/children")
                rm -f "$child_batch_file"
                local child_error
                child_error=$(echo "$child_response" | jq -r '.message // empty' 2>/dev/null)
                if [ -n "$child_error" ]; then
                    error "Notion API error appending rows: $child_error"
                    rm -f "$blocks_file"
                    exit 1
                fi
                child_offset=$((child_offset + row_batch_size))
                [ $child_offset -lt $child_count ] && sleep 0.5
            done

            batch_start=$((i + 1))
            i=$((i + 1))
            continue
        fi

        local block_bytes
        block_bytes=$(jq ".children[$i]" "$blocks_file" | wc -c)

        # Flush if adding this block would exceed limits
        if [ $batch_count -gt 0 ] && \
           ([ $((batch_bytes + block_bytes)) -gt $max_bytes_per_batch ] || \
            [ $batch_count -ge $max_blocks_per_batch ]); then
            flush_batch "$batch_start" "$batch_count" "$notion_page_id"
            sleep 0.5
            batch_start=$i
            batch_count=0
            batch_bytes=0
        fi

        batch_count=$((batch_count + 1))
        batch_bytes=$((batch_bytes + block_bytes))
        i=$((i + 1))
    done

    # Upload any remaining blocks
    if [ $batch_count -gt 0 ]; then
        flush_batch "$batch_start" "$batch_count" "$notion_page_id"
    fi

    log "Successfully uploaded $batch_num batch(es) to Notion"

    # Clean up
    rm -f "$blocks_file"
    success "File '$markdown_file' successfully deployed to Notion!"
}

# Deploy a single file to Notion
deploy_file() {
    local file_path="$1"

    log "Processing file: $file_path"

    # Check if file exists
    if [ ! -f "$file_path" ]; then
        warning "File not found: $file_path - skipping"
        return 1
    fi

    # Get Notion page ID from mappings
    local page_id=$(get_notion_page_id "$file_path")
    if [ -z "$page_id" ] || [ "$page_id" = "null" ]; then
        warning "No Notion page mapping found for: $file_path - skipping"
        return 1
    fi

    log "Found Notion page ID: ${page_id:0:8}... for $file_path"

    # Check if file has changed (unless forced)
    if [ "${FORCE_DEPLOY:-false}" = "false" ] && ! has_file_changed "$file_path"; then
        log "No changes detected in $file_path, skipping deployment"
        return 0
    fi

    # Deploy to Notion
    update_notion_page "$file_path" "$page_id"
    return 0
}

# Deploy multiple files
deploy_changed_files() {
    local files="$1"
    local deployed_count=0
    local skipped_count=0
    local error_count=0

    if [ "$files" = "all" ]; then
        log "Deploying all mapped files..."
        # Get all mapped files from mappings file
        files=$(grep -v "^#" "$MAPPINGS_FILE" | grep "=" | cut -d'=' -f1 | tr '\n' ',')
    fi

    # Convert comma-separated list to array
    IFS=',' read -ra file_array <<< "$files"

    for file_path in "${file_array[@]}"; do
        # Trim whitespace
        file_path=$(echo "$file_path" | xargs)

        if [ -z "$file_path" ]; then
            continue
        fi

        if deploy_file "$file_path"; then
            deployed_count=$((deployed_count + 1))
        else
            error_count=$((error_count + 1))
        fi
    done

    log "Deployment complete: $deployed_count deployed, $error_count errors"
    return 0
}

# Handle command line arguments
case "${1:-}" in
    --deploy-changed)
        log "Starting Notion deployment for changed files..."
        check_dependencies
        check_environment

        if [ -z "$CHANGED_FILES" ]; then
            error "CHANGED_FILES environment variable not set"
            exit 1
        fi

        deploy_changed_files "$CHANGED_FILES"
        log "Deployment process completed"
        ;;
    --force)
        log "Force deployment requested for all mapped files"
        check_dependencies
        check_environment
        export FORCE_DEPLOY=true
        deploy_changed_files "all"
        log "Deployment process completed"
        ;;
    --deploy-file)
        if [ -z "$2" ]; then
            error "File path required for --deploy-file option"
            exit 1
        fi
        log "Deploying single file: $2"
        check_dependencies
        check_environment
        export FORCE_DEPLOY=true
        deploy_file "$2"
        log "Deployment process completed"
        ;;
    --help|help)
        echo "Usage: $0 [options]"
        echo ""
        echo "Options:"
        echo "  --deploy-changed    Deploy files specified in CHANGED_FILES env var"
        echo "  --force             Force deployment of all mapped files"
        echo "  --deploy-file FILE  Deploy a specific file"
        echo "  --help              Show this help message"
        echo ""
        echo "Environment variables:"
        echo "  NOTION_TOKEN     - Your Notion integration token (required)"
        echo "  CHANGED_FILES    - Comma-separated list of changed files (for --deploy-changed)"
        echo ""
        echo "Configuration files:"
        echo "  .github/notion-mappings.txt - Maps markdown files to Notion page IDs"
        echo ""
        echo "Examples:"
        echo "  $0 --deploy-changed"
        echo "  $0 --force"
        echo "  $0 --deploy-file _static/runbooks/service-principal-rotation.md"
        ;;
    *)
        error "Unknown option: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
esac
