# User-Calibrated Micro SFX Families

Use this reference when selecting among the bundled `micro_01`-`micro_50` files. These labels come from human review plus source-video timestamp/frame evidence and should take precedence over broad catalog tags when the task asks for a specific feel.

Source-video analysis artifacts live at:

- `tmp/micro-sfx-source-analysis/source/kouspure_7632344637574761749.mp4`
- `tmp/micro-sfx-source-analysis/frames/`
- `tmp/micro-sfx-source-analysis/contact-sheets/`
- `tmp/micro-sfx-source-analysis/family-review/`
- `tmp/micro-sfx-source-analysis/analysis_report.md`
- `tmp/micro-sfx-source-analysis/source_timeline_by_family.csv`

## Families

### kinetic-dial-selection

Files: `micro_01`-`micro_18`, `micro_40`.

Use for cursor hover/selection without a hard click: physical dial detents, quickly moving over selectable objects, rapidly changing images/effects, scrolling through options, or adding tactile SFX to motion itself. These often read best as a chain of small clicks rather than one isolated click.

Source evidence: early logo/pill assembly and state-change motion, plus a later tiny text transition for `micro_40`.

### soft-kinetic-dial-selection

Files: `micro_38`, `micro_39`, `micro_41`-`micro_50`.

Use as the lighter, softer version of `kinetic-dial-selection`: gentle hover feedback, subtle outro/logo/text steps, small UI passovers, and background kinetic detail where a hard click would feel too intentional.

Source evidence: small word/logo outro reveals and soft Spotify-logo build.

### iphone-typing-character

Files: `micro_23`-`micro_25`.

Use for subtle character-level type-on, iPhone-like typing clicks, small word appearances, or individual text glyphs showing up. These are close to the kinetic family but should be preferred when the visual event is text becoming readable.

Source evidence: headline/paragraph text reveal frames.

### deep-thud-stop-heavy

Files: `micro_18`, `micro_26`, `micro_27`.

Use for heavier stops, endings, final text/item punctuation, and motion-graphic objects settling. These are still in the same micro UI family, but they should land at the end of a move rather than run continuously during browsing.

Source evidence: pill stop/landing and heavier text-block settle frames.

### carousel-scroll-deep

Files: `micro_28`-`micro_36`.

Use for carousel/card/list browsing: swiping through cards, images, effects, or option rows. These have more body than tiny typing ticks and fit continuous selection motion.

Source evidence: list/carousel scroll, option rows moving, and pill carousel selection.

### triple-confirm

Files: `micro_37`.

Use for a three-part confirmation, short three-beat flourish, quick text flourish, lock-in, or affirmative selected-state feedback.

Source evidence: selected pill confirmation moment.

### kinetic-motion-tail-bridge

Files: `micro_19`-`micro_22`.

Use as bridge sounds between rapid selection clicks and object arrivals: small motion tails, profile/object convergence, connector-like movement, or short avatar/profile assembly motion.

Source evidence: avatar/profile objects entering and settling.

## Selection Rule

When the visual target is known, choose by family first, then by exact file:

- Rapid selection/motion chain: start with `kinetic-dial-selection`.
- Softer selection or outro detail: use `soft-kinetic-dial-selection`.
- Character typing/reveal: use `iphone-typing-character`.
- End/landing/heavy stop: use `deep-thud-stop-heavy`.
- Carousel/list/object browsing: use `carousel-scroll-deep`.
- Affirming three-beat lock: use `triple-confirm`.
- Profile/object convergence or short transition tail: use `kinetic-motion-tail-bridge`.

Only fall back to generic `click`, `tap`, `tick`, `pop`, `hit`, or `whoosh` labels when no source-calibrated family matches the visual action.
