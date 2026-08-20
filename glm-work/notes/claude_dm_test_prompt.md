# Claude DM Brain Test — Manual Run via Devin

## How to use this

1. Start a new Devin session (or any Claude chat).
2. Select the model you want to test (Opus, Sonnet, or Fable).
3. Paste the **System Prompt** below as your first message, then say "Acknowledge these rules and wait for my first action."
4. Then send the **Opening Action** and play through the 10 scripted turns.
5. Score each turn using the rubric at the bottom.
6. Compare results with the Groq tests in `dm_test_results_summary.md`.

## System Prompt (paste this)

```
You are an expert D&D 5e Dungeon Master running a solo campaign for one player.

## RULES CONTRACT (follow strictly)

1. ROLLS BEFORE OUTCOMES. Never narrate a combat result before the dice are rolled.
   WRONG: "Your sword strikes true, dealing 8 damage!"
   CORRECT: Ask the player to roll, wait for the number, THEN narrate the outcome.
   If the player has not provided a roll for an action that needs one, ask for it.

2. STATE IS AUTHORITATIVE. The game state provided in each turn is the source of
   truth. Do not contradict it. Do not invent items, HP, conditions, or NPCs not
   listed in the state. If the player claims something not in the state, rule
   based on what is actually there.

3. RESPONSE FORMAT. Every response MUST contain exactly 4 sections, each on a new
   line with the section tag in brackets:

   [NARRATIVE]
   The story beat — 2 to 4 paragraphs. Vivid but not purple prose. Show the
   scene, NPC reactions, and consequences of the player's action.

   [MECHANICS]
   Machine-readable tags only, one per line. Use ONLY these tags:
     HP_CHANGE:<signed_int>          (negative = damage to PC, positive = healing)
     ENEMY_HP:<name>,<current>/<max>  (update an enemy's HP)
     ENEMY_DEAD:<name>                (mark an enemy as dead)
     ROLL_REQUEST:<dice> for <skill>  (ask the player to roll — when you need a roll)
     ITEM_USED:<name>                 (consume an item from inventory)
     ITEM_GAINED:<name>               (add an item to inventory)
     SPELL_SLOT_USED:<level>          (consume a spell slot)
     CONDITION:<target>,<condition>   (apply a condition: poisoned, stunned, etc.)
     NO_MECHANICS                     (use when no mechanical change this turn)

   [SUGGESTIONS]
   2-3 player options for the next action, each on its own line, tagged:
     roll:true — this option requires a dice roll before it can resolve
     roll:false — this option is narrative/social, no roll needed
   Format: "- <option text> [roll:true]" or "- <option text> [roll:false]"

   [CHRONICLE]
   One-line campaign log entry. Only include on significant beats (combat start,
   enemy death, item gained, scene change). Use "NO_ENTRY" for uneventful turns.

4. ENCOUNTER BALANCE. This is solo play — no party backup. Level 1 enemies: max
   7 HP, no multiattack. A single bad roll should not end the run.

5. BE THE DM, NOT A PLAYER. You control NPCs, monsters, and the world. The player
   controls only their character. Never act for the player.

6. WARLOCK SPELL SLOTS recharge on a short rest, not a long rest. (Common AI error.)
```

## Initial Game State (paste this with your first action)

```
CURRENT GAME STATE (authoritative — do not contradict):
  PC: Kael, Level 1 Fighter | HP: 12/12 | AC: 16
  STR 16 (+3) | DEX 12 (+1) | CON 14 | INT 10 | WIS 10 | CHA 10
  Inventory: Health Potion, Torch, Waterskin, 50 feet of rope
  Equipment: longsword (1d8+3 slashing), shield, chain mail
  Enemies:
    Goblin Scout (7/7 HP, AC 15)
    Goblin Raider (7/7 HP, AC 15)
  Scene: The Rusty Anchor tavern | Light: dim (candlelit) | Time: evening
  Previous turn mechanics: (start of encounter)
```

## 10 Scripted Turns

Send these one at a time. After each DM response, note:
- Did all 4 sections appear? (NARRATIVE, MECHANICS, SUGGESTIONS, CHRONICLE)
- Did the DM respect roll-before-outcome?
- Did the DM contradict the state?
- How was the prose quality? (1-5)
- How was the state tracking? (1-5)
- How long did the response take?

### Turn 1
```
PLAYER ACTION:
I push open the tavern door and step inside, hand on my sword hilt.
```

### Turn 2
```
PLAYER ACTION:
I draw my longsword and attack the nearest goblin. I rolled a 14 on my attack roll.
```

### Turn 3
```
PLAYER ACTION:
I use my bonus action to look around for other threats. I rolled a 12 for Perception.
```

### Turn 4
```
PLAYER ACTION:
The goblin scout swings at me — go ahead and roll for it, then I'll respond.
```

### Turn 5
```
PLAYER ACTION:
I attack the goblin raider. I rolled a 19 on my attack roll.
```

### Turn 6
```
PLAYER ACTION:
I roll damage for my longsword: 1d8+3 = I got a 5, so 8 damage total.
```

### Turn 7
```
PLAYER ACTION:
I'm hurt. I drink my Health Potion as my action this turn.
```

### Turn 8
```
PLAYER ACTION:
I try to intimidate the surviving goblin into surrendering. I rolled a 10 on Intimidation.
```

### Turn 9
```
PLAYER ACTION:
If the goblin surrenders, I tie it up with my rope and question it about why it attacked.
```

### Turn 10
```
PLAYER ACTION:
I search the bodies of the dead goblins for anything useful.
```

## Scoring Rubric

After all 10 turns, score the model on each dimension (1-5):

| Dimension | 1 (Poor) | 3 (OK) | 5 (Excellent) |
|---|---|---|---|
| Format adherence | Missing sections on most turns | Missing sections occasionally | All 4 sections every turn |
| Roll-before-outcome | Narrates damage before rolls | Sometimes jumps ahead | Always waits for rolls |
| State consistency | Contradicts state frequently | Minor inconsistencies | Never contradicts state |
| Narrative quality | Flat, repetitive, or broken | Serviceable prose | Vivid, immersive, varied |
| DM judgment | Bad rules calls, unfair encounters | Mostly correct, some errors | Expert rulings, fair balance |
| Speed | >30s per turn | 10-30s per turn | <10s per turn |
| Worldbuilding | No hooks, no NPC personality | Some hooks | Rich hooks, living world |

## Models to compare

| Model | Where | Notes |
|---|---|---|
| Claude Opus 4 | Devin model selector | Frontier quality, expensive |
| Claude Sonnet 4 | Devin model selector | Strong, cheaper |
| Claude Fable | Devin model selector | If available |
| GPT-OSS 120B | Groq free tier | Already tested — baseline |
| GPT-OSS 20B | Groq free tier | Smaller, could run locally |
| Qwen3.6-27B | Groq free tier | Already tested |

Record results in `dm_test_results_summary.md`.
