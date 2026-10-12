# project.json reference

`init_project.py` writes this file in the project folder. It holds the person's choices and the sources; tuned
numbers stay in the scripts (`vcore.py`). Edit it with the person's answers; every script reads it on start and
refuses (exit 2) when it isn't valid JSON or a source file is missing.

Keys you leave out take the defaults below. Nested settings merge, so `"captions": {"highlight": "#00C2A8"}`
keeps the default font and size.

```json
{
  "version": 1,
  "sources": {
    "A": {"file": "take1.mp4", "label": "Take A", "display_size": [1080, 1920], "duration_s": 412.3, "fps": 30.0,
          "audio": {"sample_rate": 48000, "channels": 2}}
  },
  "language": "en",
  "output_dir": "edits",
  "name_pill": {"text": "", "title": ""},
  "captions": {"font": "Inter", "size": 100, "highlight": "#FFD84D"},
  "platforms": [],
  "corrections": [],
  "casing": {},
  "phrases": []
}
```

| Key | Meaning | Who sets it |
|---|---|---|
| `sources` | Id (short letters/digits) → recording. `file` is absolute, or relative to the project folder; the other fields are probed facts used to skip re-probing. Don't move the project folder if paths are relative. | `init_project.py` |
| `language` | Transcription language code. English is the tuned and tested one; others run but number words are only expanded for English. | Intake |
| `output_dir` | Where finished videos go (`<output_dir>/shorts`, `/long`). Relative to the project folder. | Default |
| `name_pill` | On-screen name for the first seconds. Empty `text` = none. Ask exactly how it should read; a spec's `lower_third` overrides it per video. | Intake |
| `captions.font` | Caption font family. Its ExtraBold file must be in the toolkit fonts folder. | Intake (rarely) |
| `captions.size` | Caption text size in px at 1080 wide. Mouth clearance scales with it. | Intake (rarely) |
| `captions.highlight` | Colour of the word being spoken, `#RRGGBB`. | Intake |
| `platforms` | Where the series will post, for planning and copy (e.g. `["linkedin", "instagram"]`). | Intake |
| `corrections` | Evidence-backed word fixes: `{"src", "t", "old", "new", "evidence"}`. `t` is within 1.5 s of the aligned word's start; `new` may be several words, or `""` to delete a word the transcriber invented. Evidence is required. | `video-audio` step 5 |
| `casing` | Lowercase word → caption spelling, e.g. `{"acme": "ACME"}`. "I" forms are built in. | `video-audio` step 6, confirmed with the person |
| `phrases` | Two consecutive words shown differently: `["word1", "word2", "Shown1", "Shown2"]`. | Same |
