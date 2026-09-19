# One ledger, five boards, every device

Until now each board kept its bets in the browser you added them from. A bet
added on your phone stayed on your phone; the same board on your laptop showed
an empty ledger. This is the fix: one Google Sheet all five boards read and
write, so the bets, the results and the bankroll are the same everywhere.

Nothing about how the boards work changes. They still keep their own copy in the
browser, they still settle bets themselves, and they still work with no signal at
all — the sheet is where those copies meet, not something they depend on.

**Written for someone who has never opened Apps Script.** Ten minutes, once.

---

## What you end up with

- A Google Sheet named whatever you like, with three tabs: `bets`, `settings`
  and `devices`. Every bet is one row you can read and sort by hand.
- A **Sync** button in the corner of every board. Tap it to see the shared
  bankroll and how each board is doing.
- **One bankroll across all five.** Kelly sizing on every board reads the same
  number: what you started with, plus everything that has settled anywhere. A
  bad weekend on the props board shrinks the next MLB stake.
- **Ledger HQ** — a sixth page showing every bet from every board at once, with
  a bankroll curve, ROI by board, tier and market, and a way to settle a bet
  from your phone.

---

## Part 1 — the sheet (about 5 minutes)

**1. Make the sheet.** Go to [sheets.new](https://sheets.new). Name it
something you will recognise later, like `Bet Ledger`. Leave it empty.

**2. Open the script editor.** In the menu bar: **Extensions → Apps Script**.
A new tab opens with a code editor and a file called `Code.gs` containing a few
lines of sample code.

**3. Paste the code in.** Click once in the code area, select everything
(`Cmd+A` on a Mac, `Ctrl+A` on Windows) and delete it. Then open
[`apps-script/Code.gs`](apps-script/Code.gs) from this repository, copy the
whole file, and paste it in. Press `Cmd+S` / `Ctrl+S` to save. The tab title
changes from "Untitled project" once it saves.

**4. Run the setup.** Above the code there is a dropdown that says `doGet` or
`setup`. Choose **setup**, then press **Run**.

Google will stop you the first time and say **Authorization required**. This is
normal — you are giving your own script permission to edit your own sheet.

- Click **Review permissions**
- Choose your Google account
- You will see *"Google hasn't verified this app"*. That only means the script
  isn't published in Google's marketplace. Click **Advanced**, then
  **Go to Untitled project (unsafe)**
- Click **Allow**

The script runs and an **Execution log** appears at the bottom with a line like:

```
Your sync token:  3u8ka...
```

**Copy that token somewhere you can get at it from your phone.** It is the
password to your ledger. You will type it into each device once.

**5. Publish it.** Top right: **Deploy → New deployment**.

- Click the gear icon beside **Select type** and choose **Web app**
- Description: anything, e.g. `Shared bet ledger v1`
- **Execute as:** `Me`
- **Who has access:** `Anyone`
- Click **Deploy**, approve the second permission prompt the same way as before

You get a **Web app URL** ending in `/exec`. **Copy that too.** It and the token
are the two things every device needs.

> **On "Anyone".** It means anyone who knows that long URL can reach the script.
> The token is what actually lets them in, which is why it is never committed to
> any of these repositories — you type it into each device by hand. If you ever
> think it has leaked, run `resetToken` in the Apps Script editor and reconnect
> your devices.

---

## Part 2 — the boards (about 30 seconds each)

Upload the new files to each repository (see each board's `SYNC.md` for its
file list), wait for GitHub Pages to redeploy, then on each board:

1. Open the board. There is now a **Sync** pill in the bottom corner saying
   *Sync off*.
2. Tap it. Paste the **Web app URL** and the **token**. Give the device a name
   you will recognise in the `devices` tab — `iPhone`, `Work laptop`.
3. Tap **Connect**.

The pill turns green and says *Synced*. Any bets already in that browser are
pushed up on the first sync, so nothing is lost by connecting late.

Repeat on each board and each device. Same URL, same token, every time.

**Set your bankroll once.** In the Sync panel, put your real starting bankroll
in and save. Every board sizes its stakes off that number plus everything
settled since, so it only needs setting in one place.

---

## Part 3 — Your one-page KEVBOTBETS hub

The hub is already published at
**https://chillychilly14.github.io/bet-ledger-hq/**. Bookmark this one address.

1. Open **Ledger**, paste the same web app URL and token, and connect.
2. Use **MLB, NFL, NCAAF, Props** or **Ladder** in the navigation. Each board
   opens inside the page, keeping its own controls and automatic data updates.
3. Switch back to **Ledger** for the cross-sport view. The boards share the
   connection settings within the same browser on this GitHub Pages domain;
   connect separately on each device.
4. On iPhone: Safari **Share → Add to Home Screen** creates one KEVBOTBETS icon.

There is no need to create another repository or upload these files again.
For a fresh installation, copy the complete repository, including `hub.js`,
`hub.css`, `ledger.html` and the icons. GitHub Pages serves `main` from
`/ (root)`. The original standalone ledger remains available at `ledger.html`.

---

## How it behaves

**When you add a bet** it appears on the sheet within a couple of seconds and on
your other devices the next time they sync — on load, when you come back to the
tab, and every five minutes while a board is open.

**When a bet settles** — by the board grading it, or by you tapping Win on
Ledger HQ — the result travels the same way. A device that was switched off can
never push a stale "still pending" over a result the sheet already has; the
script refuses that write.

**When two devices change the same bet**, the later change wins.

**When a browser is cleared**, the board notices its ledger has emptied and puts
the bets straight back from the sheet rather than deleting them everywhere. It
tells you what happened and offers the other choice if you really did mean to
delete them.

**When you are offline**, everything still works. Bets go into the browser as
usual and are sent up the next time there is a connection.

---

## If something is wrong

**"That token was rejected."** The token has a typo, or you ran `resetToken`
after connecting. Copy it again from the Apps Script log and reconnect.

**"Could not reach the sheet."** Usually the URL. It must be the **Web app URL**
ending in `/exec` — not the address of the sheet, and not the address of the
script editor. Re-copy it from **Deploy → Manage deployments**.

**"Run setup() once in the Apps Script editor."** The deployment went out before
`setup` was run. Run it, then try again.

**Nothing appears on the sheet.** Check the `devices` tab — if your device is
listed there, it is reaching the script and the problem is elsewhere. If it is
not, the URL or token is wrong.

**You changed the code.** Editing `Code.gs` does not change what is live.
**Deploy → Manage deployments → the pencil icon → Version: New version →
Deploy.** The URL stays the same.

---

## What is on the sheet

The `bets` tab has one row per bet, with the columns you would expect — date,
board, event, market, selection, line, price, stake, tier, status, P/L — plus
three the sync uses: `updated_at` (which change is the latest), `deleted` (a bet
removed elsewhere), and `native_json`, which carries the board's own record of
the bet verbatim.

**You can edit the sheet by hand**, and boards will pick it up. Change `status`
to `Win`, or fix a `stake`, and bump `updated_at` to the current time so the
change is seen as newer than what the devices are holding. Leave `id` and
`native_json` alone.

The `settings` tab holds your starting bankroll. The `devices` tab is a log of
which devices have synced and when — useful only for telling whether a device is
actually talking to the sheet.
