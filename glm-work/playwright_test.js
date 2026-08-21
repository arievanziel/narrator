// Playwright test: screenshots + video recording of Narrator app
// Run: node playwright_test.js
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const BASE = 'http://localhost:5102';
const OUT = path.join(__dirname, 'outputs', 'playwright');
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    recordVideo: { dir: OUT, size: { width: 1440, height: 900 } },
  });
  const page = await context.newPage();

  // Collect console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', err => consoleErrors.push(`PAGE ERROR: ${err.message}`));

  console.log('1. Loading intro screen...');
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(OUT, '01_intro.png'), fullPage: false });
  console.log('   Screenshot: 01_intro.png');

  // Check intro overlay is visible
  const introVisible = await page.locator('#intro-overlay').isVisible();
  console.log(`   Intro overlay visible: ${introVisible}`);

  // Fill in the intro form
  console.log('2. Filling intro form...');
  await page.fill('#intro-name', 'Kael');
  await page.selectOption('#intro-style', 'dark fantasy');
  await page.fill('#intro-setting', 'a haunted mountain village');
  await page.fill('#intro-persona', 'a grizzled veteran');
  await page.selectOption('#intro-atmosphere', 'tense');
  await page.screenshot({ path: path.join(OUT, '02_intro_filled.png') });
  console.log('   Screenshot: 02_intro_filled.png');

  // Start the game
  console.log('3. Starting game...');
  await page.click('#intro-start-btn');
  // Wait for story to appear — look for narrator-text or any text in story-content
  await page.waitForSelector('#story-content .narrator-text, #story-content .player-action, #story-content > div', { timeout: 60000 });
  await page.waitForTimeout(5000); // Wait for audio generation to start
  await page.screenshot({ path: path.join(OUT, '03_game_started.png') });
  console.log('   Screenshot: 03_game_started.png');

  // Check story content
  const storyText = await page.textContent('#story-content');
  console.log(`   Story text length: ${storyText.length} chars`);

  // Check choices
  const choices = await page.locator('.choice-item').count();
  console.log(`   Choices: ${choices}`);

  // Click the first choice
  if (choices > 0) {
    console.log('4. Clicking first choice...');
    await page.locator('.choice-item').first().click();
    await page.waitForTimeout(5000);
    // Wait for new story content to be added
    await page.waitForFunction(() => {
      const c = document.getElementById('story-content');
      return c && c.children.length > 3; // more content added
    }, { timeout: 60000 });
    await page.waitForTimeout(5000);
    await page.screenshot({ path: path.join(OUT, '04_after_choice.png') });
    console.log('   Screenshot: 04_after_choice.png');
  }

  // Type a custom action
  console.log('5. Typing custom action...');
  const inputField = page.locator('.input-block input').first();
  if (await inputField.isVisible()) {
    await inputField.fill('I attack the goblin with my longsword!');
    await page.screenshot({ path: path.join(OUT, '05_action_typed.png') });
    console.log('   Screenshot: 05_action_typed.png');

    // Press Enter to send
    await inputField.press('Enter');
    await page.waitForTimeout(5000);
    await page.waitForTimeout(5000);
    await page.screenshot({ path: path.join(OUT, '06_after_action.png') });
    console.log('   Screenshot: 06_after_action.png');
  }

  // Open settings panel
  console.log('6. Opening settings...');
  await page.click('#tab-settings');
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(OUT, '07_settings.png') });
  console.log('   Screenshot: 07_settings.png');

  // Change TTS engine
  console.log('7. Changing TTS engine...');
  await page.selectOption('#set-tts', 'qwen3');
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, '08_tts_qwen3.png') });
  console.log('   Screenshot: 08_tts_qwen3.png');

  // Change theme
  console.log('8. Changing theme...');
  await page.selectOption('#set-theme', 'sepia');
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, '09_theme_sepia.png') });
  console.log('   Screenshot: 09_theme_sepia.png');

  await page.selectOption('#set-theme', 'dark');
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, '10_theme_dark.png') });
  console.log('   Screenshot: 10_theme_dark.png');

  // Open left panel (character info)
  console.log('9. Opening left panel...');
  await page.click('#tab-left');
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(OUT, '11_left_panel.png') });
  console.log('   Screenshot: 11_left_panel.png');

  // Check audio player
  console.log('10. Checking audio player...');
  const audioPlayer = page.locator('#audio-player');
  const audioSrc = await audioPlayer.getAttribute('src');
  console.log(`   Audio src: ${audioSrc || 'none'}`);
  await page.screenshot({ path: path.join(OUT, '12_audio_state.png') });
  console.log('   Screenshot: 12_audio_state.png');

  // Wait a bit more for any audio generation
  await page.waitForTimeout(5000);
  await page.screenshot({ path: path.join(OUT, '13_final.png') });
  console.log('   Screenshot: 13_final.png');

  // Report console errors
  console.log('\n=== Console Errors ===');
  if (consoleErrors.length === 0) {
    console.log('No console errors!');
  } else {
    consoleErrors.forEach(e => console.log(`  ${e}`));
  }

  // Close — this saves the video
  console.log('\nClosing browser (saving video)...');
  await page.close();
  await context.close();
  await browser.close();

  // Find the video file
  const videos = fs.readdirSync(OUT).filter(f => f.endsWith('.webm'));
  console.log(`\nVideo files: ${videos.join(', ')}`);
  console.log(`Screenshots: ${fs.readdirSync(OUT).filter(f => f.endsWith('.png')).length}`);
  console.log(`\nAll artifacts in: ${OUT}`);
})();
