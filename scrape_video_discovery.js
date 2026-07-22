/**
 * Platform-wide video discovery — unlike scrape_accounts.js/scrape_watchlist.js
 * (which only ever see tracked accounts' own timelines), this searches X's
 * public search with filter:videos across a fixed set of industry keywords,
 * so ANY account's video post can surface, not just ones already tracked in
 * accounts_config.json. Feeds TrendForceDash's cross-platform X Video
 * Ranking section (see video_ranking.py on the dashboard side).
 *
 * Reuses session.json - the same login session scrape_watchlist.js expects,
 * saved by the main mention-tracker scraper. Run that first if this errors
 * out with "Not logged in."
 *
 * Usage: node scrape_video_discovery.js [--since YYYY-MM-DD]
 */
require('dotenv').config();
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { toTaiwanISOString } = require('./tz_util');

const sinceArg = process.argv.includes('--since') ? process.argv[process.argv.indexOf('--since') + 1] : null;
const sinceDate = sinceArg || new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
if (sinceArg) console.log(`Running with custom since date: ${sinceDate}`);

// Batched industry keywords (TrendForce's own coverage domain - semiconductor
// / AI hardware news), each combined with filter:videos so results are
// video posts from ANY account, not a fixed list. Kept to ~5 terms per
// query, same batching reasoning as scrape_watchlist.js's from: batches -
// a handful of broad queries costs far less scrape time than one query per
// term while still covering the domain.
const KEYWORD_BATCHES = [
  ['TSMC', 'Nvidia', 'Samsung', 'SK hynix', 'Micron'],
  ['Intel', 'AMD', 'semiconductor', 'chip', 'foundry'],
  ['DRAM', 'NAND', 'HBM', 'EUV', 'AI chip'],
];
const SEARCH_QUERIES = KEYWORD_BATCHES.map((terms) => {
  const orPart = terms.map((t) => (t.includes(' ') ? `"${t}"` : t)).join(' OR ');
  return `(${orPart}) filter:videos since:${sinceDate}`;
});

const SESSION_FILE = path.join(__dirname, 'session.json');
const CSV_DIR = path.join(__dirname, 'csv');
const RAW_FILE = path.join(__dirname, 'raw_video_discovery.json');
fs.mkdirSync(CSV_DIR, { recursive: true });

async function scrapeVideoTweets(page, query, maxScrolls = 15) {
  const url = `https://x.com/search?q=${encodeURIComponent(query)}&src=typed_query&f=live`;
  console.log(`\nSearching: "${query}"`);
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);

  // Detect blank/error page and wait for recovery - same recovery loop as
  // scrape_watchlist.js's scrapeTweets(), same underlying flakiness.
  for (let attempt = 0; attempt < 3; attempt++) {
    const bodyText = await page.evaluate(() => document.body?.innerText?.trim() || '');
    const isBlank = bodyText.length < 50;
    const hasError = await page.$('span:has-text("Something went wrong")');
    if (!isBlank && !hasError) break;
    console.log(`  Blank or error page detected, waiting 15s before retry (${attempt + 1}/3)...`);
    await page.waitForTimeout(15000);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(5000);
  }

  const seen = new Set();
  const tweets = [];

  for (let scroll = 0; scroll < maxScrolls; scroll++) {
    await page.waitForSelector('[data-testid="tweet"]', { timeout: 10000 }).catch(() => {});

    const newTweets = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('[data-testid="tweet"]')).map((el) => {
        const textEl = el.querySelector('[data-testid="tweetText"]');
        const text = textEl ? textEl.innerText : '';

        const userEl = el.querySelector('[data-testid="User-Name"]');
        const links = userEl ? Array.from(userEl.querySelectorAll('a')) : [];
        const handle = links[1] ? links[1].innerText : '';

        const timeEl = el.querySelector('time');
        const timestamp = timeEl ? timeEl.getAttribute('datetime') : '';

        const tweetLinkEl = el.querySelector('a[href*="/status/"]');
        const tweetUrl = tweetLinkEl ? 'https://x.com' + tweetLinkEl.getAttribute('href') : '';

        const getStatText = (testId) => {
          const btn = el.querySelector(`[data-testid="${testId}"]`);
          if (!btn) return '0';
          const span = btn.querySelector('span > span');
          return span ? span.innerText : '0';
        };

        // filter:videos in the search query already restricts results to
        // video posts, but confirm via the player element itself rather
        // than trusting the query filter blindly - same reasoning as
        // scrape_accounts.js's hasVideo check.
        const hasVideo = el.querySelectorAll('[data-testid="videoPlayer"], [data-testid="videoComponent"]').length > 0;

        // Views - same analytics-link technique as scrape_accounts.js.
        const viewsEl = el.querySelector('a[href*="/analytics"]');
        let views = '0';
        if (viewsEl) {
          const ariaLabel = viewsEl.getAttribute('aria-label') || '';
          const match = ariaLabel.match(/([\d,\.]+[KMB]?)\s*view/i);
          if (match) views = match[1];
          else {
            const span = viewsEl.querySelector('span > span');
            if (span) views = span.innerText.trim();
          }
        }

        return {
          text, handle, timestamp, tweetUrl, hasVideo, views,
          likes: getStatText('like'),
          retweets: getStatText('retweet'),
        };
      });
    });

    let addedCount = 0;
    for (const tweet of newTweets) {
      if (!tweet.hasVideo) continue; // belt-and-suspenders past the query filter
      const key = tweet.tweetUrl || tweet.text;
      if (key && !seen.has(key)) { seen.add(key); tweets.push(tweet); addedCount++; }
    }

    console.log(`  Scroll ${scroll + 1}/${maxScrolls} — +${addedCount} new video post(s) (total: ${tweets.length})`);
    if (addedCount === 0 && scroll > 2) { console.log('  No new video posts, stopping early.'); break; }

    await page.evaluate(() => window.scrollBy(0, window.innerHeight * 3));
    await page.waitForTimeout(2500);
  }

  tweets.forEach((t) => { t.timestamp = toTaiwanISOString(t.timestamp); });
  return tweets;
}

