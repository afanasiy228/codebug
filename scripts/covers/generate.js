// Builds the generated profile covers into covers/*.webp.
// Usage: node scripts/covers/generate.js [name...]   (needs Playwright, cwebp, img2webp)
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
const OUT = path.join(ROOT, 'covers');
const FULL = [1600, 440];
const ANIM = [1280, 352];
const THUMB = [480, 132];
const FRAMES = 48;           // 4 s loop at 12 fps
const FRAME_MS = 83;
const SOFT = new Set();

function savePng(dataUrl, file) {
  fs.writeFileSync(file, Buffer.from(dataUrl.split(',')[1], 'base64'));
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const only = new Set(process.argv.slice(2));
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setContent('<canvas id="c"></canvas>');
  await page.addScriptTag({ path: path.join(__dirname, 'scenes.js') });
  const names = await page.evaluate(() => window.coverNames);
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'covers-'));

  for (const name of names.stills) {
    if (only.size && !only.has(name)) continue;
    for (const [suffix, [w, h]] of [['', FULL], ['.thumb', THUMB]]) {
      const png = path.join(tmp, `${name}${suffix}.png`);
      savePng(await page.evaluate(([n, w, h]) => { renderStill(n, w, h); return document.getElementById('c').toDataURL('image/png'); }, [name, w, h]), png);
      execFileSync('cwebp', ['-quiet', '-q', '82', png, '-o', path.join(OUT, `${name}${suffix}.webp`)]);
    }
    console.log('still', name);
  }

  for (const name of names.frames) {
    if (only.size && !only.has(name)) continue;
    // Soft, dark gradients band badly at low quality, so they get a higher one.
    const soft = SOFT.has(name);
    for (const [suffix, [w, h], q] of [['', ANIM, soft ? '92' : '70'], ['.thumb', THUMB, soft ? '88' : '65']]) {
      const files = [];
      for (let i = 0; i < FRAMES; i++) {
        const png = path.join(tmp, `${name}${suffix}-${String(i).padStart(3, '0')}.png`);
        savePng(await page.evaluate(([n, w, h, t]) => { renderFrame(n, w, h, t); return document.getElementById('c').toDataURL('image/png'); }, [name, w, h, i / FRAMES]), png);
        files.push(png);
      }
      execFileSync('img2webp', ['-loop', '0', '-lossy', '-q', q, '-m', '6', '-d', String(FRAME_MS), ...files, '-o', path.join(OUT, `${name}${suffix}.webp`)]);
    }
    console.log('anim', name);
  }

  await browser.close();
  fs.rmSync(tmp, { recursive: true, force: true });
})();
