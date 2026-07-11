#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 /path/to/Anki2/<Profile>/collection.media" >&2
  exit 2
fi

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
destination="$1"

if [ ! -d "$destination" ]; then
  echo "Destination is not a directory: $destination" >&2
  exit 2
fi

find "$project_dir/outputs" -type f -path '*/media/gaz-*' -exec cp {} "$destination"/ \;
echo "Copied Gazetteer media to $destination"
