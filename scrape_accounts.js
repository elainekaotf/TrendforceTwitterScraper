require('dotenv').config();
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const SESSION_FILE = path.join(__dirname, 'session.json');
const CSV_DIR = path.join(__dirname, 'csv');
fs.mkdirSync(CSV_DIR, { recursive: true });

const INDIVIDUAL_ACCOUNTS = ['@technews_tw'];

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
    // Verify logged in
    await page.goto('https://x.com/home', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    const isLoggedIn = await page.$('[data-testid="SideNav_AccountSwitcher_Button"]');
    if (!isLoggedIn) {
      console.log('Not logged in. Please run the main scraper first to save a session.');
      process.exit(1);
    }

    for (const handle of INDIVIDUAL_ACCOUNTS) {
      const cleanHandle = handle.replace('@', '');
      const cacheFile = path.join(__dirname, `cache_${cleanHandle}.json`);

      let tweets;
      if (fs.existsSync(cacheFile)) {
        tweets = JSON.parse(fs.readFileSync(cacheFile, 'utf8'));
        console.log(`${handle}: loaded ${tweets.length} tweets from cache. Delete cache_${cleanHandle}.json to re-scrape.`);
      } else {
        tweets = await scrapeTimeline(page, handle, 200);
        fs.writeFileSync(cacheFile, JSON.stringify(tweets, null, 2));
      }

      // Keep only tweets where the URL contains the account's own handle (filters replies + others' tweets)
      const originalTweets = tweets.filter(t => {
        if (t.isRetweet) return false;
        if (!t.tweetUrl) return false;
        // Tweet URL format: https://x.com/handle/status/...
        const urlHandle = t.tweetUrl.split('/')[3]?.toLowerCase();
        return urlHandle === cleanHandle.toLowerCase();
      });
      console.log(`  Filtered out ${tweets.length - originalTweets.length} retweets. ${originalTweets.length} original tweets remain.`);
      console.log(`  Enriching ${originalTweets.length} tweets (translation + keywords)...`);
      const enriched = enrichTweets(originalTweets);

      const header = 'timestamp,views,likes,retweets,replies,hasImages,keywords,tweetUrl,text\n';
      const rows = enriched.map(t =>
        [t.timestamp, t.views ?? '0', t.likes, t.retweets, t.replies,
         t.hasImages ? 'yes' : 'no',
         safe(t.keywords), safe(t.tweetUrl), safe(t.text)].join(',')
      ).join('\n');

      const csvFile = path.join(CSV_DIR, `${cleanHandle}.csv`);
      fs.writeFileSync(csvFile, header + rows);
      console.log(`Saved csv/${cleanHandle}.csv (${tweets.length} tweets)`);
    }

  } catch (err) {
    console.error('Error:', err.message);
    await page.screenshot({ path: 'error-screenshot.png' });
  } finally {
    await browser.close();
  }
}

main();
