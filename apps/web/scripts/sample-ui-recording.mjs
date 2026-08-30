import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { pathToFileURL } from "node:url";

const [videoPath, outputDirectory] = process.argv.slice(2);
if (!videoPath || !outputDirectory) {
  throw new Error("Usage: node sample-ui-recording.mjs <video> <output-directory>");
}

await mkdir(outputDirectory, { recursive: true });
const browser = await chromium.launch({
  headless: true,
  args: ["--allow-file-access-from-files"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const source = pathToFileURL(videoPath).href;
await page.goto(source, { waitUntil: "load" });
await page.addStyleTag({
  content: `
    * { box-sizing: border-box; }
    html, body { margin: 0; width: 100%; height: 100%; background: #050807; overflow: hidden; }
    video { width: 100% !important; height: 100% !important; object-fit: contain; }
  `,
});
const metadata = await page.locator("video").evaluate((video) => ({
  duration: video.duration,
  width: video.videoWidth,
  height: video.videoHeight,
}));

for (const [index, ratio] of [0.04, 0.22, 0.42, 0.62, 0.82, 0.97].entries()) {
  await page.locator("video").evaluate((video, time) => {
    return new Promise((resolve) => {
      video.addEventListener("seeked", resolve, { once: true });
      video.currentTime = time;
    });
  }, metadata.duration * ratio);
  await page.screenshot({
    path: `${outputDirectory}/frame-${index + 1}.jpg`,
    type: "jpeg",
    quality: 58,
  });
}

console.log(JSON.stringify(metadata));
await browser.close();
