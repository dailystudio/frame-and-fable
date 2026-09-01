#!/usr/bin/env bash
# ==============================================================================
# Script: t-pose-multiviews.sh
# Description: Wrapper around model-multiviews.sh that generates Left, Right,
#              and Back views of a model in T-POSE from a front reference image.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
MULTIVIEW_SCRIPT="${SCRIPT_DIR}/model-multiviews.sh"

if [[ ! -f "${MULTIVIEW_SCRIPT}" ]]; then
    echo "Error: model-multiviews.sh not found at ${MULTIVIEW_SCRIPT}" >&2
    exit 1
fi

show_help() {
    cat << EOF
Usage:
  $(basename "$0") <REF_IMAGE> [EXTRA_PROMPT] [OPTIONS...]
  $(basename "$0") -i <REF_IMAGE> [-p EXTRA_PROMPT] [OPTIONS...]

Description:
  Generates multi-view (Left, Right, Back) images of a model in T-POSE.
  Wraps model-multiviews.sh and automatically appends "T-POSE" to the prompt.

Arguments:
  REF_IMAGE       Path to front reference image of the model
  EXTRA_PROMPT    Optional extra prompt appended alongside "T-POSE"

Options:
  -i, --image IMAGE_PATH        Path to front reference image
  -p, --extra-prompt PROMPT     Additional prompt to append (e.g. "clay style")
  -h, --help                    Show this help message
  ...                           Any other flags are forwarded to gemini-image.py
                                (e.g. --transparent, -m 3.1-flash, -o outputs/)

Examples:
  $(basename "$0") character_front.png
  $(basename "$0") character_front.png "keep white background, clay style"
  $(basename "$0") -i character_front.png -p "3D render, clay style" --transparent
EOF
}

REF_IMAGE=""
EXTRA_PROMPT=""
EXTRA_ARGS=()

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            show_help
            exit 0
            ;;
        -i|--image)
            if [[ $# -lt 2 ]]; then
                echo "Error: $1 requires an image path." >&2
                exit 1
            fi
            REF_IMAGE="$2"
            shift 2
            ;;
        -p|--prompt|--extra-prompt)
            if [[ $# -lt 2 ]]; then
                echo "Error: $1 requires a prompt string." >&2
                exit 1
            fi
            EXTRA_PROMPT="$2"
            shift 2
            ;;
        *)
            if [[ -z "${REF_IMAGE}" && ! "$1" =~ ^- ]]; then
                REF_IMAGE="$1"
                shift
            elif [[ -z "${EXTRA_PROMPT}" && ! "$1" =~ ^- ]]; then
                EXTRA_PROMPT="$1"
                shift
            else
                EXTRA_ARGS+=("$1")
                shift
            fi
            ;;
    esac
done

if [[ -z "${REF_IMAGE}" ]]; then
    echo "Error: Reference image is required." >&2
    echo ""
    show_help
    exit 1
fi

# Combine "T-POSE" with any additional prompt
if [[ -n "${EXTRA_PROMPT}" ]]; then
    COMBINED_PROMPT="T-POSE, ${EXTRA_PROMPT}"
else
    COMBINED_PROMPT="T-POSE"
fi

# Invoke model-multiviews.sh
exec "${MULTIVIEW_SCRIPT}" \
    "${REF_IMAGE}" \
    "${COMBINED_PROMPT}" \
    ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
