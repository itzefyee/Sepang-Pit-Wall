import puppeteer from 'puppeteer';
import { preview } from 'vite';
import path from 'path';

async function run() {
  console.log('[Recorder] Starting Vite preview server programmatically...');
  const previewServer = await preview({
    preview: {
      port: 4173,
      host: '127.0.0.1'
    }
  });
  console.log('[Recorder] Vite preview server listening on http://127.0.0.1:4173');

  console.log('[Recorder] Launching headless browser with WebGL...');
  const browser = await puppeteer.launch({
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--enable-webgl',
      '--ignore-gpu-blocklist',
      '--use-gl=angle',
      '--use-angle=default',
      '--window-size=1600,900'
    ]
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 900 });

  console.log('[Recorder] Loading Sepang app...');
  await page.goto('http://127.0.0.1:4173', { waitUntil: 'domcontentloaded', timeout: 15000 });
  await new Promise(r => setTimeout(r, 2500));

  const shots = [
    { name: 'frame_01_overview_start.png', cam: 'overview', waitMs: 2000, weather: 'sun' },
    { name: 'frame_02_turn1_hairpin.png', cam: 'turn1', waitMs: 2000, weather: 'sun' },
    { name: 'frame_03_turn5_esses.png', cam: 'turn5', waitMs: 2000, weather: 'sun' },
    { name: 'frame_04_monsoon_radar.png', cam: 'overview', waitMs: 2500, weather: 'approaching_squall' },
    { name: 'frame_05_monsoon_deluge.png', cam: 'straights', waitMs: 2500, weather: 'torrential_monsoon' },
    { name: 'frame_06_cockpit_onboard.png', cam: 'onboard', waitMs: 2500, weather: 'drying' }
  ];

  for (const shot of shots) {
    console.log('[Recorder] Capturing ' + shot.name + ' (Cam: ' + shot.cam + ', Weather: ' + shot.weather + ')...');
    await page.evaluate((c, w) => {
      const cb = document.querySelector('[data-cam="' + c + '"]');
      if (cb) cb.click();
      const wb = document.querySelector('[data-weather="' + w + '"]');
      if (wb) wb.click();
    }, shot.cam, shot.weather);
    await new Promise(r => setTimeout(r, shot.waitMs));
    await page.screenshot({ path: path.join('recordings', shot.name) });
    console.log('[Recorder] Saved ' + shot.name);
  }

  console.log('[Recorder] Playthrough recording successfully completed!');
  await browser.close();
  previewServer.httpServer.close();
  process.exit(0);
}

run().catch(e => {
  console.error('[Recorder Error]', e);
  process.exit(1);
});