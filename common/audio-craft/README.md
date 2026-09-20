# gemini-audio

A comprehensive Python CLI tool for generating human voice and music using the Google Gemini / Lyria APIs (Gemini 3.1 Flash TTS & Lyria 3.5 Music models), built according to the official [Gemini Text-to-Speech Generation](https://ai.google.dev/gemini-api/docs/speech-generation) and [Gemini Music Generation](https://ai.google.dev/gemini-api/docs/music-generation) documentation.

---

## Complete Features

### 1. Human Voice / Speech Generation (Gemini TTS)
- **Controllable Text Recitation**:
  - Direct style, accent, pace, and tone using natural language instructions (e.g., *"Say cheerfully: Have a wonderful day!"* or *"Speak in a mysterious whisper:"*).
- **30 Prebuilt Output Voices**:
  - Choose from 30 distinct character voices ranging from upbeat (`Puck`) and firm (`Kore`) to bright (`Zephyr`), excitable (`Fenrir`), informative (`Charon`), gravelly (`Algenib`), breathy (`Enceladus`), and mature (`Gacrux`).
- **Multi-Speaker Dialogue (Up to 2 Speakers)**:
  - Generate full conversational exchanges between two characters with `--speakers "Speaker1:Voice1,Speaker2:Voice2"` or `--speaker1` and `--speaker2`.
- **Expressive Inline Audio Tags**:
  - Fine-grained emotional and paralinguistic control embedded directly in transcript text: `[whispers]`, `[laughs]`, `[sighs]`, `[excited]`, `[gasp]`, `[cough]`, `[yawn]`, `[serious]`, `[shouting]`, `[trembling]`, `[sarcastic]`, etc.
- **Multilingual Support**:
  - Automatically recognizes and generates speech across 40+ languages (English, Chinese/Mandarin, Spanish, French, German, Japanese, Korean, Hindi, etc.).

### 2. Music Generation (Google Lyria)
- **Full-Length Song Composition (`lyria-3.5`)**:
  - Flagship model designed for complete songs with complex structural coherence (verses, choruses, bridges, outros), vocals, and lyrics in 44.1 kHz high-fidelity stereo audio.
- **30-Second Music Clips & Loops (`lyria-3-clip-preview`)**:
  - Generate high-quality 30-second soundtrack loops, video themes, or musical teasers.
- **Multimodal Image-to-Music (`-i` / `--image`)**:
  - Pass 1 to 10 reference images to visually inspire the music's mood, color palette, and instrumentation.
- **Custom Lyrics Support**:
  - Feed your own lyrics marked with structural tags (`[Verse]`, `[Chorus]`, `[Bridge]`, `[Outro]`) to guide vocal synthesis.
- **Automatic Lyrics & Structure Extraction**:
  - Automatically extracts and formats generated lyrics and musical sections.

### 3. Sound Effects (SFX) & Foley Generation (Google Lyria & AI Sound Designer)
- **Action & Combat Impacts (`--sfx` / `--foley`)**:
  - Synthesize heavy martial arts punches, kick whooshes, bone crunches, sword clashes, and cinematic bass drops.
- **Creature & Animal Audio**:
  - Produce realistic predator roars (tiger, lion, bear), morning songbird chirps, wolf howls, and fantasy monster vocals.
- **Environmental & Nature Soundscapes**:
  - Rainstorms, rolling thunder, howling wind, cracking campfires, ocean waves, and dense jungle ambience.
- **Sci-Fi & Mechanical Audio**:
  - Plasma cannon blasts, laser sweeps, airlock pressure releases, robotic servos, and futuristic engine hums.
- **AI Sound Designer (`--sfx --generate-prompt`)**:
  - Automatically translates high-level concepts into Hollywood-grade acoustic sound design prompts using Gemini 3.8 Flash.
- **Vocal Creature Performance & Combat Grunts (Gemini TTS)**:
  - Steer voice models to perform creature growls, battle cries, and pain/impact vocalizations using emotional audio tags.

### 4. Gemini 3.8 Flash AI Script & Prompt Generation (`--generate-script` / `--generate-prompt`)
- **Automated Dialogue & Scriptwriting**:
  - Turn a topic or concept into an expressive script or multi-speaker podcast conversation with speaker tags and inline audio tags.
- **Interactive Approval & Prompt Refinement**:
  - Displays generated prompt/script and offers interactive feedback: proceed (`[y]`), abort (`[n]`), regenerate (`[r]`), or suggest edits (`[s]`).
  - Auto-confirm with `-y` / `--yes` or view prompt only with `--prompt-only`.

### 5. Audio Formats & Output Management (`-o` / `--output`)
- **Output Formats**:
  - Supports standard `.wav` (PCM 24 kHz 16-bit mono) and `.mp3` (with automatic ffmpeg transcoding if installed).
- **Default Directory & Naming**:
  - Generated files are saved to `./outputs/` (gitignored) using the unique Gemini interaction ID (e.g., `./outputs/64fa3b0c1e82.wav`).
  - Custom target filenames or output directories are fully supported (e.g. `-o ./my_tracks/theme.mp3`).

---

## Installation & Setup

1. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Set your Gemini API Key:
   ```bash
   export GEMINI_API_KEY="your-gemini-api-key"
   ```
   *(The tool also automatically searches for keys in `.env` files in the workspace)*

3. Make executable (optional):
   ```bash
   chmod +x gemini-audio gemini-audio.py presets/*.sh
   ```

---

## Voice Library (30 Prebuilt Voices)

Run `./gemini-audio --list-voices` to view all available voices:

| Voice Name | Tonal Characteristics | Best Use Cases |
| :--- | :--- | :--- |
| **Kore** *(Default)* | Firm, steady, grounded | Narration, announcements, reliable hosts |
| **Puck** | Upbeat, energetic, engaging | Commercials, dynamic podcasts, youth dialogue |
| **Zephyr** | Bright, warm, clear | Friendly tutorials, cheerful guides |
| **Fenrir** | Excitable, punchy, dynamic | Action scenes, gaming announcers |
| **Charon** | Informative, serious, documentary-style | Documentaries, serious presentations |
| **Leda** | Youthful, fresh, vibrant | Teen characters, energetic vlogs |
| **Orus** | Firm, confident, resonant | Authority figures, formal narration |
| **Aoede** | Breezy, light, pleasant | Casual conversation, wellness audio |
| **Callirrhoe** | Easy-going, relaxed | Cozy stories, friendly banter |
| **Autonoe** | Bright, optimistic, clear | Explainers, uplifting messages |
| **Enceladus** | Breathy, gentle, intimate | Secrets, emotional scenes, ASMR-style |
| **Iapetus** | Clear, crisp, articulate | Instructional content, audiobooks |
| **Umbriel** | Calm, friendly, even | Relaxed interviews, bedtime stories |
| **Algieba** | Smooth, silky, polished | Luxury ads, suave characters |
| **Despina** | Smooth, soothing, melodic | Meditation, poetic narration |
| **Erinome** | Crisp, focused, precise | Technical explanations |
| **Algenib** | Gravelly, rugged, deep | Wizards, seasoned warriors, gritty detectives |
| **Rasalgethi** | Informative, explanatory | Science podcasts, educational guides |
| **Laomedeia** | Cheerful, radiant | Joyful announcements, animated characters |
| **Achernar** | Soft, gentle, subdued | Introspective dialogue, somber scenes |
| **Alnilam** | Firm, steady, anchored | News anchors, historical reenactments |
| **Schedar** | Even, balanced, measured | Professional voiceovers |
| **Gacrux** | Mature, seasoned, warm | Elder mentor, grandfatherly advice |
| **Pulcherrima** | Forward, vivid, direct | Dramatic proclamations |
| **Achird** | Friendly, welcoming, natural | Community hosts, conversational podcasts |
| **Zubenelgenubi**| Casual, informal, relaxed | Everyday casual dialogue |
| **Vindemiatrix** | Gentle, compassionate, quiet | Empathetic counselors, soft-spoken characters |
| **Sadachbia** | Lively, spirited, expressive | Comedic characters, animated stories |
| **Sadaltager** | Knowledgeable, academic, precise | Professors, medical/academic lectures |
| **Sulafat** | Warm, comforting, hearty | Storytellers, hospitable figures |

---

## Expressive Audio Tags Guide

Run `./gemini-audio --list-tags` to see all supported audio tags:

| Tag | Effect & Cadence |
| :--- | :--- |
| `[whispers]` | Soft, conspiratorial, intimate delivery |
| `[shouting]` | Projecting voice with force and high intensity |
| `[excited]` | Rapid tempo, bright pitch, enthusiastic inflection |
| `[laughs]` / `[giggles]` | Embedded natural chuckle or laughter |
| `[sighs]` | Audible breathy exhale of fatigue, relief, or resignation |
| `[gasp]` | Sharp intake of breath denoting surprise or shock |
| `[cough]` | Slight realistic cough or throat-clearing |
| `[yawn]` | Drowsy vocal delivery with audible yawn |
| `[tired]` | Weary, dragging, slightly slurred cadence |
| `[serious]` | Low pitch, measured, grave authority |
| `[amazed]` | Wonder, awe, marveling tone |
| `[curious]` | Inquisitive cadence with rising pitch inflections |
| `[mischievously]` | Playful, impish, plotting inflection |
| `[panicked]` | Breathless, rushed, distressed vocalization |
| `[sarcastic]` | Dry, cynical, deadpan emphasis |
| `[trembling]` | Vulnerable, emotional, shaky delivery |

---

## Sound Effects (SFX) & Foley Prompting Guide

When generating sound effects via `--sfx` (powered by Google Lyria 3 Clip), prompt specificity determines the physical realism, punch, and spatial fidelity of the output audio.

### The 4-Part Acoustic Sound Design Formula
To achieve Hollywood-grade cinematic sound effects, construct your prompt using these four acoustic layers:

$$\text{SFX Prompt} = \text{[Wind-up / Pre-attack]} + \text{[Impact / Core Event]} + \text{[Material Texture]} + \text{[Acoustic Environment]}$$

1. **Pre-Attack / Wind-up**: The physical movement preceding the sound (e.g., *high-speed whooshing air*, *mechanical charge-up*, *deep breath intake*).
2. **Transient Impact / Primary Event**: The instant peak of energy (e.g., *sharp leather slap*, *60Hz sub-bass chest thud*, *bone-cracking strike*, *explosive snap*).
3. **Material Texture & Harmonic Detail**: What objects are interacting (e.g., *steel-on-steel ring*, *guttural raspy vocal fry*, *splintering pine wood*, *wet snarling transients*).
4. **Acoustic Environment & Decay**: The acoustic space where the sound propagates (e.g., *tight concrete training dojo*, *dense humid rainforest canopy*, *cavernous mountain echo*).

---

### Sound Effect Design Recipe Matrix

| Sound Effect Category | Key Acoustic Components | Example Prompt |
| :--- | :--- | :--- |
| **Martial Arts Kick / Punch** | Fast whoosh + slap transient + 60Hz sub-bass thud + room decay | `"Sound effect: High-velocity whoosh of a martial arts kick cutting air, slamming into torso with sharp transient slap, followed by a heavy punch, deep 60Hz sub-bass thud, visceral crunch, tight room reverb"` |
| **Sword & Blade Clash** | Metallic swing + screeching steel contact + high harmonic ringing | `"Sound effect: Two broadswords clashing violently at high speed, screeching steel-on-steel friction, bright sparking transient, and long ringing metallic resonance decay"` |
| **Tiger / Predator Roar** | Low chest growl + raspy vocal fry + snarling transient + jungle decay | `"Sound effect: A ferocious, guttural tiger roar featuring deep sub-bass chest resonance, aggressive raspy vocal fry, and wet snarling transients, decaying into a dense humid rainforest"` |
| **Bird Chirps & Forest** | Multi-pitch warbles + canaries + feather flutters + gentle canopy wind | `"Sound effect: Serene morning songbirds chirping and singing high in the forest canopy, crisp polyphonic bird trills, natural foley SFX, gentle wind rustling through leaves"` |
| **Sci-Fi Plasma Cannon** | Energy spool + rapid downward pitch blast + heat sizzle + sub drop | `"Sound effect: Futuristic plasma cannon firing, high-pitched energy ionization charge-up followed by an explosive concussive plasma burst, searing electrical sizzle, and deep sub-bass shockwave"` |
| **Explosion & Shockwave** | Concussive crack + deep subsonic rumble + cascading debris | `"Sound effect: Massive cinematic explosion detonation, instantaneous supersonic shockwave crack, rolling 40Hz sub-bass rumble, and falling rock and dirt debris scatter"` |
| **Thunder & Lightning** | Instantaneous electrical snap + rolling low-frequency thunderclap | `"Sound effect: Close-proximity lightning strike, sharp explosive electrical snap immediately giving way to a massive rolling low-frequency thunder rumble echoing across the valley"` |
| **Airlock / Pneumatic Door**| High-pressure air hiss + heavy metallic sliding latch + seal thunk | `"Sound effect: Sci-fi spaceship airlock door opening, intense pressurized steam decompression hiss, heavy motorized steel track movement, and final mechanical latch click"` |

---

## Usage Examples

### 1. Single-Speaker Human Voice (TTS)
```bash
./gemini-audio "Hello and welcome! Today we are exploring the frontiers of artificial intelligence." -v Puck -o ./outputs/welcome.wav
```

### 2. Expressive Speech with Directorial Notes & Audio Tags
```bash
./gemini-audio "Say playfully: [whispers] Did you hear that? [gasp] I think someone is in the attic! [laughs] Just kidding!" -v Zephyr -o ./outputs/playful.wav
```

### 3. Multi-Speaker Dialogue Generation
Generate a two-person conversation with distinct voices:
```bash
./gemini-audio "Maya: [excited] Have you seen the latest telescope imagery?
Robert: [sighs] Yes Maya, and it's completely rewriting astrophysics." \
  --speakers "Maya:Zephyr,Robert:Charon" \
  -o ./outputs/astronomy_chat.wav
```

### 4. AI Script Generation (Powered by Gemini 3.8 Flash)
Let Gemini 3.8 write a full podcast teaser, review it interactively, then generate speech:
```bash
./gemini-audio "A podcast teaser debating whether time travel is theoretically possible" \
  --generate-script \
  --speakers "Liam:Puck,Dr. Elena:Kore" \
  -o ./outputs/time_travel_podcast.wav
```

*(Add `-y` / `--yes` to proceed immediately without interactive confirmation, or `--prompt-only` to view the script without synthesizing)*

### 5. Text-to-Music Generation (Lyria 3.5 Full Song)
```bash
./gemini-audio "An uplifting 128 BPM indie-electronic track featuring rhythmic synth plucks, driving acoustic drums, and an anthemic melodic chorus" \
  --music \
  -m lyria-3.5 \
  -o ./outputs/indie_electronic.mp3
```

### 6. Short 30-Second Music Loop / Teaser (`lyria-3-clip-preview`)
```bash
./gemini-audio "8-bit nostalgic retro arcade battle music, chiptune melody with driving bassline" \
  -m clip \
  -o ./outputs/retro_loop.mp3
```

### 7. Multimodal Image-to-Music (Soundtrack Inspired by Visuals)
Pass a landscape or character concept artwork to compose matching music:
```bash
./gemini-audio "An evocative, atmospheric ambient soundtrack capturing the emotional tone and colors of this visual artwork" \
  --music \
  -i /path/to/fantasy_landscape.jpg \
  -o ./outputs/landscape_soundtrack.mp3
```

### 8. Custom Song Lyrics with Structural Tags
```bash
./gemini-audio "A soulful acoustic ballad:
[Verse 1]
Footsteps in the morning rain,
echoes of an old refrain.
[Chorus]
Hold on to the light we knew,
every horizon leads back to you." \
  --music \
  -o ./outputs/ballad.mp3
```

### 9. Sound Effects & Foley Generation (`--sfx` / `--foley`)
Use `--sfx` (powered by Google Lyria 3 Clip) to synthesize isolated physical foley, creature vocalizations, impacts, and environmental textures:

#### 9.1 Martial Arts Kick & Heavy Punch Impacts:
```bash
./gemini-audio "High-velocity whoosh of a martial arts kick cutting air, slamming into a torso with a sharp transient slap, followed by a heavy punch, deep 60Hz sub-bass thud, visceral crunch, tight room reverb" \
  --sfx \
  -o ./outputs/combat_hit.mp3
```

#### 9.2 Sword Clashes & Blade Weapon Combat:
```bash
./gemini-audio "Two heavy steel broadswords clashing furiously at high speed, screeching metallic blade-on-blade friction, bright ringing harmonic sustain, and echoing stone chamber reverb" \
  --sfx \
  -o ./outputs/sword_clash.mp3
```

#### 9.3 Ferocious Tiger Roar & Jungle Predator Audio:
```bash
./gemini-audio "A fierce, guttural tiger roar featuring deep sub-bass chest resonance, aggressive raspy vocal fry, and wet snarling transients, decaying into a dense humid rainforest" \
  --sfx \
  -o ./outputs/tiger_roar.mp3
```

#### 9.4 Songbirds & Forest Morning Ambience:
```bash
./gemini-audio "Serene morning songbirds chirping and singing high in the forest canopy, crisp natural foley SFX, polyphonic canary trills, gentle wind rustling through pine leaves" \
  --sfx \
  -o ./outputs/bird_chirps.mp3
```

#### 9.5 Thunderstorm & Heavy Rain Downpour:
```bash
./gemini-audio "A sudden deafening lightning strike crack followed by a colossal rolling 35Hz sub-bass thunderclap rumbling across hills, accompanied by torrential rain hitting wet pavement" \
  --sfx \
  -o ./outputs/thunderstorm.mp3
```

#### 9.6 Sci-Fi Plasma Cannon & Mechanical Airlock:
```bash
./gemini-audio "High-tech plasma railgun firing, high-frequency capacitor charging whine erupting into a concussive ionized plasma blast, electrical sizzle, and deep sub-bass shockwave" \
  --sfx \
  -o ./outputs/plasma_blast.mp3
```

#### 9.7 Automated Hollywood SFX Design with Gemini 3.8 Flash (`--generate-prompt`):
Give any simple idea; Gemini 3.8 Flash acts as a sound engineer to write the full acoustic layer breakdown before generating:
```bash
# Example 1: Action fight scene
./gemini-audio "An intense boxing match with rapid body blows, glove impacts, and heavy breathing" \
  --sfx \
  --generate-prompt \
  -o ./outputs/boxing_sfx.mp3 -y

# Example 2: Mythological creature
./gemini-audio "A massive winged dragon landing heavily on rocky terrain and exhaling a fiery snarl" \
  --sfx \
  --generate-prompt \
  -o ./outputs/dragon_sfx.mp3 -y
```

### 10. Vocal Creature Performance & Combat Grunts (Gemini TTS)
In addition to acoustic foley, you can direct Gemini TTS voices to perform creature vocals, combat grunts, and pain/action reactions:

#### 10.1 Ferocious Beast Vocalization:
```bash
./gemini-audio "Say like a ferocious beast: [growls deeply] Grrrr... [roaring loudly with raw power] ROAAAARRR!" \
  -v Fenrir \
  -o ./outputs/tiger_vocal.wav
```

#### 10.2 Combat Action Grunt & Impact Reaction:
```bash
./gemini-audio "Perform combat reactions: [sharp breath exhale] Hiyah! [grunting from a heavy punch impact] Oof! [panting] You won't beat me!" \
  -v Orus \
  -o ./outputs/combat_grunt.wav
```

#### 10.3 Whistling & Bird Song Mimicry:
```bash
./gemini-audio "Whistle and chirp like morning birds in a tree: [whistling sweetly] Tweet-tweet! Chirp chirp chirp, twiddle tweet!" \
  -v Aoede \
  -o ./outputs/bird_mimic.wav
```

### 11. Read Transcript, Lyrics, or SFX Prompts from File
```bash
./gemini-audio -f my_script.txt -v Kore -o ./outputs/narration.wav
```

---

## Ready-to-Use Presets

Pre-configured shell scripts are provided in `./presets/`:

- **`./presets/podcast-dialogue.sh [Topic]`**:
  Generates a 2-host science/tech podcast discussion.
  ```bash
  ./presets/podcast-dialogue.sh "The mystery of dark matter in dwarf galaxies"
  ```

- **`./presets/character-monologue.sh [Concept]`**:
  Generates a dramatic monologue with rich emotional tags.
  ```bash
  ./presets/character-monologue.sh "A cyberpunk hacker realizing the AI mainframe is sentient"
  ```

- **`./presets/cinematic-soundtrack.sh [Theme]`**:
  Composes an orchestral film score with Lyria 3.5.
  ```bash
  ./presets/cinematic-soundtrack.sh "A perilous sea voyage through storm and fog toward an enchanted island"
  ```

- **`./presets/sound-effect.sh [Description]`**:
  Synthesizes realistic action foley, nature sounds, or creature roars.
  ```bash
  ./presets/sound-effect.sh "Martial arts kick whoosh and heavy punch impact"
  ```

- **`./presets/music-from-image.sh <image_path> [style]`**:
  Composes music inspired by an image file.
  ```bash
  ./presets/music-from-image.sh artwork.png "Ambient fantasy flute and harp"
  ```

---

## CLI Options Reference

```text
positional arguments:
  prompt                Text prompt, speech transcript, or idea for prompt generation. Use '-' for stdin.

options:
  -f, --file FILE       Path to a text file containing the transcript, lyrics, or prompt.
  --mode {voice,music,sfx}
                        Explicit generation mode: 'voice' (Gemini TTS), 'music' (Lyria), or 'sfx' (Foley & Sound Effects).
  --music               Shortcut to enable music generation mode (uses Lyria 3.5 by default).
  --sfx, --foley        Shortcut to generate sound effects and foley (uses Lyria 3 Clip by default).
  --speech, --tts       Shortcut to force voice/speech generation mode.
  -m, --model MODEL     Model name or alias (e.g. gemini-3.1-flash-tts-preview, lyria-3.5, clip).
  -o, --output OUTPUT   Destination audio file or directory (e.g., ./outputs/track.mp3).
  -v, --voice VOICE     Prebuilt voice name for single-speaker TTS (default: Kore).
  --speakers SPEAKERS   Multi-speaker mapping: "Speaker1:Voice1,Speaker2:Voice2".
  --speaker1 SPEAKER1   Speaker 1 mapping (e.g. "Alice:Kore").
  --speaker2 SPEAKER2   Speaker 2 mapping (e.g. "Bob:Puck").
  -i, --image IMAGES    Path to reference image(s) for music generation (up to 10 images).
  --generate-script     Use Gemini 3.8 Flash to write an expressive script or music prompt.
  -y, --yes             Auto-confirm the generated script/prompt.
  --prompt-only         Display generated prompt/script and exit.
  --list-models         Display supported Gemini TTS and Lyria models.
  --list-voices         Display all 30 prebuilt voices.
  --list-tags           Display list of expressive inline audio tags.
  --info                Print summary of audio generation features.
  --api-key API_KEY     Gemini API Key override.
  -V, --verbose         Print detailed execution logs.
```
