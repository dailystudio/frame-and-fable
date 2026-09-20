#!/usr/bin/env python3
"""
gemini-audio: CLI tool for generating human voice and music using the Google Gemini / Lyria API.

Supports:
- Human Voice / Speech Generation (TTS):
  * Single-speaker expressive speech with style, accent, and pacing directions
  * 30 prebuilt distinct voices (Kore, Puck, Zephyr, Fenrir, Charon, Leda, etc.)
  * Multi-speaker dialogue generation (up to 2 speakers)
  * Expressive inline audio tags ([whispers], [laughs], [sighs], [excited], etc.)
  * Multilingual speech generation across 40+ supported languages
- Music Generation (Lyria):
  * Lyria 3.5 flagship music generation (full songs, verse/chorus/bridge, 44.1 kHz stereo)
  * Lyria 3 Clip 30-second clips, loops, and previews
  * Multimodal Image-to-Music (inspire audio tracks from up to 10 reference images)
  * Custom song lyrics with section markers ([Verse], [Chorus], [Bridge], [Outro])
  * Automatic lyrics and structure extraction
- Gemini 3.8 Flash AI Script & Prompt Generation:
  * Automatically craft character scripts, podcast dialogues, or music prompts
  * Interactive confirmation and prompt refinement ([Y/n/r/s])
- Audio Format Conversion & Management:
  * Automatic WAV header authoring for PCM audio and high-quality MP3 encoding
  * Default ./outputs/ directory and unique interaction ID naming

Based on Google Gemini API Audio & Music documentation:
https://ai.google.dev/gemini-api/docs/speech-generation
https://ai.google.dev/gemini-api/docs/music-generation
"""

import sys
import os
import re
import time
import shutil
import base64
import secrets
import argparse
import mimetypes
import subprocess
import wave
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple, Union

try:
    from google import genai
    from google.genai import types
except ImportError:
    # Auto-detect local virtualenv if available
    venv_python = Path(__file__).resolve().parent / ".venv" / "bin" / "python3"
    if venv_python.exists() and sys.executable != str(venv_python):
        result = subprocess.run([str(venv_python)] + sys.argv, check=False)
        sys.exit(result.returncode)
    print("Error: 'google-genai' package is not installed.", file=sys.stderr)
    print("Please install it using: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)


# -----------------------------------------------------------------------------
# Models & Aliases
# -----------------------------------------------------------------------------

VOICE_MODELS: Dict[str, str] = {
    "gemini-3.1-flash-tts-preview": "Gemini 3.1 Flash TTS Preview (Default Voice: fastest, expressive, controllable)",
    "gemini-2.5-flash-preview-tts": "Gemini 2.5 Flash Preview TTS",
    "gemini-2.5-pro-preview-tts": "Gemini 2.5 Pro Preview TTS (nuanced prosody, rich emotion)",
}

MUSIC_MODELS: Dict[str, str] = {
    "lyria-3.5": "Lyria 3.5 (Default Music: full-length songs with verse/chorus structure, 44.1kHz stereo)",
    "lyria-3-clip-preview": "Lyria 3 Clip Preview (30s clips, loops, previews)",
    "lyria-3-pro-preview": "Lyria 3 Pro Preview (complex compositions, 48kHz audio)",
}

MODEL_ALIASES: Dict[str, str] = {
    # Voice aliases
    "tts": "gemini-3.1-flash-tts-preview",
    "3.1-tts": "gemini-3.1-flash-tts-preview",
    "3.1-flash-tts": "gemini-3.1-flash-tts-preview",
    "flash-tts": "gemini-3.1-flash-tts-preview",
    "2.5-flash-tts": "gemini-2.5-flash-preview-tts",
    "2.5-tts": "gemini-2.5-flash-preview-tts",
    "2.5-pro-tts": "gemini-2.5-pro-preview-tts",
    "pro-tts": "gemini-2.5-pro-preview-tts",
    # Music aliases
    "lyria": "lyria-3.5",
    "lyria-3.5": "lyria-3.5",
    "3.5": "lyria-3.5",
    "music": "lyria-3.5",
    "lyria-clip": "lyria-3-clip-preview",
    "clip": "lyria-3-clip-preview",
    "3-clip": "lyria-3-clip-preview",
    "lyria-pro": "lyria-3-pro-preview",
}

DEFAULT_VOICE_MODEL = "gemini-3.1-flash-tts-preview"
DEFAULT_MUSIC_MODEL = "lyria-3.5"
DEFAULT_CHAT_MODEL = "gemini-3.8-flash"
FALLBACK_CHAT_MODEL = "gemini-2.5-flash"


# -----------------------------------------------------------------------------
# Prebuilt Voices (30 Options)
# -----------------------------------------------------------------------------

AVAILABLE_VOICES: Dict[str, Tuple[str, str]] = {
    "kore": ("Kore", "Firm, steady, grounded (Default Voice)"),
    "puck": ("Puck", "Upbeat, energetic, engaging"),
    "zephyr": ("Zephyr", "Bright, warm, clear"),
    "fenrir": ("Fenrir", "Excitable, dynamic, punchy"),
    "charon": ("Charon", "Informative, serious, documentary-style"),
    "leda": ("Leda", "Youthful, fresh, vibrant"),
    "orus": ("Orus", "Firm, confident, resonant"),
    "aoede": ("Aoede", "Breezy, light, pleasant"),
    "callirrhoe": ("Callirrhoe", "Easy-going, relaxed, conversational"),
    "autonoe": ("Autonoe", "Bright, optimistic, clear"),
    "enceladus": ("Enceladus", "Breathy, gentle, intimate"),
    "iapetus": ("Iapetus", "Clear, crisp, articulate"),
    "umbriel": ("Umbriel", "Easy-going, calm, friendly"),
    "algieba": ("Algieba", "Smooth, silky, polished"),
    "despina": ("Despina", "Smooth, soothing, melodic"),
    "erinome": ("Erinome", "Clear, crisp, focused"),
    "algenib": ("Algenib", "Gravelly, rugged, deep"),
    "rasalgethi": ("Rasalgethi", "Informative, explanatory, clear"),
    "laomedeia": ("Laomedeia", "Upbeat, cheerful, radiant"),
    "achernar": ("Achernar", "Soft, gentle, subdued"),
    "alnilam": ("Alnilam", "Firm, steady, grounded"),
    "schedar": ("Schedar", "Even, balanced, measured"),
    "gacrux": ("Gacrux", "Mature, seasoned, warm"),
    "pulcherrima": ("Pulcherrima", "Forward, vivid, direct"),
    "achird": ("Achird", "Friendly, welcoming, natural"),
    "zubenelgenubi": ("Zubenelgenubi", "Casual, informal, relaxed"),
    "vindemiatrix": ("Vindemiatrix", "Gentle, compassionate, quiet"),
    "sadachbia": ("Sadachbia", "Lively, spirited, expressive"),
    "sadaltager": ("Sadaltager", "Knowledgeable, academic, precise"),
    "sulafat": ("Sulafat", "Warm, comforting, hearty"),
}


# -----------------------------------------------------------------------------
# Expressive Audio Tags Reference
# -----------------------------------------------------------------------------

EXPRESSIVE_AUDIO_TAGS: List[Tuple[str, str]] = [
    ("[whispers]", "Soft, whispered delivery for secrets or intimate lines"),
    ("[shouting]", "Loud, projecting voice with force and intensity"),
    ("[excited]", "High-energy, enthusiastic, fast-paced speech"),
    ("[laughs]", "Audible chuckle or laughter embedded in line"),
    ("[giggles]", "Light, playful laughter"),
    ("[sighs]", "Audible breathy exhale conveying fatigue, relief, or resignation"),
    ("[gasp]", "Sharp audible intake of breath indicating shock or surprise"),
    ("[cough]", "Realistic slight cough or throat-clearing sound"),
    ("[yawn]", "Audible yawn indicating drowsiness or boredom"),
    ("[tired]", "Weary, slower, slightly slurred or dragging delivery"),
    ("[serious]", "Measured, grave, authoritative tone"),
    ("[amazed]", "Wonder, awe, marveling cadence"),
    ("[curious]", "Inquisitive, questioning tone with upward inflections"),
    ("[mischievously]", "Playful, scheming, impish cadence"),
    ("[panicked]", "Breathless, accelerated, fearful delivery"),
    ("[sarcastic]", "Dry, cynical, deadpan emphasis"),
    ("[trembling]", "Shaky, vulnerable, emotional delivery"),
]


# -----------------------------------------------------------------------------
# Helper Functions: Env & Key Loading
# -----------------------------------------------------------------------------

def load_dotenv():
    """Load API key from .env files if not present in os.environ."""
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent.parent / "storybook-craft" / ".env",
    ]
    for env_path in candidates:
        if env_path.exists():
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k not in os.environ:
                                os.environ[k] = v
                if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
                    break
            except Exception:
                pass


