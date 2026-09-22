---
name: audio-craft
description: Generates human voice, expressive speech, multi-speaker dialogue, sound effects, foley, and full-length music using Google Gemini TTS and Google Lyria models via the gemini-audio CLI. Use when asked to create character voices, speech with emotional tone/accents, multi-speaker podcast/dialogue audio, sound effects, action impacts, ambient soundscapes, background music, or full songs from text or reference images.
metadata:
  author: Frame & Fable
  keywords:
    - audio-craft
    - gemini-audio
    - tts
    - speech-generation
    - lyria
    - music-generation
    - sound-effects
    - sfx
    - foley
    - voice-acting
    - dialogue
---

# Audio Craft (`audio-craft` / `gemini-audio`)

`audio-craft` provides high-fidelity AI audio generation powered by Google Gemini 3.1 Flash TTS (speech & dialogue), Google Lyria 3.5 & 3 Clip (music composition), and Gemini 3.8 Flash (automated scriptwriting and acoustic sound design).

---

## 1. Quick Command Overview

When installed system-wide, the CLI is accessible anywhere via `gemini-audio` or `audio-craft`:

```bash
# Global CLI command (in PATH):
gemini-audio [OPTIONS]
# or
audio-craft [OPTIONS]

# System-wide venv fallback:
~/.local/share/frame-and-fable/venvs/audio-craft/bin/python \
  /Volumes/Workspace/gitrepos/dailystudio/frame-and-fable/common/audio-craft/gemini-audio.py [OPTIONS]
```

### Environment Setup
Set your Gemini API key in your shell:
```bash
export GEMINI_API_KEY="your-gemini-api-key"
```

---

## 2. Key Capabilities & Usage Workflows

### A. Human Voice & Speech Generation (Gemini TTS)

#### 1. Single-Speaker Expressive Speech
Direct voice style, accent, pacing, and emotion using natural language instructions:
```bash
# Generate expressive speech with a chosen voice:
gemini-audio --prompt "Say cheerfully: Welcome to the magical kingdom of Frame and Fable!" \
  --voice Puck \
  -o welcome.wav

# Whisper or mysterious tone:
gemini-audio --prompt "Speak in a mysterious whisper: The ancient clockwork tower has finally awakened." \
  --voice Kore \
  -o mystery.wav
```

#### 2. Expressive Inline Audio Tags
Embed emotion, reactions, and physical vocalizations directly within text:
- Supported tags: `[whispers]`, `[laughs]`, `[sighs]`, `[excited]`, `[gasp]`, `[cough]`, `[yawn]`, `[serious]`, `[shouting]`, `[trembling]`, `[sarcastic]`, `[panting]`
```bash
gemini-audio --prompt "I can't believe we actually found it [gasp]! Look at the treasure glowing in the dark [excited]! But wait... [whispers] did you hear that footstep?" \
  --voice Zephyr \
  -o cave_discovery.wav
```

#### 3. Multi-Speaker Dialogue (Up to 2 Speakers)
Generate natural conversations between two distinct characters:
```bash
gemini-audio \
  --speakers "Detective:Fenrir,Suspect:Aoede" \
  --prompt "Detective: Where were you when the clock struck midnight? Suspect: I was alone in the library [sighs]... reading the archives." \
  -o interrogation.wav
```

#### 4. Voice Roster Reference (30 Built-in Voices)
- Upbeat / Youthful: `Puck`, `Zephyr`, `Fenrir`
- Firm / Grounded: `Kore`, `Leda`, `Orus`
- Informative / Narrator: `Charon`, `Aoede`, `Calliope`
- Mature / Gravelly: `Algenib`, `Gacrux`, `Enceladus`

---

### B. Music Generation (Google Lyria)

#### 1. Full-Length Song Composition (`lyria-3.5`)
Generates 44.1 kHz stereo songs with structural coherence and vocals:
```bash
gemini-audio --music \
  --prompt "An epic orchestral fantasy soundtrack with soaring violins, driving brass, and heroic drums" \
  -o battle_theme.mp3
```

