name: RSA Sniper Bot
on:
  schedule:
    - cron: '*/5 * * * *'
  workflow_dispatch:
    inputs:
      scan_mode:
        description: 'Scan Depth'
        required: true
        default: 'Live (500 files)'
        type: choice
        options:
        - Live (500 files)
        - Deep Scan (10,000 files)
      test_ticker:
        description: 'OPTIONAL: Test Specific Ticker'
        required: false
        default: ''

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install edgartools requests packaging yfinance "hishel<0.1.0" python-dateutil
      - name: Run Sniper
        env:
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          SCAN_MODE: ${{ github.event.inputs.scan_mode }}
          TEST_TICKER: ${{ github.event.inputs.test_ticker }}
        run: python rsa_sniper.py
      - name: Save Memory
        run: |
          git config --global user.name "RSA-Bot"
          git config --global user.email "bot@github.com"
          git add seen_filings.txt || true
          git commit -m "Update memory" || true
          git push