def resolve_model_name(model_arg: str) -> str:
    """Resolve model alias or return exact model name."""
    lowered = model_arg.strip().lower()
    if lowered in MODEL_ALIASES:
        return MODEL_ALIASES[lowered]
    return model_arg


def resolve_voice_name(voice_arg: str) -> str:
    """Normalize and validate prebuilt voice name."""
    lowered = voice_arg.strip().lower()
    if lowered in AVAILABLE_VOICES:
        return AVAILABLE_VOICES[lowered][0]
    # Return as-is if customized or titlecased
    return voice_arg.capitalize()


def is_music_model(model_name: str) -> bool:
    """Return True if model is a Lyria music model."""
    return "lyria" in model_name.lower() or model_name.lower() in [
        "lyria-3.5", "lyria-3-clip-preview", "lyria-3-pro-preview"
    ]


def sanitize_id_for_filename(raw_id: Optional[str]) -> str:
    """Extract and sanitize interaction ID or generate random hex token."""
    if raw_id:
        base_id = str(raw_id).strip().split("/")[-1]
        cleaned = re.sub(r"[^\w\-]", "_", base_id).strip("_")
        if cleaned:
            return cleaned
    return secrets.token_hex(8)


# -----------------------------------------------------------------------------
# Image Loading for Multimodal Music
# -----------------------------------------------------------------------------

def get_image_mime_type(file_path: str) -> str:
    """Detect image MIME type or default to image/jpeg."""
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type and mime_type.startswith("image/"):
        return mime_type
    ext = Path(file_path).suffix.lower()
    if ext in [".jpg", ".jpeg"]:
        return "image/jpeg"
    elif ext == ".png":
        return "image/png"
    elif ext == ".webp":
        return "image/webp"
    return "image/jpeg"


def load_image_part(file_path: str) -> types.Part:
    """Load image file as types.Part for Gemini multimodal chat."""
    path = Path(file_path)
    if not path.exists():
        print(f"Error: Input image file '{file_path}' does not exist.", file=sys.stderr)
        sys.exit(1)
    mime_type = get_image_mime_type(file_path)
    try:
        with open(path, "rb") as f:
            data = f.read()
        return types.Part.from_bytes(data=data, mime_type=mime_type)
    except Exception as e:
        print(f"Error reading image '{file_path}': {e}", file=sys.stderr)
        sys.exit(1)


