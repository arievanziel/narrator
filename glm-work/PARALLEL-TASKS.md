# Parallel Task Handoff — for multiple GLM instances or Sonnet coordination

**Created:** 2026-08-17 ~20:15
**Context:** Qwen3-TTS download in progress (~60 min remaining). Arie wants to
parallelize the remaining Phase 1 work across multiple GLM instances (or have
Sonnet coordinate). This doc describes self-contained tasks that can run in
parallel without conflicting with each other or with the main download.

## Shared constraints (apply to all tasks)

- Work only in `glm-work/` (or a new `glm-work-parallel-N/` folder if you want
  isolation). Never edit `sonnet-work/`, `docs/`, or Arie's files.
- The Python venv is at `glm-work/.venv` (Python 3.12, uv-managed). Activate with
  `source glm-work/.venv/bin/activate`.
- Kokoro PyTorch is installed and working. mlx-audio is installed. UTMOSv2 is
  installed (model download was paused — resume with `python score_utmos.py`).
- Qwen3-TTS VoiceDesign model is downloading to
  `glm-work/models/qwen3_voicedesign_8bit/`. Do NOT start any task that needs
  this model until the download completes.
- No microphone input, ever. No final model recommendation in RESULTS.md.
- Preserve human `>` lines in markdown docs. Backup before editing files with
  human input.

## Task A: Kokoro voice comparison catalog

**Goal:** Generate short samples with all 54 Kokoro voices so Arie can pick
which ones work best for narrator vs specific NPC types.

**Self-contained?** Yes — only needs Kokoro PyTorch (already installed).