const safe = (s) => `"${String(s ?? '').replace(/"/g, '""').replace(/\n/g, ' ')}"`;

function writeDiscoveryCsv(tweets) {
  const outFile = path.join(CSV_DIR, 'video_discovery.csv');
  const header = 'timestamp,handle,views,likes,retweets,tweetUrl,text\n';

  // Merge with whatever's already on disk (keyed by tweetUrl), same
  // refresh-in-place reasoning as scrape_accounts.js - views/likes keep
  // climbing after posting, and re-running this script shouldn't just
  // pile up duplicate rows for the same video.
  const existingByUrl = new Map();
  if (fs.existsSync(outFile)) {
    const lines = fs.readFileSync(outFile, 'utf8').split('\n').slice(1).filter((l) => l.trim());
    for (const line of lines) {
      const cols = line.match(/(".*?"|[^,]+)(?=,|$)/g) || [];
      const unq = (s) => (s || '').replace(/^"|"$/g, '').replace(/""/g, '"');
      const url = unq(cols[5]);
      if (url) existingByUrl.set(url, line);
    }
  }

  for (const t of tweets) {
    const row = [t.timestamp, safe(t.handle), t.views || '0', t.likes, t.retweets, safe(t.tweetUrl), safe(t.text)].join(',');
    existingByUrl.set(t.tweetUrl, row);
  }

  const body = Array.from(existingByUrl.values()).join('\n');
  fs.writeFileSync(outFile, header + body + (body ? '\n' : ''));
  console.log(`\nWrote ${outFile} (${existingByUrl.size} total video posts discovered)`);
}

async function main() {
  const browser = await chromium.launch({
    headless: false,
    args: ['--no-sandbox', '--disable-blink-features=AutomationControlled'],
  });

  const contextOptions = {
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    viewport: { width: 1280, height: 900 },
  };
  if (fs.existsSync(SESSION_FILE)) contextOptions.storageState = SESSION_FILE;

  const context = await browser.newContext(contextOptions);
  const page = await context.newPage();

  try {
    await page.goto('https://x.com/home', { waitUntil: 'domcontentloaded' });
    const isLoggedIn = await page.waitForSelector('[data-testid="SideNav_AccountSwitcher_Button"]', { timeout: 15000 }).catch(() => null);
    if (!isLoggedIn) {
      console.log('Not logged in. Please run the main scraper first to save a session.');
      process.exit(1);
    }

    let allTweets = [];
    if (fs.existsSync(RAW_FILE)) {
      allTweets = JSON.parse(fs.readFileSync(RAW_FILE, 'utf8'));
      console.log(`\nResuming — loaded ${allTweets.length} video posts from raw_video_discovery.json`);
      console.log('Delete raw_video_discovery.json to start a fresh scrape.\n');
    } else {
      for (let qi = 0; qi < SEARCH_QUERIES.length; qi++) {
        const tweets = await scrapeVideoTweets(page, SEARCH_QUERIES[qi], 15);
        allTweets.push(...tweets);
        fs.writeFileSync(RAW_FILE, JSON.stringify(allTweets, null, 2));
        if (qi < SEARCH_QUERIES.length - 1) {
          console.log('  Cooling down 10s before next batch...');
          await page.waitForTimeout(10000);
        }
      }
    }

    const deduped = [];
    const seenUrls = new Set();
    for (const t of allTweets) {
      const key = t.tweetUrl || t.text;
      if (key && !seenUrls.has(key)) { seenUrls.add(key); deduped.push(t); }
    }

    writeDiscoveryCsv(deduped);
    fs.unlinkSync(RAW_FILE);
  } catch (err) {
    console.error('Error:', err.message);
    await page.screenshot({ path: path.join(__dirname, 'error-video-discovery.png') }).catch(() => {});
  } finally {
    await browser.close();
  }
}

main();
