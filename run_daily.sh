#!/bin/bash
cd /Users/elainekao/TrendforceTwitterScraper
npm run scrape
npm run scrape:watchlist
npm run scrape:competitors

# RSS citation crawler — no browser needed, runs fast
node /Users/elainekao/google-citations/rss-crawler.js