def load_image_input(file_path: str) -> Dict[str, Any]:
    """Load image file and return base64 encoded data dict for Gemini Interactions API."""
    path = Path(file_path)
    if not path.exists():
        print(f"Error: Input image file '{file_path}' does not exist.", file=sys.stderr)
        sys.exit(1)
    mime_type = get_image_mime_type(file_path)
    try:
        with open(path, "rb") as f:
            img_bytes = f.read()
        b64_data = base64.b64encode(img_bytes).decode("utf-8")
        return {
            "type": "image",
            "data": b64_data,
            "mime_type": mime_type,
        }
    except Exception as e:
        print(f"Error reading image '{file_path}': {e}", file=sys.stderr)
        sys.exit(1)


# -----------------------------------------------------------------------------
# Audio File Saving & Transcoding
# -----------------------------------------------------------------------------

def write_pcm_to_wav(
    pcm_bytes: bytes,
    wav_path: Path,
    sample_rate: int = 24000,
    channels: int = 1,
    sample_width: int = 2
) -> None:
    """Write raw PCM bytes to a standard WAV file with valid RIFF header."""
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)


def transcode_audio_with_ffmpeg(
    input_path: Path,
    output_path: Path,
    verbose: bool = False
) -> bool:
    """Transcode audio file using ffmpeg if available."""
    ffmpeg_bin = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
    if not os.path.exists(ffmpeg_bin) and not shutil.which("ffmpeg"):
        return False
    cmd = [
        ffmpeg_bin if os.path.exists(ffmpeg_bin) else "ffmpeg",
        "-y",
        "-i", str(input_path),
        str(output_path)
    ]
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL if not verbose else None,
            stderr=subprocess.DEVNULL if not verbose else None,
            check=True
        )
        return True
    except Exception as ex:
        if verbose:
            print(f"[gemini-audio] Warning: ffmpeg transcoding failed: {ex}", file=sys.stderr)
        return False


def save_audio_output(
    raw_bytes: bytes,
    target_path: Path,
    is_pcm: bool = False,
    is_mp3: bool = False,
    verbose: bool = False
) -> Path:
    """Save audio bytes to destination file, transcoding if required."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    ext = target_path.suffix.lower()

    if is_pcm:
        # Source is 24kHz 16-bit mono PCM (from Gemini TTS)
        if ext == ".wav":
            write_pcm_to_wav(raw_bytes, target_path)
            return target_path
        else:
            # Save temporary wav then convert to requested format (e.g. .mp3)
            temp_wav = target_path.with_suffix(".temp.wav")
            write_pcm_to_wav(raw_bytes, temp_wav)
            if transcode_audio_with_ffmpeg(temp_wav, target_path, verbose=verbose):
                try:
                    temp_wav.unlink()
                except Exception:
                    pass
                return target_path
            else:
                # ffmpeg not available, fallback to wav
                fallback_path = target_path.with_suffix(".wav")
                shutil.move(str(temp_wav), str(fallback_path))
                print(f"[gemini-audio] Note: ffmpeg not found. Saved audio as WAV at: {fallback_path}")
                return fallback_path

    elif is_mp3:
        # Source is MP3 (from Lyria)
        if ext == ".mp3":
            with open(target_path, "wb") as f:
                f.write(raw_bytes)
            return target_path
        else:
            temp_mp3 = target_path.with_suffix(".temp.mp3")
            with open(temp_mp3, "wb") as f:
                f.write(raw_bytes)
            if transcode_audio_with_ffmpeg(temp_mp3, target_path, verbose=verbose):
                try:
                    temp_mp3.unlink()
                except Exception:
                    pass
                return target_path
            else:
                fallback_path = target_path.with_suffix(".mp3")
                shutil.move(str(temp_mp3), str(fallback_path))
                print(f"[gemini-audio] Note: ffmpeg not found. Saved audio as MP3 at: {fallback_path}")
                return fallback_path
    else:
        # Raw write
        with open(target_path, "wb") as f:
            f.write(raw_bytes)
        return target_path


# -----------------------------------------------------------------------------
# Informational Listings
# -----------------------------------------------------------------------------

def list_models_info():
    """Print available audio models and specifications."""
    print("\n" + "=" * 80)
    print("Available Gemini Audio & Music Models")
    print("=" * 80)
    print("\n--- Human Voice / Speech Generation (TTS) ---")
    print("  gemini-3.1-flash-tts-preview  (default / aliases: tts, 3.1-tts, flash-tts)")
    print("      Flagship TTS model. Supports precise recitation, natural language style,")
    print("      pace and tone steering, multi-speaker dialogues, and audio tags.")
    print("  gemini-2.5-flash-preview-tts  (aliases: 2.5-flash-tts, 2.5-tts)")
    print("      Fast, responsive TTS model.")
    print("  gemini-2.5-pro-preview-tts    (aliases: 2.5-pro-tts, pro-tts)")
    print("      Pro TTS model offering deep nuance and rich expressive prosody.")

    print("\n--- Music Generation (Lyria) ---")
    print("  lyria-3.5                     (default / aliases: lyria, 3.5, music)")
    print("      Flagship music generation model. Produces full-length songs with coherent")
    print("      structural progression (verses, choruses, bridges), vocals, and lyrics.")
    print("      High-fidelity 44.1 kHz stereo audio. Supports image-to-music guidance.")
    print("  lyria-3-clip-preview          (aliases: lyria-clip, clip, 3-clip)")
    print("      Specialized for 30-second clips, loops, themes, and short previews.")
    print("  lyria-3-pro-preview           (aliases: lyria-pro)")
    print("      Premium music model for complex arrangements and 48 kHz stereo audio.")
    print("=" * 80 + "\n")


def list_voices_info():
    """Print all 30 prebuilt output voices with tonal descriptions."""
    print("\n" + "=" * 80)
    print("Available Gemini TTS Output Voices (30 Options)")
    print("=" * 80)
    print(f"{'Voice Name':<16} {'Tone & Characteristics':<60}")
    print("-" * 80)
    for key, (vname, desc) in AVAILABLE_VOICES.items():
        is_default = " [DEFAULT]" if key == "kore" else ""
        print(f"  {vname:<14}{is_default:<10} {desc}")
    print("-" * 80)
    print("Usage: Specify --voice <Name> (e.g., --voice Puck or --voice Zephyr)")
    print("       For multi-speaker: --speakers \"Speaker1:Kore,Speaker2:Puck\"")
    print("=" * 80 + "\n")


def list_tags_info():
    """Print expressive audio tags guide."""
    print("\n" + "=" * 80)
    print("Expressive Audio Tags Guide (TTS Directorial Control)")
    print("=" * 80)
    print("Insert inline tags in your transcript to control emotional delivery, tone, and pacing:")
    print("-" * 80)
    for tag, desc in EXPRESSIVE_AUDIO_TAGS:
        print(f"  {tag:<18} {desc}")
    print("-" * 80)
    print("Example Prompt with Directorial Notes & Audio Tags:")
    print("  \"Say playfully: [whispers] I have a secret to tell you... [excited] We did it!\"")
    print("\nExample Multi-Speaker Conversation:")
    print("  \"Alice: [amazed] Look at those northern lights!\\nBob: [sighs] I've never seen anything so beautiful.\"")
    print("=" * 80 + "\n")


# -----------------------------------------------------------------------------
# Multi-Speaker Parsing
# -----------------------------------------------------------------------------

def parse_multi_speaker_config(
    speakers_arg: Optional[str],
    speaker1_arg: Optional[str] = None,
    speaker2_arg: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    Parse speaker configurations into a list of {'speaker': name, 'voice': voice}.
    Supports formats:
      --speakers "Alice:Kore,Bob:Puck"
      --speaker1 "Alice:Kore" --speaker2 "Bob:Puck"
    """
    configs: List[Dict[str, str]] = []
    
    if speakers_arg:
        pairs = [p.strip() for p in speakers_arg.split(",") if p.strip()]
        for p in pairs:
            if ":" in p:
                s_name, v_name = p.split(":", 1)
                configs.append({"speaker": s_name.strip(), "voice": resolve_voice_name(v_name.strip())})
            else:
                configs.append({"speaker": p.strip(), "voice": "Kore"})
                
    if speaker1_arg:
        if ":" in speaker1_arg:
            s_name, v_name = speaker1_arg.split(":", 1)
            configs.append({"speaker": s_name.strip(), "voice": resolve_voice_name(v_name.strip())})
        else:
            configs.append({"speaker": speaker1_arg.strip(), "voice": "Kore"})
            
    if speaker2_arg:
        if ":" in speaker2_arg:
            s_name, v_name = speaker2_arg.split(":", 1)
            configs.append({"speaker": s_name.strip(), "voice": resolve_voice_name(v_name.strip())})
        else:
            configs.append({"speaker": speaker2_arg.strip(), "voice": "Puck"})

    # Limit to at most 2 speakers as supported by the current API
    if len(configs) > 2:
        print(f"[gemini-audio] Warning: Gemini TTS currently supports up to 2 distinct speakers. Using first 2.", file=sys.stderr)
        configs = configs[:2]

    return configs


