// State
let history = [];
let turnCount = 0;
let currentAudio = null;
let audioPollTimer = null;
let isPlaying = false;
let audioDuration = 0;
let audioPosition = 0;
let audioUpdateTimer = null;
let settings = { autoroll: true, music: true, tts: 'kokoro', speed: 1.0, musicVol: 0.12, musicSrc: 'library', model: 'gemini-3.5-flash-lite', narrationVol: 1.0 };
let currentMood = 'exploration';
let bgMusicPlaying = false;
let lastState = null;          // most recent game state (for re-render on storyteller toggle)
let currentChapter = null;     // most recent chapter object from /api/turn

// TASK 1a — Lexicon layer: single source of truth for player-visible strings.
// storytellerMode (default false, persisted in localStorage) reveals mechanics.
// When off: D&D jargon is hidden or translated to literary phrasing.
let storytellerMode = (localStorage.getItem('narrator_storytellerMode') === 'true');

const LEXICON = {
  dm: 'the Narrator',
  sessionZero: 'Foreword',
  turn: 'passage',
  hp: 'Condition',
  ac: 'Armor',          // hidden entirely when storytellerMode is off
  enemies: 'Present in this scene',
  mechanics: 'Storyteller\u2019s notes',
  inventory: 'Belongings',
  chronicle: 'The story so far',
  save: 'Place bookmark',
  load: 'Resume reading',
  newGame: 'New book',
  // "class" → "vocation": rendered from state.pc_vocation (falls back to pc_class)
  vocation: 'Vocation',
  character: 'Your character',
  equipment: 'Carried',
};

// Spell out chapter numbers in words (not digits or roman numerals).
const NUMBER_WORDS = ['Zero','One','Two','Three','Four','Five','Six','Seven','Eight','Nine','Ten',
                      'Eleven','Twelve','Thirteen','Fourteen','Fifteen','Sixteen','Seventeen','Eighteen','Nineteen','Twenty',
                      'Twenty-One','Twenty-Two','Twenty-Three','Twenty-Four','Twenty-Five'];
function numberToWord(n) {
  if (n >= 0 && n < NUMBER_WORDS.length) return NUMBER_WORDS[n];
  return n.toString();
}

// v0.4a: Segment queue state
let queueState = null;       // last queue status from server
let currentSegIndex = 0;     // which segment is currently playing
let queuePollTimer = null;   // timer for queue polling
let freetextDebounceTimer = null;
let freetextGenId = null;

// Panel toggling
function togglePanel(name) {
  const app = document.getElementById('app');
  if (name === 'left') {
    app.classList.toggle('show-left');
    document.getElementById('tab-left').classList.toggle('active');
    document.getElementById('ctab-left').classList.toggle('active');
  } else if (name === 'settings') {
    app.classList.toggle('show-settings');
    document.getElementById('tab-settings').classList.toggle('active');
    document.getElementById('ctab-settings').classList.toggle('active');
  }
}
function toggleBar() {
  document.getElementById('app').classList.toggle('hide-topbar');
}

// Settings
function toggleSetting(name, el) {
  el.classList.toggle('on');
  settings[name] = el.classList.contains('on');
  if (name === 'music') { updateBgMusic(); }
}

// TASK 1a — Storyteller's notes toggle: reveal/hide mechanics, dice, AC, raw changes.
function toggleStorytellerMode(el) {
  el.classList.toggle('on');
  storytellerMode = el.classList.contains('on');
  localStorage.setItem('narrator_storytellerMode', storytellerMode ? 'true' : 'false');
  applyStorytellerMode();
}

// Apply storyteller-mode gating to the current DOM (toggle visibility of mechanics).
function applyStorytellerMode() {
  const root = document.documentElement;
  if (storytellerMode) {
    root.classList.add('storyteller-mode');
  } else {
    root.classList.remove('storyteller-mode');
  }
  // Re-render the left panel so stats show/hide
  if (lastState) updateState(lastState);
}
function changeModel(val) { settings.model = val; }
function changeTTS(val) { settings.tts = val; }
function changeSpeed(val) { settings.speed = parseFloat(val); document.getElementById('speed-val').textContent = val + 'x'; }
function changeMusicVol(val) { settings.musicVol = parseFloat(val); document.getElementById('musicvol-val').textContent = Math.round(val*100) + '%'; updateBgMusic(); }
function changeNarrationVol(val) {
  settings.narrationVol = parseFloat(val);
  document.getElementById('narrvol-val').textContent = Math.round(val*100) + '%';
  const player = document.getElementById('audio-player');
  player.volume = settings.narrationVol;
}
function changeMusicSrc(val) { settings.musicSrc = val; updateBgMusic(); }

// v0.8: Music crossfade — use a second hidden audio element for smooth transitions
let bgMusicCrossfading = false;

function updateBgMusic() {
  const player = document.getElementById('bg-music-player');
  if (!settings.music) {
    player.pause();
    bgMusicPlaying = false;
    return;
  }
  const url = `/api/music?mood=${currentMood}&source=${settings.musicSrc}`;
  if (player.src.indexOf(url) === -1) {
    // v0.8: Crossfade if music is already playing
    if (bgMusicPlaying && !player.paused) {
      crossfadeMusic(url);
    } else {
      player.src = url;
      player.volume = settings.musicVol;
      if (bgMusicPlaying) player.play().catch(()=>{});
    }
  } else {
    player.volume = settings.musicVol;
  }
}

// v0.8: Crossfade between old and new music tracks over ~2 seconds
function crossfadeMusic(newUrl) {
  if (bgMusicCrossfading) return;  // don't stack crossfades
  bgMusicCrossfading = true;

  const oldPlayer = document.getElementById('bg-music-player');
  const newPlayer = document.getElementById('bg-music-player-2');

  // Set up new player
  newPlayer.src = newUrl;
  newPlayer.volume = 0;
  newPlayer.loop = true;

  const targetVol = settings.musicVol;
  const fadeDuration = 2000;  // 2 seconds
  const steps = 20;
  const stepTime = fadeDuration / steps;
  const volStep = targetVol / steps;
  let step = 0;

  newPlayer.play().catch(()=>{});

  const fadeInterval = setInterval(() => {
    step++;
    const newVol = Math.min(step * volStep, targetVol);
    const oldVol = Math.max(targetVol - step * volStep, 0);

    newPlayer.volume = Math.min(newVol, 1);
    oldPlayer.volume = Math.min(oldVol, 1);

    if (step >= steps) {
      clearInterval(fadeInterval);
      // Swap: make new player the primary
      oldPlayer.pause();
      oldPlayer.src = '';
      // Swap IDs so the rest of the code still finds the active player
      oldPlayer.id = 'bg-music-player-2';
      newPlayer.id = 'bg-music-player';
      bgMusicCrossfading = false;
    }
  }, stepTime);
}

function setMood(mood) {
  if (mood && mood !== currentMood) {
    currentMood = mood;
    // tb-mood was removed in the book header redesign — no topbar mood display.
    const moodEl = document.getElementById('tb-mood');
    if (moodEl) moodEl.textContent = mood;
    updateBgMusic();
  }
}

