const puppeteer = require(process.env.PUPPETEER_PATH || "puppeteer-core");
const assert = require("node:assert/strict");
(async () => {
  const b = await puppeteer.launch({
    executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome",
    args: ["--no-sandbox", "--enable-unsafe-swiftshader"],
  });
  try {
    const p = await b.newPage();
    const errors = [];
    p.on("pageerror", (e) => errors.push(e.message));
    await p.setViewport({ width: 1440, height: 900 });
    await p.evaluateOnNewDocument(() =>
      localStorage.setItem("ng-mode", "dark"),
    );
    await p.goto(process.env.TEST_URL || "http://127.0.0.1:8000");
    await p.waitForFunction(
      () =>
        document.querySelector(".scene").dataset.renderer === "panorama-360",
    );
    await new Promise((r) => setTimeout(r, 500));
    console.log("panorama loaded");
    const angle = async (n) => {
      await p.$eval(
        "#panorama-angle",
        (e, n) => {
          e.value = n;
          e.dispatchEvent(new Event("input", { bubbles: true }));
        },
        n,
      );
      await new Promise((r) => setTimeout(r, 120));
    };
    for (const n of [0, 90, 180, 270, 360]) {
      await angle(n);
      await p.screenshot({ path: "/tmp/h2n-pano-" + n + ".png" });
      assert(
        Math.abs(
          Number(await p.$eval(".scene", (e) => e.dataset.yaw)) -
            (((n + 180) % 360) - 180),
        ) < 1,
      );
    }
    await angle(170);
    await p.mouse.move(1370, 380);
    await p.mouse.down();
    await p.mouse.move(600, 380, { steps: 20 });
    await p.mouse.up();
    assert(Number(await p.$eval(".scene", (e) => e.dataset.yaw)) < 0);
    await p.type("#q-input", "Vẫn gõ khi xoay 360");
    await p.click("#q-input");
    await p.mouse.down();
    assert.notEqual(
      await p.$eval(".workspace", (e) => e.dataset.dragging),
      "true",
    );
    await p.mouse.up();
    await p.click("#scene-reset");
    assert(Math.abs(Number(await p.$eval(".scene", (e) => e.dataset.yaw))) < 2);
    await p.setViewport({ width: 390, height: 844 });
    await p.reload();
    await p.waitForFunction(
      () =>
        document.querySelector(".scene").dataset.renderer === "panorama-360",
    );
    await new Promise((resolve) => setTimeout(resolve, 800));
    await angle(180);
    assert.equal(
      await p.evaluate(() => document.documentElement.scrollWidth > innerWidth),
      false,
    );
    await p.screenshot({ path: "/tmp/h2n-pano-mobile.png" });
    await p.emulateMediaFeatures([
      { name: "prefers-reduced-motion", value: "reduce" },
    ]);
    await p.reload();
    await p.waitForFunction(
      () =>
        document.querySelector(".scene").dataset.renderer === "panorama-360",
    );
    assert.equal(
      await p.$eval("#motion-toggle", (e) => e.getAttribute("aria-pressed")),
      "false",
    );
    await angle(270);
    assert.equal(Number(await p.$eval(".scene", (e) => e.dataset.yaw)), -90);
    await p.setViewport({ width: 320, height: 568 });
    assert.equal(
      await p.evaluate(() => document.documentElement.scrollWidth > innerWidth),
      false,
    );
    const offline = await b.newPage();
    await offline.setRequestInterception(true);
    offline.on("request", (request) =>
      request.url().includes("library-panorama.png")
        ? request.abort()
        : request.continue(),
    );
    await offline.goto(process.env.TEST_URL || "http://127.0.0.1:8000");
    await offline.waitForFunction(
      () => document.querySelector(".scene").dataset.renderer === "static",
    );
    await offline.type(
      "#q-input",
      "Vẫn dùng chat khi ảnh toàn cảnh không tải được",
    );
    assert.match(
      await offline.$eval("#q-input", (e) => e.value),
      /Vẫn dùng chat/,
    );
    assert(await offline.$eval("#panorama-angle", (e) => e.disabled));
    await offline.close();
    assert.deepEqual(errors, []);
    console.log(
      "PASS 0/90/180/270/360, drag across seam, text editing, reset and mobile slider.",
    );
  } finally {
    await b.close();
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
