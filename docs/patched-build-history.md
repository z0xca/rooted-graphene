# History of the patched build (15 to 24 September)

## Decisions before the patch

- **16 September.** A source build of GrapheneOS was judged too costly. It needs a build host with 32 GiB RAM and about 240 GiB disk, and a rebuild for each release.
- **21 September.** The shutdowns became frequent. The chosen path: patch the official GrapheneOS OTA, sign it with our own keys, and lock the bootloader to those keys. No source build.

## Method

- The tool is **avbroot** 3.34.1. It unpacks the official OTA, replaces partitions, and signs the result with our AVB key and OTA key.
- The patcher is **my-avbroot-setup** at commit `9161b3e13416790d7e6da21d9dac5a14bc724504`, by chenxiaolong (the author of avbroot, afsr and Custota). It was read in full before use: about 1,000 lines of Python, with no network code.
- Other tools: **afsr** 2.0.0 (edits ext4 file systems) and **custota-tool** 6.6. The Custota app module 6.6 was added. Each release zip was verified with the SSH signing key of chenxiaolong.
- Verified boot stays on. The boot state is yellow ("custom key") and not orange ("unlocked").

**The thermal edit.** Our module `norththermrewire.py` changes the two files `/vendor/etc/thermal_info_config.json` (22 formulas) and `/vendor/etc/thermal_info_config_charge.json` (4 formulas). In each formula that reads `north_therm`, it adds the coefficient of `north_therm` to `cam_therm`. Then it removes `north_therm` from the formula. The result is the same as "use the reading of `cam_therm` in place of `north_therm`".

Two earlier designs were rejected:
- **Alias `north_therm` to `cam_therm`.** Invalid, because `north_therm` is a real kernel zone and a `TriggerSensor` for 11 top-level models. The HAL requires that trigger sensors exist.
- **Set the coefficient to 0.** Not safe. The HAL reads every linked sensor before it applies the coefficients. One failed read makes the whole virtual sensor return ERROR. The fault is progressive, so the formulas must not read the sensor at all.

**Independent verification (21 September, a separate review).** Result: GO, about 95 % confidence. A live capture showed `north_therm` 54.94 °C and `VIRTUAL-SKIN` 52.56 °C, all through `VIRTUAL-SKIN-SUB-4`. Only `VIRTUAL-SKIN` can reach status 6. The kernel device tree (ZUMA HUSKY MP overlay) gives `north_therm` only a passive 125 °C trip, so the JSON edit is sufficient. The only kernel critical trip on the board is `quiet_therm` at 57 °C. With the patch, `VIRTUAL-SKIN` stays at 35 to 40 °C during the real spikes.

## The keys

- The keys are RSA-4096 and encrypted with passphrases.
- The private keys are `avb.key` and `ota.key`. The public files are `avb_pkmd.bin` (the boot-screen fingerprint) and `ota.crt`.

CAUTION: Do not lose `avb.key` or `ota.key`. Without them, a new update needs a bootloader unlock, and the unlock erases all data on the phone.

## The first implementation

The first implementation was a local project with one script for each step: keys, patch, verification, flash, soak test, lock and update. This fork replaced it.

## Reviews before the flash (21 September)

Two reviews found faults in the flash plan. All were corrected before the flash:
- `avbroot ota extract --fastboot` without `--all` extracts only boot, init_boot, system, vbmeta and vendor_boot. It does not extract `vendor`, which holds the fix. The flash script got `--all` and a check for each image.
- The phone ran 2026091901, a real GrapheneOS "security preview" release. It is newer than the stable 2026091900, and not the same release. An earlier note said that they were the same, and that note was wrong. The rollback check now compares the build date of the phone with the date of the OTA.
- The second slot (B) still held stock GrapheneOS. A bootloader locked to our key refuses that slot. So slot B had to receive our build by recovery sideload before the lock.
- The GrapheneOS setup wizard has the box "disable OEM unlocking" ticked by default. It must be unticked after each wipe.
- The property `sys.oem_unlock_allowed` does not exist on this build. The Settings switch and `fastboot flashing get_unlock_ability` are the correct checks.

## Flashing day (21 September, 21:10 to 21:55)

1. `40-flash.sh 2026091901` unlocked the bootloader (erase), flashed all partitions and installed our AVB key. The phone booted slot A.
2. On the phone, both thermal files were byte-identical to the verified build. `VIRTUAL-SKIN-SUB-4` read `cam_therm` 0.9, `soc_therm` 0.05, `neutral_therm` 0.01. No formula read `north_therm`.
3. **The soak test caught a real spike.** At 21:27:46 `north_therm` read 54.82 °C for two samples. `VIRTUAL-SKIN` stayed at 36.2 °C with status 0. On the stock build this reading gave status 5.
4. The first sideload to slot B failed at 66 % with "error 9 kDownloadTransferError", status 5. The cause was the USB link. The kernel log showed about 12 disconnects while the phone was held. The second attempt, with the phone flat on the table, completed with status 0.
5. `45-lock.sh` locked the bootloader (erase again). Result: locked, yellow boot state, `vbmeta` device state locked. The boot screen showed the fingerprint of our key.
6. After the lock, the GrapheneOS updater `app.seamlessupdate.client` was disabled again.

**Auditor.** The GrapheneOS Auditor app cannot pair with this phone. Its code accepts a self-signed (yellow) boot state only with GrapheneOS keys, and it reports "invalid verified boot key fingerprint" for ours. Auditor was dropped.

## Move to the fork (24 September)

The fork `z0xca/rooted-graphene` of `schnatterer/rooted-graphene` replaced the first implementation. It uses the same patcher commit and tool versions. See [fork.md](fork.md).