function setTheme(theme) {
  const root = document.documentElement;
  if (theme === 'dark') {
    root.style.setProperty('--bg', '#1a1a1e');
    root.style.setProperty('--bg-soft', '#22222a');
    root.style.setProperty('--bg-panel', '#26262e');
    root.style.setProperty('--ink', '#d8d6d2');
    root.style.setProperty('--ink-mid', '#a8a6a2');
    root.style.setProperty('--ink-light', '#78767a');
    root.style.setProperty('--ink-faint', '#504e52');
    root.style.setProperty('--rule', '#38383e');
    root.style.setProperty('--rule-soft', '#2e2e34');
    root.style.setProperty('--accent', '#c8a040');
    root.style.setProperty('--accent-soft', 'rgba(200,160,64,0.15)');
    root.style.setProperty('--hp-good', '#5a9a5a');
    root.style.setProperty('--hp-bad', '#c05050');
    root.style.setProperty('--hp-mid', '#d8a830');
  } else if (theme === 'sepia') {
    root.style.setProperty('--bg', '#f0e6d2');
    root.style.setProperty('--bg-soft', '#e8dcc4');
    root.style.setProperty('--bg-panel', '#e2d6be');
    root.style.setProperty('--ink', '#3a2e1e');
    root.style.setProperty('--ink-mid', '#5a4e3e');
    root.style.setProperty('--ink-light', '#8a7e6e');
    root.style.setProperty('--ink-faint', '#b0a490');
    root.style.setProperty('--rule', '#d0c4a8');
    root.style.setProperty('--rule-soft', '#d8ccb0');
    root.style.setProperty('--accent', '#8b6914');
    root.style.setProperty('--accent-soft', 'rgba(139,105,20,0.12)');
    root.style.setProperty('--hp-good', '#4a7a4a');
    root.style.setProperty('--hp-bad', '#a04040');
    root.style.setProperty('--hp-mid', '#b8860b');
  } else {
    // Light (default)
    root.style.setProperty('--bg', '#e6e4e0');
    root.style.setProperty('--bg-soft', '#dedcd8');
    root.style.setProperty('--bg-panel', '#d8d6d2');
    root.style.setProperty('--ink', '#1c1c1a');
    root.style.setProperty('--ink-mid', '#4a4a48');
    root.style.setProperty('--ink-light', '#8a8a86');
    root.style.setProperty('--ink-faint', '#b0b0ac');
    root.style.setProperty('--rule', '#c4c2be');
    root.style.setProperty('--rule-soft', '#d0ceca');
    root.style.setProperty('--accent', '#8b6914');
    root.style.setProperty('--accent-soft', 'rgba(139,105,20,0.1)');
    root.style.setProperty('--hp-good', '#4a7a4a');
    root.style.setProperty('--hp-bad', '#a04040');
    root.style.setProperty('--hp-mid', '#b8860b');
  }
}

// Dice roller
let diceRollHistory = [];
let lastManualRoll = null;       // last d20 result for manual_roll (Fix 2)

function rollDice(btn, sides) {
  btn.classList.add('rolling');
  setTimeout(() => btn.classList.remove('rolling'), 300);
  const result = Math.floor(Math.random() * sides) + 1;
  const el = document.getElementById('dice-result');
  el.innerHTML = `<span class="roll-val">${result}</span> <span style="color:var(--ink-faint)">on d${sides}</span>`;
  // Add to history
  diceRollHistory.unshift({sides, result, time: new Date()});
  if (diceRollHistory.length > 10) diceRollHistory.pop();
  updateDiceHistory();
  // Fix 2: Store d20 results for manual_roll — don't append text to input.
  // The backend reads data.manual_roll and uses it in the DC-then-roll flow.
  if (sides === 20) {
    lastManualRoll = result;
    // Show a subtle indicator that the roll is ready to send
    el.innerHTML += ' <span style="color:var(--ink-faint);font-size:11px;">(will be used for your next action)</span>';
  }
}

function updateDiceHistory() {
  const el = document.getElementById('dice-history');
  if (!el) return;
  el.innerHTML = diceRollHistory.map(r =>
    `<div class="dice-history-item">d${r.sides}: <span class="dice-history-val">${r.result}</span></div>`
  ).join('');
}

// Start game from intro
async function startGame(opts = {}) {
  const overlay = document.getElementById('intro-overlay');
  const startBtn = document.getElementById('intro-start-btn');
  if (startBtn) { startBtn.disabled = true; startBtn.textContent = 'Starting...'; }
  // The intro form was removed in v1 — "Open the book" always uses defaults/procedural generation.
  // The foreword (Session Zero) is the way to customize the story.
  const params = opts.skip ? {} : {};
  overlay.classList.add('hidden');
  // Show the main app
  document.getElementById('app').classList.add('show-app');
  document.getElementById('app').classList.add('show-left');
  document.getElementById('tab-left').classList.add('active');
  document.getElementById('ctab-left').classList.add('active');
  await newGame(params);
  if (startBtn) { startBtn.disabled = false; startBtn.textContent = 'Open the book with defaults'; }
}

// New game
async function newGame(params = {}) {
  history = [];
  turnCount = 0;
  document.getElementById('story-content').innerHTML = '';
  const typing = showTyping();
  try {
    const resp = await fetch('/api/newgame', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(params),
    });
    const data = await resp.json();
    typing.remove();
    if (data.error) { addError(data.error); return; }
    document.getElementById('model-label').textContent = data.model;
    settings.autoroll = data.auto_roll;
    updateSettingsUI();
    updateState(data.state);
    if (data.story) addStoryTurn(data, true);
    if (data.audio_enabled) pollAudio(data.audio_turn_id);
    updateBudget(data.budget);
    fetchChronicle();
    fetchChapters();
    // Start/restart background music
    if (settings.music) {
      bgMusicPlaying = true;
      if (data.scene) currentMood = data.scene;
      updateBgMusic();
      document.getElementById('bg-music-player').play().catch(()=>{});
    }
    fetchProviderStatus();
  } catch(e) { typing.remove(); addError('Connection error: ' + e.message); }
}

// Send action
async function sendAction() {
  const input = document.querySelector('.input-block input');
  if (!input) return;
  const action = input.value.trim();
  if (!action) return;
  input.value = '';
  const btn = document.querySelector('.input-block button');
  if (btn) { btn.disabled = true; btn.textContent = '...'; }

  addPlayerAction(action);
  const typing = showTyping();

  try {
    // Fix 2: Send manual_roll if the player rolled a d20 and auto-roll is off.
    const postBody = { action, settings: { autoroll: settings.autoroll, music: settings.music, tts: settings.tts, speed: settings.speed, musicVol: settings.musicVol, musicSrc: settings.musicSrc, model: settings.model, narrationVol: settings.narrationVol } };
    if (lastManualRoll !== null && !settings.autoroll) {
      postBody.manual_roll = lastManualRoll;
      lastManualRoll = null;  // consume it — one roll per action
    }
    const resp = await fetch('/api/turn', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(postBody),
    });
    const data = await resp.json();
    typing.remove();
    if (data.error) { addError(data.error); }
    else {
      updateState(data.state);
      if (data.model) {
        document.getElementById('model-label').textContent = data.model;
        settings.model = data.model;
        document.getElementById('set-model').value = data.model;
      }
      addStoryTurn(data);
      if (data.audio_enabled && data.audio_turn_id) pollAudio(data.audio_turn_id);
      updateBudget(data.budget);
      if (data.fallback_used) {
        showFallbackWarning(data.original_model, data.model);
      }
      fetchChronicle();
      fetchChapters();
      fetchProviderStatus();
    }
  } catch(e) { typing.remove(); addError('Connection error: ' + e.message); }
  if (btn) { btn.disabled = false; btn.textContent = 'Send'; }
  if (input) input.focus();
}

