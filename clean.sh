#!/usr/bin/env bash
# clean.sh — remove training-generated artifacts & caches,
# while PROTECTING everything under ./versions/ (including latest model files).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

DRY_RUN=0
FORCE=0
KEEP_LATEST_MODEL=1   # default: keep only newest model dir (OUTSIDE ./versions)

usage() {
  cat <<'EOF'
Usage: ./clean.sh [options]

Options:
  --dry-run            Print what would be deleted, but do not delete.
  --keep-all-models    Do not delete any model dirs (outside ./versions).
  --keep-latest-model  Keep only the newest model dir (outside ./versions) [default].
  --force              Do not ask for confirmation.
  -h, --help           Show this help.

Safety:
- Never deletes anything under ./versions/ (including ./versions/0.01/model/*).
- Does not delete general images (png/jpg) to preserve README/notebook media.
EOF
}

say() { printf "%s\n" "$*"; }

rm_safe() {
  local path="$1"
  # Never delete current/parent directory
  if [[ "$path" == "." || "$path" == "./" || "$path" == ".." || "$path" == "../" ]]; then
    return 0
  fi
  # HARD SAFETY: protect ./versions/*
  if [[ "$path" == ./versions/* ]]; then
    return 0
  fi

  if [[ -e "$path" ]]; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
      say "[dry-run] rm -rf -- $path"
    else
      rm -rf -- "$path"
      say "deleted: $path"
    fi
  fi
}

# Find and delete matches, excluding ./versions/*
find_rm() {
  local desc="$1"; shift
  say "-> $desc"
  while IFS= read -r p; do
    rm_safe "$p"
  done < <(
    find . \
      -path "./versions/*" -prune -o \
      \( "$@" \) -print
  )
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --keep-all-models) KEEP_LATEST_MODEL=0; shift ;;
    --keep-latest-model) KEEP_LATEST_MODEL=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) say "Unknown option: $1"; usage; exit 1 ;;
  esac
done

say "Cleaning repo at: $ROOT_DIR"
say "dry-run: $DRY_RUN"
say "keep-latest-model (outside ./versions): $KEEP_LATEST_MODEL"
say "NOTE: ./versions/* is protected and will not be touched."
say ""

if [[ "$FORCE" -ne 1 && "$DRY_RUN" -ne 1 ]]; then
  read -r -p "This will delete training artifacts & caches (NOT ./versions). Continue? [y/N] " ans
  case "${ans:-N}" in
    y|Y|yes|YES) ;;
    *) say "Aborted."; exit 1 ;;
  esac
fi

###############################################################################
# 1) Caches
###############################################################################
find_rm "Remove Python caches" \
  -type d \( -name "__pycache__" -o -name ".pytest_cache" -o -name ".mypy_cache" -o -name ".ruff_cache" \) -prune

find_rm "Remove notebook checkpoints" \
  -type d -name ".ipynb_checkpoints" -prune

###############################################################################
# 2) Training-derived arrays & artifacts (outside ./versions only)
###############################################################################
find_rm "Remove training-derived numpy dumps (*.npy/*.npz)" \
  -type f \( -name "*.npy" -o -name "*.npz" \)

find_rm "Remove tensorboard event files & logs" \
  -type f \( -name "events.out.tfevents.*" -o -name "*.log" \)

###############################################################################
# 3) Common run/log folders (outside ./versions only)
###############################################################################
rm_safe "./wandb"
rm_safe "./mlruns"
rm_safe "./runs"
rm_safe "./logs"

###############################################################################
# 4) Model directories named "model" (outside ./versions only)
# Default: keep only newest; or keep all if --keep-all-models.
###############################################################################
mapfile -t MODEL_DIRS < <(
  find . -path "./versions/*" -prune -o -type d -name "model" -print | sort
)

if [[ "${#MODEL_DIRS[@]}" -gt 0 ]]; then
  if [[ "$KEEP_LATEST_MODEL" -eq 1 ]]; then
    LATEST_MODEL="$(ls -td "${MODEL_DIRS[@]}" 2>/dev/null | head -n 1 || true)"
    say "-> Keeping newest model dir (outside ./versions): ${LATEST_MODEL:-<none>}"
    for d in "${MODEL_DIRS[@]}"; do
      if [[ "$d" != "$LATEST_MODEL" ]]; then
        rm_safe "$d"
      fi
    done
  else
    say "-> Keeping all model dirs (outside ./versions)"
  fi
fi

###############################################################################
# 5) Loose TF checkpoint files (outside ./versions only)
# WARNING: This removes checkpoint/test.* files anywhere else in repo.
###############################################################################
find_rm "Remove loose TensorFlow checkpoint files (outside ./versions)" \
  -type f \( -name "*.data-*" -o -name "*.index" -o -name "*.meta" -o -name "checkpoint" \)

say ""
say "Done."
if [[ "$DRY_RUN" -eq 1 ]]; then
  say "Dry-run only: nothing was deleted."
fi
