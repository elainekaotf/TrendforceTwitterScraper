require('dotenv').config();
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const SESSION_FILE = path.join(__dirname, 'session.json');
const CSV_DIR = path.join(__dirname, 'csv');
const FOLLOWER_HISTORY_FILE = path.join(__dirname, 'follower_history.json');
fs.mkdirSync(CSV_DIR, { recursive: true });

function parseFollowerCount(str) {
  if (!str || str === 'unknown') return null;
  str = str.replace(/,/g, '').trim();
  if (str.endsWith('K')) return Math.round(parseFloat(str) * 1000);
  if (str.endsWith('M')) return Math.round(parseFloat(str) * 1000000);
  return parseInt(str) || null;
}

function recordFollowers(handle, count) {
  const history = fs.existsSync(FOLLOWER_HISTORY_FILE)
    ? JSON.parse(fs.readFileSync(FOLLOWER_HISTORY_FILE, 'utf8'))
    : {};
  if (!history[handle]) history[handle] = [];
  const today = new Date().toISOString().slice(0, 10);
  // Only record once per day
  if (!history[handle].length || history[handle][history[handle].length - 1].date !== today) {
    history[handle].push({ date: today, followers: count });
    fs.writeFileSync(FOLLOWER_HISTORY_FILE, JSON.stringify(history, null, 2));
    console.log(`  Followers recorded: ${count.toLocaleString()}`);
  }
}

