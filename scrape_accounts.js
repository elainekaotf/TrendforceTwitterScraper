require('dotenv').config();
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const SESSION_FILE = path.join(__dirname, 'session.json');
const CSV_DIR = path.join(__dirname, 'csv');
fs.mkdirSync(CSV_DIR, { recursive: true });

const INDIVIDUAL_ACCOUNTS = ['@TrendForce', '@technews_tw', '@dylan522p', '@jukan05', '@QQ_Timmy', '@SemiAnalysis_'];

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
      const csvFile = path.join(CSV_DIR, `${cleanHandle}.csv`);

      // Load existing tweet URLs from CSV so we don't re-enrich duplicates
      const existingUrls = new Set();
      let existingRows = '';
      if (fs.existsSync(csvFile)) {
        const lines = fs.readFileSync(csvFile, 'utf8').split('\n');
        existingRows = lines.slice(1).filter(l => l.trim()).join('\n'); // skip header
        for (const line of lines.slice(1)) {
          // tweetUrl is column 8 (index 7), quoted
          const match = line.match(/(?:^|,)"?(https?:\/\/[^",\n]+)"?/);
          // more robust: split by comma respecting quotes
          const cols = line.match(/("(?:[^"]|"")*"|[^,]*)/g) || [];
          const url = cols[7] ? cols[7].replace(/^"|"$/g, '') : '';
          if (url) existingUrls.add(url);
        }
        console.log(`${handle}: ${existingUrls.size} existing tweets in CSV.`);
      }

      // Scrape recent timeline (fewer scrolls for daily top-up)
      console.log(`${handle}: scraping recent tweets...`);
      const maxScrolls = 15;
      const tweets = await scrapeTimeline(page, handle, maxScrolls);

      // Filter to own original tweets not already in CSV
      const newTweets = tweets.filter(t => {
        if (t.isRetweet) return false;
        if (!t.tweetUrl) return false;
        const urlHandle = t.tweetUrl.split('/')[3]?.toLowerCase();
        if (urlHandle !== cleanHandle.toLowerCase()) return false;
        if (existingUrls.has(t.tweetUrl)) return false;
        existingUrls.add(t.tweetUrl); // dedup within this scrape batch too
        return true;
      });

      console.log(`  ${newTweets.length} new tweets to add.`);
      if (newTweets.length === 0) {
        console.log(`  Nothing new for ${handle}, skipping.`);
        continue;
      }

      console.log(`  Enriching ${newTweets.length} new tweets...`);
      const enriched = enrichTweets(newTweets);

      const header = 'timestamp,views,likes,retweets,replies,hasImages,keywords,tweetUrl,text,translated_text\n';
      const newRows = enriched.map(t =>
        [t.timestamp, t.views ?? '0', t.likes, t.retweets, t.replies,
         t.hasImages ? 'yes' : 'no',
         safe(t.keywords), safe(t.tweetUrl), safe(t.text), safe(t.translatedText ?? '')].join(',')
      ).join('\n');

      // Prepend new rows (newest first) then existing rows
      const combined = existingRows
        ? header + newRows + '\n' + existingRows
        : header + newRows;
      fs.writeFileSync(csvFile, combined);
      console.log(`Updated csv/${cleanHandle}.csv (+${newTweets.length} new, ${existingUrls.size + newTweets.length} total)`);
    }

  } catch (err) {
    console.error('Error:', err.message);
    await page.screenshot({ path: 'error-screenshot.png' });
  } finally {
    await browser.close();
  }
}

main();