// Add story turn to display
function addStoryTurn(data, isFirst = false) {
  turnCount = data.turn || turnCount + 1;
  const container = document.getElementById('story-content');

  // Update background music mood
  if (data.scene) setMood(data.scene);

  // TASK 1c: Track chapter for the book header
  if (data.chapter) currentChapter = data.chapter;

  // TASK 1c: Chapter heading — only when chapter.is_new (NOT a turn mark)
  if (data.chapter && data.chapter.is_new) {
    const heading = document.createElement('div');
    heading.className = 'chapter-heading';
    const num = data.chapter.number || 1;
    heading.id = 'chapter-' + num;
    heading.innerHTML =
      `<div class="chapter-number">Chapter ${escapeHtml(numberToWord(num))}</div>` +
      `<div class="chapter-title">${escapeHtml(data.chapter.title || '')}</div>` +
      `<div class="chapter-rule"></div>`;
    container.appendChild(heading);
    // Refresh the TOC since a new chapter just opened
    fetchChapters();
  }

  // TASK 1c: Scene-setting paragraph — only on chapter opening, with drop cap
  if (data.chapter && data.chapter.is_new && data.scene_setting) {
    const scene = document.createElement('div');
    scene.className = 'scene-setting';
    scene.textContent = data.scene_setting;
    container.appendChild(scene);
  }

  // TASK 1c: No roman-numeral turn mark — removed per spec.

  // Story segments (word-for-word = what's spoken)
  if (data.segments && data.segments.length) {
    for (const seg of data.segments) {
      const passage = document.createElement('div');
      passage.className = 'story-passage';
      if (seg.kind === 'narrator') {
        passage.innerHTML = `<div class="narrator-text">${escapeHtml(seg.text)}</div>`;
      } else {
        passage.innerHTML = `<div class="speaker-label">${escapeHtml(seg.speaker)}</div><div class="dialogue-text">"${escapeHtml(seg.text)}"</div>`;
      }
      container.appendChild(passage);
    }
  } else if (data.response) {
    // Fallback: show raw response
    const passage = document.createElement('div');
    passage.className = 'story-passage';
    passage.innerHTML = `<div class="narrator-text">${escapeHtml(data.response)}</div>`;
    container.appendChild(passage);
  }

  // v0.4b: Roll result display (dice roll indicator) — gated by storyteller mode
  if (data.roll && data.contested && storytellerMode) {
    const rollDiv = document.createElement('div');
    rollDiv.className = 'roll-result-display';
    const isSuccess = data.roll.result === 'SUCCESS' || data.roll.result === 'CRITICAL_SUCCESS';
    const isCrit = data.roll.result === 'CRITICAL_SUCCESS';
    const isFumble = data.roll.result === 'CRITICAL_FAILURE';
    let resultClass = isSuccess ? 'roll-success' : 'roll-failure';
    if (isCrit) resultClass = 'roll-crit';
    if (isFumble) resultClass = 'roll-fumble';
    let resultText = data.roll.result.replace(/_/g, ' ');
    rollDiv.className = `roll-result-display ${resultClass}`;
    rollDiv.innerHTML = `
      <div class="roll-dice">${escapeHtml(data.roll.dice)}</div>
      <div class="roll-roll">${data.roll.roll}${data.roll.modifier ? (data.roll.modifier > 0 ? ' + ' + data.roll.modifier : ' ' + data.roll.modifier) : ''} = <strong>${data.roll.total}</strong></div>
      <div class="roll-dc">DC ${data.roll.dc}</div>
      <div class="roll-outcome">${escapeHtml(resultText)}</div>
    `;
    container.appendChild(rollDiv);
  }

  // TASK 1a: State changes / reader notes — storyteller mode shows raw "changes",
  // default mode shows "reader_notes" (literary) instead.
  if (storytellerMode && data.changes && data.changes.length) {
    const changes = document.createElement('div');
    changes.className = 'state-changes';
    const label = document.createElement('div');
    label.className = 'state-changes-label';
    label.textContent = LEXICON.mechanics;
    changes.appendChild(label);
    data.changes.forEach(c => {
      const span = document.createElement('div');
      let cls = 'state-change';
      if (c.includes('REJECTED')) cls += ' rejected';
      else if (c.includes('→') && c.includes('-')) cls += ' hp-down';
      else if (c.includes('→') && c.includes('+')) cls += ' hp-up';
      else if (c.includes('Gained:')) cls += ' gained';
      else if (c.includes('Roll requested')) cls += ' roll';
      span.className = cls;
      span.textContent = c;
      changes.appendChild(span);
    });
    container.appendChild(changes);
  } else if (!storytellerMode && data.reader_notes && data.reader_notes.length) {
    const notes = document.createElement('div');
    notes.className = 'reader-notes';
    const label = document.createElement('div');
    label.className = 'reader-notes-label';
    label.textContent = LEXICON.mechanics;
    notes.appendChild(label);
    data.reader_notes.forEach(n => {
      const span = document.createElement('div');
      span.className = 'reader-note';
      span.textContent = n;
      notes.appendChild(span);
    });
    container.appendChild(notes);
  }

  // Choices — 🎲 hidden unless storyteller mode
  if (data.suggestions && data.suggestions.length) {
    const choices = document.createElement('div');
    choices.className = 'choices-block';
    choices.innerHTML = '<div class="choices-label">What do you do?</div>';
    data.suggestions.forEach((s, i) => {
      const item = document.createElement('div');
      item.className = 'choice-item';
      item.innerHTML = `<span class="choice-letter">${i+1}</span><span>${escapeHtml(s.text)}</span>${s.roll && storytellerMode ? '<span class="choice-roll">\uD83C\uDFB2 roll</span>' : ''}`;
      item.onclick = () => useChoice(s.text);
      choices.appendChild(item);
    });
    container.appendChild(choices);

    // v0.4a: Pre-generate audio for all choices
    preGenerateChoices(data.suggestions.map(s => s.text));
  }

  // Input area
  if (!isFirst) {
    // Remove old input areas
    document.querySelectorAll('.input-block').forEach(el => el.remove());
  }
  const inputArea = document.createElement('div');
  inputArea.className = 'input-block';
  inputArea.innerHTML = `<input type="text" placeholder="What do you do?" onkeypress="if(event.key==='Enter')sendAction()" autofocus><button onclick="sendAction()">Send</button>`;
  container.appendChild(inputArea);

  // v0.4a: Debounced free-text audio generation
  const inputEl = inputArea.querySelector('input');
  if (inputEl) {
    inputEl.addEventListener('input', onFreeTextInput);
    inputEl.addEventListener('blur', () => {
      // Don't cancel on blur — the text might still be sent
    });
  }

  // Add a subtle hint about keyboard shortcuts
  if (isFirst) {
    const hint = document.createElement('div');
    hint.style.cssText = 'font-size:11px;color:var(--ink-faint);text-align:center;padding:0.5rem;font-style:italic;';
    hint.textContent = 'Press 1-9 to choose, Enter to send, Esc to close panels';
    container.appendChild(hint);
  }

  // Scroll to bottom smoothly
  const mainArea = document.getElementById('main-area');
  mainArea.scrollTo({ top: mainArea.scrollHeight, behavior: 'smooth' });
  if (inputArea.querySelector('input')) inputArea.querySelector('input').focus();
}

function useChoice(text) {
  const input = document.querySelector('.input-block input');
  if (input) { input.value = text; sendAction(); }
}

// v0.4a: Pre-generate choice audio as soon as suggestions arrive
async function preGenerateChoices(choiceTexts) {
  if (!settings.tts || settings.tts === 'silent') return;
  try {
    await fetch('/api/choices/pre_generate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ choices: choiceTexts }),
    });
  } catch(e) { /* silent fail — pre-generation is best-effort */ }
}