async function scrapeFollowers(page, handle) {
  const cleanHandle = handle.replace('@', '');
  try {
    await page.goto(`https://x.com/${cleanHandle}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    const count = await page.evaluate(() => {
      // X no longer wraps the follower count in an <a href="/followers"> link —
      // it's now plain text like "5,242 Followers" (link target is /verified_followers).
      const match = document.body.innerText.match(/([\d,.]+[KMB]?)\s*Followers/i);
      return match ? match[1] : null;
    });
    return parseFollowerCount(count);
  } catch (e) {
    console.warn(`  Could not scrape followers for ${handle}:`, e.message);
    return null;
  }
}

const ALL_ACCOUNTS = ['@TrendForce', '@technews_tw', '@dylan522p', '@jukan05', '@QQ_Timmy', '@SemiAnalysis_'];
// Optional: `node scrape_accounts.js @Handle1 @Handle2` scrapes only those
// accounts (used by run_daily.sh to retry just @TrendForce if it got missed
// earlier in a run). No handle args = scrape everything, as before.
const requestedHandles = process.argv.slice(2).filter(a => a.startsWith('@'));
const INDIVIDUAL_ACCOUNTS = requestedHandles.length ? requestedHandles : ALL_ACCOUNTS;

function enrichTweets(tweets) {
  try {
    const output = execSync('python3 enrich_accounts.py', {
      input: JSON.stringify(tweets),
      cwd: __dirname,
      maxBuffer: 20 * 1024 * 1024,
    });
    return JSON.parse(output.toString());
  } catch (e) {
    console.warn('Enrichment failed:', e.message);
    return tweets.map(t => ({ ...t, keywords: '', language: 'unknown', translatedText: '' }));
  }
}

const safe = (s) => `"${String(s ?? '').replace(/"/g, '""').replace(/\n/g, ' ')}"`;

// Parses one CSV line into raw fields, preserving quotes so a field can be
// reassigned and the row rejoined with `.join(',')` without re-escaping.
function parseCsvLine(line) {
  const cols = [];
  let i = 0;
  const n = line.length;
  while (i <= n) {
    if (line[i] === '"') {
      let j = i + 1, val = '"';
      while (j < n) {
        if (line[j] === '"' && line[j + 1] === '"') { val += '""'; j += 2; }
        else if (line[j] === '"') { val += '"'; j++; break; }
        else { val += line[j]; j++; }
      }
      cols.push(val);
      i = j + 1;
    } else {
      let j = line.indexOf(',', i);
      if (j === -1) j = n;
      cols.push(line.slice(i, j));
      i = j + 1;
    }
  }
  return cols;
}

const unquote = (s) => (s || '').replace(/^"|"$/g, '').replace(/""/g, '"');

const UPDATE_WINDOW_MS = 7 * 24 * 60 * 60 * 1000;

async function scrapeTimeline(page, handle, maxScrolls = 15) {
  const cleanHandle = handle.replace('@', '');
  console.log(`\nScraping timeline for ${handle}...`);
  await page.goto(`https://x.com/${cleanHandle}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);

  // Retry up to 3 times if Twitter shows "Something went wrong"
  for (let attempt = 0; attempt < 3; attempt++) {
    const errorEl = await page.$('span:has-text("Something went wrong")');
    if (!errorEl) break;
    console.log(`  Twitter error page detected, retrying (${attempt + 1}/3)...`);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(5000);
  }

  const seen = new Set();
  const tweets = [];

  for (let scroll = 0; scroll < maxScrolls; scroll++) {
    // Handle mid-scroll "Something went wrong" errors
    const errorEl = await page.$('span:has-text("Something went wrong")');
    if (errorEl) {
      console.log('  Twitter error mid-scroll, reloading...');
      await page.reload({ waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(5000);
    }
    await page.waitForSelector('[data-testid="tweet"]', { timeout: 10000 }).catch(() => {});

    const newTweets = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('[data-testid="tweet"]')).map((el) => {
        const textEl = el.querySelector('[data-testid="tweetText"]');
        const text = textEl ? textEl.innerText : '';

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

        const hasImages = el.querySelectorAll('[data-testid="tweetPhoto"] img').length > 0;

        const isRetweet = text.startsWith('RT @');

        const userEl = el.querySelector('[data-testid="User-Name"]');
        const userLinks = userEl ? Array.from(userEl.querySelectorAll('a')) : [];
        const tweetHandle = userLinks[1] ? userLinks[1].innerText.toLowerCase() : '';

        // Views — rendered as an analytics link with aria-label containing "views"
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
          text, timestamp, tweetUrl, hasImages, isRetweet, tweetHandle, views,
          likes: getStatText('like'),
          retweets: getStatText('retweet'),
          replies: getStatText('reply'),
        };
      });
    });

    let addedCount = 0;
    for (const tweet of newTweets) {
      const key = tweet.tweetUrl || tweet.text;
      if (key && !seen.has(key)) { seen.add(key); tweets.push(tweet); addedCount++; }
    }

    console.log(`  Scroll ${scroll + 1}/${maxScrolls} — +${addedCount} new (total: ${tweets.length})`);
    if (addedCount === 0 && scroll > 15) { console.log('  No new tweets after 15 empty scrolls, stopping early.'); break; }

    // Scroll to the last tweet element rather than a fixed pixel amount
    // This is more reliable with Twitter's virtualized rendering
    await page.evaluate(() => {
      const tweets = document.querySelectorAll('[data-testid="tweet"]');
      if (tweets.length > 0) {
        tweets[tweets.length - 1].scrollIntoView({ behavior: 'instant', block: 'end' });
      } else {
        window.scrollBy(0, window.innerHeight * 2);
      }
    });
    await page.waitForTimeout(4000);
  }

  return tweets;
}

async function main() {
  const contextOptions = {
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    viewport: { width: 1280, height: 900 },
  };
  if (fs.existsSync(SESSION_FILE)) contextOptions.storageState = SESSION_FILE;

  let browser = await chromium.launch({
    headless: false,
    args: ['--no-sandbox', '--disable-blink-features=AutomationControlled'],
  });
  let context = await browser.newContext(contextOptions);
  let page = await context.newPage();

  // If the browser/page dies mid-run (observed 2026-07-07: an X error mid-scroll
  // triggered a reload that never came back, closing the page entirely and taking
  // the whole script down with it — nothing after that account ever scraped, and
  // the daily run silently stopped before watchlist/competitors/publish ever ran),
  // relaunch a fresh browser so the remaining accounts still get processed instead
  // of one account's crash aborting everything downstream.
  async function relaunchBrowser() {
    console.log('  Browser/page appears dead — relaunching a fresh one...');
    try { await browser.close(); } catch {}
    browser = await chromium.launch({
      headless: false,
      args: ['--no-sandbox', '--disable-blink-features=AutomationControlled'],
    });
    context = await browser.newContext(contextOptions);
    page = await context.newPage();
  }

  const failedAccounts = [];

  try {
    // Verify logged in
    await page.goto('https://x.com/home', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    const isLoggedIn = await page.$('[data-testid="SideNav_AccountSwitcher_Button"]');
    if (!isLoggedIn) {
      console.log('Not logged in. Please run the main scraper first to save a session.');
      process.exit(1);
    }

    for (const handle of INDIVIDUAL_ACCOUNTS) {
      try {
        await scrapeOneAccount(page, handle);
      } catch (err) {
        console.error(`  [!] ${handle} failed: ${err.message}`);
        failedAccounts.push(handle);
        // A page/browser closure kills every subsequent page.* call the same
        // way, so detect that specifically and recover instead of letting it
        // silently take out every account after this one.
        if (page.isClosed() || /Target page|context or browser has been closed/i.test(err.message)) {
          try {
            await relaunchBrowser();
          } catch (relaunchErr) {
            console.error(`  [!] Could not relaunch browser: ${relaunchErr.message}. Aborting remaining accounts.`);
            break;
          }
        }
      }
    }

    if (failedAccounts.length) {
      console.log(`\nCompleted with failures on: ${failedAccounts.join(', ')}`);
    }
  } catch (err) {
    console.error('Error:', err.message);
    if (!page.isClosed()) {
      await page.screenshot({ path: 'error-screenshot.png' }).catch(() => {});
    }
  } finally {
    await browser.close().catch(() => {});
  }

  if (failedAccounts.length) process.exitCode = 1;
}

async function scrapeOneAccount(page, handle) {
  const cleanHandle = handle.replace('@', '');
  const csvFile = path.join(CSV_DIR, `${cleanHandle}.csv`);

  // Load existing rows, keyed by tweetUrl, so we can refresh stats in place.
  // Self-heals duplicate rows left behind by prior overlapping scrape runs:
  // if a URL already appeared, keep whichever row has higher views and
  // drop the other instead of silently leaving both in the file.
  const existingByUrl = new Map(); // url -> { cols, idx }
  const existingLines = [];
  const droppedIdx = new Set();
  if (fs.existsSync(csvFile)) {
    const lines = fs.readFileSync(csvFile, 'utf8').split('\n').filter(l => l.trim());
    let dupesFound = 0;
    for (const line of lines.slice(1)) {
      const cols = parseCsvLine(line);
      const idx = existingLines.push(line) - 1;
      const url = unquote(cols[7]);
      if (!url) continue;
      const prior = existingByUrl.get(url);
      if (!prior) {
        existingByUrl.set(url, { cols, idx });
        continue;
      }
      dupesFound++;
      const priorViews = parseFollowerCount(prior.cols[1]) || 0;
      const thisViews = parseFollowerCount(cols[1]) || 0;
      if (thisViews > priorViews) {
        droppedIdx.add(prior.idx);
        existingByUrl.set(url, { cols, idx });
      } else {
        droppedIdx.add(idx);
      }
    }
    if (dupesFound) console.log(`  ${handle}: cleaned up ${dupesFound} duplicate row(s) found in CSV.`);
    console.log(`${handle}: ${existingByUrl.size} existing tweets in CSV.`);
  }

  // Scrape recent timeline (fewer scrolls for daily top-up)
  console.log(`${handle}: scraping recent tweets...`);
  const maxScrolls = 15;
  const tweets = await scrapeTimeline(page, handle, maxScrolls);

  // Split into: brand-new tweets to enrich+append, and existing tweets
  // (posted within the last 7 days) whose stats we refresh in place —
  // views/likes keep climbing for days after posting, so a one-time
  // scrape at first sight was undercounting them.
  const now = Date.now();
  const seenThisBatch = new Set();
  const newTweets = [];
  let updatedCount = 0;

  for (const t of tweets) {
    if (t.isRetweet) continue;
    if (!t.tweetUrl) continue;
    const urlHandle = t.tweetUrl.split('/')[3]?.toLowerCase();
    if (urlHandle !== cleanHandle.toLowerCase()) continue;
    if (seenThisBatch.has(t.tweetUrl)) continue;
    seenThisBatch.add(t.tweetUrl);

    const existing = existingByUrl.get(t.tweetUrl);
    if (existing) {
      const age = now - new Date(t.timestamp).getTime();
      if (age <= UPDATE_WINDOW_MS) {
        existing.cols[1] = t.views || '0';
        existing.cols[2] = t.likes;
        existing.cols[3] = t.retweets;
        existing.cols[4] = t.replies;
        existing.cols[5] = t.hasImages ? 'yes' : 'no';
        existingLines[existing.idx] = existing.cols.join(',');
        updatedCount++;
      }
      continue;
    }
    newTweets.push(t);
  }

  // Always record follower count regardless of new/updated tweets
  const followerCount = await scrapeFollowers(page, handle);
  if (followerCount) recordFollowers(cleanHandle, followerCount);

  console.log(`  ${newTweets.length} new tweets, ${updatedCount} existing tweets refreshed.`);
  if (newTweets.length === 0 && updatedCount === 0 && droppedIdx.size === 0) {
    console.log(`  Nothing new, updated, or duplicated for ${handle}, skipping write.`);
    return;
  }

  let newRows = '';
  if (newTweets.length) {
    console.log(`  Enriching ${newTweets.length} new tweets...`);
    const enriched = enrichTweets(newTweets);
    newRows = enriched.map(t =>
      [t.timestamp, t.views ?? '0', t.likes, t.retweets, t.replies,
       t.hasImages ? 'yes' : 'no',
       safe(t.keywords), safe(t.tweetUrl), safe(t.text), safe(t.translatedText ?? '')].join(',')
    ).join('\n');
  }

  const header = 'timestamp,views,likes,retweets,replies,hasImages,keywords,tweetUrl,text,translated_text\n';
  const survivingLines = existingLines.filter((_, i) => !droppedIdx.has(i));
  // Prepend new rows (newest first) then existing rows (refreshed in place)
  const combined = header
    + (newRows ? newRows + '\n' : '')
    + survivingLines.join('\n') + (survivingLines.length ? '\n' : '');
  fs.writeFileSync(csvFile, combined);
  console.log(`Updated csv/${cleanHandle}.csv (+${newTweets.length} new, ${updatedCount} refreshed, ${droppedIdx.size} duplicates removed, ${existingByUrl.size + newTweets.length} total)`);
}

main();
