#!/usr/bin/env bash
# ==============================================================================
# Script: model-multiviews.sh
# Description: Generates multi-view images from a front reference image using
#              gemini-image.py. Supports default and custom view sets.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." >/dev/null 2>&1 && pwd)"
GEMINI_SCRIPT="${PROJECT_ROOT}/gemini-image.py"

# Resolve python interpreter
if [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
    PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
elif [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
    PYTHON_BIN="${VIRTUAL_ENV}/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "Error: Python interpreter not found." >&2
    exit 1
fi

if [[ ! -f "${GEMINI_SCRIPT}" ]]; then
    echo "Error: gemini-image.py not found at ${GEMINI_SCRIPT}" >&2
    exit 1
fi

show_help() {
    cat << EOF
Usage:
  $(basename "$0") <REF_IMAGE> [EXTRA_PROMPT] [OPTIONS...]
  $(basename "$0") -i <REF_IMAGE> [-p EXTRA_PROMPT] [-v VIEWS] [OPTIONS...]

Arguments:
  REF_IMAGE       Path to front reference image of the model
  EXTRA_PROMPT    Optional extra prompt appended to each view prompt

Options:
  -i, --image IMAGE_PATH        Path to front reference image
  -p, --extra-prompt PROMPT     Additional prompt to append (e.g. "keep white background")
  -v, --views VIEWS             Semicolon- or comma-separated list of views to generate
                                (e.g. "left; top; bottom" or "front, back, left, right")
                                Default: "left; right; back"
  -r, -a, --ratio RATIO         Aspect ratio for generated views (default: 1:1)
  -s, --size SIZE               Resolution for generated views (default: 4K)
  -h, --help                    Show this help message
  ...                           Any other flags are forwarded to gemini-image.py
                                (e.g. --transparent, -m 3.1-flash, -o outputs/)

Examples:
  $(basename "$0") character_front.png
  $(basename "$0") character_front.png "keep white background, clay style"
  $(basename "$0") garment.png -v "left; top; bottom" -p "account for hollow parts of the model"
  $(basename "$0") -i character_front.png -p "3D render, clay style" --transparent
  $(basename "$0") -i character_front.png -r 16:9 -s 2K
EOF
}

trim() {
    local var="$*"
    var="${var#"${var%%[![:space:]]*}"}"
    var="${var%"${var##*[![:space:]]}"}"
    echo -n "$var"
}

REF_IMAGE=""
EXTRA_PROMPT=""
CUSTOM_VIEWS_RAW=""
ASPECT_RATIO="1:1"
IMAGE_SIZE="4K"
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
        -v|--views)
            if [[ $# -lt 2 ]]; then
                echo "Error: $1 requires a views string." >&2
                exit 1
            fi
            CUSTOM_VIEWS_RAW="$2"
            shift 2
            ;;
        --views=*)
            CUSTOM_VIEWS_RAW="${1#*=}"
            shift
            ;;
        -r|-a|--ratio|--aspect-ratio)
            if [[ $# -lt 2 ]]; then
                echo "Error: $1 requires an aspect ratio." >&2
                exit 1
            fi
            ASPECT_RATIO="$2"
            shift 2
            ;;
        -r=*|-a=*|--ratio=*|--aspect-ratio=*)
            ASPECT_RATIO="${1#*=}"
            shift
            ;;
        -s|--size|--resolution)
            if [[ $# -lt 2 ]]; then
                echo "Error: $1 requires a size/resolution." >&2
                exit 1
            fi
            IMAGE_SIZE="$2"
            shift 2
            ;;
        -s=*|--size=*|--resolution=*)
            IMAGE_SIZE="${1#*=}"
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

if [[ ! -f "${REF_IMAGE}" ]]; then
    echo "Error: Reference image not found: ${REF_IMAGE}" >&2
    exit 1
fi

# Build views list
VIEWS=()

if [[ -n "${CUSTOM_VIEWS_RAW}" ]]; then
    IFS=";" read -ra RAW_TOKENS <<< "${CUSTOM_VIEWS_RAW}"
    if [[ ${#RAW_TOKENS[@]} -le 1 && "${CUSTOM_VIEWS_RAW}" =~ , ]]; then
        IFS="," read -ra RAW_TOKENS <<< "${CUSTOM_VIEWS_RAW}"
    fi

    for raw in "${RAW_TOKENS[@]}"; do
        token="$(trim "$raw")"
        [[ -z "$token" ]] && continue

        if [[ "$token" =~ ^[Gg]enerate ]]; then
            base_prompt="$token"
            name="$token"
        else
            cap_token="$(echo "$token" | awk '{for(i=1;i<=NF;i++)sub(/./,toupper(substr($i,1,1)),$i)}1')"
            if [[ "$token" =~ [Vv]iew$ ]]; then
                base_prompt="Generate model's ${token}"
                name="${cap_token}"
            else
                base_prompt="Generate model's ${token} view"
                name="${cap_token} View"
            fi
        fi

        if [[ -n "${EXTRA_PROMPT}" ]]; then
            prompt="${base_prompt}, ${EXTRA_PROMPT}"
        else
            prompt="${base_prompt}"
        fi

        VIEWS+=("${name}|${prompt}")
    done
else
    # Default views: Left, Right, Back
    DEFAULT_LIST=("left" "right" "back")
    for v in "${DEFAULT_LIST[@]}"; do
        cap_v="$(echo "$v" | awk '{for(i=1;i<=NF;i++)sub(/./,toupper(substr($i,1,1)),$i)}1')"
        base_prompt="Generate model's ${v} view"
        name="${cap_v} View"

        if [[ -n "${EXTRA_PROMPT}" ]]; then
            prompt="${base_prompt}, ${EXTRA_PROMPT}"
        else
            prompt="${base_prompt}"
        fi

        VIEWS+=("${name}|${prompt}")
    done
fi

if [[ ${#VIEWS[@]} -eq 0 ]]; then
    echo "Error: No valid views specified." >&2
    exit 1
fi

echo "================================================================"
echo " Starting Multi-view Generation"
echo " Reference Image : ${REF_IMAGE}"
if [[ -n "${EXTRA_PROMPT}" ]]; then
    echo " Extra Prompt    : ${EXTRA_PROMPT}"
fi
echo " Total Views     : ${#VIEWS[@]}"
echo " Aspect Ratio    : ${ASPECT_RATIO}"
echo " Resolution      : ${IMAGE_SIZE}"
if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
    echo " Extra Options   : ${EXTRA_ARGS[*]}"
fi
echo "================================================================"
echo ""

TOTAL=${#VIEWS[@]}
CURRENT=1

for ITEM in "${VIEWS[@]}"; do
    NAME="${ITEM%%|*}"
    PROMPT="${ITEM#*|}"

    echo "----------------------------------------------------------------"
    echo "[${CURRENT}/${TOTAL}] Generating ${NAME}..."
    echo "Prompt: \"${PROMPT}\""
    echo "----------------------------------------------------------------"

    "${PYTHON_BIN}" "${GEMINI_SCRIPT}" \
        "${PROMPT}" \
        -i "${REF_IMAGE}" \
        -r "${ASPECT_RATIO}" \
        -s "${IMAGE_SIZE}" \
        ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}

    echo ""
    CURRENT=$((CURRENT + 1))
done

echo "================================================================"
echo " All ${TOTAL} views generated successfully!"
echo "================================================================"
