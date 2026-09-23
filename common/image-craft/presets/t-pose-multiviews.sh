#!/usr/bin/env bash
# ==============================================================================
# Script: t-pose-multiviews.sh
# Description: Generates multi-view images of a model in T-POSE from any reference
#              image (not required to be a front view).
#              Phase 1: Generates canonical front view in standard T-pose.
#              Phase 2: Uses that front view to generate the remaining views
#                       (Left, Right, Back by default).
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." >/dev/null 2>&1 && pwd)"
MULTIVIEW_SCRIPT="${SCRIPT_DIR}/model-multiviews.sh"
GEMINI_SCRIPT="${PROJECT_ROOT}/gemini-image.py"

# Resolve model-multiviews executable (sibling script, command in PATH, or local script)
MULTIVIEW_CMD=()
if [[ -x "${SCRIPT_DIR}/model-multiviews" ]]; then
    MULTIVIEW_CMD=("${SCRIPT_DIR}/model-multiviews")
elif [[ -f "${SCRIPT_DIR}/model-multiviews.sh" ]]; then
    MULTIVIEW_CMD=("${SCRIPT_DIR}/model-multiviews.sh")
elif command -v model-multiviews >/dev/null 2>&1; then
    MULTIVIEW_CMD=("$(command -v model-multiviews)")
elif [[ -x "${HOME}/.local/bin/model-multiviews" ]]; then
    MULTIVIEW_CMD=("${HOME}/.local/bin/model-multiviews")
else
    echo "Error: Neither 'model-multiviews' command nor '${MULTIVIEW_SCRIPT}' was found." >&2
    exit 1
fi

# Resolve gemini-image executable (binary, wrapper, or local python script)
GEMINI_EXEC=()
if command -v gemini-image >/dev/null 2>&1; then
    GEMINI_EXEC=("$(command -v gemini-image)")
elif [[ -x "${HOME}/.local/bin/gemini-image" ]]; then
    GEMINI_EXEC=("${HOME}/.local/bin/gemini-image")
elif [[ -f "${GEMINI_SCRIPT}" ]]; then
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
    GEMINI_EXEC=("${PYTHON_BIN}" "${GEMINI_SCRIPT}")
else
    echo "Error: Neither 'gemini-image' command nor '${GEMINI_SCRIPT}' was found." >&2
    exit 1
fi

is_image_file() {
    local file="$1"
    if [[ -f "$file" ]]; then
        local ext="${file##*.}"
        ext="$(echo "$ext" | tr '[:upper:]' '[:lower:]')"
        case "$ext" in
            png|jpg|jpeg|webp|gif|bmp|tiff) return 0 ;;
        esac
    fi
    return 1
}

show_help() {
    cat << EOF
Usage:
  $(basename "$0") <REF_IMAGE> [STYLE_IMAGE] [EXTRA_PROMPT] [OPTIONS...]
  $(basename "$0") -i <REF_IMAGE> [-S <STYLE_IMAGE>] [-p EXTRA_PROMPT] [OPTIONS...]

Description:
  Generates multi-view (Front, Left, Right, Back) images of a model in T-POSE.
  Accepts any reference image of the model (does not need to be a front view).

  Two-phase generation workflow:
    Phase 1: Generates the front view of the model in standard T-pose using
             the reference image, optional style reference, and constrained prompting.
    Phase 2: Uses the generated front view as the canonical reference to
             generate the remaining views (Left, Right, Back by default).

Arguments:
  REF_IMAGE       Path to reference image of the model (any pose or angle)
  STYLE_IMAGE     Optional path to reference image describing the desired style
  EXTRA_PROMPT    Optional extra prompt appended to generation prompts

Options:
  -i, --image IMAGE_PATH        Path to reference image
  -S, --style, --style-image    Path to style reference image (e.g. "Use style.png style to draw content of model.png")
  -p, --prompt, --extra-prompt PROMPT
                                Additional prompt to append (e.g. "clay style")
  -v, --views VIEWS             Override remaining views (default: "left; right; back")
  --front-prompt PROMPT         Override prompt used for Phase 1 front view generation
  --skip-front-gen, --is-front-view
                                Skip Phase 1 (if input image is already a front T-pose view)
  -r, -a, --ratio RATIO         Aspect ratio for generated views (default: 1:1)
  -s, --size SIZE               Resolution for generated views (default: 4K)
  -o, --output OUTPUT           Output directory (e.g. outputs/) or file stem (e.g. outputs/char.png)
  -h, --help                    Show this help message
  ...                           Any other flags are forwarded to gemini-image.py
                                (e.g. --transparent, -m 3.1-flash)

Examples:
  $(basename "$0") character.png
  $(basename "$0") character.png style_art.png
  $(basename "$0") character.png style_art.png "keep white background, clay style"
  $(basename "$0") -i character.png -S style_art.png -p "3D render, clay style" --transparent
  $(basename "$0") -i character.png -o outputs/character.png
  $(basename "$0") -i character.png -r 16:9 -s 2K
EOF
}