// v0.4a: Debounced free-text audio generation
// Trigger after ~2-3 words or ~1 second of no typing
function onFreeTextInput(e) {
  const text = e.target.value.trim();
  if (!text || text.length < 3) return;  // too short to bother
  if (!settings.tts || settings.tts === 'silent') return;

  // Cancel any in-flight generation
  if (freetextDebounceTimer) clearTimeout(freetextDebounceTimer);
  if (freetextGenId) {
    fetch('/api/freetext/cancel', { method: 'POST' }).catch(()=>{});
    freetextGenId = null;
  }

  // Debounce: wait ~1 second of no typing
  freetextDebounceTimer = setTimeout(async () => {
    // Check if text is still the same (player might have kept typing)
    const currentText = e.target.value.trim();
    if (currentText !== text || currentText.length < 3) return;

    try {
      const resp = await fetch('/api/freetext/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ text: currentText }),
      });
      const data = await resp.json();
      if (data.gen_id) {
        freetextGenId = data.gen_id;
        // Fix 5: Poll /api/freetext_status until the audio is ready, then play it.
        pollFreetextStatus(data.gen_id);
      }
    } catch(e) { /* silent fail */ }
  }, 1000);
}

// Fix 5: Poll /api/freetext_status and play the audio when ready.
// Shows a subtle "voicing..." indicator near the input while generating.
let freetextPollTimer = null;
function pollFreetextStatus(genId) {
  if (freetextPollTimer) clearInterval(freetextPollTimer);
  const indicator = document.createElement('span');
  indicator.id = 'freetext-voicing';
  indicator.style.cssText = 'color:var(--ink-faint);font-size:11px;margin-left:8px;font-style:italic;';
  indicator.textContent = 'voicing...';
  const inputBlock = document.querySelector('.input-block');
  if (inputBlock) inputBlock.appendChild(indicator);

  freetextPollTimer = setInterval(async () => {
    try {
      const resp = await fetch(`/api/freetext_status?gen_id=${genId}`);
      const data = await resp.json();
      if (data.state === 'READY') {
        clearInterval(freetextPollTimer);
        freetextPollTimer = null;
        if (indicator) indicator.remove();
        // Play the generated audio
        const audio = new Audio(`/audio/freetext/${genId}.wav`);
        audio.volume = settings.narrationVol;
        audio.play().catch(() => {});
      } else if (data.state === 'FAILED' || data.state === 'superseded' || data.status === 'unknown') {
        clearInterval(freetextPollTimer);
        freetextPollTimer = null;
        if (indicator) indicator.remove();
      }
    } catch(e) {
      clearInterval(freetextPollTimer);
      freetextPollTimer = null;
      if (indicator) indicator.remove();
    }
  }, 500);
}

function addPlayerAction(text) {
  const container = document.getElementById('story-content');
  const el = document.createElement('div');
  el.className = 'player-action';
  el.textContent = text;
  container.appendChild(el);
  document.getElementById('main-area').scrollTop = document.getElementById('main-area').scrollHeight;
}

function showTyping() {
  const container = document.getElementById('story-content');
  const el = document.createElement('div');
  el.className = 'typing-indicator';
  el.innerHTML = 'The Narrator is weaving the story <span class="typing-dots"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></span>';
  container.appendChild(el);
  document.getElementById('main-area').scrollTop = document.getElementById('main-area').scrollHeight;
  return el;
}

function addError(msg) {
  const container = document.getElementById('story-content');
  const el = document.createElement('div');
  el.className = 'story-passage';
  el.style.color = 'var(--hp-bad)';
  el.textContent = '⚠ ' + msg;
  container.appendChild(el);
}

function showFallbackWarning(originalModel, fallbackModel) {
  const container = document.getElementById('story-content');
  const el = document.createElement('div');
  el.className = 'story-passage';
  el.style.color = 'var(--hp-mid)';
  el.style.fontSize = '13px';
  el.style.padding = '0.5rem 1rem';
  el.style.background = 'rgba(184,134,11,0.1)';
  el.style.borderRadius = '6px';
  el.innerHTML = `⚠ Budget limit reached — switched from <b>${escapeHtml(originalModel)}</b> to free model <b>${escapeHtml(fallbackModel)}</b>`;
  container.appendChild(el);
  document.getElementById('main-area').scrollTop = document.getElementById('main-area').scrollHeight;
}

async function saveGame() {
  try {
    const resp = await fetch('/api/save', {method: 'POST'});
    const data = await resp.json();
    if (data.error) addError('Save failed: ' + data.error);
    else addError('Bookmark placed at passage ' + data.turn);
  } catch(e) { addError('Save error: ' + e.message); }
}

async function loadGame() {
  try {
    const resp = await fetch('/api/load', {method: 'POST'});
    const data = await resp.json();
    if (data.error) { addError(data.error); return; }
    updateState(data.state);
    turnCount = data.turn;
    addError('Resumed reading at passage ' + data.turn);
    fetchChronicle();
    fetchChapters();
  } catch(e) { addError('Load error: ' + e.message); }
}

async function fetchChronicle() {
  try {
    const resp = await fetch('/api/chronicle');
    const data = await resp.json();
    const list = document.getElementById('chronicle-list');
    if (list) {
      const entries = data.chronicle || [];
      if (entries.length === 0) {
        list.innerHTML = '<div style="color:var(--ink-faint);font-style:italic;">No entries yet</div>';
      } else {
        list.innerHTML = entries.map((e, i) => `<div style="padding:0.3rem 0;border-bottom:1px solid var(--rule-soft);"><span style="color:var(--ink-faint);font-size:11px;">${escapeHtml(LEXICON.turn)} ${i+1}</span><br>${escapeHtml(e)}</div>`).join('');
      }
    }
  } catch(e) {}
}

// TASK 1d: Fetch the table of contents from /api/chapters and render it as
// "The story so far". Each entry scrolls to the chapter heading (id="chapter-N").
async function fetchChapters() {
  try {
    const resp = await fetch('/api/chapters');
    const data = await resp.json();
    const list = document.getElementById('toc-list');
    if (!list) return;
    const chapters = data.chapters || [];
    if (chapters.length === 0) {
      list.innerHTML = '<div style="color:var(--ink-faint);font-style:italic;">The book has not yet begun</div>';
      return;
    }
    list.innerHTML = chapters.map(ch => {
      const num = ch.number || 1;
      const title = escapeHtml(ch.title || 'Untitled');
      const numWord = escapeHtml(numberToWord(num));
      return `<div class="toc-entry" onclick="scrollToChapter(${num})">` +
             `<span class="toc-num">Chapter ${numWord}</span>` +
             `<span class="toc-title">${title}</span></div>`;
    }).join('');
  } catch(e) {}
}

