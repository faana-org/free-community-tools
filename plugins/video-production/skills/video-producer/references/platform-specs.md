# Platform specs for talking-head video

API limits are from the Zernio API documentation (https://docs.zernio.com/llms-full.txt, read September 2026).
Platforms change limits: re-check the Zernio platform pages before relying on a number.

## Delivery formats

| Platform | Short | Long cut | Hard limits through the API |
|---|---|---|---|
| LinkedIn | 9:16, 1080×1920 | 4:5, 1080×1350 (fills the feed on desktop and mobile) | 1 video per post · MP4/MOV/AVI · ≤5 GB · 3 s–10 min personal (30 min company page) · aspect 1:2.4–2.4:1 · 10–60 fps |
| Instagram | Reel 9:16, 1080×1920 | none: a single video always publishes as a Reel, ≤90 s | Reel 3–90 s · ≤300 MB · H.264 · 30 fps · caption 2,200 characters |
| TikTok | 9:16, 1080×1920 | 9:16 up to 10 min | 3 s–10 min · ≤4 GB · MP4/MOV/WebM · H.264 · caption 2,200 characters |
| YouTube Shorts | 9:16, ≤3 min | n/a | classified as a Short automatically when ≤3 min and vertical; no custom thumbnail through the API |
| YouTube long-form | n/a | 16:9 recommended (not built) | title ≤100 characters, description ≤5,000 |

The master encode (H.264 High, 30 fps constant, yuv420p, AAC 48 kHz, `+faststart`, metadata stripped, CRF 17)
satisfies every platform above.

## Format decisions from vertical phone footage

- **9:16:** native crop with face-aware framing and a 1.10× base zoom for stabilisation headroom.
- **4:5:** cropped from the vertical source; loses only sky and torso. Captions sit lower (80% of height).
- **16:9:** a real design decision, not built. A plain crop of vertical footage is extreme. Options to discuss:
  a blurred fill behind a centred vertical panel, a side panel carrying captions, or posting ≤3 min vertical as
  a Short instead.
- **Instagram and a long cut over 90 s:** a two-part Reel split with a cliffhanger cut, or shorts only there.

## Caption placement and platform UI

Verified placement: 9:16 caption centre at y 1330 of 1920 (69%); 4:5 at y 1080 of 1350 (80%); name pill 150 px
above the caption line.

Reels, TikTok and Shorts overlay controls along the bottom (caption text, audio label) and the right (like,
comment, share). Exact safe zones change with app versions and aren't documented by Zernio.
- **Conservative rule:** keep text between about 15% and 72% of frame height and at least 12% in from the right.
- The built 9:16 placement puts the caption's bottom edge at about 72% of height, inside that zone. Confirm
  with a real upload before a platform's first batch; a TikTok draft or a private YouTube upload is a safe check.

## Copy constraints

| Platform | Before the fold | Limit | Links | Notes |
|---|---|---|---|---|
| LinkedIn | first ~2 lines | 3,000 | put links in the first comment (per Zernio's docs, LinkedIn suppresses posts with a URL in the text) | near-duplicate text is rejected, even weeks later; published text can be edited |
| Instagram | first 125 characters | 2,200 | not clickable; first comment or bio | hashtags go in the caption; no edit through the API |
| TikTok | short | 2,200 | none | no edit after publishing; API moderation is stricter than the app |
| YouTube | title + first description lines | title 100 / description 5,000 | description is fine | without a title, the first line of the text becomes the title |

Mentions (`@Name`) sent through an API usually arrive as plain text, not a tag. Adjust per platform and show
the change in the approval preview.

## Posting velocity (Zernio)

- 25 posts per account per hour.
- Daily: Instagram 100 per rolling 24 h; TikTok 15 videos on Business connections; 50 for other platforms.
- The same content to the same account within 24 h is rejected as a duplicate.
