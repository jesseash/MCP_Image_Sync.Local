#!/usr/bin/env bash
set -e

IMAGE_NAME_FETCH="fetch-reader"
IMAGE_NAME_ONESEARCH="onesearch"
IMAGE_TAG="latest"

# Always run from the directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE}")" && pwd)"
cd "$SCRIPT_DIR"

PAT_FILE="$SCRIPT_DIR/pat.txt"

# Verify pat.txt exists and has content
if [ ! -s "$PAT_FILE" ]; then
    echo "Error: pat.txt is missing or empty in $SCRIPT_DIR"
    exit 1
fi

# Prompt for GitHub username if not already passed via environment
if [ -z "$GITHUB_USER" ]; then
    read -rp "Enter your GitHub username: " GITHUB_USER
fi

# Strip accidental whitespace and check that a username was entered
GITHUB_USER=$(echo "$GITHUB_USER" | tr -d '[:space:]')
if [ -z "$GITHUB_USER" ]; then
    echo "Error: GitHub username cannot be empty."
    exit 1
fi

# Read PAT and strip any spaces or Windows line endings
CR_PAT=$(tr -d '[:space:]' < "$PAT_FILE")

# Ensure lowercase username for GHCR
OWNER_LOWER=$(echo "$GITHUB_USER" | tr '[:upper:]' '[:lower:]')
IMAGE_URI_FETCH="ghcr.io/${OWNER_LOWER}/${IMAGE_NAME_FETCH}:${IMAGE_TAG}"
IMAGE_URI_ONESEARCH="ghcr.io/${OWNER_LOWER}/${IMAGE_NAME_ONESEARCH}:${IMAGE_TAG}"

echo "Logging into ghcr.io as $OWNER_LOWER..."
echo "$CR_PAT" | sudo docker login ghcr.io -u "$OWNER_LOWER" --password-stdin
# 1. Handle SearxNG
 
 sudo docker pull searxng/searxng:latest
 sudo docker tag searxng/searxng:latest ghcr.io/$OWNER_LOWER/searxng-engine:latest
 sudo docker push ghcr.io/$OWNER_LOWER/searxng-engine:latest


# 2. Handle Python Tester
sudo docker pull python:3.11
sudo docker tag python:3.11 ghcr.io/$OWNER_LOWER/python-tester:3.11
sudo docker push ghcr.io/$OWNER_LOWER/python-tester:3.11


echo "Building $IMAGE_URI_ONESEARCH from Dockerfile..."
sudo docker build -f Dockerfile.onesearch -t "$IMAGE_URI_ONESEARCH" .
echo "Pushing $IMAGE_URI_ONESEARCH  to GHCR..."
sudo docker push "$IMAGE_URI_ONESEARCH"


echo "Done! Pushed to $IMAGE_URI_ONESEARCH"

echo "Building $IMAGE_URI_FETCH from Dockerfile..."
sudo docker build -f Dockerfile.fetch -t "$IMAGE_URI_FETCH" .

echo "Pushing $IMAGE_URI_FETCH to GHCR..."
sudo docker push "$IMAGE_URI_FETCH"

echo "Done! Pushed to $IMAGE_URI_FETCH"
