# Load the recovery into one repository

## 1. Keep the recovery archive

Extract the download. Keep an untouched copy. Use the **repository** folder as
the new repository root. The accompanying **original-sources.zip** is a separate
backup; do not upload that archive as your website.

The package is account-independent. GitHub access and any account suspension
must be resolved with GitHub; importing source does not itself reinstate access.

## 2. Publish the repository

Target repository: **https://github.com/KEVBOTBETS/BETTINGHQ**

With GitHub Desktop signed into `KEVBOTBETS`:

1. Choose **File → Clone Repository → URL**, enter the target repository URL,
   and select an empty local destination.
2. Copy the contents of the extracted `repository` folder into that checkout.
   Include the hidden `.github` directory and `.gitignore`. Do not nest the
   `repository` folder itself inside the checkout. Preserve the checkout's `.git`.
3. Ensure the branch is named **main**. Review and commit the recovery files,
   then **Push origin**. If this new repository already has work you want to keep,
   review overlapping files before replacing them.
4. Public repositories can use GitHub Pages on GitHub Free. For a private
   repository, check your plan's Pages availability before publishing.

Before the first commit, review the source files and configuration. The recovery
contains model history, ticket archives and original bankroll configuration;
it does not include browser-only wagers or login credentials.

## 3. Turn on publication

In the repository on GitHub:

1. **Settings → Pages → Build and deployment → Source → GitHub Actions**.
2. Ensure Actions are enabled. The workflow requests the write permission needed
   to save public model history; organization policy must allow that permission.
3. **Actions → Check, refresh and publish → Run workflow → main → all**.
4. Wait for both **build** and **publish** to succeed. The run performs the model,
   pricing, ledger, browser and migration checks before publishing refreshed data.
5. Open the website URL shown by the publish job. It opens Weekly football.

The first push may run before Pages is enabled. After enabling Pages, run the
workflow again. No sportsbook credentials or paid API keys are required by the
included data pipelines. Upstream public feeds still need to be available.

## 4. Weekly use

- **Weekly football:** choose the seven-day window and NFL or College football.
  The default view includes research leans; **Model-qualified games** narrows it.
- **Moneyline:** choose a date, then select winners or use the predicted winners.
  Choices are saved in that browser and lock at game start.
- **NFL / NCAAF / MLB:** full model detail, simulator, source health and existing
  qualification rules.
- **Ledger:** reconnect your existing Google Sheet using its existing setup.
  A different account/domain has different browser storage. Do not clear the
  old browser's saved data before exporting or recovering anything you need.

The all-model schedule runs every three hours. Football gets extra hourly
refreshes at :53 during 15:00–23:59 UTC on Thursday through Sunday. GitHub cron
is best-effort; this is not a live in-game betting feed. Manually refresh before
using a slate if the source status is stale.

## 5. Check the installation

Confirm that all eight hub tabs open, each recovered sport has a recent source
timestamp, and the date matches the games you want. Check at least one matchup
against ESPN and your actual sportsbook's current price. A current winner
prediction is not a claim that any offered moneyline has positive value.

If a build fails, open its first failing step. It deliberately stops before
publishing unverified replacement data. The previous successful site remains.
If a source commit lands during a long build, that older build stops and the
newer queued run publishes, preventing old code from replacing new code.

Season is currently **2026**. For a new season, review both football settings
files, preseason priors and `MLB_SEASON` together; never relabel old history as
new-season predictions.

Official setup references:
- https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
- https://docs.github.com/en/pages/getting-started-with-github-pages/about-github-pages
