<p align="center"><img src="icon.png" width="96" alt="Tok2Tube icon"></p>

# Tok2Tube

**Post your TikTok videos to YouTube Shorts, without the watermark, from a small desktop app.**

Paste links to your TikTok posts. Tok2Tube downloads the clean copy (no TikTok watermark), fills in the YouTube
title, description and tags from your TikTok caption, lets you edit them, and uploads to your channel as
Shorts. It runs on your PC with your own Google sign-in. There is no account, no subscription and no server in
between.

- Watermark-free downloads (through [yt-dlp](https://github.com/yt-dlp/yt-dlp)). A video that only comes with
  the watermark is flagged and not uploaded.
- The caption becomes the description, its first line the title and its hashtags the tags. You can edit
  every field before uploading.
- Private by default. Choose unlisted or public, or schedule a time.
- Several YouTube channels: **+ Add account** for each one, then pick which channel to upload to from the
  dropdown at the top. Every Google account you add must be a test user in your Google Cloud project (see
  the setup below). A Google account with brand channels asks which channel when you sign in.
- Remembers what it has posted on each channel, so nothing goes up twice. A **Posted** tab links each video to its TikTok
  and its YouTube copy.
- Warns you about the things that trip uploads up:
  - TikTok-library music, which YouTube may claim or mute;
  - videos over 3 minutes, which aren't Shorts;
  - landscape videos.

> Only use it for videos you made and own. Tok2Tube is not affiliated with TikTok, YouTube or Google.

## Install (Windows)

1. Install [Python 3.10+](https://www.python.org/downloads/) and tick **Add python.exe to PATH**.
2. Download this repo (**Code → Download ZIP**) and unzip it somewhere permanent, e.g. `Documents\Tok2Tube`.
3. Double-click **`install.bat`**. It sets up the app in that folder and puts a **Tok2Tube** shortcut on your
   desktop.

Run `install.bat` again any time to update the packages. yt-dlp updates often, which keeps TikTok downloads
working.

On macOS or Linux, run `python -m venv .venv && .venv/bin/pip install -r requirements.txt`, then
`.venv/bin/python -m tok2tube`.

## One-time Google setup

YouTube only accepts uploads from an app that you register yourself, in your own free Google Cloud project.
It takes about 10 minutes, once:

1. Go to [console.cloud.google.com](https://console.cloud.google.com/) and create a project (any name).
2. **APIs & Services → Library**: search **YouTube Data API v3** and click **Enable**.
3. **APIs & Services → OAuth consent screen** (also called *Google Auth Platform*):
   - Choose **External**, give the app a name, and enter your email as the support and contact address.
   - Under **Audience → Test users**, click **+ Add users** and add the Google account that owns your
     YouTube channel. Without this the sign-in stops at *"Access blocked … has not completed the Google
     verification process"*.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**: application type **Desktop app**
   → **Create** → **Download JSON**.
5. Open Tok2Tube → **Settings → Choose client_secret.json…**, pick the file you downloaded, then click
   **+ Add account**.
   - Google shows *"Google hasn't verified this app"*. That's your own app, so click **Advanced → Go to …**.
   - Windows sometimes saves the file as `client_secret.json.json`. Tok2Tube doesn't mind the name.

While your app is in **Testing**, Google ends the sign-in after 7 days; Tok2Tube tells you, and you click
**Sign in** again. To avoid that, fill in the **Branding** page and click **Publish app** (no review is needed
for your own account).

## Use

1. Paste one or more TikTok links (one per line) and click **Fetch**.
2. Check each card: the title, description, tags, privacy, and an optional schedule (`YYYY-MM-DD HH:MM`, your
   local time).
3. Tick the ones to post, then click **Upload checked to YouTube**.

## Where your data is

Nothing personal is stored next to the code. Your Google client file, your sign-in token, the downloads and
the posted history live in `%APPDATA%\Tok2Tube` (**Settings → Open data folder**). Delete that folder to
remove everything. **Sign out** removes the selected channel's sign-in.

## Limits

- TikTok changes its site often. If downloads stop working, run `install.bat` again to update yt-dlp.
  If a download fails with *"Unexpected response from webpage request"*, the browser-impersonation package
  (`curl_cffi`) is missing: `install.bat` installs it.
- YouTube's API caps uploads per project per day. You can see your quota under **APIs & Services → Quotas**.
- Music added from TikTok's sound library is licensed for TikTok, not YouTube. Expect a Content ID claim or
  muted audio on those.

## Licence

MIT. See [LICENSE](LICENSE).