// Scroll to a chapter heading by id.
function scrollToChapter(num) {
  const heading = document.getElementById('chapter-' + num);
  if (heading) {
    heading.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

async function fetchProviderStatus() {
  try {
    const resp = await fetch('/api/providers');
    const data = await resp.json();
    const el = document.getElementById('provider-status');
    if (el) {
      const current = data.current_model;
      const providers = data.providers || [];
      const lines = providers.map(p => {
        const isCurrent = p.id === current;
        const dot = p.available ? (p.free ? '🟢' : '🟡') : '🔴';
        const label = isCurrent ? `<b>${p.name}</b>` : p.name;
        const cost = p.free ? 'free' : 'paid';
        return `${dot} ${label} (${cost})`;
      });
      el.innerHTML = lines.join('<br>');
    }
  } catch(e) {}
}

// Update state display
function updateState(state) {
  if (!state) return;
  lastState = state;
  const hpPct = (state.pc_hp / state.pc_max_hp) * 100;
  const hpColor = hpPct > 60 ? 'var(--hp-good)' : hpPct > 30 ? 'var(--hp-mid)' : 'var(--hp-bad)';

  // TASK 1b: Book header — title left, chapter centre, controls right.
  // Stats are NO LONGER in the topbar; they live in the left panel only.
  const bookTitle = document.getElementById('tb-booktitle');
  if (bookTitle) bookTitle.textContent = state.pc_name ? state.pc_name + '\u2019s Tale' : 'Untitled Book';
  const chapterLabel = document.getElementById('tb-chapter');
  if (chapterLabel) {
    if (currentChapter && currentChapter.title) {
      const num = currentChapter.number || 1;
      chapterLabel.textContent = 'Chapter ' + numberToWord(num) + ' \u00B7 ' + currentChapter.title;
    } else {
      chapterLabel.textContent = 'Chapter One';
    }
  }

  // TASK 1d: Left panel — "Your character" (book lexicon)
  // Vocation: use pc_vocation (falls back to pc_class if empty)
  const vocation = state.pc_vocation || state.pc_class || '—';
  document.getElementById('char-info').innerHTML = `
    <div class="panel-item"><span>Name</span><span>${escapeHtml(state.pc_name)}</span></div>
    <div class="panel-item"><span>${escapeHtml(LEXICON.vocation)}</span><span>${escapeHtml(vocation)}</span></div>
    <div class="panel-item"><span>${escapeHtml(LEXICON.hp)}</span><span style="color:${hpColor}">${state.pc_hp}/${state.pc_max_hp}</span></div>
    <div class="hp-bar panel-hp-bar"><div class="hp-fill" style="width:${hpPct}%;background:${hpColor}"></div></div>`;

  // TASK 1a: Full ability scores + AC — only in storyteller mode
  const statsEl = document.getElementById('char-stats');
  if (storytellerMode) {
    const statMod = (v) => Math.floor((v - 10) / 2);
    const modStr = (m) => m >= 0 ? `+${m}` : `${m}`;
    statsEl.innerHTML = `
      <div class="panel-item"><span>AC</span><span>${state.pc_ac}</span></div>
      <div class="stat-grid">
        <div class="stat-box"><div class="stat-val">${state.pc_str}</div><div class="stat-mod">${modStr(statMod(state.pc_str))}</div><div class="stat-label">STR</div></div>
        <div class="stat-box"><div class="stat-val">${state.pc_dex}</div><div class="stat-mod">${modStr(statMod(state.pc_dex))}</div><div class="stat-label">DEX</div></div>
        <div class="stat-box"><div class="stat-val">${state.pc_con}</div><div class="stat-mod">${modStr(statMod(state.pc_con))}</div><div class="stat-label">CON</div></div>
        <div class="stat-box"><div class="stat-val">${state.pc_int}</div><div class="stat-mod">${modStr(statMod(state.pc_int))}</div><div class="stat-label">INT</div></div>
        <div class="stat-box"><div class="stat-val">${state.pc_wis}</div><div class="stat-mod">${modStr(statMod(state.pc_wis))}</div><div class="stat-label">WIS</div></div>
        <div class="stat-box"><div class="stat-val">${state.pc_cha}</div><div class="stat-mod">${modStr(statMod(state.pc_cha))}</div><div class="stat-label">CHA</div></div>
      </div>`;
    statsEl.style.display = '';
  } else {
    statsEl.innerHTML = '';
    statsEl.style.display = 'none';
  }

  // TASK 1d: Equipment → "Carried"
  const eqList = document.getElementById('equipment-list');
  if (state.equipment) {
    eqList.innerHTML = state.equipment.split(',').map(e => {
      e = e.trim();
      if (!e) return '';
      return `<div class="panel-item"><span>${escapeHtml(e)}</span></div>`;
    }).join('') || '<div class="panel-item" style="color:var(--ink-faint)">None</div>';
  } else {
    eqList.innerHTML = '<div class="panel-item" style="color:var(--ink-faint)">None</div>';
  }

  // Conditions (extracted from mechanics changes)
  const condList = document.getElementById('conditions-list');
  // Check if state has conditions (future: from WorldStore)
  if (state.conditions && state.conditions.length) {
    condList.innerHTML = state.conditions.map(c =>
      `<div class="panel-item"><span class="condition-badge">${escapeHtml(c)}</span></div>`
    ).join('');
  } else {
    condList.innerHTML = '<div class="panel-item" style="color:var(--ink-faint)">None</div>';
  }

  // TASK 1a: Enemies → "Present in this scene" — only in storyteller mode
  const enemySection = document.getElementById('enemy-section');
  if (storytellerMode) {
    if (enemySection) enemySection.style.display = '';
    document.getElementById('enemy-list').innerHTML = state.enemies.map(e =>
      `<div class="enemy-item ${e.alive ? '' : 'dead'}"><div class="enemy-dot ${e.alive ? 'alive' : 'dead'}"></div><span>${escapeHtml(e.name)}</span><span class="enemy-status">${e.hp}/${e.max_hp} HP, AC ${e.ac}</span></div>`
    ).join('') || '<div class="panel-item" style="color:var(--ink-faint)">None</div>';
  } else {
    if (enemySection) enemySection.style.display = 'none';
  }

  // TASK 1d: Inventory → "Belongings"
  document.getElementById('inv-list').innerHTML = state.inventory.map(i =>
    `<div class="panel-item"><span>${escapeHtml(i)}</span></div>`
  ).join('') || '<div class="panel-item" style="color:var(--ink-faint)">Empty</div>';
}

function updateSettingsUI() {
  const ar = document.getElementById('set-autoroll');
  if (settings.autoroll) ar.classList.add('on'); else ar.classList.remove('on');
  document.getElementById('set-model').value = settings.model;
  document.getElementById('set-tts').value = settings.tts;
  // TASK 1a: storyteller toggle
  const sm = document.getElementById('set-storyteller');
  if (sm) { if (storytellerMode) sm.classList.add('on'); else sm.classList.remove('on'); }
  applyStorytellerMode();
}

function updateBudget(budget) {
  if (!budget) return;
  const pct = (budget.spent / budget.budget) * 100;
  document.getElementById('budget-spent').textContent = '$' + budget.spent.toFixed(2);
  document.getElementById('budget-fill').style.width = Math.min(pct, 100) + '%';
  document.getElementById('budget-fill').style.background = pct > 80 ? 'var(--hp-bad)' : pct > 50 ? 'var(--hp-mid)' : 'var(--hp-good)';
  document.getElementById('budget-text').textContent = `$${budget.spent.toFixed(2)} / $${budget.budget.toFixed(2)}`;
}

// Audio playback — v0.4a segment queue consumer
function pollAudio(turnId) {
  if (!turnId) return;
  // Show generating indicator
  document.getElementById('audio-gen-bar').style.display = 'block';
  document.getElementById('audio-gen-fill').style.width = '5%';
  document.getElementById('audio-status').textContent = 'generating...';
  document.getElementById('audio-label').textContent = 'Generating audio';

  if (queuePollTimer) clearInterval(queuePollTimer);
  currentSegIndex = 0;
  audioDuration = 0;

  let pollCount = 0;
  queuePollTimer = setInterval(async () => {
    pollCount++;
    if (pollCount > 300) { // 5 min timeout
      clearInterval(queuePollTimer);
      document.getElementById('audio-status').textContent = 'timeout';
      document.getElementById('audio-gen-bar').style.display = 'none';
      return;
    }
    try {
      const resp = await fetch(`/api/queue_status?turn_id=${turnId}`);
      const data = await resp.json();
      if (data.status === 'unknown') {
        // Fall back to legacy polling
        clearInterval(queuePollTimer);
        pollAudioLegacy(turnId);
        return;
      }
      queueState = data;

      // Update progress bar
      const pct = data.total > 0 ? Math.round((data.ready / data.total) * 100) : 0;
      document.getElementById('audio-gen-fill').style.width = Math.max(pct, 5) + '%';

      // Update status text
      const readySegs = data.segments.filter(s => s.state === 'READY').length;
      const genSegs = data.segments.filter(s => s.state === 'GENERATING' || s.state === 'FALLBACK_GENERATING').length;
      if (genSegs > 0) {
        document.getElementById('audio-status').textContent =
          `segment ${data.ready + 1}/${data.total} generating...`;
      } else if (readySegs < data.total) {
        document.getElementById('audio-status').textContent =
          `${readySegs}/${data.total} segments ready`;
      }

      // Start playing as soon as the first segment is ready
      if (readySegs > 0 && !isPlaying && currentSegIndex < data.total) {
        const seg = data.segments[currentSegIndex];
        if (seg && seg.state === 'READY' && seg.audio_url) {
          playSegment(turnId, seg, data);
        } else if (seg && seg.state === 'FAILED') {
          // Skip failed segments
          currentSegIndex++;
          if (currentSegIndex < data.total) {
            // Check again immediately
            pollCount--;
          }
        }
      }

      // All done?
      if (data.done && currentSegIndex >= data.total) {
        clearInterval(queuePollTimer);
        document.getElementById('audio-gen-bar').style.display = 'none';
        if (!isPlaying) {
          document.getElementById('audio-status').textContent = 'done';
        }
      }
    } catch(e) {}
  }, 800);
}

function playSegment(turnId, seg, qData) {
  const player = document.getElementById('audio-player');
  player.src = seg.audio_url;
  player.volume = settings.narrationVol;
  audioDuration = seg.duration || 0;

  document.getElementById('audio-play').disabled = false;
  document.getElementById('audio-label').textContent =
    `Narrator · turn ${toRoman(turnCount)} · seg ${seg.index + 1}/${qData.total}`;
  document.getElementById('audio-time').textContent =
    `0:00 / ${formatTime(seg.duration)}`;

  // Duck background music during narration
  const bgPlayer = document.getElementById('bg-music-player');
  if (bgPlayer && bgMusicPlaying) {
    bgPlayer.volume = settings.musicVol * 0.3;
  }

  // Hide gen bar once first segment starts playing
  document.getElementById('audio-gen-bar').style.display = 'none';
  document.getElementById('audio-status').textContent = '';

  // v0.8: Fade-in at segment start (50ms)
  player.volume = 0;
  player.play().then(() => {
    isPlaying = true;
    document.getElementById('audio-play').textContent = '⏸';
    startAudioUpdate();
    // Smooth fade-in
    _fadeInVolume(player, settings.narrationVol, 50);
  }).catch(() => {});

  player.onended = () => {
    currentSegIndex++;
    isPlaying = false;
    document.getElementById('audio-play').textContent = '▶';
    stopAudioUpdate();

    // Check if next segment is ready
    if (queueState && currentSegIndex < queueState.total) {
      const nextSeg = queueState.segments[currentSegIndex];
      if (nextSeg && nextSeg.state === 'READY' && nextSeg.audio_url) {
        // Play next segment immediately
        playSegment(turnId, nextSeg, queueState);
      } else if (nextSeg && nextSeg.state === 'FAILED') {
        // Skip failed, try next
        while (currentSegIndex < queueState.total &&
               queueState.segments[currentSegIndex].state === 'FAILED') {
          currentSegIndex++;
        }
        if (currentSegIndex < queueState.total) {
          const skipSeg = queueState.segments[currentSegIndex];
          if (skipSeg && skipSeg.state === 'READY' && skipSeg.audio_url) {
            playSegment(turnId, skipSeg, queueState);
          } else {
            // Next segment not ready yet — show generating indicator
            document.getElementById('audio-gen-bar').style.display = 'block';
            document.getElementById('audio-status').textContent = 'generating next segment...';
          }
        } else {
          // All segments done
          finishPlayback();
        }
      } else {
        // Next segment not ready yet — show generating indicator
        document.getElementById('audio-gen-bar').style.display = 'block';
        document.getElementById('audio-status').textContent = 'generating next segment...';
      }
    } else {
      // All segments done
      finishPlayback();
    }
  };
}

function finishPlayback() {
  const bgPlayer = document.getElementById('bg-music-player');
  if (bgPlayer && bgMusicPlaying) {
    bgPlayer.volume = settings.musicVol;
  }
  document.getElementById('audio-gen-bar').style.display = 'none';
  document.getElementById('audio-status').textContent = '';
  document.getElementById('audio-label').textContent = `Narrator · turn ${toRoman(turnCount)} · done`;
}

// Legacy fallback: if queue endpoint returns unknown, use old single-file polling
function pollAudioLegacy(turnId) {
  document.getElementById('audio-gen-bar').style.display = 'block';
  document.getElementById('audio-gen-fill').style.width = '30%';
  document.getElementById('audio-status').textContent = 'generating...';
  document.getElementById('audio-label').textContent = 'Generating audio';

  if (audioPollTimer) clearInterval(audioPollTimer);
  let pollCount = 0;
  audioPollTimer = setInterval(async () => {
    pollCount++;
    if (pollCount > 180) {
      clearInterval(audioPollTimer);
      document.getElementById('audio-status').textContent = 'timeout';
      document.getElementById('audio-gen-bar').style.display = 'none';
      return;
    }
    try {
      const resp = await fetch(`/api/audio_status?turn_id=${turnId}`);
      const data = await resp.json();
      if (data.status === 'ready') {
        clearInterval(audioPollTimer);
        document.getElementById('audio-gen-bar').style.display = 'none';
        loadAudioLegacy(data.audio_url, data.duration);
      } else if (data.status === 'error') {
        clearInterval(audioPollTimer);
        document.getElementById('audio-gen-bar').style.display = 'none';
        document.getElementById('audio-status').textContent = 'error: ' + (data.error || 'unknown');
      } else if (data.status === 'generating') {
        const pct = data.progress || Math.min(30 + pollCount * 2, 90);
        document.getElementById('audio-gen-fill').style.width = pct + '%';
        if (data.segment_info) {
          document.getElementById('audio-status').textContent = data.segment_info;
        }
      }
    } catch(e) {}
  }, 1000);
}

function loadAudioLegacy(url, duration) {
  const player = document.getElementById('audio-player');
  player.src = url;
  audioDuration = duration;
  document.getElementById('audio-play').disabled = false;
  document.getElementById('audio-label').textContent = `Narrator · turn ${toRoman(turnCount)}`;
  document.getElementById('audio-time').textContent = `0:00 / ${formatTime(duration)}`;
  document.getElementById('audio-status').textContent = '';
  const bgPlayer = document.getElementById('bg-music-player');
  if (bgPlayer && bgMusicPlaying) {
    bgPlayer.volume = settings.musicVol * 0.3;
  }
  player.volume = settings.narrationVol;
  player.play().then(() => {
    isPlaying = true;
    document.getElementById('audio-play').textContent = '⏸';
    startAudioUpdate();
  }).catch(() => {});
  player.onended = () => {
    isPlaying = false;
    document.getElementById('audio-play').textContent = '▶';
    stopAudioUpdate();
    if (bgPlayer && bgMusicPlaying) {
      bgPlayer.volume = settings.musicVol;
    }
  };
}

function toggleAudio() {
  const player = document.getElementById('audio-player');
  if (player.paused) {
    player.play().then(() => { isPlaying = true; document.getElementById('audio-play').textContent = '⏸'; startAudioUpdate(); }).catch(()=>{});
  } else {
    player.pause(); isPlaying = false; document.getElementById('audio-play').textContent = '▶'; stopAudioUpdate();
  }
}

function replayAudio() {
  const player = document.getElementById('audio-player');
  if (!player.src) return;
  player.currentTime = 0;
  player.play().then(() => { isPlaying = true; document.getElementById('audio-play').textContent = '⏸'; startAudioUpdate(); }).catch(()=>{});
}

function startAudioUpdate() {
  if (audioUpdateTimer) clearInterval(audioUpdateTimer);
  let fadeOutStarted = false;
  audioUpdateTimer = setInterval(() => {
    const player = document.getElementById('audio-player');
    if (player.duration) {
      const pct = (player.currentTime / player.duration) * 100;
      document.getElementById('audio-fill').style.width = pct + '%';
      document.getElementById('audio-time').textContent = `${formatTime(player.currentTime)} / ${formatTime(player.duration)}`;
      // v0.8: Fade out in last 100ms for smooth segment transition
      const remaining = player.duration - player.currentTime;
      if (!fadeOutStarted && remaining < 0.1 && remaining > 0) {
        fadeOutStarted = true;
        _fadeOutVolume(player, 0, 80);
      }
    }
    if (player.ended) { isPlaying = false; document.getElementById('audio-play').textContent = '▶'; stopAudioUpdate(); }
  }, 200);
}
function stopAudioUpdate() { if (audioUpdateTimer) { clearInterval(audioUpdateTimer); audioUpdateTimer = null; } }

// Fix 3: seekAudio removed — seek bar is now a non-interactive progress indicator.
// Cross-segment seeking is broken and per Arie's "work fully or be removed" directive,
// we make it display-only for v1. Play/pause and replay still work.
function seekAudio(e) { /* no-op — progress indicator only */ }

// --- Session Zero / Foreword — integrated into the main book area ---
let szActive = false;
let szTurnCount = 0;

async function openSessionZero() {
  const intro = document.getElementById('intro-overlay');
  intro.classList.add('hidden');
  // Show the main app area — the foreword renders in #story-content, not a separate overlay.
  document.getElementById('app').classList.add('show-app');
  szActive = true;
  szTurnCount = 0;
  // Clear story content and show a foreword heading
  const container = document.getElementById('story-content');
  container.innerHTML = '';
  // Add a foreword chapter heading — this IS the first page of the book
  const heading = document.createElement('div');
  heading.className = 'chapter-heading';
  heading.innerHTML = '<div class="chapter-number">Foreword</div>' +
    '<div class="chapter-title">Before the story begins</div>' +
    '<div class="chapter-rule"></div>';
  container.appendChild(heading);
  // Add a model picker inline (small, at the top of the foreword)
  const modelPick = document.createElement('div');
  modelPick.style.cssText = 'text-align:center;margin-bottom:1.5rem;font-size:13px;color:var(--ink-faint);';
  modelPick.innerHTML = '<label>Narrator voice: <select id="sz-model" style="font-size:13px;' +
    'background:var(--bg);border:1px solid var(--rule);border-radius:4px;padding:2px 6px;color:var(--ink-mid);">' +
    '<option value="gemini-3.5-flash-lite">Gemini Flash (free)</option>' +
    '<option value="openai/gpt-oss-120b">GPT-OSS 120B (free)</option>' +
    '<option value="claude-haiku-4-5">Claude Haiku (paid)</option>' +
    '</select></label> &nbsp; ' +
    '<a href="#" onclick="szSkipToGame();return false;" style="color:var(--ink-faint);font-size:12px;">skip to defaults</a>';
  container.appendChild(modelPick);
  await szStart();
}

async function szStart() {
  const modelEl = document.getElementById('sz-model');
  const model = modelEl ? modelEl.value : settings.model;
  szAddTyping();
  try {
    const resp = await fetch('/api/session_zero/start', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({model}),
    });
    const data = await resp.json();
    szRemoveTyping();
    if (data.error) { szAddNarrator(data.error); return; }
    szTurnCount = data.turn || 1;
    szAddNarrator(data.narrative, data.suggestions);
    updateBudget(data.budget);
    // Fix 4: Lock the model picker after the first exchange.
    if (modelEl) modelEl.disabled = true;
    szShowInput();
  } catch(e) { szRemoveTyping(); szAddNarrator('Connection error: ' + e.message); }
}

async function szSendAnswer(answer) {
  if (!szActive) return;
  const input = document.getElementById('sz-input');
  if (!answer) {
    answer = input ? input.value.trim() : '';
    if (!answer) return;
    input.value = '';
  }
  szAddPlayer(answer);
  szHideInput();
  szAddTyping();
  try {
    const resp = await fetch('/api/session_zero/turn', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({answer}),
    });
    const data = await resp.json();
    szRemoveTyping();
    if (data.error) { szAddNarrator('Error: ' + data.error); szShowInput(); return; }
    szTurnCount = data.turn || szTurnCount + 1;
    szAddNarrator(data.narrative, data.suggestions);
    updateBudget(data.budget);
    if (data.done) {
      setTimeout(() => szFinish(), 1500);
    } else {
      szShowInput();
    }
  } catch(e) { szRemoveTyping(); szAddNarrator('Connection error: ' + e.message); szShowInput(); }
}

