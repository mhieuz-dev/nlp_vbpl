# Frontend smoke test

Start a static server from the repository root:

```sh
python3 -m http.server 8765 --directory web
```

Run with Node, Puppeteer Core and Chrome available:

```sh
PUPPETEER_PATH=/absolute/path/to/puppeteer-core node tests/browser/smoke.cjs
```

If Puppeteer Core is resolvable normally, omit `PUPPETEER_PATH`. Override
`CHROME_PATH` and `TEST_URL` as needed. Screenshots go to `/tmp/verdict-*.png`.
API responses are explicitly simulated: this verifies rendering and interaction,
not legal answer quality or availability of the generation provider.

Covers multi-turn request context, history persistence and filtering, citations,
recoverable failures, suggested question drafts, keyboard submission, mobile
layout/drawer, motion persistence, reduced motion and actual WebGL initialization.

360° viewer checks (0°, 90°, 180°, 270°, 360°, crossing the back seam with a
mouse drag, chat input isolation, reset, and mobile angle slider):

```sh
PUPPETEER_PATH=/absolute/path/to/puppeteer-core node tests/browser/panorama.cjs
```

The panorama test defaults to `http://127.0.0.1:8000`; override `TEST_URL` when
using the static preview. The smoke test now expects the `panorama-360` renderer.
