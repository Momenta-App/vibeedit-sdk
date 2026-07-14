---
name: vibeedit-effects-punctuation
description: Apply fan-edit effects as precise punctuation: beat flashes, object-only flashes, shakes, zooms, glitches, masks, curtain reveals, color switches, and transitions.
---

# VibeEdit Effects Punctuation

Use this skill when deciding what effects to add to a fan edit and when those effects should happen.

## Core Rule

Effects are punctuation, not decoration. Every flash, shake, zoom, glitch, blur, mask, and color switch needs a beat, lyric, quote, motion, or story reason.

## Effect Timing

- Full-frame flash: 1 to 3 frames on a major impact only.
- Object-only flash: minor beat, percussion run, or repeated note pattern.
- Shake: short impulse on impact; do not blur the subject for the whole shot.
- Zoom punch: beat hit, face realization, weapon/action impact, or lyric stress.
- Slow zoom: pressure, grief, dread, confidence, or quote emphasis.
- Chromatic/glitch: interruption, villain energy, digital/game/anime intensity, or mental fracture.
- Blur/radial/lens warp: transition or speed, not permanent softness.
- Glow/outline: subject separation or heroic/villain emphasis.

## Object-Only Flash Recipe

When minor notes happen in a row, do not always cut clips. Use segmentation:

1. Find a shot with multiple clear objects or people.
2. Use SAM 2.1, SAM 3.1, Apple Vision masks, or local segmentation to isolate each object.
3. Keep the base video unchanged.
4. On each minor beat, flash only one masked object.
5. Use white/red exposure, edge glow, or short brightness boost on the masked layer.
6. Return immediately to normal so the edit remains readable.

## Curtain And Cutout Intro

For character-focused intros:

- Start from black with a foreground cutout of the character.
- Open a horizontal curtain from the center: bars move up/down to reveal video.
- Optionally place rapidly cycling themed images or frames behind the curtain.
- Keep the cutout in front while the background reveal begins.
- Move into full video when the song starts or the first major beat lands.

For a simple reverse-crush / curtain reveal where the screen starts black and the source video opens from the center, route to `vibeedit-reverse-curtain-reveal`. Use that skill instead of reimplementing the bars when the request needs horizontal or vertical black-bar opening, adjustable speed, easing, and production-library output.

For the character-cutout version of that idea, route to `vibeedit-reverse-curtain-subject-reveal`. Use it when the request needs a masked person/character moment, slowed cutout footage, subject-over-curtain or subject-under-curtain layering, or a random-frame-stutter background behind the cutout.

## Color-Switch Effect

Use black-and-white or low-saturation at the beginning when the edit is restrained. Switch to color on intensity, drop, transformation, quote answer, or character decision.

## QA Checklist

- Every effect has a timestamp and purpose.
- No effect hides the key face, body, or action.
- Minor beats use smaller effects than major beats.
- Full-screen flashes are rare.
- Effect intensity rises with story intensity.
