const puppeteer = require(process.env.PUPPETEER_PATH || "puppeteer-core");
const assert = require("node:assert/strict");
(async () => {
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome",
    headless: true,
    args: [
      "--no-sandbox",
      "--disable-dev-shm-usage",
      "--enable-unsafe-swiftshader",
    ],
  });
  const page = await browser.newPage(),
    errors = [],
    requests = [];
  let failure = false,
    rateLimited = 0;
  page.on("pageerror", (e) => errors.push(e.message));
  await page.setViewport({ width: 1440, height: 900 });
  await page.evaluateOnNewDocument(() =>
    localStorage.setItem("ng-mode", "dark"),
  );
  await page.setRequestInterception(true);
  const payload = {
    answer: "**Nội dung kiểm thử giao diện.** Căn cứ tham khảo [1].",
    answered: true,
    citations: [1],
    chunks: [
      {
        n: 1,
        article: 1,
        title: "Văn bản kiểm thử",
        text: "Đây là dữ liệu giả lập để kiểm tra trích dẫn, không phải nội dung tư vấn pháp luật.",
        score: 0.9,
      },
    ],
    timings: { retrieve_ms: 100, generate_ms: 200 },
    model: "Mô hình kiểm thử",
  };
  page.on("request", (r) => {
    if (r.url().endsWith("/api/corpus"))
      return r.respond({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          chunks: 49063,
          documents: 624,
          last_refreshed: "2026-09-19",
          newest_issue_date: "2026-09-01",
        }),
      });
    if (r.url().endsWith("/api/ask/stream")) {
      requests.push(JSON.parse(r.postData()));
      if (rateLimited > 0) {
        rateLimited--;
        return r.respond({
          status: 200,
          contentType: "text/event-stream",
          body:
            'event: error\ndata: {"error":"Mô hình đang nhận quá nhiều câu hỏi trong một phút.","retry_after":1}\n\n',
        });
      }
      return r.respond(
        failure
          ? { status: 502, body: "failed" }
          : {
              status: 200,
              contentType: "text/event-stream",
              body:
                'event: step\ndata: {"step":"retrieve","ms":100}\n\nevent: done\ndata: ' +
                JSON.stringify(payload) +
                "\n\n",
            },
      );
    }
    r.continue();
  });
  await page.goto(process.env.TEST_URL || "http://127.0.0.1:8765");
  await page.waitForFunction(
    () => document.querySelector(".scene").dataset.renderer === "panorama-360",
  );
  await page.waitForFunction(
    () => document.querySelector("#corpus-count").textContent === "49.063",
  );
  await page.click(".qchip");
  assert.match(await page.$eval("#q-input", (e) => e.value), /Di chúc/);
  assert.equal(requests.length, 0);
  await page.keyboard.press("Enter");
  await page.waitForSelector(".card-answer");
  assert.equal(requests.length, 1);
  await page.click(".ref");
  assert(
    await page.$eval(".statute", (e) => e.classList.contains("highlight")),
  );
  await page.click(".card-src summary");
  assert(await page.$eval(".card-src", (e) => e.open));
  await page.type("#q-input", "Hỏi tiếp nội dung kiểm thử");
  await page.keyboard.press("Enter");
  await page.waitForFunction(
    () => document.querySelectorAll(".card-answer").length === 2,
  );
  assert.equal(requests[1].history.length, 2);
  await page.screenshot({
    path: "/tmp/verdict-conversation.png",
    fullPage: true,
  });
  await page.reload();
  await page.waitForSelector(".chatitem");
  await page.click(".chatitem");
  await page.waitForFunction(
    () => document.querySelectorAll(".card-answer").length === 2,
  );
  assert.equal(requests.length, 2);
  await page.click("#new-chat");
  assert(await page.$eval("#state-thread", (e) => e.hidden));
  assert.equal(await page.$eval("#q-input", (e) => e.value), "");
  await page.type("#history-filter", "no matches");
  assert.match(
    await page.$eval("#chat-list", (e) => e.textContent),
    /Không tìm thấy/,
  );
  await page.$eval("#history-filter", (e) => {
    e.value = "";
    e.dispatchEvent(new Event("input"));
  });
  failure = true;
  await page.type("#q-input", "Kiểm tra lỗi");
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => !document.querySelector("#ask-err").hidden);
  assert.equal(await page.$eval("#q-input", (e) => e.value), "Kiểm tra lỗi");
  await page.click("#new-chat");
  failure = false;
  // Giới hạn theo phút: đếm ngược, giữ câu hỏi, tự hỏi lại đúng MỘT lần.
  const countdown = () => {
    const e = document.querySelector("#ask-err");
    return !e.hidden && /Tự thử lại sau \d+ giây/.test(e.textContent);
  };
  rateLimited = 1;
  let before = requests.length;
  await page.type("#q-input", "Kiểm tra giới hạn");
  await page.keyboard.press("Enter");
  await page.waitForFunction(countdown);
  assert.equal(
    await page.$eval("#q-input", (e) => e.value),
    "Kiểm tra giới hạn",
  );
  await page.waitForSelector(".card-answer");
  assert.equal(requests.length, before + 2);
  await page.click("#new-chat");
  rateLimited = 5;
  before = requests.length;
  await page.type("#q-input", "Vẫn bị giới hạn");
  await page.keyboard.press("Enter");
  await page.waitForFunction(countdown);
  await page.waitForFunction(() => {
    const e = document.querySelector("#ask-err");
    return !e.hidden && !/Tự thử lại sau/.test(e.textContent);
  });
  await new Promise((r) => setTimeout(r, 1500));
  assert.equal(requests.length, before + 2);
  assert.equal(
    await page.$eval("#q-input", (e) => e.value),
    "Vẫn bị giới hạn",
  );
  await page.click("#new-chat");
  rateLimited = 0;
  await page.click("#motion-toggle");
  assert.equal(
    await page.$eval("#motion-toggle", (e) => e.getAttribute("aria-pressed")),
    "false",
  );
  await page.reload();
  await page.waitForFunction(
    () => document.querySelector(".scene").dataset.renderer,
  );
  assert.equal(
    await page.$eval("#motion-toggle", (e) => e.getAttribute("aria-pressed")),
    "false",
  );
  await page.click("#about-open");
  assert(await page.$eval("dialog", (e) => e.open));
  await page.keyboard.press("Escape");
  assert.equal(await page.$eval("dialog", (e) => e.open), false);
  await page.setViewport({ width: 390, height: 844 });
  await page.reload();
  await new Promise((r) => setTimeout(r, 800));
  assert.equal(await page.$eval("html", (e) => e.dataset.sidebar), "closed");
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
    false,
  );
  await page.screenshot({ path: "/tmp/verdict-mobile.png", fullPage: true });
  await page.click("#side-toggle");
  assert.equal(await page.$eval("#sidebar", (e) => e.inert), false);
  await page.keyboard.press("Escape");
  assert.equal(await page.$eval("#sidebar", (e) => e.inert), true);
  await page.type("#q-input", "Kiểm thử màn hình nhỏ");
  await page.keyboard.press("Enter");
  await page.waitForSelector(".card-answer");
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
    false,
  );
  await page.screenshot({
    path: "/tmp/verdict-mobile-chat.png",
    fullPage: true,
  });
  await page.emulateMediaFeatures([
    { name: "prefers-reduced-motion", value: "reduce" },
  ]);
  await page.reload();
  await page.waitForFunction(
    () => document.querySelector(".scene").dataset.renderer,
  );
  assert.equal(
    await page.$eval("#motion-toggle", (e) => e.getAttribute("aria-pressed")),
    "false",
  );
  assert.deepEqual(errors, []);
  console.log(
    "PASS: 360 panorama, corpus, topic draft, Enter submit, follow-up context, citations, history persistence/search, errors/retry draft, rate-limit countdown with single auto-retry, motion preference, modal, mobile drawer/layout, reduced motion.",
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