REF_IMAGE=""
STYLE_IMAGE=""
EXTRA_PROMPT=""
VIEWS=""
ASPECT_RATIO="1:1"
IMAGE_SIZE="4K"
OUTPUT_TARGET=""
FRONT_PROMPT_OVERRIDE=""
SKIP_FRONT_GEN=false
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
        -S|--style|--style-image|--style-ref)
            if [[ $# -lt 2 ]]; then
                echo "Error: $1 requires an image path." >&2
                exit 1
            fi
            STYLE_IMAGE="$2"
            shift 2
            ;;
        -S=*|--style=*|--style-image=*|--style-ref=*)
            STYLE_IMAGE="${1#*=}"
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
        --front-prompt)
            if [[ $# -lt 2 ]]; then
                echo "Error: $1 requires a prompt string." >&2
                exit 1
            fi
            FRONT_PROMPT_OVERRIDE="$2"
            shift 2
            ;;
        --front-prompt=*)
            FRONT_PROMPT_OVERRIDE="${1#*=}"
            shift
            ;;
        --skip-front-gen|--is-front-view)
            SKIP_FRONT_GEN=true
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
        -o|--output)
            if [[ $# -lt 2 ]]; then
                echo "Error: $1 requires an output path." >&2
                exit 1
            fi
            OUTPUT_TARGET="$2"
            shift 2
            ;;
        -o=*|--output=*)
            OUTPUT_TARGET="${1#*=}"
            shift
            ;;
        -m|--model|-f|--format|-video|--video|--previous-id|--prev|--interaction-id|--thinking-level|--api-key)
            if [[ $# -lt 2 ]]; then
                echo "Error: $1 requires an argument." >&2
                exit 1
            fi
            EXTRA_ARGS+=("$1" "$2")
            shift 2
            ;;
        -m=*|--model=*|-f=*|--format=*|-video=*|--video=*|--previous-id=*|--prev=*|--interaction-id=*|--thinking-level=*|--api-key=*)
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
                elif [[ -z "${STYLE_IMAGE}" ]] && is_image_file "$1"; then
                    STYLE_IMAGE="$1"
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
            elif [[ -z "${STYLE_IMAGE}" && ! "$1" =~ ^- ]] && is_image_file "$1"; then
                STYLE_IMAGE="$1"
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

# Resolve reference image to absolute path
REF_IMAGE="$(cd "$(dirname "${REF_IMAGE}")" && pwd)/$(basename "${REF_IMAGE}")"

if [[ -n "${STYLE_IMAGE}" ]]; then
    if [[ ! -f "${STYLE_IMAGE}" ]]; then
        echo "Error: Style reference image not found: ${STYLE_IMAGE}" >&2
        exit 1
    fi
    STYLE_IMAGE="$(cd "$(dirname "${STYLE_IMAGE}")" && pwd)/$(basename "${STYLE_IMAGE}")"
fi

# ------------------------------------------------------------------------------
# Phase 1: Generate Front View in T-POSE (if not skipped)
# ------------------------------------------------------------------------------
GENERATED_FRONT_IMAGE=""

if [[ "${SKIP_FRONT_GEN}" == true ]]; then
    echo "================================================================"
    echo " Skipping Phase 1: Using provided reference image directly as front view."
    echo " Reference Image: ${REF_IMAGE}"
    echo "================================================================"
    echo ""
    GENERATED_FRONT_IMAGE="${REF_IMAGE}"
else
    # Build front view prompt with strict constraints
    if [[ -n "${STYLE_IMAGE}" ]]; then
        style_name="$(basename "${STYLE_IMAGE}")"
        ref_name="$(basename "${REF_IMAGE}")"
        BASE_PROMPT="Use ${style_name} style to draw the content of ${ref_name}. Create a front-view T-pose of this character"
        if [[ -n "${EXTRA_PROMPT}" ]]; then
            BASE_PROMPT="${BASE_PROMPT}, ${EXTRA_PROMPT}"
        fi
    else
        BASE_PROMPT="Create a front-view T-pose of this character"
        if [[ -n "${EXTRA_PROMPT}" ]]; then
            BASE_PROMPT="${BASE_PROMPT}, ${EXTRA_PROMPT}"
        fi
    fi
    FRONT_VIEW_PROMPT="${FRONT_PROMPT_OVERRIDE:-$BASE_PROMPT}"

    # Determine Phase 1 output path argument
    PHASE1_OUT_ARGS=()
    EXPLICIT_FRONT_FILE=""
    if [[ -n "${OUTPUT_TARGET}" ]]; then
        if [[ "${OUTPUT_TARGET}" == */ || -d "${OUTPUT_TARGET}" ]]; then
            mkdir -p "${OUTPUT_TARGET}"
            PHASE1_OUT_ARGS+=("-o" "${OUTPUT_TARGET}")
        else
            target_dir="$(dirname "${OUTPUT_TARGET}")"
            target_filename="$(basename "${OUTPUT_TARGET}")"
            mkdir -p "${target_dir}"
            if [[ "${target_filename}" =~ \. ]]; then
                target_stem="${target_filename%.*}"
                target_ext=".${target_filename##*.}"
            else
                target_stem="${target_filename}"
                target_ext=""
            fi
            EXPLICIT_FRONT_FILE="${target_dir}/${target_stem}_front${target_ext}"
            PHASE1_OUT_ARGS+=("-o" "${EXPLICIT_FRONT_FILE}")
        fi
    fi

    echo "================================================================"
    echo " Phase 1: Generating Front View (T-POSE)"
    echo " Content Image   : ${REF_IMAGE}"
    if [[ -n "${STYLE_IMAGE}" ]]; then
        echo " Style Reference : ${STYLE_IMAGE}"
    fi
    echo " Aspect Ratio    : ${ASPECT_RATIO}"
    echo " Resolution      : ${IMAGE_SIZE}"
    if [[ -n "${EXPLICIT_FRONT_FILE}" ]]; then
        echo " Output Target   : ${EXPLICIT_FRONT_FILE}"
    elif [[ -n "${OUTPUT_TARGET}" ]]; then
        echo " Output Target   : ${OUTPUT_TARGET}"
    fi
    echo " Prompt          : \"${FRONT_VIEW_PROMPT}\""
    echo "================================================================"
    echo ""

    PHASE1_IMAGE_ARGS=("-i" "${REF_IMAGE}")
    if [[ -n "${STYLE_IMAGE}" ]]; then
        PHASE1_IMAGE_ARGS+=("${STYLE_IMAGE}")
    fi

    TMP_LOG="$(mktemp)"
    set +e
    "${GEMINI_EXEC[@]}" \
        -p "${FRONT_VIEW_PROMPT}" \
        "${PHASE1_IMAGE_ARGS[@]}" \
        -r "${ASPECT_RATIO}" \
        -s "${IMAGE_SIZE}" \
        ${PHASE1_OUT_ARGS[@]+"${PHASE1_OUT_ARGS[@]}"} \
        ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} 2>&1 | tee "${TMP_LOG}"
    GEN_STATUS="${PIPESTATUS[0]}"
    set -e

    if [[ ${GEN_STATUS} -ne 0 ]]; then
        echo "" >&2
        echo "Error: Failed to generate front view in T-pose (exit code: ${GEN_STATUS})." >&2
        rm -f "${TMP_LOG}"
        exit "${GEN_STATUS}"
    fi

    # Extract saved image path from output
    GENERATED_FRONT_IMAGE="$(grep -E "Successfully saved generated image" "${TMP_LOG}" | tail -n 1 | sed -E 's/.*Successfully saved generated image (to |\([0-9]+\/[0-9]+\) to )//')"
    rm -f "${TMP_LOG}"

    if [[ -z "${GENERATED_FRONT_IMAGE}" && -n "${EXPLICIT_FRONT_FILE}" && -f "${EXPLICIT_FRONT_FILE}" ]]; then
        GENERATED_FRONT_IMAGE="${EXPLICIT_FRONT_FILE}"
    fi

    if [[ -z "${GENERATED_FRONT_IMAGE}" || ! -f "${GENERATED_FRONT_IMAGE}" ]]; then
        echo "" >&2
        echo "Error: Could not locate generated front view image at '${GENERATED_FRONT_IMAGE}'." >&2
        exit 1
    fi

    # Resolve generated front image to absolute path
    GENERATED_FRONT_IMAGE="$(cd "$(dirname "${GENERATED_FRONT_IMAGE}")" && pwd)/$(basename "${GENERATED_FRONT_IMAGE}")"

    echo ""
    echo "----------------------------------------------------------------"
    echo " Front View generated: ${GENERATED_FRONT_IMAGE}"
    echo "----------------------------------------------------------------"
    echo ""
