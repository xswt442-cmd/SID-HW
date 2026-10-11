#!/usr/bin/env bash
set -euo pipefail

# 用法：SID=2453721 [COUNT_PER_GROUP=131072] [GROUP_COUNT=16] ./2453721-hw1-q1.sh
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SID="${SID:-2453721}"
COUNT_PER_GROUP="${COUNT_PER_GROUP:-131072}"
GROUP_COUNT="${GROUP_COUNT:-16}"
OUT="$ROOT/output"
SECONDS=0
mkdir -p "$OUT"

python3 "$ROOT/generate_primes.py" \
  --sid "$SID" --count "$COUNT_PER_GROUP" --groups "$GROUP_COUNT" --output-dir "$OUT"

merged="$OUT/${SID}-hw1-q1.txt"
: > "$merged"
wc_total=0
for ((i=0; i<GROUP_COUNT; i++)); do
  part="$OUT/${SID}-hw1-q1-${i}.txt"
  cat "$part" >> "$merged"
  count=$(wc -w < "$part")
  printf '%s: %s words\n' "$(basename "$part")" "$count"
  wc_total=$((wc_total + count))
done
merged_count=$(wc -w < "$merged")
printf '%s: %s words\n' "$(basename "$merged")" "$merged_count"
if ((wc_total == merged_count)); then
  printf 'YES: the total wc is equal to %s\n' "$wc_total"
else
  printf 'NO: the total wc of 16 files is %s, and the wc of the merged file is %s\n' "$wc_total" "$merged_count"
  exit 1
fi
printf 'generation and merge time: %ss\n' "$SECONDS"