#### 2. 30-Second Soundtrack Loops & Teasers (`lyria-3-clip-preview`)
```bash
gemini-audio --music \
  --model lyria-3-clip-preview \
  --prompt "A relaxing lofi hip hop beat with rain ambience and gentle Rhodes piano keys" \
  -o lofi_loop.wav
```

#### 3. Multimodal Image-to-Music (`-i` / `--image`)
Feed 1 to 10 reference images to guide the musical aesthetic, mood, and instrumentation:
```bash
gemini-audio --music \
  -i concept_art.png scenery.jpg \
  --prompt "Cinematic ambient theme matching the visual tone and atmosphere of these illustrations" \
  -o concept_score.wav
```

#### 4. Custom Song Lyrics with Structural Markers
```bash
gemini-audio --music \
  --prompt "Uplifting synthwave pop track" \
  --lyrics "[Verse] Neon lights reflections in the rain. Driving fast without a single pain. [Chorus] Electric sky, hold on tight, we are flying through the night! [Outro] Fading into the dawn." \
  -o synthwave_song.mp3
```

---

### C. Sound Effects (SFX) & Foley Generation

Synthesize impacts, nature soundscapes, creature vocals, and sci-fi mechanical audio:
```bash
# Combat impact:
gemini-audio --sfx \
  --prompt "Heavy cinematic martial arts punch with low-end bass sub drop and whoosh" \
  -o punch.wav

# Environmental soundscape:
gemini-audio --sfx \
  --prompt "Distant rolling thunder over a dense bamboo forest with wind rustling leaves" \
  -o storm_ambience.wav

# AI Sound Designer (translates concepts into Hollywood-grade acoustic prompts):
gemini-audio --sfx \
  --generate-prompt "A massive cybernetic dragon firing a plasma beam" \
  -y \
  -o dragon_plasma.wav
```

---

### D. Automated Dialogue & Scriptwriting (`--generate-script`)

Uses Gemini 3.8 Flash to write rich scripts complete with speaker voices and inline tags:
```bash
# Generate script and confirm automatically (-y):
gemini-audio \
  --generate-script "Two adventurers arguing over which ancient lever to pull in a crumbling temple" \
  -y \
  -o temple_argument.wav

# Preview script only without audio generation:
gemini-audio \
  --generate-script "A humorous sci-fi cooking show hosted by an alien chef" \
  --prompt-only
```

---

## 3. Command Reference & Arguments

| Flag | Description | Default |
|---|---|---|
| `-p, --prompt` | Text description, speech script, or music direction | (Required) |
| `-v, --voice` | Output voice for speech (e.g. `Puck`, `Kore`, `Zephyr`) | `Puck` |
| `--speakers` | Multi-speaker voice mapping (`Speaker1:Voice1,Speaker2:Voice2`) | None |
| `--music` | Switch engine mode to music generation (Google Lyria) | Off |
| `--sfx, --foley` | Switch engine mode to sound effects generation | Off |
| `-i, --image` | Reference image path(s) for multimodal music inspiration | None |
| `-m, --model` | Engine model (`lyria-3.5`, `lyria-3-clip-preview`, etc.) | Auto |
| `-o, --output` | Target output audio file (`.wav` or `.mp3`) or directory | `./outputs/<id>.wav` |
| `--generate-script` | Generate dialogue script with Gemini 3.8 Flash | None |
| `--generate-prompt` | Generate acoustic SFX prompt with Gemini 3.8 Flash | None |
| `-y, --yes` | Auto-confirm generated prompts without interactive prompt | Off |
| `--prompt-only` | Output generated prompt/script and exit without audio synthesis | Off |
| `--list-voices` | Print all 30 prebuilt speech voices and descriptions | - |

---

## 4. Agent Best Practices

1. **Non-Interactive Execution**: Always include `-y` or specify `--output <path>` directly when running via agent bash tools to avoid hanging on interactive user confirmation prompts.
2. **Format Selection**: Specify `.mp3` for smaller distribution assets (requires system `ffmpeg`), or `.wav` for uncompressed raw PCM audio.
3. **Dialogue Tagging**: When writing multi-speaker dialogue, use the format `CharacterName: [emotion] Words here.` to ensure optimal TTS parsing.
