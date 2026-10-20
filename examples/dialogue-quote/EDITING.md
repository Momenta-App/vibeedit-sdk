# Caption / quote starting point

The clean example generates a color-motion stand-in and a sine tone to demonstrate layout and exact editable bindings. Its labels are synthetic and are not spoken dialogue or measured ASR output. Render that fixture with `python render.py` after preparing the browser capability.

For real editing, initialize a fresh copy using your video and source-time words:

```sh
python render.py --video "user clip.mp4" --words "reviewed words.json"
```

The word JSON is `{ "words": [{ "id": "word-0", "text": "Keep", "startUs": 100000, "endUs": 700000 }] }`. IDs are stable and times are integer microseconds in normalized original video time, not unadjusted audio milliseconds. Retain the audio-origin offset when importing service evidence; do not invent speaker/person ownership. Your source file is copied by exact SHA-256 and its native clock census remains in the project.

Initialization creates `project.vibeedit.json`, a source-bound immutable local word baseline and word-by-word CompositionSpec layers with `metadata.reviewWord`. Open word review with the actual source/baseline IDs returned by `vibeedit project inspect`. Make corrections through the shared project revision service, then `project apply-review --domain words` with the same source/baseline and current revision. Render the returned composition. Calling this example again honors the project's current revision and does not replace approved words or source media.

For an actual quote edit, select an understandable sentence, preserve its original audio and breath, then choose motivated cutaways rather than treating a layout fixture as an editorial decision. For talking heads, place captions where they remain readable and clear of the actual face. Inspect the rendered opening, word timing, line length, audio balance and end; retain the user's revision. No model pass or human signoff is claimed by a successful template render.