# -----------------------------------------------------------------------------
# AI Script & Prompt Generation (Gemini 3.8 Flash)
# -----------------------------------------------------------------------------

def generate_script_or_prompt_with_gemini(
    client: genai.Client,
    idea_text: str,
    mode: str,
    multi_speaker: bool = False,
    speakers: Optional[List[Dict[str, str]]] = None,
    ref_images: Optional[List[str]] = None,
    chat_model: str = DEFAULT_CHAT_MODEL,
    verbose: bool = False,
) -> str:
    """
    Use Gemini 3.8 Flash to write a high-impact prompt, script, or lyrics.
    """
    system_instruction = (
        "You are an expert audio producer, screenwriter, and music director specializing in Google Gemini audio and music generation.\n"
        "Your task is to craft vivid, well-structured, production-ready prompts or scripts tailored for Gemini TTS or Lyria Music generation.\n"
    )

    prompt_parts: List[Any] = []

    if mode in ["sfx", "foley"]:
        instructions = (
            f"You are a master Hollywood sound designer and Foley artist.\n"
            f"Craft an optimal sound effect prompt for audio synthesis based on this concept:\n"
            f"\"{idea_text}\"\n\n"
            f"Requirements:\n"
            f"1. Focus strictly on acoustic textures, physical dynamics, frequencies, and material impacts.\n"
            f"2. For physical impacts (e.g. punch, kick, hit): specify the whooshing wind-up, the punchy transient impact, sub-bass thud, and physical room reverb.\n"
            f"3. For animal/nature sounds (e.g. tiger roar, bird song): describe the guttural resonance, pitch modulation, breath, and natural environment.\n"
            f"4. Prefix the output with 'Sound effect: ' or 'Foley SFX: '.\n"
            f"5. Keep the prompt focused, vivid, and under 50 words.\n"
            f"6. Output ONLY the raw prompt ready for audio generation without conversational preamble."
        )
        if ref_images:
            for idx, img_path in enumerate(ref_images):
                prompt_parts.append(f"### Reference Image {idx + 1}:")
                try:
                    prompt_parts.append(load_image_part(img_path))
                except Exception as ex:
                    if verbose:
                        print(f"Warning loading image for prompt generation: {ex}")
        prompt_parts.append(instructions)

    elif mode == "voice":
        if multi_speaker and speakers and len(speakers) >= 2:
            s1 = speakers[0]["speaker"]
            s2 = speakers[1]["speaker"]
            instructions = (
                f"Create a natural, engaging conversation between {s1} and {s2} based on this topic:\n"
                f"\"{idea_text}\"\n\n"
                f"Requirements:\n"
                f"1. Precede each speaker's lines with '{s1}: ' or '{s2}: '.\n"
                f"2. Use expressive inline audio tags naturally (e.g., [whispers], [laughs], [sighs], [excited], [serious]).\n"
                f"3. Keep the dialogue dynamic, authentic, and around 80-150 words.\n"
                f"4. Do NOT include stage directions in asterisks or parentheses. Use only bracketed audio tags like [laughs].\n"
                f"5. Output ONLY the raw transcript lines ready for recitation."
            )
        else:
            instructions = (
                f"Create a compelling vocal recitation script based on this request:\n"
                f"\"{idea_text}\"\n\n"
                f"Requirements:\n"
                f"1. Start with a clear directorial performance instruction if appropriate (e.g. 'Say cheerfully:', 'Speak in a calm, authoritative voice:').\n"
                f"2. Incorporate expressive inline audio tags (e.g., [whispers], [excited], [sighs], [serious]) to direct inflection.\n"
                f"3. Keep the text engaging, articulate, and around 50-100 words.\n"
                f"4. Output ONLY the speech script ready for recitation."
            )
        prompt_parts.append(instructions)

    else:  # mode == "music"
        instructions = (
            f"Craft an optimal Google Lyria music generation prompt and lyrics based on this concept:\n"
            f"\"{idea_text}\"\n\n"
            f"Requirements:\n"
            f"1. Analyze any reference images provided (atmosphere, culture, architecture, color, fighting game stage vibe).\n"
            f"2. Specify genre, mood, tempo (BPM), key instruments (both traditional and modern electronic/percussive beats), and production style.\n"
            f"3. If instrumental or battle BGM, keep it focused on high-energy, combat-ready instrumentation, rhythm, and progression.\n"
            f"4. Ensure the prompt is vivid and musically descriptive.\n"
            f"5. Output ONLY the music prompt without conversational preamble."
        )
        if ref_images:
            for idx, img_path in enumerate(ref_images):
                prompt_parts.append(f"### Reference Image {idx + 1}:")
                try:
                    prompt_parts.append(load_image_part(img_path))
                except Exception as ex:
                    if verbose:
                        print(f"Warning loading image for prompt generation: {ex}")
        prompt_parts.append(instructions)

    models_to_try = [chat_model, FALLBACK_CHAT_MODEL]
    for model_name in models_to_try:
        try:
            if verbose:
                print(f"[gemini-audio] Generating script/prompt using {model_name}...")
            chat = client.chats.create(
                model=model_name,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.7,
                )
            )
            response = chat.send_message(prompt_parts)
            raw_text = getattr(response, "text", "") or ""
            clean_text = raw_text.strip()
            # Strip markdown code blocks if wrapped
            if clean_text.startswith("```") and clean_text.endswith("```"):
                lines = clean_text.splitlines()
                if len(lines) >= 2:
                    clean_text = "\n".join(lines[1:-1]).strip()
            return clean_text
        except Exception as e:
            if verbose:
                print(f"[gemini-audio] Warning: Generation with {model_name} failed: {e}")
            continue

    raise RuntimeError(f"Failed to generate prompt with models: {', '.join(models_to_try)}")


