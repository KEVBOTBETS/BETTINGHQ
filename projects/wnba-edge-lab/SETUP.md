# Setup

1. Create a GitHub repository named `wnba-edge-lab`.
2. Upload this package to the repository root and commit to `main`.
3. In **Settings → Pages**, choose **GitHub Actions** as the source.
4. Push a change or run **Refresh and deploy WNBA Edge Lab** from Actions.

No feed credentials, spreadsheet, copied odds or slate file is required. The
scheduled workflow refreshes the public ESPN WNBA feeds automatically, commits
only updated real-data state, and deploys `site/` to GitHub Pages.

For local verification:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m pipeline.build
```

The offline option uses only the latest successfully fetched real-data cache:

```bash
python -m pipeline.build --offline
```

## Using My Ledger

1. Open **Best Bets** and verify the displayed price is still available at the
   named sportsbook.
2. If you place the wager, enter the amount you actually risked and click
   **Add to My Ledger**.
3. Open **My Ledger** to review pending and settled wagers. Model picks you did
   not confirm never appear there.
4. Use **Export JSON** for a restorable backup or **Export CSV** for a
   spreadsheet copy. Browser storage is device-specific.
