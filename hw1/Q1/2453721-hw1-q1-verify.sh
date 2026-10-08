#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SID="2453721"
OUT="$ROOT/output"
TOTAL=0
for ((i=0; i<16; i++)); do
  file="$OUT/${SID}-hw1-q1-${i}.txt"
  count=$(wc -w < "$file")
  printf '%s: %s words\n' "$(basename "$file")" "$count"
  TOTAL=$((TOTAL + count))
done
merged="$OUT/${SID}-hw1-q1.txt"
merged_count=$(wc -w < "$merged")
printf '%s: %s words\n' "$(basename "$merged")" "$merged_count"
if ((TOTAL == merged_count)); then
  printf 'YES: the total wc is equal to %s\n' "$TOTAL"
else
  printf 'NO: the total wc of 16 files is %s, and the wc of the merged file is %s\n' "$TOTAL" "$merged_count"
  exit 1
fi
