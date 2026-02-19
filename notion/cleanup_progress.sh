#!/bin/bash
# Cleanup script for delete_duplicates progress file

PROGRESS_FILE="fetch_progress.json"

if [ -f "$PROGRESS_FILE" ]; then
    echo "Found progress file: $PROGRESS_FILE"
    read -p "Do you want to delete it and start fresh? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm "$PROGRESS_FILE"
        echo "Progress file deleted. Next run will start from the beginning."
    else
        echo "Progress file kept. Next run will resume from saved position."
    fi
else
    echo "No progress file found. Nothing to clean up."
fi
