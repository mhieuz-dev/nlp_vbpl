# H2N LAW visual assets

## Current 360° background

- `library-panorama.png`: 1774 × 887 (2:1) equirectangular image generated with
  the built-in image-generation tool, using the user's `back_ground.jpg` as a
  visual reference. A second generation corrected the left/right edge zones.
  The original user file is unchanged. The unseen surroundings are AI-created,
  not recovered photographic evidence of the original room.
- `../scene.js` uses self-hosted **Pannellum 2.5.6** from
  https://github.com/mpetroff/pannellum (MIT). Vendor files and license are under
  `../vendor/pannellum/`. No PanoDreamer code or model is installed.
- This is continuous, full 360° panoramic viewing from a fixed position, not
  free-roaming geometry or a model of each object. Image synthesis may leave
  perspective or seam imperfections.
- Drag empty workspace with the primary mouse button to look around; yaw wraps
  across ±180° with no stopping point. Use the angle slider on mobile or with a
  keyboard. Chat text and controls never initiate a drag. `Đặt lại góc` restores
  the initial view; `Tự xoay 360°` toggles ambient rotation (not manual controls).
- Automatic rotation stops while typing, when hidden, or under reduced-motion
  settings. Manual rotation stays available under reduced motion, responding
  immediately to user actions. If WebGL or the panorama fails, the original
  static photo remains behind a fully usable chat interface.
- [Generation prompts](panorama-prompts.md) record both built-in tool calls.

## Retained source assets

- `background.jpg`: unchanged copy of user-supplied `back_ground.jpg`, used as
  loading / static fallback.
- The prior 2.5D depth map is not tracked here: the panorama renderer replaced
  it and nothing in `web/` reads it, so neither the map nor its generator was
  ever committed.
- `ve-vietnam-*.ttf`: self-hosted Be Vietnam Pro from Google Fonts, SIL OFL;
  see `FONT-LICENSE.txt`.

The product name is H2N LAW. Existing `ng-*`, `verdict-motion`, and internal
`LuatAI` identifiers remain stable to preserve history and preferences.
