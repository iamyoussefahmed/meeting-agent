# Meeting Agent

A self-hosted notetaker for Google Meet. Invite the bot's email address to a meeting and it will:

1. join the call about a minute before it starts (someone in the meeting admits it),
2. transcribe everyone, in English, Egyptian Arabic or a mix of both,
3. when the call ends, write English notes with Claude: summary, key points, decisions, action items with owners and due dates, and open questions,
4. email one copy of the notes, with the full transcript attached, to you plus every invitee on your company domain(s). External guests never get anything.

It runs on your own computer. Nothing is hosted in the cloud except the APIs it calls.

> **Mac or Windows?** Steps 1 to 8 below are written for a Mac. On Windows, read [Windows setup (WSL)](#windows-setup-wsl) first. It tells you exactly which steps change, and everything else is the same.

```
Google Calendar (bot's)  ──iCal feed──>  watcher (Python, this repo)
                                            │  sends the bot
                                            ▼
                                 Attendee (Docker, self-hosted)  ──audio──>  ElevenLabs Scribe
                                            │  transcript
                                            ▼
                                 Claude Sonnet  ──notes──>  Gmail (SMTP)  ──>  you + coworkers
```

| Piece | What it is | Cost |
|---|---|---|
| [Attendee](https://github.com/attendee-labs/attendee) | Open-source meeting bot that joins Meet in a headless browser | Free, runs in Docker |
| ElevenLabs Scribe | Speech to text, handles Arabic and code-switching well | Paid per audio hour (free tier exists) |
| Claude API (`claude-sonnet-5-5`) | Writes the notes | A few cents per meeting |
| Gmail SMTP | Sends the email | Free |
| Google Calendar secret iCal link | Tells the watcher which meetings the bot is invited to | Free, no OAuth or Google Cloud project |

---

## 1. What you need

- A Mac (Apple Silicon or Intel) with at least 16 GB RAM and ~20 GB free disk.
- [Homebrew](https://brew.sh).
- Accounts:
  - **Anthropic API** account with billing set up: https://console.anthropic.com
  - **ElevenLabs** account: https://elevenlabs.io
  - A **new Gmail account for the bot** (for example `yourname.notetaker@gmail.com`). People invite this address to meetings.
  - A Gmail account to **send** the notes from. It can be the bot account or your own Gmail. It must have 2-Step Verification on so you can create an App Password. (Brand-new Gmail accounts are sometimes blocked from turning on 2-Step Verification for a while. If that happens, send from your own Gmail.)

Install the tools:

```bash
brew install git python@3.12
```

```bash
brew install --cask docker
```

Open **Docker Desktop** from Applications once, finish its setup, and leave it running. In Docker Desktop > Settings > General, turn on **"Use Rosetta for x86_64/amd64 emulation on Apple Silicon"** (the Attendee image is amd64) and **"Start Docker Desktop when you sign in"**. In Settings > Resources, give it at least 6 GB of memory.

---

## 2. Get the code

```bash
git clone <this-repo-url> meeting-agent
cd meeting-agent
git clone https://github.com/attendee-labs/attendee.git attendee
```

The `attendee/` folder is the bot server. It is ignored by git so it stays a separate checkout. The setup was tested with Attendee commit `94976b9`. If a newer version breaks something, run `cd attendee && git checkout 94976b9`.

---

## 3. Start Attendee (Docker)

All commands below are run from the `meeting-agent` folder. `infra/attendee.sh` is a wrapper around `docker compose` that adds `infra/attendee.local.yaml`, which:

- adds **SeaweedFS**, a free local S3-compatible store, for recordings (Attendee normally needs AWS S3),
- sets `restart: unless-stopped` so everything comes back whenever Docker Desktop starts.

```bash
chmod +x infra/*.sh
infra/attendee.sh build
```

The build takes 5 to 15 minutes. Then generate Attendee's own secrets:

```bash
infra/attendee.sh run --rm attendee-app-local python init_env.py > attendee/.env
```

Open `attendee/.env` in a text editor and add these four lines at the end. The storage is only reachable from your Mac, but still pick your own secret value:

```
AWS_RECORDING_STORAGE_BUCKET_NAME=attendee-recordings
AWS_ACCESS_KEY_ID=attendee
AWS_SECRET_ACCESS_KEY=<make up a long random string>
AWS_DEFAULT_REGION=us-east-1
```

Start everything, set up the database and create the storage bucket:

```bash
infra/attendee.sh up -d
```

```bash
infra/attendee.sh exec attendee-app-local python manage.py migrate
```

```bash
infra/create_bucket.sh
```

Check that six containers are running (app, worker, scheduler, postgres, redis, s3):

```bash
docker ps
```

### Create your Attendee account and API key

1. Open http://localhost:8000 and **sign up** with any email and password. This account only exists on your Mac.
2. No email is actually sent. Get the confirmation link from the logs and open it in your browser:
   ```bash
   infra/attendee.sh logs attendee-app-local | grep confirm-email
   ```
3. Log in. Go to **API Keys**, create a key and copy it. It goes in `.env` as `ATTENDEE_API_KEY` (step 6).
4. Go to **Settings > Credentials** and add your **ElevenLabs** API key. In ElevenLabs (Profile > API Keys) the key only needs **Speech to Text** access.

---

## 4. Set up the Python app

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

---

## 5. Link the Google accounts

### 5a. The bot's calendar (which meetings to join)

Sign in to Google Calendar (https://calendar.google.com) **as the bot account**.

1. **Settings (gear) > General > Event settings > "Add invitations to my calendar"**: choose **"From everyone"**. Otherwise invites from people the bot has never emailed don't appear on its calendar.
2. **Settings > Settings for my calendars >** (the bot's calendar) **> Integrate calendar**. Copy **"Secret address in iCal format"**. It goes in `.env` as `BOT_CALENDAR_ICS_URL`.

Treat this link like a password: anyone who has it can read the bot's calendar. If it leaks, click **Reset** next to it in the same place and update `.env`.

### 5b. The sending Gmail (App Password)

Sign in to the Gmail account that will send the notes.

1. Turn on 2-Step Verification: https://myaccount.google.com/signinoptions/twosv
2. Create an App Password: https://myaccount.google.com/apppasswords. Name it "Meeting Agent" and copy the 16-character password. It goes in `.env` as `GMAIL_APP_PASSWORD`.

If the App Passwords page says it isn't available, 2-Step Verification is not on yet, or the account is a Workspace account whose admin has disabled App Passwords.

---

## 6. Fill in `.env`

Open `.env` in a text editor and fill in every value:

| Variable | What to put |
|---|---|
| `ATTENDEE_API_KEY` | Key from the Attendee dashboard (step 3) |
| `BOT_NAME` | Name shown in the meeting, e.g. `Jane's Notetaker` |
| `OWNER_NAME` | Your first name. The notes are written for you, and the bot's chat greeting uses it |
| `ANTHROPIC_API_KEY` | From https://console.anthropic.com > API Keys |
| `GMAIL_BOT_ADDRESS` | The Gmail that sends the notes (step 5b) |
| `GMAIL_APP_PASSWORD` | Its App Password (spaces are fine) |
| `BOT_CALENDAR_ICS_URL` | The bot's secret iCal address (step 5a) |
| `BOT_CALENDAR_EMAIL` | The bot address people invite. Leave empty if it is the same as `GMAIL_BOT_ADDRESS` |
| `EMAIL_TO` | Your email. You always get the notes |
| `COMPANY_DOMAINS` | Your company's email domain(s), comma-separated, e.g. `acme.com,acme.co.uk`. Invitees on these domains get the notes; nobody else does |

`.env` and `attendee/.env` are in `.gitignore`. Never commit or share them.

---

## 7. Test it

Check the calendar link works. This lists invited meetings with a Meet link in the next 7 days:

```bash
.venv/bin/python -m meeting_agent upcoming
```

Then send the bot to a test meeting by hand. Start a Google Meet, then run:

```bash
.venv/bin/python -m meeting_agent join https://meet.google.com/abc-defg-hij
```

Admit the bot when it asks to join, talk for a minute, then end the call. A few minutes later you should get the notes email. With `join`, only `EMAIL_TO` gets the notes.

---

## 8. Run it automatically

Install the watcher as a macOS login service. It checks the bot's calendar every minute, starts at login and restarts itself if it crashes:

```bash
infra/install_watcher.sh
```

Re-run that command after any change to `.env` or the code, so the watcher picks it up. To remove it:

```bash
infra/install_watcher.sh uninstall
```

### Day to day

- **To get notes for a meeting**, add the bot's email to the Google Calendar invite as a guest. The meeting needs a Google Meet link.
- **Admit the bot** when it knocks, about a minute before the start. It joins as a guest, so someone in the meeting has to let it in unless the meeting's access is set to Open. It waits up to 15 minutes in the waiting room.
- It posts a short chat message saying it is transcribing.
- It leaves on its own about a minute after it is the only one left, then emails the notes.
- **Keep the Mac awake, plugged in and online** during meetings. If the Mac sleeps, the bot can't join. In System Settings > Battery (or Energy), turn on "Prevent automatic sleeping when the display is off" when on power.

### Watching what it does

```bash
tail -f data/watcher.log | grep -v 'calendar check failed'
```

The `grep -v` hides network error lines, which can include the secret calendar link. Typical lines: `joining …`, `state: joined_recording` (in the call), `state: ended`, `notes emailed to …`.

Everything for each meeting (transcript JSON, readable transcript, notes JSON) is saved in `data/<bot-id>/`.

### If the bot doesn't leave after the meeting

The bot only leaves when it thinks it is alone. A phone or laptop left connected to the call keeps it there, and the notes won't be sent until it leaves. Make it leave with the bot ID from the log (it starts with `bot_`):

```bash
set -a; . ./.env; set +a; curl -X POST -H "Authorization: Token $ATTENDEE_API_KEY" http://localhost:8000/api/v1/bots/BOT_ID_HERE/leave
```

The watcher notices and sends the notes a minute or two later.

### Rebuild or resend notes

```bash
.venv/bin/python -m meeting_agent notes BOT_ID_HERE
```

This summarizes again and emails `EMAIL_TO` only.

---

## Windows setup (WSL)

The agent itself works on Windows: Docker, Attendee, the Python code and all the accounts are the same. What differs is **how you install the tools** (there is no Homebrew on Windows), **the terminal you type commands into**, and **how the watcher keeps running in the background** (there are no macOS LaunchAgents on Windows).

The easiest way is **WSL** (Windows Subsystem for Linux). It is free and built into Windows 10 and 11, and gives you an Ubuntu Linux terminal. Linux uses the same kind of commands as a Mac, so almost every command in this README works unchanged inside it.

**The golden rule:** unless a step says *PowerShell*, type every command into the **Ubuntu** terminal, and keep the project inside Ubuntu's own folders (`~/meeting-agent`), not on `C:\`. Files on `C:\` are much slower from Linux and can break the scripts.

You need Windows 10 (version 22H2) or Windows 11, 16 GB RAM, ~25 GB free disk, and administrator rights for the first step.

### W1. Install WSL and Ubuntu (do this first)

1. Click Start, type **PowerShell**, right-click **Windows PowerShell** and choose **Run as administrator**.
2. Run:
   ```powershell
   wsl --install -d Ubuntu
   ```
3. **Restart the PC** when it finishes.
4. After the restart an **Ubuntu** window opens by itself (if not, open **Ubuntu** from the Start menu). Wait for it to finish installing, then choose a Linux **username** and **password**. This password is only for Ubuntu; you need it whenever a command starts with `sudo`. Nothing shows on screen while you type it, which is normal.
5. Check it is WSL **version 2**. In PowerShell (no admin needed):
   ```powershell
   wsl -l -v
   ```
   The `VERSION` column must say `2`, and note the `NAME` (usually `Ubuntu`). If it says 1, run `wsl --set-version Ubuntu 2`.

From now on, "the Ubuntu terminal" means: Start menu > **Ubuntu**. (In **Windows Terminal** you can also pick Ubuntu from the tab dropdown.)

### W2. Install the tools (replaces step 1's Homebrew commands)

In the **Ubuntu** terminal:

```bash
sudo apt update && sudo apt install -y git python3 python3-venv python3-pip curl nano
```

Check Python is 3.10 or newer:

```bash
python3 --version
```

### W3. Install Docker Desktop for Windows (replaces step 1's Docker part)

1. Download **Docker Desktop for Windows** from https://www.docker.com/products/docker-desktop/ and install it. When the installer asks, keep **"Use WSL 2 instead of Hyper-V"** ticked.
2. Open Docker Desktop and finish its setup (you can skip signing in).
3. In Docker Desktop > **Settings**:
   - **General**: tick **"Use the WSL 2 based engine"** and **"Start Docker Desktop when you sign in to your computer"**.
   - **Resources > WSL integration**: turn on **Ubuntu**, then click **Apply & restart**.
4. Close and reopen the Ubuntu terminal, then check Docker works from inside it:
   ```bash
   docker ps
   ```
   An empty table (just column headings) is correct. "command not found" means the WSL integration switch for Ubuntu is off.

You do **not** need the Rosetta setting from step 1; that is Mac-only. A normal Intel or AMD Windows PC runs the Attendee image natively.

### W4. Get the code (step 2, inside Ubuntu)

In the Ubuntu terminal:

```bash
cd ~
git clone https://github.com/iamyoussefahmed/meeting-agent.git meeting-agent
cd meeting-agent
git clone https://github.com/attendee-labs/attendee.git attendee
```

Use git inside Ubuntu, not Git for Windows, so the scripts keep Linux line endings.

To see these files in Windows Explorer, type `explorer.exe .` in the Ubuntu terminal, or go to `\\wsl$\Ubuntu\home\<your-linux-username>\meeting-agent`.

### W5. Start Attendee (step 3, unchanged)

Follow step 3 exactly as written, in the Ubuntu terminal, from the `~/meeting-agent` folder. Two notes:

- To edit `attendee/.env`, use `nano attendee/.env`. Paste with right-click (or Ctrl+Shift+V), save with **Ctrl+O** then **Enter**, and exit with **Ctrl+X**. Or, if you use VS Code, type `code .` to open the folder in VS Code (it installs its WSL helper the first time).
- Open http://localhost:8000 in your normal Windows browser. It reaches Docker inside WSL automatically.

### W6. Set up the Python app (replaces step 4's first command)

Ubuntu calls Python `python3`, not `python3.12`:

```bash
cd ~/meeting-agent
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

### W7. Google accounts, `.env`, and testing (steps 5, 6 and 7, unchanged)

Do steps 5 and 6 as written. Edit `.env` with `nano .env` (or `code .`). Then run step 7's test commands in the Ubuntu terminal.

### W8. Run it automatically (replaces step 8)

`infra/install_watcher.sh` is Mac-only. On Windows, two files do the same job:

- `infra/run_watcher.sh` runs the watcher inside Ubuntu, writes to `data/watcher.log`, and restarts it 30 seconds after it stops for any reason.
- `infra/install_watcher_windows.ps1` creates a Windows **Task Scheduler** task named `MeetingAgentWatcher`. It starts `run_watcher.sh` hidden every time you log in to Windows. While it runs it also keeps WSL itself running, so you don't need an Ubuntu window open.

First, in the **Ubuntu** terminal, make the scripts runnable (skip if you already did this in step 3):

```bash
cd ~/meeting-agent
chmod +x infra/*.sh
```

Then, in **PowerShell** (normal, not administrator), install the task. The script lives inside WSL, so point PowerShell at it with its `\\wsl$` path. Replace `<your-linux-username>`:

```powershell
powershell -ExecutionPolicy Bypass -File "\\wsl$\Ubuntu\home\<your-linux-username>\meeting-agent\infra\install_watcher_windows.ps1"
```

You should see "Watcher installed and started". If you get **Access is denied**, run the same command in PowerShell opened as administrator. If your distro is not called `Ubuntu` (see W1 step 5) or you cloned somewhere other than `~/meeting-agent`, add `-Distro <name>` or `-RepoPath <path>` to the end of the command.

Check it is running, in the Ubuntu terminal:

```bash
pgrep -af "meeting_agent watch"
```

```bash
tail -n 5 ~/meeting-agent/data/watcher.log
```

You should see a line like `watching the bot's calendar every 60s`. You can also see the task in Start > **Task Scheduler** > Task Scheduler Library > `MeetingAgentWatcher`.

**After changing `.env` or the code**, restart the watcher so it picks up the change. In the Ubuntu terminal:

```bash
pkill -f "meeting_agent watch"
```

`run_watcher.sh` starts it again within 30 seconds, with the new settings.

**To remove it**, in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File "\\wsl$\Ubuntu\home\<your-linux-username>\meeting-agent\infra\install_watcher_windows.ps1" -Uninstall
```

### W9. Keep the PC awake

The bot can only join while the PC is on, awake, logged in and online. Docker Desktop must be running too (W3 turns on its auto-start).

- Windows 11: Settings > **System > Power & battery > Screen and sleep**, set **"When plugged in, put my device to sleep after"** to **Never**.
- Windows 10: Settings > **System > Power & sleep**, set **Sleep, When plugged in** to **Never**.
- On a laptop, also set **"When I close the lid"** to **Do nothing** (Control Panel > Power Options > Choose what closing the lid does) if you plan to close it during meetings.
- Signing out of Windows stops the watcher. Locking the screen (Win+L) is fine.

### Everything else

"Day to day", "Watching what it does", "If the bot doesn't leave", "Rebuild or resend notes" and "Troubleshooting" all work the same. Run their commands in the Ubuntu terminal from `~/meeting-agent`. Windows-specific problems:

| Problem | Fix |
|---|---|
| `wsl --install` says virtualization is not enabled | Turn on virtualization (Intel VT-x / AMD-V or SVM) in the PC's BIOS/UEFI settings, then try again. |
| `docker: command not found` in Ubuntu | Docker Desktop > Settings > Resources > WSL integration > turn on Ubuntu > Apply & restart, then reopen Ubuntu. |
| `$'\r': command not found` when running a script | The files were cloned with Windows Git and got Windows line endings. Delete the folder and clone again inside Ubuntu (W4). |
| `install_watcher_windows.ps1 cannot be loaded because running scripts is disabled` | Use the full command from W8, which includes `-ExecutionPolicy Bypass`. |
| Watcher not running after a restart | Check the `MeetingAgentWatcher` task exists in Task Scheduler and that you are logged in. Run W8's install command again. |
| http://localhost:8000 doesn't open | Docker Desktop isn't running, or the containers are stopped. Start Docker Desktop, then `infra/attendee.sh up -d` in Ubuntu. |

---

## Who gets the notes

- `EMAIL_TO` always.
- Every invitee (and the organizer) on the calendar event whose address is exactly on one of `COMPANY_DOMAINS`, **whether or not they attended**.
- Never anyone else: external guests, people who joined without an invite, or the bot itself.
- All recipients are on one shared email.
- If nothing was transcribed (the bot wasn't admitted, or the meeting had no speech), only `EMAIL_TO` gets a short "no speech captured" notice.

Meetings started with `join` (not from the calendar) only go to `EMAIL_TO`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `upcoming` shows nothing | Check the bot is on the invite's guest list (watch for typos), that the event has a Meet link, and that "Add invitations" is "From everyone" (step 5a). |
| Bot never knocks | Is the watcher running (`launchctl list \| grep meetingagent`)? Is Docker Desktop running (`docker ps`)? Was the Mac awake? Check `data/watcher.log`. |
| Email not sent, log shows an SMTP auth error | Wrong `GMAIL_APP_PASSWORD`, or 2-Step Verification was turned off (which deletes App Passwords). |
| "No speech captured" email although people talked | The bot was in the call but got no audio. Check the bot in the Attendee dashboard (http://localhost:8000). It happens occasionally; a recording of the call is kept there. |
| Bot shows `fatal_error` | Open the bot in the Attendee dashboard to see why. Often the Meet link was wrong or the bot was denied entry. |
| Attendee stopped after a restart | Start Docker Desktop. The containers come back by themselves. Or run `infra/attendee.sh up -d`. |
| `calendar check failed` lines in the log | Usually Wi-Fi or sleep. The watcher tries again every minute. |

Useful Docker commands:

```bash
infra/attendee.sh ps
```

```bash
infra/attendee.sh logs -f attendee-worker-local
```

```bash
infra/attendee.sh down
```

---

## Project layout

```
meeting_agent/
  __main__.py         CLI: watch, upcoming, join, notes
  config.py           reads .env
  calendar_watch.py   reads the bot's iCal feed, decides what to join
  attendee_client.py  Attendee REST API (create bot, state, transcript, chat)
  pipeline.py         one meeting end to end, and who gets the notes
  summarize.py        Claude prompt and the notes structure
  emailer.py          HTML email and Gmail SMTP
infra/
  attendee.sh           docker compose wrapper for the Attendee stack
  attendee.local.yaml   compose overrides (local S3, auto restart)
  create_bucket.sh      creates the recordings bucket
  install_watcher.sh    installs the watcher as a LaunchAgent (Mac)
  run_watcher.sh        runs the watcher and restarts it if it stops (Windows/WSL)
  install_watcher_windows.ps1  starts run_watcher.sh at Windows login (Task Scheduler)
.env.example          all settings, documented
```

## Privacy and security

- Tell people the meeting is being transcribed. The bot posts a chat message when it joins, but check what your company and local law require.
- Audio goes to ElevenLabs for transcription and the transcript goes to Anthropic for the notes. Recordings and transcripts stay on your Mac in Docker volumes and `data/`.
- Secrets live only in `.env` and `attendee/.env`. Both are git-ignored.

## Limits

- The bot joins as an anonymous guest, so it has to be admitted. Signed-in bots need Google Workspace with SAML SSO.
- It runs only while your computer is on and awake.
- Google Meet only.