async function szFinish() {
  if (!szActive) return;
  szActive = false;
  szAddNarrator('Turning the page...');
  szAddTyping();
  try {
    const resp = await fetch('/api/session_zero/finish', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({}),
    });
    const data = await resp.json();
    szRemoveTyping();
    if (data.error) { szAddNarrator('Error starting game: ' + data.error); return; }
    // The foreword is done — the first chapter renders in the same story-content area.
    document.getElementById('app').classList.add('show-left');
    document.getElementById('tab-left').classList.add('active');
    document.getElementById('ctab-left').classList.add('active');
    document.getElementById('model-label').textContent = data.model;
    settings.autoroll = data.auto_roll;
    updateSettingsUI();
    updateState(data.state);
    if (data.segments || data.story) addStoryTurn(data, true);
    if (data.audio_enabled) pollAudio(data.audio_turn_id);
    updateBudget(data.budget);
    fetchChronicle();
    fetchChapters();
    if (settings.music) {
      bgMusicPlaying = true;
      if (data.scene) currentMood = data.scene;
      updateBgMusic();
      document.getElementById('bg-music-player').play().catch(()=>{});
    }
    fetchProviderStatus();
  } catch(e) { szRemoveTyping(); szAddNarrator('Connection error: ' + e.message); }
}