**Steps:**
1. Create `glm-work/run_voice_catalog.py`
2. Use a short neutral test sentence (e.g. "The dragon's eyes opened slowly,
   revealing gold-flecked irises that had not blinked in a thousand years.")
3. Generate one WAV per voice using the Kokoro PyTorch pipeline:
   ```python
   from kokoro import KPipeline
   pipeline = KPipeline(lang_code="a")
   ps, tokens = pipeline.g2p(text)
   for result in pipeline.generate_from_tokens(tokens=tokens, voice=VOICE_NAME):
       # save audio
   ```
4. Save to `glm-work/outputs/voice_catalog/{voice_name}.wav`
5. Create `glm-work/notes/voice_catalog.md` with a table mapping each voice to
   a subjective description (gender, accent, tone) based on listening.
6. The full 54-voice list: check `pipeline.voices` or the Kokoro repo.

**Output:** `glm-work/outputs/voice_catalog/*.wav` + `glm-work/notes/voice_catalog.md`

**Conflict risk:** None — writes only to new files.

## Task B: GUI design wireframes

**Goal:** Sketch the UI for the eventual Narrator app (post-Phase-1).

**Self-contained?** Yes — pure design work, no code execution needed.

**Steps:**
1. Create `glm-work/notes/gui_design.md`
2. Design these screens (markdown wireframes or ASCII art):
   - **Main narration screen:** text paste area, voice picker, generate button,
     audio player, playback queue
   - **Voice assignment screen:** split narration into segments, assign a voice
     to each segment (narrator vs NPC1 vs NPC2)
   - **Speaker tag editor:** highlight [S1]/[S2] tags in the text, let user
     map tags to voices
   - **Settings:** model selection, default voice, speed/pitch controls
3. Consider the workflow: Arie pastes from Claude → reviews/edits speaker tags →
   assigns voices → generates → listens → regenerates specific segments if needed
4. Reference the multivoice project's screenplay format and TTS-Story's web UI
   for inspiration (see `glm-work/notes/pipeline_design_reference.md`)
5. Note which parts are model-specific (voice picker changes based on model:
   Kokoro presets vs Qwen3 VoiceDesign descriptions vs Higgs ref audio)

**Output:** `glm-work/notes/gui_design.md`

**Conflict risk:** None — writes only to new files.

## Task C: Input preprocessing module

**Goal:** Build the text parser that splits pasted Claude text into segments
(narrator vs dialogue), extracts emotion cues, and inserts pause markers.

**Self-contained?** Yes — pure Python text processing, no model dependencies.

**Steps:**
1. Create `glm-work/narrator_parser.py`
2. Parse these patterns from pasted text:
   - `[S1]`/`[S2]` speaker tags → segment with speaker label
   - `(whispering)`, `(shouting)`, etc. → emotion cue (use multivoice's
     `EMOTION_MAPPINGS` dict as reference — see
     `glm-work/notes/pipeline_design_reference.md`)
   - Unquoted text between dialogue lines → narrator segment
   - Quoted dialogue without speaker tags → detect and label as character speech
   - `[beat]`/`[long beat]` → pause markers
3. Output a list of segments:
   ```python
   @dataclass
   class Segment:
       speaker: str  # "narrator", "S1", "S2", or character name
       text: str
       emotion: Optional[str]  # "whispering", "shouting", etc.
       pause_after: float  # seconds of silence to insert after this segment
   ```
4. Write tests in `glm-work/test_parser.py` using the existing test scripts
   (`test_scripts/1_single_speaker.txt`, `2_multi_speaker.txt`, `3_long_form.txt`)
   as test input.
5. This module is model-agnostic — it produces segments that any TTS engine
   can consume. The engine-specific adapter (Kokoro vs Qwen3 vs Higgs) is a
   separate layer.

**Output:** `glm-work/narrator_parser.py` + `glm-work/test_parser.py`

**Conflict risk:** None — writes only to new files.

## Task D: Download monitoring + Qwen3 test execution

**Goal:** Monitor the Qwen3-TTS download, run the test suite when it completes,
and update RESULTS.md.

**Self-contained?** Yes — this is what the current GLM instance is doing.

**Steps:**
1. Monitor `glm-work/models/qwen3_voicedesign_8bit/model.safetensors` size
   (target: 2.39 GB) and `speech_tokenizer/model.safetensors` (target: 682 MB)
2. When both complete, run `python smoke_test_qwen3_mlx.py` first
3. If smoke test passes, run `python run_qwen3_voicedesign.py`
4. Update `RESULTS.md` with Qwen3-TTS timings and observations
5. Resume UTMOSv2 download and score all outputs

**Output:** Updated `RESULTS.md`, `glm-work/outputs/qwen3_voicedesign/*.wav`

**Conflict risk:** Writes to `RESULTS.md` — coordinate if other tasks also
update it. Safest approach: Task D updates RESULTS.md, other tasks write to
separate notes files.

## Task E: Dia-1.6B and Higgs Audio V2 testing

**Goal:** Download and test Dia-1.6B and Higgs Audio V2 via mlx-audio.

**Self-contained?** Partially — requires downloads (3.22 GB for Dia, 4.75 GB
for Higgs q6). Check with Arie before starting downloads (20 GB budget).

**Steps:**
1. Ask Arie for download approval (mention sizes: Dia 3.22 GB, Higgs q6 4.75 GB)
2. Download via `hf download` or curl (curl is more reliable on slow connections)
3. Run `python run_dia_1_6b.py` (test runner already written)
4. Run `python run_higgs_audio.py` (test runner already written, uses q6 model)
5. Update RESULTS.md with timings and observations

**Output:** `glm-work/outputs/dia_1_6b/*.wav`, `glm-work/outputs/higgs_audio_v2/*.wav`

**Conflict risk:** Writes to RESULTS.md — coordinate with Task D. Also competes
for bandwidth with the Qwen3 download if run in parallel.

## Recommended parallelization

- **Instance 1 (current):** Task D (download monitoring + Qwen3 test)
- **Instance 2:** Task A (Kokoro voice catalog) — no download, no conflicts
- **Instance 3:** Task C (input preprocessing) — no download, no conflicts
- **Instance 4:** Task B (GUI design) — no code execution, no conflicts
- **Task E:** Run after Qwen3 download completes (bandwidth competition)

Tasks A, B, C can all start immediately and run in parallel with zero conflict
risk. They write to separate files and don't need any downloads.
