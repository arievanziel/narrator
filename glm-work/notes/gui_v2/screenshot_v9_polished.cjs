const { chromium } = require('playwright');
const { join } = require('path');
const fs = require('fs');

const screenshotDir = join(__dirname, 'screenshots');

const states = [
  { id: 'default', label: 'Default state (everything collapsed, just reading)', actions: [] },
  { id: 'left-panel', label: 'Left panel open', actions: ['left'] },
  { id: 'right-panel', label: 'Right panel open (settings)', actions: ['settings'] },
  { id: 'both-panels', label: 'Both side panels open', actions: ['left', 'settings'] },
  { id: 'topbar', label: 'Top bar visible', actions: ['topbar'] },
  { id: 'no-topbar', label: 'Top bar hidden (max reading space)', actions: ['no-topbar'] },
  { id: 'audio-expanded', label: 'Audio bar expanded (full controls + session metadata)', actions: ['audio-expand'] },
  { id: 'left-audio', label: 'Left panel + audio expanded', actions: ['left', 'audio-expand'] },
  { id: 'left-no-topbar', label: 'Left panel + top bar hidden (toggle anchoring test)', actions: ['left', 'no-topbar'] },
  { id: 'everything', label: 'Everything open (both panels + top bar + audio)', actions: ['left', 'settings', 'topbar', 'audio-expand'] },
];

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    deviceScaleFactor: 2,
  });

  const manifest = [];
  const filePath = join(__dirname, 'v9-circle-buttons.html');
  const page = await context.newPage();

  for (const state of states) {
    await page.goto(`file://${filePath}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(400);

    for (const action of state.actions) {
      if (action === 'left') {
        await page.evaluate(() => {
          document.getElementById('app').classList.add('show-left');
          document.getElementById('toggleLeftBtn').classList.add('active');
        });
      } else if (action === 'settings') {
        await page.evaluate(() => {
          document.getElementById('app').classList.add('show-settings');
          document.getElementById('toggleSettingsBtn').classList.add('active');
        });
      } else if (action === 'topbar') {
        await page.evaluate(() => {
          document.getElementById('app').classList.remove('hide-topbar');
        });
      } else if (action === 'no-topbar') {
        await page.evaluate(() => {
          document.getElementById('app').classList.add('hide-topbar');
        });
      } else if (action === 'audio-expand') {
        await page.evaluate(() => {
          document.getElementById('app').classList.remove('audio-collapsed');
        });
      }
    }

    await page.waitForTimeout(400);

    const name = `v9-polished_${state.id}.png`;
    await page.screenshot({ path: join(screenshotDir, name), fullPage: false });
    manifest.push({ file: name, state: state.label, stateId: state.id });
    console.log(`  ${name}`);
  }

  await page.close();
  await browser.close();

  fs.writeFileSync(join(screenshotDir, 'v9-polished-manifest.json'), JSON.stringify(manifest, null, 2));
  console.log(`\nDone! ${manifest.length} screenshots`);
}

run().catch(console.error);
