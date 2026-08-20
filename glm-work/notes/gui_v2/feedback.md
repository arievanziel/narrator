# GUI v2 — structured feedback

**Mockups:** `glm-work/notes/gui_v2/sepia.html`, `ink.html`, `midnight.html`
**Index page:** `glm-work/notes/gui_v2/index.html` (links to all three)
**Design references:** Kindle vanishing chrome, Readable theme (cream paper + Crimson Pro), Parchment warm-paper aesthetic, e-ink/calm-tech design philosophy

**How to use:** open each mockup, click around (choices + free text both work), then write your feedback on `>` lines. You can compare all three or just react to the one that resonates.

---

## Which direction?

1. Which mockup feels closest to what you want?
   (Sepia / Ink / Midnight / none of them / a mix — say which parts from which)

> ink, by far the best
> but the audio indicator i like better as a line, like in the other examples, better a line than a dot, and it could even be more inside the view instead of the bottom edge. maybe combined with a pulsing dot or something as indicator that the sound is playing.
> this whole app is very much about audio, so audio elements and visual indicators of audio may be getting more attention
> and in ink there is no settings button visible, but this is an easy fix

2. Light or dark? (Sepia and Ink are light, Midnight is dark. If you want a dark version of the Sepia aesthetic, or a light version of Midnight, say so.)

> light is great in ink, but i'd like to see a dark version in the same simple style

---

## Sepia — Warm Paper

Cream background, EB Garamond serif, burnt sienna accents, justified text with drop caps, thin audio line at bottom edge.

3. Does the drop cap work, or is it too "classic book" for an interactive app?

> yeah, too dramatic with this amount of repeating paragraphs. Perhaps keep the idea for chapter titles, perhaps with a fully illustrated drop cap in later versions.

4. Justified text — good for reading, or do you prefer left-aligned (ragged right)?

> no strong preference, but readibility will be key

5. The choice style (text with a left border that slides in on hover) — too subtle, or right?

> nice and simple, but could be cleaner and simpler

6. The audio indicator (thin sienna line at the very bottom) — is it visible enough?

> nice, but could get more attention

---

## Ink — Quiet Monochrome

> absolute winner gui style

Soft gray, Spectral serif at light weight, no accent color, Roman numeral turn markers, narrator has no label, breathing audio dot.

7. The "no label for narrator" decision — narrator is the default voice, so it doesn't need a label. Does this work, or is it confusing without it?

> yes, great idea. No labels where they are not needed.

8. No accent color at all — calming, or too flat / boring?

> perfection, nice and simple

9. The breathing audio dot (bottom-right corner) — too subtle? Would you miss it?

> nice idea, but combined with a line and more visible in center screen would be better. breathing animation is a great idea to show 'audio is playing' but it should be animated only when playing audio, so UX design will be key in this.

10. Roman numeral turn markers (III, IV, V…) — nice touch, or pretentious?

> great choice, roman nummerals or normal numbering or letters are all great options, and no label 'turn' is a great idea. less labels the better.

---

## Midnight — Lamplight

Warm dark, Cormorant Garamond, amber accents with glow, lamplight radial gradient, flickering ember loading indicator, glowing audio bar.

11. The lamplight glow effect (radial gradient from top) — atmospheric, or distracting?

> nice touch, could be used in dark version of ink theme

12. The flickering ember dots while generating — nice, or too much?

> nice, but could be spaced wider and more subtle, more like fireflies or tiny glittering specks

13. Choice cards with amber glow on hover — feels right for the mood, or too "gamey"?

> too dramatic, simpler would be better

14. Is this too dark for extended play sessions? (Eye strain consideration.)

> no, not at all, but keep in mind that for dark themes the contrast between text and background is most important, not too much, not too little. Perhaps a contrast slider in settings would be a great extra addition in the future when we start UX design.

---

## Shared elements (all three)

15. Auto-hiding chrome (tap top of screen to show HP/settings) — good for immersion, or annoying because you forget it's there?

> good idea, but keep it simple and useful. I like that there is no visible hint or 'handle' you need to know where it is. Will need a lot of UX testing though.

16. The "you said: [your action]" line between turns — useful, or noise?

> nice, but could be more subtle, maybe just a small icon or indicator or just "you: [text/action]""
> could you also put some try-out examples of other 'action' elements like dice rolls, attacks, items gained or lost, or things like that, keep it very very subtle, but try out lot's of different elements or indicators, so i can see what works or not.

17. Three choices + free text input — right number? (The current serve_dm_web.py has 2-3 suggestions from the DM brain.)

> yes, although in final app version the UX engine will naturally decide the amount of suggestions, but we will always keep a free text input. I like it very subtle and simple. feel free to simplify even further if you have ideas.
> send button could be just a subtly animated icon, no need for the text 'send'

18. Is the book-like typography (serif, large size, generous leading) right for this app, or would you prefer a more "app-like" sans-serif?

> yes, great like this. Perhaps later we will add settings for user to adjust the typography, so feel free to show me some more experiments in next versions to compare.

---

## What's missing

19. Anything you expected to see that isn't in any of the three?

> the screen width could be adjustable by the user, or adjust automatically on screen size. Although i DO very much like the small page width feel currently, so maybe it's ok like this. We can experiment a bit with wider page size, but it should always feel like a 'modern' book.

20. Any of the following you'd want visible at all times (not hidden behind tap)?
    - HP / health
    - Inventory
    - Dice roller
    - Character sheet
    - Map / location
    - Audio controls (play/pause/skip)
    - Session save/load

> maybe only audio controls always visible, but i think anything should be easily accessible but hidden as a default

---

## Priority for next iteration

Pick top 2-3:
- [x] Pick one style and refine it further
- [ ] Mix elements from multiple styles (specify which)
- [ ] Add always-visible game state (HP, inventory)
- [x] Add a dice roller > keep it simple, but intuitive, probably we will make it fully automated and not as an interactive element, but still an animated version would be great to try out how it would work as interactive UX. But keep it visually very simple.
- [ ] Add session save/load UI
- [x] Add voice/audio settings panel
- [x low prio for now] Make it responsive for phone testing
- [ ] Other:

> see my prompt:

> great work! 2 ink is by far my favourite. Can you extend it with extra panels for audio control, the top status bar with more information, a side panel with things like inventory, npc's, quest log, just some invented things for now to fill the mockup. If you have other ideas to put more gui elements that might inspire other ux later, feel free to add some mockup elements.
> Also add a settings panel with different mock settings that you can change.

> And create a dark screen version in the same style as 2 ink.