function szSkipToGame() {
  if (!confirm('Skip the foreword and start with default settings?')) return;
  szActive = false;
  startGame({skip: true});
}

function szChangeModel(model) {
  settings.model = model;
}

// Render foreword messages as book-style paragraphs in #story-content
function szAddNarrator(text, suggestions) {
  const container = document.getElementById('story-content');
  const p = document.createElement('p');
  p.className = 'narration';
  p.style.cssText = 'margin-bottom:1.2rem;line-height:1.9;text-align:justify;';
  p.textContent = text;
  container.appendChild(p);
  // Preset answer buttons — only real user answers, not narrator text
  if (suggestions && suggestions.length) {
    const sugDiv = document.createElement('div');
    sugDiv.className = 'sz-presets';
    sugDiv.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px;margin:0.8rem 0 1.2rem;';
    suggestions.forEach(s => {
      const btn = document.createElement('button');
      btn.className = 'sz-preset-btn';
      btn.style.cssText = 'background:var(--bg);border:1px solid var(--rule);border-radius:6px;padding:4px 12px;cursor:pointer;font-size:13px;color:var(--ink-mid);font-family:inherit;transition:all 0.15s;';
      btn.textContent = s;
      btn.onmouseenter = () => { btn.style.borderColor = 'var(--accent)'; btn.style.color = 'var(--ink)'; };
      btn.onmouseleave = () => { btn.style.borderColor = 'var(--rule)'; btn.style.color = 'var(--ink-mid)'; };
      btn.onclick = () => szSendAnswer(s);
      sugDiv.appendChild(btn);
    });
    container.appendChild(sugDiv);
  }
  container.parentElement.scrollTop = container.parentElement.scrollHeight;
}