def refine_prompt_interactively(
    client: genai.Client,
    current_prompt: str,
    mode: str,
    chat_model: str = DEFAULT_CHAT_MODEL,
) -> Tuple[bool, str]:
    """
    Present the generated prompt to the user with interactive approval:
    y = proceed, n = abort, r = regenerate, s = suggest refinement, p = print and exit.
    """
    print("\n" + "=" * 80)
    print(f"[gemini-audio] Generated {mode.capitalize()} Script / Prompt:")
    print("=" * 80)
    print(current_prompt)
    print("=" * 80)

    while True:
        try:
            choice = input(
                "\nProceed with audio generation? [Y=yes / n=abort / r=regenerate / s=suggestion / p=prompt-only]: "
            ).strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted by user.")
            return False, current_prompt

        if choice in ["y", "yes", ""]:
            return True, current_prompt
        elif choice in ["n", "no", "q", "quit"]:
            print("Aborted.")
            return False, current_prompt
        elif choice in ["p", "prompt-only"]:
            print("\nFinal Prompt:\n", current_prompt)
            sys.exit(0)
        elif choice in ["r", "regenerate"]:
            print("\n[gemini-audio] Regenerating prompt...")
            return True, current_prompt
        elif choice in ["s", "suggestion", "edit"]:
            try:
                suggestion = input("Enter your suggestion or modification instructions: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nKeeping current prompt.")
                continue
            if not suggestion:
                continue
            print(f"\n[gemini-audio] Modifying prompt based on: \"{suggestion}\"...")
            try:
                refine_query = (
                    f"Here is the existing script/prompt:\n\"\"\"\n{current_prompt}\n\"\"\"\n\n"
                    f"Please rewrite and modify it according to this instruction:\n\"{suggestion}\"\n\n"
                    "Output ONLY the revised text without preamble."
                )
                chat = client.chats.create(model=chat_model)
                resp = chat.send_message(refine_query)
                updated = (getattr(resp, "text", "") or "").strip()
                if updated:
                    current_prompt = updated
                    print("\n" + "=" * 80)
                    print("[gemini-audio] Revised Prompt:")
                    print("=" * 80)
                    print(current_prompt)
                    print("=" * 80)
            except Exception as ex:
                print(f"[gemini-audio] Error during refinement: {ex}")
        else:
            print("Invalid option. Please enter y, n, r, s, or p.")