fi

# ------------------------------------------------------------------------------
# Phase 2: Generate Remaining Views using Front View as reference
# ------------------------------------------------------------------------------
REMAINING_VIEWS=""
if [[ -n "${VIEWS}" ]]; then
    IFS=";" read -ra RAW_TOKENS <<< "${VIEWS}"
    if [[ ${#RAW_TOKENS[@]} -le 1 && "${VIEWS}" =~ , ]]; then
        IFS="," read -ra RAW_TOKENS <<< "${VIEWS}"
    fi

    KEPT_TOKENS=()
    for raw in "${RAW_TOKENS[@]}"; do
        token="$(echo -n "$raw" | sed -E 's/^[[:space:]]+|[[:space:]]+$//g')"
        [[ -z "$token" ]] && continue
        lower_token="$(echo "$token" | tr '[:upper:]' '[:lower:]')"
        # If Phase 1 generated front view, avoid re-generating front view
        if [[ "${SKIP_FRONT_GEN}" == false ]]; then
            if [[ "$lower_token" == "front" || "$lower_token" == "front view" || "$lower_token" == "front_view" || "$lower_token" == *"generate model"*"front view"* ]]; then
                continue
            fi
        fi
        KEPT_TOKENS+=("$token")
    done

    if [[ ${#KEPT_TOKENS[@]} -gt 0 ]]; then
        REMAINING_VIEWS=""
        for k in "${KEPT_TOKENS[@]}"; do
            if [[ -z "${REMAINING_VIEWS}" ]]; then
                REMAINING_VIEWS="${k}"
            else
                REMAINING_VIEWS="${REMAINING_VIEWS}; ${k}"
            fi
        done
    else
        REMAINING_VIEWS="__NONE__"
    fi
fi

if [[ "${REMAINING_VIEWS}" == "__NONE__" ]]; then
    echo "================================================================"
    echo " No remaining views to generate. Front view complete."
    echo " Front View: ${GENERATED_FRONT_IMAGE}"
    echo "================================================================"
    exit 0
fi

# Combine "T-POSE" with any additional prompt for remaining views
if [[ -n "${EXTRA_PROMPT}" ]]; then
    COMBINED_PROMPT="T-POSE, ${EXTRA_PROMPT}"
else
    COMBINED_PROMPT="T-POSE"
fi

PHASE2_ARGS=()
if [[ -n "${STYLE_IMAGE}" ]]; then
    PHASE2_ARGS+=("-S" "${STYLE_IMAGE}")
fi
if [[ -n "${REMAINING_VIEWS}" ]]; then
    PHASE2_ARGS+=("-v" "${REMAINING_VIEWS}")
fi
if [[ -n "${OUTPUT_TARGET}" ]]; then
    PHASE2_ARGS+=("-o" "${OUTPUT_TARGET}")
fi

echo "================================================================"
echo " Phase 2: Generating Remaining Views using Front View"
echo " Canonical Front Reference : ${GENERATED_FRONT_IMAGE}"
if [[ -n "${STYLE_IMAGE}" ]]; then
    echo " Style Reference           : ${STYLE_IMAGE}"
fi
if [[ -n "${REMAINING_VIEWS}" ]]; then
    echo " Views to Generate         : ${REMAINING_VIEWS}"
else
    echo " Views to Generate         : left; right; back (default)"
fi
echo "================================================================"
echo ""

# Invoke model-multiviews.sh with generated front view as reference
exec "${MULTIVIEW_CMD[@]}" \
    -i "${GENERATED_FRONT_IMAGE}" \
    -p "${COMBINED_PROMPT}" \
    -r "${ASPECT_RATIO}" \
    -s "${IMAGE_SIZE}" \
    ${PHASE2_ARGS[@]+"${PHASE2_ARGS[@]}"} \
    ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
