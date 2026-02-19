#!/bin/bash
# Docker build and run script for delete_duplicates.py
# This script builds the Docker image and runs it with proper volume mounting

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="notion-app"
CONTAINER_NAME="notion-duplicate-cleaner"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}   Notion Duplicate Cleaner - Docker Runner${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Function to print colored messages
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is running
print_info "Checking Docker status..."
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker and try again."
    exit 1
fi
print_success "Docker is running"

# Navigate to project root
cd "$PROJECT_ROOT"
print_info "Project root: $PROJECT_ROOT"

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_error ".env file not found in $PROJECT_ROOT"
    print_error "Please create .env with NOTION_API_KEY and CRM_DATABASE_ID"
    exit 1
fi
print_success ".env file found"

# Check if Dockerfile exists
if [ ! -f "notion/Dockerfile" ]; then
    print_error "Dockerfile not found at notion/Dockerfile"
    exit 1
fi
print_success "Dockerfile found"

# Check for existing progress file
if [ -f "notion/fetch_progress.json" ]; then
    print_warning "Found existing progress file (fetch_progress.json)"
    PROGRESS_SIZE=$(du -h "notion/fetch_progress.json" | cut -f1)
    PROGRESS_PAGES=$(grep -o '"results":\[' "notion/fetch_progress.json" | wc -l | tr -d ' ')
    print_info "Progress file size: $PROGRESS_SIZE"
    echo ""
    echo -e "${YELLOW}The script will resume from previous progress.${NC}"
    echo -e "${YELLOW}To start fresh, delete the progress file first:${NC}"
    echo -e "${YELLOW}  rm notion/fetch_progress.json${NC}"
    echo ""
    read -p "Continue with existing progress? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Cancelled by user"
        exit 0
    fi
else
    print_info "No progress file found - will start from beginning"
fi

echo ""
print_info "Building Docker image: $IMAGE_NAME"
echo -e "${BLUE}------------------------------------------------${NC}"

# Build Docker image
if docker build -f notion/Dockerfile -t "$IMAGE_NAME" .; then
    print_success "Docker image built successfully"
else
    print_error "Failed to build Docker image"
    exit 1
fi

echo ""
print_info "Checking for existing container..."

# Remove existing container if it exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    print_warning "Removing existing container: $CONTAINER_NAME"
    docker rm -f "$CONTAINER_NAME" > /dev/null 2>&1
fi

echo ""
print_info "Starting container with volume mount..."
print_info "Volume: $PROJECT_ROOT/notion -> /app"
echo -e "${BLUE}------------------------------------------------${NC}"
echo ""

# Run the container with volume mount
# Using --rm to automatically remove container when it exits
docker run \
    --rm \
    --name "$CONTAINER_NAME" \
    -v "$PROJECT_ROOT/notion:/app" \
    -v "$PROJECT_ROOT/.env:/app/.env" \
    "$IMAGE_NAME"

# Capture exit code
EXIT_CODE=$?

echo ""
echo -e "${BLUE}------------------------------------------------${NC}"

if [ $EXIT_CODE -eq 0 ]; then
    print_success "Script completed successfully!"
    
    # Check if progress file still exists (shouldn't if completed)
    if [ -f "notion/fetch_progress.json" ]; then
        print_warning "Progress file still exists - script may have been interrupted"
        print_info "Run this script again to resume"
    else
        print_success "Progress file cleaned up - all done!"
    fi
else
    print_error "Script exited with error code: $EXIT_CODE"
    
    # Check if progress was saved
    if [ -f "notion/fetch_progress.json" ]; then
        print_info "Progress has been saved to: notion/fetch_progress.json"
        print_success "Run this script again to resume from where it stopped"
    fi
    
    exit $EXIT_CODE
fi

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}              Done!${NC}"
echo -e "${GREEN}================================================${NC}"