# -----------------------------------------------------------------------------
# Core Generation: Human Voice (Gemini TTS)
# -----------------------------------------------------------------------------

def generate_voice_tts(
    client: genai.Client,
    text_input: str,
    model: str = DEFAULT_VOICE_MODEL,
    voice: str = "Kore",
    speakers: Optional[List[Dict[str, str]]] = None,
    output_path: Optional[Path] = None,
    stream: bool = False,
    verbose: bool = False,
) -> Path:
    """Generate human speech using Gemini TTS (Interactions API)."""
    resolved_model = resolve_model_name(model)
    resolved_voice = resolve_voice_name(voice)

    # Build speech_config
    if speakers and len(speakers) >= 2:
        speech_config_payload = [
            {"speaker": s["speaker"], "voice": s["voice"]}
            for s in speakers
        ]
        if verbose:
            print(f"[gemini-audio] Multi-speaker TTS configuration: {speech_config_payload}")
    else:
        speech_config_payload = [{"voice": resolved_voice}]
        if verbose:
            print(f"[gemini-audio] Single-speaker TTS voice: {resolved_voice}")

    start_time = time.time()
    spinner_chars = ["|", "/", "-", "\\"]
    spin_idx = 0

    print(f"\n[gemini-audio] Generating speech with {resolved_model}...")

    try:
        interaction = client.interactions.create(
            model=resolved_model,
            input=text_input,
            response_format={"type": "audio"},
            generation_config={
                "speech_config": speech_config_payload
            }
        )
    except Exception as e:
        print(f"\n[gemini-audio] Error calling TTS API: {e}", file=sys.stderr)
        sys.exit(1)

    elapsed = round(time.time() - start_time, 2)
    print(f"[gemini-audio] Voice generation completed in {elapsed}s!")

    output_audio = getattr(interaction, "output_audio", None)
    if not output_audio or not getattr(output_audio, "data", None):
        print("Error: No audio data received from TTS model.", file=sys.stderr)
        sys.exit(1)

    audio_bytes = base64.b64decode(output_audio.data)

    # Determine filename
    interaction_id = sanitize_id_for_filename(getattr(interaction, "id", None))
    if output_path is None:
        target_file = Path("./outputs") / f"{interaction_id}.wav"
    elif output_path.is_dir() or str(output_path).endswith(("/", "\\")):
        target_file = output_path / f"{interaction_id}.wav"
    else:
        target_file = output_path

    saved_path = save_audio_output(
        raw_bytes=audio_bytes,
        target_path=target_file,
        is_pcm=True,
        verbose=verbose
    )

    print(f"[gemini-audio] Audio saved to: {saved_path}")
    print(f"[gemini-audio] Interaction ID: {interaction_id}")
    return saved_path


# -----------------------------------------------------------------------------
# Core Generation: Music (Lyria)
# -----------------------------------------------------------------------------

def generate_music_lyria(
    client: genai.Client,
    prompt: str,
    model: str = DEFAULT_MUSIC_MODEL,
    ref_images: Optional[List[str]] = None,
    output_path: Optional[Path] = None,
    verbose: bool = False,
) -> Path:
    """Generate high-fidelity music using Google Lyria (Interactions API)."""
    resolved_model = resolve_model_name(model)

    # Build input payload
    if ref_images:
        input_payload: List[Any] = [{"type": "text", "text": prompt}]
        for img_path in ref_images:
            if verbose:
                print(f"[gemini-audio] Attaching reference image: {img_path}")
            input_payload.append(load_image_input(img_path))
    else:
        input_payload = prompt

    start_time = time.time()
    print(f"\n[gemini-audio] Composing music with {resolved_model}...")
    if ref_images:
        print(f"[gemini-audio] Guiding with {len(ref_images)} reference image(s)...")

    try:
        interaction = client.interactions.create(
            model=resolved_model,
            input=input_payload,
            response_format={"type": "audio"}
        )
    except Exception as e:
        print(f"\n[gemini-audio] Error calling Music API: {e}", file=sys.stderr)
        sys.exit(1)

    elapsed = round(time.time() - start_time, 2)
    print(f"[gemini-audio] Music composition completed in {elapsed}s!")

    # Extract lyrics / song structure if present
    output_text = getattr(interaction, "output_text", None)
    if output_text and output_text.strip() and output_text.strip() != "<instrumental>":
        print("\n" + "-" * 50)
        print("Generated Song Structure & Lyrics:")
        print("-" * 50)
        print(output_text.strip())
        print("-" * 50 + "\n")
    elif output_text and "<instrumental>" in output_text:
        print("[gemini-audio] Track Type: Instrumental")

    # Extract audio bytes
    audio_bytes = None
    output_audio = getattr(interaction, "output_audio", None)
    if output_audio and getattr(output_audio, "data", None):
        audio_bytes = base64.b64decode(output_audio.data)
    else:
        # Fallback to inspecting steps
        steps = getattr(interaction, "steps", []) or []
        for step in steps:
            if getattr(step, "type", "") == "model_output":
                for block in getattr(step, "content", []) or []:
                    if getattr(block, "type", "") == "audio" and getattr(block, "data", None):
                        audio_bytes = base64.b64decode(block.data)
                        break

    if not audio_bytes:
        print("Error: No audio data returned by music generation model.", file=sys.stderr)
        sys.exit(1)

    # Determine filename
    interaction_id = sanitize_id_for_filename(getattr(interaction, "id", None))
    if output_path is None:
        target_file = Path("./outputs") / f"{interaction_id}.mp3"
    elif output_path.is_dir() or str(output_path).endswith(("/", "\\")):
        target_file = output_path / f"{interaction_id}.mp3"
    else:
        target_file = output_path

    saved_path = save_audio_output(
        raw_bytes=audio_bytes,
        target_path=target_file,
        is_mp3=True,
        verbose=verbose
    )

    print(f"[gemini-audio] Music saved to: {saved_path}")
    print(f"[gemini-audio] Interaction ID: {interaction_id}")
    return saved_path


