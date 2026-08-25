import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'fs';
import { join, dirname, basename } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const screenshotDir = join(__dirname, 'screenshots');
mkdirSync(screenshotDir, { recursive: true });

const variants = [
  { file: 'ink-extended.html', name: 'base-ink-extended', label: 'Base (Ink Extended Light)' },
  { file: 'ink-dark.html', name: 'base-ink-dark', label: 'Base (Ink Extended Dark)' },
  { file: 'v1-bookmark.html', name: 'v1-bookmark', label: 'v1 Bookmark Tabs' },
  { file: 'v2-topbar-cmd.html', name: 'v2-topbar-cmd', label: 'v2 Top Bar Command Center' },
  { file: 'v3-edge-rails.html', name: 'v3-edge-rails', label: 'v3 Edge Rails' },
  { file: 'v4-audio-hub.html', name: 'v4-audio-hub', label: 'v4 Audio Hub' },
  { file: 'v5-ultra-minimal.html', name: 'v5-ultra-minimal', label: 'v5 Ultra Minimal' },
  { file: 'v6-ribbons.html', name: 'v6-ribbons', label: 'v6 Ribbon Bookmarks' },
  { file: 'v7-dog-ears.html', name: 'v7-dog-ears', label: 'v7 Dog-Eared Pages' },
  { file: 'v8-margin-marks.html', name: 'v8-margin-marks', label: 'v8 Margin Marks' },
  { file: 'v9-circle-buttons.html', name: 'v9-circle-buttons', label: 'v9 Circle Buttons' },
];

// States to capture for each variant
const states = [
  { id: 'default', label: 'Default state (everything collapsed/hidden, just reading)', actions: [] },
  { id: 'left-panel', label: 'Left panel open (character/inventory)', actions: ['left'] },
  { id: 'right-panel', label: 'Right panel open (settings)', actions: ['settings'] },
  { id: 'both-panels', label: 'Both side panels open simultaneously', actions: ['left', 'settings'] },
  { id: 'topbar', label: 'Top bar visible (status bar)', actions: ['topbar'] },
  { id: 'bottombar', label: 'Bottom bar visible (info bar)', actions: ['bottombar'] },
  { id: 'all-bars', label: 'All bars visible (top + bottom)', actions: ['topbar', 'bottombar'] },
  { id: 'audio-expanded', label: 'Audio bar expanded (full controls)', actions: ['audio-expand'] },
  { id: 'left-audio', label: 'Left panel + audio expanded', actions: ['left', 'audio-expand'] },
  { id: 'everything', label: 'Everything open (both panels + both bars + audio)', actions: ['left', 'settings', 'topbar', 'bottombar', 'audio-expand'] },
];

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    deviceScaleFactor: 2,
  });

  const manifest = [];

  for (const variant of variants) {
    const filePath = join(__dirname, variant.file);
    const page = await context.newPage();

    try {
      await page.goto(`file://${filePath}`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(500);

      for (const state of states) {
        // Reset to default state by reloading
        await page.reload({ waitUntil: 'networkidle' });
        await page.waitForTimeout(300);

        // Apply actions
        for (const action of state.actions) {
          if (action === 'left') {
            await page.evaluate(() => {
              const app = document.getElementById('app');
              if (!app.classList.contains('show-left')) app.classList.add('show-left');
              const btn = document.getElementById('toggleLeftBtn');
              if (btn) btn.classList.add('active');
            });
          } else if (action === 'settings') {
            await page.evaluate(() => {
              const app = document.getElementById('app');
              if (!app.classList.contains('show-settings')) app.classList.add('show-settings');
              const btn = document.getElementById('toggleSettingsBtn');
              if (btn) btn.classList.add('active');
            });
          } else if (action === 'topbar') {
            await page.evaluate(() => {
              const app = document.getElementById('app');
              app.classList.remove('hide-topbar');
            });
          } else if (action === 'bottombar') {
            await page.evaluate(() => {
              const app = document.getElementById('app');
              app.classList.remove('hide-bottombar');
            });
          } else if (action === 'audio-expand') {
            await page.evaluate(() => {
              const app = document.getElementById('app');
              app.classList.remove('audio-collapsed');
            });
          }
        }

        await page.waitForTimeout(400);

        const screenshotName = `${variant.name}_${state.id}.png`;
        const screenshotPath = join(screenshotDir, screenshotName);
        await page.screenshot({ path: screenshotPath, fullPage: false });

        manifest.push({
          file: screenshotName,
          variant: variant.label,
          variantFile: variant.file,
          state: state.label,
          stateId: state.id,
          actions: state.actions.join(', ') || 'none',
          description: `${variant.label} — ${state.label}`,
        });

        console.log(`  ${screenshotName}`);
      }
    } catch (e) {
      console.error(`Error with ${variant.file}: ${e.message}`);
    }

    await page.close();
  }

  await browser.close();

  // Write manifest as JSON
  writeFileSync(join(screenshotDir, 'manifest.json'), JSON.stringify(manifest, null, 2));
  console.log(`\nDone! ${manifest.length} screenshots in ${screenshotDir}`);
}

run().catch(console.error);