function szAddPlayer(text) {
  const container = document.getElementById('story-content');
  const p = document.createElement('p');
  p.className = 'dialogue-entry';
  p.style.cssText = 'margin-bottom:1.2rem;margin-left:2rem;font-style:italic;color:var(--ink-mid);';
  p.textContent = '\u201C' + text + '\u201D';
  container.appendChild(p);
  container.parentElement.scrollTop = container.parentElement.scrollHeight;
}

function szAddTyping() {
  const container = document.getElementById('story-content');
  const t = document.createElement('p');
  t.id = 'sz-typing-indicator';
  t.className = 'narration';
  t.style.cssText = 'color:var(--ink-faint);font-style:italic;';
  t.textContent = 'The Narrator is weaving';
  container.appendChild(t);
  container.parentElement.scrollTop = container.parentElement.scrollHeight;
}

function szRemoveTyping() {
  const t = document.getElementById('sz-typing-indicator');
  if (t) t.remove();
}

function szShowInput() {
  // Remove any existing foreword input
  szHideInput();
  const container = document.getElementById('story-content');
  const inputArea = document.createElement('div');
  inputArea.id = 'sz-input-block';
  inputArea.className = 'input-block';
  inputArea.style.cssText = 'margin:1.5rem 0;';
  inputArea.innerHTML = '<input type="text" id="sz-input" placeholder="Your answer..." onkeydown="if(event.key===\'Enter\')szSendAnswer()" autofocus><button onclick="szSendAnswer()">Send</button>';
  container.appendChild(inputArea);
  document.getElementById('sz-input').focus();
  container.parentElement.scrollTop = container.parentElement.scrollHeight;
}

function szHideInput() {
  const existing = document.getElementById('sz-input-block');
  if (existing) existing.remove();
}

// --- Voice assignment screen ---
let voiceCastData = null;

async function openVoiceScreen() {
  const overlay = document.getElementById('voice-overlay');
  overlay.classList.add('active');
  try {
    const resp = await fetch('/api/voice/list', {method: 'POST'});
    const data = await resp.json();
    if (data.error) { console.error('Voice list error:', data.error); return; }
    voiceCastData = data.cast || {};
    renderVoiceEntries(data.cast, data.defaults || {});
  } catch(e) { console.error('Voice screen error:', e); }
}

function renderVoiceEntries(cast, defaults) {
  const container = document.getElementById('voice-entries');
  container.innerHTML = '';
  const keys = Object.keys(cast).filter(k => !k.startsWith('_'));
  keys.forEach(name => {
    const entry = document.createElement('div');
    entry.className = 'voice-entry';
    const isNarrator = name === 'narrator';
    const hint = isNarrator ? 'The storytelling voice for all narration' : 'Voice description for this character';
    entry.innerHTML = `
      <div class="voice-entry-name">${escapeHtml(name)}</div>
      <textarea id="voice-${escapeAttr(name)}" placeholder="Describe the voice...">${escapeHtml(cast[name])}</textarea>
      <div class="voice-hint">${hint}</div>
    `;
    container.appendChild(entry);
  });
  const addSection = document.createElement('div');
  addSection.className = 'voice-entry';
  addSection.style.borderStyle = 'dashed';
  addSection.innerHTML = `
    <div class="voice-entry-name">+ Add new character voice</div>
    <input type="text" id="voice-new-name" placeholder="Character name..." style="width:100%;background:var(--bg);border:1px solid var(--rule);border-radius:6px;padding:8px 10px;color:var(--ink);font-size:14px;font-family:inherit;margin-bottom:6px;outline:none;">
    <textarea id="voice-new-desc" placeholder="Describe the voice..."></textarea>
    <button class="sz-suggestion-btn" style="margin-top:6px;" onclick="addNewVoiceField()">Add</button>
  `;
  container.appendChild(addSection);
}

function addNewVoiceField() {
  const name = document.getElementById('voice-new-name').value.trim();
  const desc = document.getElementById('voice-new-desc').value.trim();
  if (!name || !desc) return;
  const container = document.getElementById('voice-entries');
  const entry = document.createElement('div');
  entry.className = 'voice-entry';
  entry.innerHTML = `
    <div class="voice-entry-name">${escapeHtml(name)}</div>
    <textarea id="voice-${escapeAttr(name)}" placeholder="Describe the voice...">${escapeHtml(desc)}</textarea>
    <div class="voice-hint">Voice description for this character</div>
  `;
  const addSection = container.lastElementChild;
  container.insertBefore(entry, addSection);
  document.getElementById('voice-new-name').value = '';
  document.getElementById('voice-new-desc').value = '';
}

async function closeVoiceScreen(save) {
  if (save && voiceCastData) {
    const keys = Object.keys(voiceCastData).filter(k => !k.startsWith('_'));
    for (const name of keys) {
      const ta = document.getElementById('voice-' + name);
      if (ta && ta.value.trim() !== voiceCastData[name]) {
        await fetch('/api/voice/assign', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({name, voice: ta.value.trim()}),
        });
      }
    }
    document.querySelectorAll('.voice-entry textarea[id^="voice-"]').forEach(ta => {
      const name = ta.id.replace('voice-', '');
      if (!voiceCastData[name] && ta.value.trim()) {
        fetch('/api/voice/assign', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({name, voice: ta.value.trim()}),
        });
      }
    });
  }
  document.getElementById('voice-overlay').classList.remove('active');
}

// Utilities
function escapeHtml(s) { if(!s) return ''; const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
function formatTime(s) { if(!s) return '0:00'; const m=Math.floor(s/60); const sec=Math.floor(s%60); return `${m}:${sec.toString().padStart(2,'0')}`; }
function toRoman(n) { const r=['','I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX']; return r[n] || n.toString(); }

// v0.8: Audio fade helpers for smooth crossfade between segments
function _fadeInVolume(player, targetVol, ms) {
  const steps = 10;
  const stepTime = ms / steps;
  const volStep = targetVol / steps;
  let step = 0;
  const fade = setInterval(() => {
    step++;
    if (step >= steps) {
      player.volume = targetVol;
      clearInterval(fade);
    } else {
      player.volume = volStep * step;
    }
  }, stepTime);
}

function _fadeOutVolume(player, targetVol, ms, callback) {
  const startVol = player.volume;
  const steps = 10;
  const stepTime = ms / steps;
  const volStep = startVol / steps;
  let step = 0;
  const fade = setInterval(() => {
    step++;
    if (step >= steps) {
      player.volume = 0;
      clearInterval(fade);
      if (callback) callback();
    } else {
      player.volume = startVol - (volStep * step);
    }
  }, stepTime);
}
function escapeAttr(s) { return s.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '&quot;').replace(/\n/g, '\\n').replace(/\r/g, '\\r'); }

// Keyboard shortcuts: Enter to send, 1-9 for choices, Esc to close panels
document.addEventListener('keydown', (e) => {
  // Enter to send (when in input field)
  if (e.key === 'Enter' && document.activeElement.tagName === 'INPUT' && document.activeElement.closest('.input-block')) {
    sendAction();
    return;
  }
  // Number keys 1-9 to select choices (only when not typing in an input)
  if (document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
    const num = parseInt(e.key);
    if (num >= 1 && num <= 9) {
      const choices = document.querySelectorAll('.choice-item');
      if (choices[num - 1]) {
        choices[num - 1].click();
        return;
      }
    }
  }
  // Escape to close all panels
  if (e.key === 'Escape') {
    document.getElementById('app').classList.remove('show-settings');
    document.getElementById('tab-settings').classList.remove('active');
    document.getElementById('ctab-settings').classList.remove('active');
  }
});
