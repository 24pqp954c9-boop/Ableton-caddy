# Ableton Caddy

Ableton Caddy is a local, read-only companion for Ableton Live. It reads the open set through the Ableton Live MCP server and suggests ideas and processing chains one channel at a time. Each suggestion gives you a reason to try the chain and something specific to listen for.

## Try it

Download or clone this repository and open `index.html` directly in your browser to preview a 124 BPM example set. No install or Live needed.

For a real set, first use Ableton MCP Link to install and activate the **AbletonMCP** Control Surface. Keep Live open with a set loaded. With `uv` installed, check the bridge and launch Caddy. The doctor command also accepts `--user-library` if your library has moved.

```sh
uvx mcp-server-ableton-live@1.8.1 doctor --json
uv run caddy.py
```

Prefer an app to terminal commands? On GitHub, download the macOS build from [Releases](https://github.com/24pqp954c9-boop/Ableton-caddy/releases/latest), unzip it and drag **AbletonCaddy.app** to Applications. Or build it yourself on a Mac:

```sh
uv run make_app.py --zip
cp -R AbletonCaddy.app /Applications/
```

Double-click **Ableton Caddy** to start the companion on port 8743 and open its tab. Opening it again while it runs just opens another tab. Quit it from the Dock icon (or Activity Monitor), or use Ctrl+C when run from a terminal. The app drives the bridge with `uv`, so install [uv](https://docs.astral.sh/uv/) first if you don't have it (the app shows an alert and quits if it can't find uv); downloaded bundles are unsigned — right-click → Open at Gatekeeper's first prompt.

The app opens a local browser tab. Choose a track, adjust its suggested role if needed, and select a focus. Refresh after adding or reordering devices in Live. The launcher and this integration target the same 1.8.1 server release as the existing setup app. End the local server with Ctrl+C. [Ableton Live MCP server](https://github.com/wstierhout/ableton-live-mcp)

## What it can do

| Focus | Example channel workflow | What to listen for |
| --- | --- | --- |
| Ideas | Try a one-bar drum variation, resample an Echo throw into a transition, split a bass into clean sub and moving harmonics, or map a Max for Live LFO to a synth filter. | Listen for a clear change between sections and a groove that still holds together. |
| Mixdown | Build a fader balance, check mono with Utility, inspect suspected overlap with Spectrum, and compare EQ Eight with a dynamic EQ such as TDR Nova or Pro-Q 4. | Audition the channels together. Use dynamic EQ when the problem appears intermittently and level-match the comparison. |
| Compression | Use Compressor or Glue Compressor for transient shaping, audition kick-to-bass ducking, level vocal phrases in stages, and compare Multiband Dynamics with a third-party multiband compressor. | Listen to the front of the hit, set release by the groove, and check whether the crossover or an extra stage changes the tone. |
| FX | Build a filtered Echo return, audition parallel Drum Buss or Saturator, duck a vocal reverb return, or automate chorus and reverb into a transition. | Check the dry signal against the return. Listen for tails between phrases and mono compatibility in parallel chains. |
| Workflow | Compare EQ placement around a compressor, save a macro-mapped FX Rack, and document or print channels that rely on installed VSTs or Max for Live devices. | Match loudness for A/B, keep a dry reference, and check that a saved rack is portable. |

Auto role matches common track names. Override it for unusual names or bus work. Overrides and your last focus persist across refreshes within the same origin: reliably in the app, which keeps the fixed port 8743. Run from a terminal with `uv run caddy.py` and the server picks a new random port at each start, so saved choices do not carry over between starts. Each suggestion card marks its device steps: ✓ the chain already holds that device (by name or by stock family word, e.g. EQ matching EQ Eight), or + not in chain when the step names a device and nothing in the chain matches it; third-party VST examples are labelled unverified because the snapshot cannot confirm them. Workflow steps such as faders, clip gain, duplicate clips, return tracks or saving a preset carry no marker. Returns are listed by name. **Export notes** downloads a Markdown document of every channel, its auto role, chain, and the listening experiments for the current focus. Nested rack chains, the Main track, and installed plug-in verification are outside this build.

Stock device availability depends on Live edition and Packs. Third-party VSTs are optional examples. Install and license them separately. The app only reads a snapshot when opened or refreshed and makes no changes to your set.

## Put a note in Live’s bottom-left Info View

1. Hover over or keyboard-focus a workflow card in Caddy. You can also click it.
2. Choose **Copy for Live Info View**.
3. In Live, toggle the Info View with **?** if it is hidden. Right-click a supported track, clip or device, choose **Edit Info Text**, and paste.
4. Hover over that item in Live to read the note. Save the Live Set to keep it.

This uses Live’s documented note workflow. Caddy’s live hover predictions currently appear on its own workflow cards. Live's public integration used here provides no verified way to inject predictions into the built-in Info View while the pointer moves across arbitrary native controls. [Ableton Live manual](https://www.ableton.com/en/manual/first-steps/#info-view)

## Release path

Ship Caddy as a separate companion first. The existing MCP Link installer handles the Remote Script and client setup. Caddy uses the same version behind a read-only MCP client and has a demo anyone can run. This lets the two apps release independently with a single Live bridge.

1. **Verify the live read.** Smoke-test a disposable Live 12 set on macOS and Windows. Compare the session snapshot with Live after renaming and reordering tracks, adding a rack, switching sets and disconnecting the Control Surface. Confirm that refreshing never modifies the set. *Done on macOS:* renames and an inserted track appear in the snapshot with track ids stable while indexes shift; Live's automatic track numbering and both undo steps restored the set byte-identical to baseline. Refresh issues no write calls. Remaining: adding a rack (must be done in Live by hand — the bridge cannot insert devices into tracks), switching sets, disconnecting the Control Surface, and the Windows pass.
2. **Improve device matching.** Read device class and rack structure where supported. Search Live’s Browser for suggestions and label available, unverified and unavailable devices separately. Offer native substitutes for unavailable VSTs, Packs and M4L assets. Preserve an explicit manual path when the Browser omits an installed plug-in.
3. **Expand the mixdown pass.** Offer a checklist across drums, bass, vocals, instruments, groups and returns. Show the evidence for each suggestion. Use supported meters or user-supplied reference audio with explicit opt-in, and keep signal measurements separate from listening hypotheses.
4. **Explore in-Live commentary.** Prototype an optional Max for Live device with annotated controls and a panel that follows validated selection events. Test how its own annotations appear in Info View and whether they can be updated at runtime. Keep the note-copy workflow available on editions without Max for Live. [Max for Live production guidelines](https://maxforlive.com/resources/M4L-Production-Guidelines.pdf)
5. **Preview chain edits.** Once real-set reads and scoping are verified, show a proposed insertion order and exact target. Re-read the target before applying, resolve devices against the current Browser, use undo grouping where supported, and report partial failures. Keep creative alternatives and listening checks visible after the edit.
6. **Package for release.** Package the companion only after physical Live tests. MCP Link can later link to Caddy from its successful connection check.
