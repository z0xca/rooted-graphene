# The fork z0xca/rooted-graphene

## Purpose

This fork of [schnatterer/rooted-graphene](https://github.com/schnatterer/rooted-graphene) builds rootless GrapheneOS OTAs for one Pixel 8 Pro (`husky`). Each OTA includes the `north_therm` fix. Upstream pins the same patcher commit and tool versions as the first build.

## Changes from upstream

| Change | Files |
|---|---|
| The build verifies the downloaded OTA with the GrapheneOS keys (`patch.py --verify-public-key-avb`, `--verify-cert-ota`) | `rooted-ota.sh`, `trust/husky-avb_pkmd.bin`, `trust/grapheneos-ota.crt` |
| The build verifies each patched OTA with our public keys (`avbroot ota verify`) before the release | `rooted-ota.sh`, `trust/signing-avb_pkmd.bin`, `trust/signing-ota.crt` |
| The build applies the thermal module by default. `NORTH_THERM_REWIRE=false` turns it off | `rooted-ota.sh`, `modules/norththermrewire.py`, `patches/my-avbroot-setup-norththermrewire.patch` |
| A schedule builds husky rootless every 6 hours (`23 */6 * * *`, UTC) | `.github/workflows/release-husky.yaml` |
| The release workflow accepts `skip-rooted` from a calling workflow, and its default device is `husky` | `.github/workflows/release-single.yaml` |
| `actions/checkout` is pinned to `3d3c42e5aac5ba805825da76410c181273ba90b1` (v7.0.1) | both workflows |

`trust/README.md` gives the provenance of each key file. The GrapheneOS AVB key matches the Pixel 8 Pro hash published at grapheneos.org/install/cli. The GrapheneOS OTA certificate is the only certificate in the `otacerts.zip` of a stock husky build.

The module file has the same code tokens as the version of the first build. Only its comments and messages changed (Simplified Technical English). Its output on the stock thermal files is byte-identical. Its SHA-256 is therefore different from the earlier `9d57cea2…`.

## GitHub configuration

| Item | Value |
|---|---|
| Secrets | `KEY_AVB_BASE64`, `KEY_OTA_BASE64`, `CERT_OTA_BASE64`, `PASSPHRASE_AVB`, `PASSPHRASE_OTA` |
| Branches | `main`, and `gh-pages` (orphan branch, the OTA server data) |
| GitHub Pages | from `gh-pages`, root folder |
| Workflows | "Release husky" and "Release single device" on. "Renovate" off (it has no `RENOVATE_TOKEN`) |
| Custota update file | `rootless/husky.json` on the GitHub Pages site of this repository |

The thermal fix is on by default in `rooted-ota.sh`. An earlier version read it from a repository variable. When that variable was missing, a push build on 24 September built without the fix. No release was made.

## Release flow

1. The schedule starts "Release husky". GitHub sometimes drops a scheduled run. The 06:23 UTC run on 24 September never started.
2. The script reads `https://releases.grapheneos.org/husky-stable-security-preview`.
3. If a release asset for that version already exists, the run stops. Code changes therefore reach the phone with the next GrapheneOS release.
4. The patcher verifies the download with the GrapheneOS keys, applies Custota, OEMUnlockOnBoot and the thermal module, and signs the result.
5. `avbroot ota verify` verifies the result with `trust/signing-*`.
6. The script creates the GitHub release, uploads the zip and the `.csig`, and commits `rootless/husky.json` to `gh-pages`.

**First release (24 September, 11:57 UTC).** Commit `8dcff4b`. Asset `husky-2026091901-8dcff4b-rootless.zip`, 1537721612 bytes, `vbmeta` digest `781d215f…`. A download of the published zip was verified. `avbroot ota verify` with `trust/signing-*` passed, the `.csig` was valid, and both thermal files were byte-identical to the verified build.

**Rebuilds.** Two builds of the same version are not bit-identical. After a forced rebuild, Custota therefore offers the same version again as an update.

**Download host.** The GitHub release host answers explicit byte ranges with 206. It answers suffix ranges (`bytes=-N`) with 501. Custota and `update_engine` use explicit ranges, so this has no effect.

**Known behavior of upstream.** Push builds run `. rooted-ota.sh && createRootedOta && createOtaServerData`. Bash ignores `errexit` inside a function that is not the last command of an `&&` list. So a failure inside `createRootedOta`, a failed verification included, does not stop a push build. The release path `. rooted-ota.sh && createAndReleaseRootedOta` stops at the first failure, so no release can pass a failed verification. An attempt to change the push line broke push builds and was reverted. Push builds depend on a fake token whose API error is ignored.

## Forced rebuild

To publish a change before the next GrapheneOS release, do these steps:

1. In the Actions tab, run "Release single device".
2. Set the device to `husky`.
3. Tick "skip rooted", "force build" and "force OTA server upload".
4. On the phone, install the update from Custota.

## Maintenance

- Once a month, click "Sync fork" on GitHub. This brings the version updates that upstream Renovate makes. It also keeps the repository active. GitHub turns off schedules after 60 days with no activity.
- For an email at each release, set Watch, then Custom, then Releases.
- Once a month, do the sensor check in [north-therm-fault.md](north-therm-fault.md).
- If you edit files in this repository by hand, turn off "trim trailing whitespace" and format-on-save. The upstream files have trailing spaces, and an editor that removes them makes merge conflicts.

## What erases the phone

- A normal update does not erase data. The phone installs to the other slot. If that slot does not boot, the phone returns to the old slot.
- Adding or removing a module, a sync from upstream, and a change between rootless and Magisk all come as normal updates.
- **A change or loss of `avb.key`** needs a bootloader unlock, and the unlock erases the phone.
- **A loss of `ota.key`** stops all updates until an unlock and a reflash.

## OEM unlocking and OEMUnlockOnBoot

- Each fork build includes OEMUnlockOnBoot. It turns OEM unlocking on again at each boot. This prevents the only state that makes a brick: bootloader locked, OS does not boot, and unlock not allowed.
- The costs of OEM unlocking are physical. A person with the phone can unlock the bootloader without the PIN. The unlock erases all data first, and the data is encrypted. A thief can erase and reuse the phone. GrapheneOS has no Google factory-reset protection. An "evil maid" can install a different OS signed with a different key. Then the data is gone, and the boot screen shows a different fingerprint.

## Rules for AI assistants in this repository

- Do not commit. Do not push. A human reviews every change and writes every commit message.
- Build and verify each change, then show the diff.
- Write the smallest possible diff. Prefer community-maintained tools and upstream mechanisms. The thermal module is the only accepted AI-written logic.
- Pin GitHub Actions to commit SHAs.
- Write prose in Simplified Technical English.
- Give plain commands, not wrapper scripts.
- Base suggestions on what the community ships or on a stated problem.

## Local test method

On a machine with rootless Podman and no subordinate UIDs, use these steps to run `patchOTAs` locally:

1. Set `CONTAINERS_STORAGE_CONF` to a file with the `vfs` driver and `ignore_chown_errors = "true"`.
2. Set `CONTAINERS_REGISTRIES_CONF` to a file with `unqualified-search-registries = ["docker.io"]`.
3. Put a test `docker` shim first in `PATH`. It runs `podman` and replaces the `chown -R` in the container command with `true`.
4. Run inside `nix-shell -p unzip jq`.
5. Unset `TMPDIR`, `TMP`, `TEMP` and `TEMPDIR`. The script copies the host environment into the container.
6. Use temporary keys. Do not use the real keys.
7. Call `. rooted-ota.sh; createRootedOta`. Do not use `&&`, or failures are ignored.

Results on 24 September: the output thermal files were byte-identical to the verified build. A zip signed with our key, presented as a GrapheneOS zip, was refused.
