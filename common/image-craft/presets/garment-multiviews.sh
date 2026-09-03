#!/usr/bin/env bash
# ==============================================================================
# Script: garment-multiviews.sh
# Description: Wrapper around model-multiviews.sh tailored for garments/clothing.
#              Generates Left, Top, and Bottom views while prompting the model
#              to account for hollow parts (sleeves, collar, openings).
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
  $(basename "$0") -i <REF_IMAGE> [-p EXTRA_PROMPT] [-v VIEWS] [OPTIONS...]

Description:
  Generates multi-view images (Left, Top, Bottom) for garments/clothing models.
  Wraps model-multiviews.sh, setting default views to "left; top; bottom" and
  automatically adding the prompt: "account for hollow parts of the model".

Arguments:
  REF_IMAGE       Path to front reference image of the garment
  EXTRA_PROMPT    Optional extra prompt appended alongside hollow parts instruction

Options:
  -i, --image IMAGE_PATH        Path to front reference image
  -p, --extra-prompt PROMPT     Additional prompt to append (e.g. "clay style")
  -v, --views VIEWS             Override views (default: "left; top; bottom")
  -r, -a, --ratio RATIO         Aspect ratio for generated views (default: 1:1)
  -s, --size SIZE               Resolution for generated views (default: 4K)
  -h, --help                    Show this help message
  ...                           Any other flags are forwarded to gemini-image.py
                                (e.g. --transparent, -m 3.1-flash, -o outputs/)

Examples:
  $(basename "$0") shirt_front.png
  $(basename "$0") jacket_front.png "denim fabric, realistic folds"
  $(basename "$0") -i dress_front.png -p "3D render" --transparent
  $(basename "$0") -i shirt.png -r 16:9 -s 2K
EOF
}

REF_IMAGE=""
EXTRA_PROMPT=""
VIEWS="left; top; bottom"
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
        --image=*)
            REF_IMAGE="${1#*=}"
            shift
            ;;
        -v|--views)
            if [[ $# -lt 2 ]]; then
                echo "Error: $1 requires a views string." >&2
                exit 1
            fi
            VIEWS="$2"
            shift 2
            ;;
        --views=*)
            VIEWS="${1#*=}"
            shift
            ;;
        -p|--prompt|--extra-prompt)
            if [[ $# -lt 2 ]]; then
                echo "Error: $1 requires a prompt string." >&2
                exit 1
            fi
            EXTRA_PROMPT="$2"
            shift 2
            ;;
        --prompt=*|--extra-prompt=*)
            EXTRA_PROMPT="${1#*=}"
            shift
            ;;
        -r|-a|--ratio|--aspect-ratio)
            if [[ $# -lt 2 ]]; then
                echo "Error: $1 requires an aspect ratio." >&2
                exit 1
            fi
            EXTRA_ARGS+=("$1" "$2")
            shift 2
            ;;
        -r=*|-a=*|--ratio=*|--aspect-ratio=*)
            EXTRA_ARGS+=("$1")
            shift
            ;;
        -s|--size|--resolution)
            if [[ $# -lt 2 ]]; then
                echo "Error: $1 requires a size/resolution." >&2
                exit 1
            fi
            EXTRA_ARGS+=("$1" "$2")
            shift 2
            ;;
        -s=*|--size=*|--resolution=*)
            EXTRA_ARGS+=("$1")
            shift
            ;;
        -m|--model|-o|--output|-f|--format|-video|--video|--previous-id|--prev|--interaction-id|--thinking-level|--api-key)
            if [[ $# -lt 2 ]]; then
                echo "Error: $1 requires an argument." >&2
                exit 1
            fi
            EXTRA_ARGS+=("$1" "$2")
            shift 2
            ;;
        -m=*|--model=*|-o=*|--output=*|-f=*|--format=*|-video=*|--video=*|--previous-id=*|--prev=*|--interaction-id=*|--thinking-level=*|--api-key=*)
            EXTRA_ARGS+=("$1")
            shift
            ;;
        --transparent-background|--transparent|--search|--grounding|--image-search|--list-models|--list-ratios|--verbose)
            EXTRA_ARGS+=("$1")
            shift
            ;;
        --*=*|-*=*)
            EXTRA_ARGS+=("$1")
            shift
            ;;
        --)
            shift
            while [[ $# -gt 0 ]]; do
                if [[ -z "${REF_IMAGE}" ]]; then
                    REF_IMAGE="$1"
                elif [[ -z "${EXTRA_PROMPT}" ]]; then
                    EXTRA_PROMPT="$1"
                else
                    EXTRA_ARGS+=("$1")
                fi
                shift
            done
            break
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

# Base instruction for garment hollow parts
GARMENT_BASE_PROMPT="when generation, account for hollow parts of the model as garments. But don't cut or remove any part of the model to show the hollow effect. We need its completely original views. "

if [[ -n "${EXTRA_PROMPT}" ]]; then
    COMBINED_PROMPT="${GARMENT_BASE_PROMPT}, ${EXTRA_PROMPT}"
else
    COMBINED_PROMPT="${GARMENT_BASE_PROMPT}"
fi

# Invoke model-multiviews.sh
exec "${MULTIVIEW_SCRIPT}" \
    -i "${REF_IMAGE}" \
    -p "${COMBINED_PROMPT}" \
    -v "${VIEWS}" \
    ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