# -----------------------------------------------------------------------------
# CLI Argument Parser
# -----------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gemini-audio",
        description="Generate human speech (TTS) and music using Google Gemini & Lyria APIs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 1. Single-speaker human voice (TTS)
  gemini-audio "Hello! Welcome to the new world of Gemini audio." -v Puck

  # 2. Expressive voice with emotion audio tags
  gemini-audio "Say playfully: [whispers] Did you know? [excited] We just launched audio generation!" -v Zephyr

  # 3. Multi-speaker conversation
  gemini-audio "Joe: How are you today Jane?\\nJane: [excitedly] Doing fantastic Joe!" --speakers "Joe:Kore,Jane:Puck"

  # 4. Generate AI script/dialogue first with Gemini 3.8 Flash
  gemini-audio "A podcast debate between two astronomers about alien civilizations" --generate-script --speakers "Anya:Kore,Liam:Puck"

  # 5. Text-to-Music generation (Lyria 3.5)
  gemini-audio "An upbeat 120 BPM indie pop track with catchy guitar riff and synth pads" --music

  # 6. Image-to-Music (inspire soundtrack from artwork/photo)
  gemini-audio "A mystical ambient track matching the mood of this scene" -i landscape.jpg --music

  # 7. Short 30-second music clip / loop
  gemini-audio "8-bit retro arcade boss battle theme" -m clip -o ./outputs/boss_theme.mp3

  # 8. List all models, 30 prebuilt voices, or audio tags
  gemini-audio --list-models
  gemini-audio --list-voices
  gemini-audio --list-tags
        """
    )

    # Positional prompt / idea
    parser.add_argument(
        "prompt",
        nargs="?",
        default=None,
        help="Text prompt, speech transcript, or idea for prompt generation. Use '-' to read from stdin."
    )

    # Input file
    parser.add_argument(
        "-f", "--file",
        help="Path to a text file containing the transcript, lyrics, or prompt."
    )

    # Generation Mode
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--mode",
        choices=["voice", "speech", "tts", "music", "sfx", "foley"],
        help="Explicit generation mode: 'voice' (Gemini TTS), 'music' (Lyria), or 'sfx' (Sound Effects & Foley)."
    )
    mode_group.add_argument(
        "--music",
        action="store_true",
        help="Shortcut to enable music generation mode (uses Lyria 3.5 by default)."
    )
    mode_group.add_argument(
        "--sfx", "--foley",
        dest="sfx_flag",
        action="store_true",
        help="Shortcut to generate Sound Effects & Foley (hits, kicks, tiger roars, bird chirps, impacts)."
    )
    mode_group.add_argument(
        "--speech", "--tts",
        dest="voice_flag",
        action="store_true",
        help="Shortcut to force voice/speech generation mode."
    )

    # Model Selection
    parser.add_argument(
        "-m", "--model",
        help=(
            "Model name or alias. Voice: 'gemini-3.1-flash-tts-preview' (default), '3.1-tts', '2.5-pro-tts'. "
            "Music: 'lyria-3.5' (default), 'clip', 'lyria-3-clip-preview', 'lyria-pro'."
        )
    )

    # Output path
    parser.add_argument(
        "-o", "--output",
        help="Destination audio file (e.g., ./outputs/voice.wav, song.mp3) or directory."
    )

    # Single-speaker voice selection
    parser.add_argument(
        "-v", "--voice", "--voice-name",
        dest="voice",
        default="Kore",
        help="Prebuilt voice name for single-speaker TTS (default: Kore). Run --list-voices to view all 30 options."
    )

    # Multi-speaker flags
    parser.add_argument(
        "--speakers",
        help="Multi-speaker mapping in 'Speaker1:Voice1,Speaker2:Voice2' format (e.g. 'Joe:Kore,Jane:Puck')."
    )
    parser.add_argument(
        "--speaker1",
        help="Speaker 1 mapping (e.g. 'Alice:Kore')."
    )
    parser.add_argument(
        "--speaker2",
        help="Speaker 2 mapping (e.g. 'Bob:Puck')."
    )

    # Image inputs for music
    parser.add_argument(
        "-i", "--image", "--ref-image",
        dest="images",
        action="append",
        help="Path to reference image(s) to inspire music generation (Lyria accepts up to 10 images)."
    )

    # Prompt / Script Generation (Gemini 3.8 Flash)
    parser.add_argument(
        "--generate-script", "--generate-prompt",
        dest="generate_prompt",
        action="store_true",
        help="Use Gemini 3.8 Flash to compose an expressive script or detailed music prompt from your idea."
    )
    parser.add_argument(
        "--chat-model",
        default=DEFAULT_CHAT_MODEL,
        help=f"Model used for prompt and script generation (default: {DEFAULT_CHAT_MODEL})."
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Auto-confirm the generated script/prompt without interactive prompts."
    )
    parser.add_argument(
        "--prompt-only",
        action="store_true",
        help="Generate and display the script/prompt, then exit without calling audio generation."
    )

    # Information commands
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="Display all supported Gemini TTS and Lyria Music models."
    )
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="Display all 30 prebuilt voices with character and timbre descriptions."
    )
    parser.add_argument(
        "--list-tags",
        action="store_true",
        help="Display list of expressive inline audio tags for TTS directing."
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Print summary information about Gemini audio generation capabilities."
    )

    # Advanced / Debug
    parser.add_argument(
        "--api-key",
        help="Gemini API Key override (otherwise read from GEMINI_API_KEY environment variable or .env)."
    )
    parser.add_argument(
        "-V", "--verbose",
        action="store_true",
        help="Print detailed execution logs."
    )

    return parser


# -----------------------------------------------------------------------------
# Main Application Flow
# -----------------------------------------------------------------------------

def main():
    parser = build_parser()
    args = parser.parse_args()

    # Informational flags exit immediately
    if args.list_models:
        list_models_info()
        return
    if args.list_voices:
        list_voices_info()
        return
    if args.list_tags:
        list_tags_info()
        return
    if args.info:
        list_models_info()
        list_voices_info()
        list_tags_info()
        return

    # Load environment variables (.env)
    load_dotenv()

    # Resolve API Key
    api_key = args.api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Error: No Gemini API Key found.", file=sys.stderr)
        print("Please set GEMINI_API_KEY environment variable or pass --api-key <YOUR_KEY>.", file=sys.stderr)
        print("You can obtain an API key at https://aistudio.google.com/", file=sys.stderr)
        sys.exit(1)

    # Initialize Gemini client
    client = genai.Client(api_key=api_key)

    # Resolve prompt input
    raw_prompt = args.prompt
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: Input file '{args.file}' does not exist.", file=sys.stderr)
            sys.exit(1)
        raw_prompt = file_path.read_text(encoding="utf-8").strip()
    elif raw_prompt == "-":
        raw_prompt = sys.stdin.read().strip()

    if not raw_prompt and not args.generate_prompt:
        parser.print_help()
        print("\nError: Please provide a text prompt/transcript, an input file (-f), or use --generate-script.", file=sys.stderr)
        sys.exit(1)

    # Resolve Generation Mode
    # Priority: explicit mode/flags -> model alias -> presence of images -> presence of speakers -> default voice
    target_mode = "voice"
    if args.mode in ["sfx", "foley"] or args.sfx_flag:
        target_mode = "sfx"
    elif args.mode in ["music"] or args.music:
        target_mode = "music"
    elif args.mode in ["voice", "speech", "tts"] or args.voice_flag:
        target_mode = "voice"
    elif args.model and is_music_model(resolve_model_name(args.model)):
        target_mode = "music"
    elif args.images:
        target_mode = "music"
    elif args.speakers or args.speaker1 or args.speaker2:
        target_mode = "voice"

    # Resolve Model
    if args.model:
        model_name = resolve_model_name(args.model)
    else:
        if target_mode == "sfx":
            model_name = "lyria-3-clip-preview"
        elif target_mode == "music":
            model_name = DEFAULT_MUSIC_MODEL
        else:
            model_name = DEFAULT_VOICE_MODEL

    # Parse multi-speaker configuration if any
    multi_speakers = parse_multi_speaker_config(
        speakers_arg=args.speakers,
        speaker1_arg=args.speaker1,
        speaker2_arg=args.speaker2,
    )

    # If multi-speaker requested, force voice mode
    if multi_speakers and target_mode not in ["voice"]:
        print("[gemini-audio] Note: Multi-speaker configuration specified. Switching to Voice mode.")
        target_mode = "voice"
        if is_music_model(model_name):
            model_name = DEFAULT_VOICE_MODEL

    # AI Script & Prompt Generation
    effective_prompt = raw_prompt or ""
    if args.generate_prompt:
        generated = generate_script_or_prompt_with_gemini(
            client=client,
            idea_text=effective_prompt or ("A dramatic combat hit and punch impact" if target_mode == "sfx" else "An interesting conversation between friends"),
            mode=target_mode,
            multi_speaker=bool(multi_speakers),
            speakers=multi_speakers,
            ref_images=args.images,
            chat_model=args.chat_model,
            verbose=args.verbose,
        )
        if args.prompt_only:
            print("\n" + "=" * 80)
            print(f"[gemini-audio] Generated {target_mode.upper()} Prompt / Script:")
            print("=" * 80)
            print(generated)
            print("=" * 80)
            sys.exit(0)

        if not args.yes:
            proceed, effective_prompt = refine_prompt_interactively(
                client=client,
                current_prompt=generated,
                mode=target_mode,
                chat_model=args.chat_model,
            )
            if not proceed:
                sys.exit(0)
        else:
            effective_prompt = generated
            print("\n" + "=" * 80)
            print(f"[gemini-audio] Generated {target_mode.upper()} Prompt / Script:")
            print("=" * 80)
            print(effective_prompt)
            print("=" * 80)
    elif target_mode == "sfx" and not effective_prompt.lower().startswith("sound effect:"):
        effective_prompt = f"Sound effect: {effective_prompt}"

    # Resolve destination path
    output_dest = Path(args.output) if args.output else None

    # Execute Audio Generation
    if target_mode in ["music", "sfx"]:
        generate_music_lyria(
            client=client,
            prompt=effective_prompt,
            model=model_name,
            ref_images=args.images,
            output_path=output_dest,
            verbose=args.verbose,
        )
    else:
        generate_voice_tts(
            client=client,
            text_input=effective_prompt,
            model=model_name,
            voice=args.voice,
            speakers=multi_speakers,
            output_path=output_dest,
            verbose=args.verbose,
        )


if __name__ == "__main__":
    main()
