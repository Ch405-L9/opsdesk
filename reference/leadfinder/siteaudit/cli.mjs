#!/usr/bin/env node
import lighthouse from 'lighthouse';
import * as chromeLauncher from 'chrome-launcher';
import { mkdir, writeFile, access } from 'node:fs/promises';
import { constants } from 'node:fs';
import { homedir } from 'node:os';
import path from 'node:path';

const [command, target] = process.argv.slice(2);
const reportRoot = path.join(
  homedir(), '.local', 'share', 'badgr-siteaudit', 'reports'
);
const chromePath = process.env.CHROME_PATH || '/usr/bin/google-chrome';

function help() {
  console.log(`
BADGR Site Audit — CLI version 0.1

Commands:
  siteaudit doctor
  siteaudit audit https://example.com
  siteaudit reports
  siteaudit help

Reports:
  ${reportRoot}

Optional environment setting:
  CHROME_PATH — override the Chrome executable

Analytics:
  Not connected in this version.
  Traffic, duration, carts, and purchases are not measured by this app.
`);
}

async function main() {
  if (!command || command === 'help' || command === '--help') {
    help();
    return;
  }

  if (command === 'reports') {
    await mkdir(reportRoot, { recursive: true });
    console.log(reportRoot);
    return;
  }

  if (command === 'doctor') {
    console.log(`Node: ${process.version}`);
    console.log(`Chrome: ${chromePath}`);
    await access(chromePath, constants.X_OK);
    console.log('Chrome executable: available');
    await mkdir(reportRoot, { recursive: true });
    await access(reportRoot, constants.W_OK);
    console.log(`Report directory: ${reportRoot}`);
    console.log('Matomo: optional; adapter not implemented yet');
    console.log('Basic checks passed. Run an audit to verify Lighthouse.');
    return;
  }

  if (command !== 'audit') {
    throw new Error(`Unknown command: ${command}. Run: siteaudit help`);
  }

  if (!target) {
    throw new Error('Supply a URL: siteaudit audit https://example.com');
  }

  const url = new URL(target);
  if (!['http:', 'https:'].includes(url.protocol)) {
    throw new Error('The URL must start with http:// or https://');
  }
  if (!url.hostname || url.username || url.password) {
    throw new Error('Use a URL with a hostname and no embedded credentials.');
  }

  await access(chromePath, constants.X_OK);
  const host = url.hostname.replace(/[^a-zA-Z0-9.-]/g, '_');
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const directory = path.join(reportRoot, `${host}-${timestamp}`);
  await mkdir(directory, { recursive: true });

  let chrome;
  try {
    console.log(`Auditing ${url.href}`);
    console.log('Running a mobile Lighthouse audit. Please wait...');

    chrome = await chromeLauncher.launch({
      chromePath,
      chromeFlags: ['--headless', '--disable-dev-shm-usage']
    });

    const result = await lighthouse(url.href, {
      port: chrome.port,
      logLevel: 'error',
      output: ['html', 'json'],
      onlyCategories: [
        'performance',
        'accessibility',
        'best-practices',
        'seo'
      ]
    });

    if (!result) throw new Error('Lighthouse returned no result.');
    if (result.lhr.runtimeError) {
      throw new Error(result.lhr.runtimeError.message);
    }

    const [html, json] = result.report;
    await writeFile(path.join(directory, 'lighthouse.html'), html);
    await writeFile(path.join(directory, 'lighthouse.json'), json);

    const scores = Object.fromEntries(
      Object.entries(result.lhr.categories).map(([key, value]) => [
        key,
        value.score === null ? null : Math.round(value.score * 100)
      ])
    );

    await writeFile(
      path.join(directory, 'summary.json'),
      JSON.stringify({
        requestedUrl: url.href,
        finalUrl: result.lhr.finalDisplayedUrl || result.lhr.finalUrl,
        collectedAt: result.lhr.fetchTime,
        lighthouseVersion: result.lhr.lighthouseVersion,
        mode: 'mobile',
        scores,
        analytics: {
          status: 'not_connected',
          message: 'Visitor and ecommerce metrics are not measured.'
        }
      }, null, 2)
    );

    for (const [category, score] of Object.entries(scores)) {
      console.log(`${category}: ${score === null ? 'N/A' : score + '/100'}`);
    }

    console.log(`\nReports saved to:\n${directory}`);
    console.log(`\nOpen HTML report:\nxdg-open "${path.join(directory, 'lighthouse.html')}"`);
  } finally {
    if (chrome) await chrome.kill();
  }
}

main().catch(error => {
  console.error(`Error: ${error.message}`);
  process.exitCode = 1;
});
