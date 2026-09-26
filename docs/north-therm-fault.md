# The north_therm hardware fault

## Summary

The Pixel 8 Pro (`husky`) has a faulty temperature sensor path. The sensor is `north_therm`. At rest it reads too cold. At random times it reads a false 55 to 58 °C for less than 7 seconds. The thermal software treats these false readings as real heat. The result was "phone is too warm" notices, short stutters and, from 16 September, thermal shutdowns. The patched build (see [patched-build-history.md](patched-build-history.md)) removes the sensor from the thermal formulas. The sensor itself is not repaired.

## Symptoms

- From 15 September, System UI showed the `high_temp` notice ("phone is too warm") about 50 times per day. The phone was idle and cool.
- Sometimes a short stutter came with the notice. It never became a freeze.
- On 15 September the phone ran GrapheneOS build 2026091001, security patch level 2026-09-01. No root.
- From 16 September the phone did thermal shutdowns. On 21 September it did 5 shutdowns, about 3.5 minutes apart: boot, run, shut down.

## The sensor

| Item | Value |
|---|---|
| Name | `north_therm` |
| Kernel zone | `thermal_zone16` |
| Hardware | an NTC thermistor on the ADC of the S2MPG15 sub-PMIC (platform device `s2mpg15-spmic-thermal`) |
| Location | top of the phone, camera-bar region (inference, see below) |
| Kernel trips | one passive trip at 125 °C. No critical trip. |

**Location evidence.** Google's own thermal model gives `north_therm` the largest weight (0.14) in `VIRTUAL-BTS-WINDOW-PARTIAL`. That sensor window is the body-temperature IR sensor in the rear camera bar. The weight of `north_therm` is about 0 in every speaker formula. The speakers and USB-C port are at the bottom. No public teardown documents the sensor.

**Best-supported placement.** The Google Service BOM for the Pixel 8 Pro (V4.2) lists an ANT1 sub-PCB (part G949-00706-01). It also lists a ZIF flat-flex cable from ANT1 to the logic board ("DIECUT, KAPTON, ANT1PCB ZIF"). The iFixit logic-board guide shows a press connector in the top-left corner. The best-supported placement of `north_therm` is on the ANT1 sub-PCB, read through its ZIF flex and the top-left interconnect. This is an inference. No document gives this location.

## How a false reading causes a notice or a shutdown

The vendor file `/vendor/etc/thermal_info_config.json` defines virtual sensors as weighted sums of real sensors:

```
VIRTUAL-SKIN-SUB-4 = 0.9 × north_therm + 0.05 × soc_therm + 0.01 × neutral_therm + 0.73
VIRTUAL-SKIN       = MAX(VIRTUAL-SKIN-SUB-0 … SUB-10)
```

This formula reproduced the logged values to the decimal. `VIRTUAL-SKIN` has the type SKIN, which sets the thermal status of the whole phone:

| VIRTUAL-SKIN | Status | Effect |
|---|---|---|
| 39 °C | 1 | light throttling |
| 52 °C | 5, EMERGENCY | "too warm" notice. CPU clusters 1 and 2 limited to step 14, GPU to 11, TPU to 7, charging `chg_mdis` 26 |
| 55 °C | 6, SHUTDOWN | orderly shutdown by the framework |

A spike of `north_therm` to about 55 °C pushed `VIRTUAL-SKIN` to about 53 °C: status 5, the notice, and a short throttle. At about 57 °C or more, `VIRTUAL-SKIN` passed 55 °C and the framework shut the phone down. The board was at about 33 to 35 °C during these events.

## Evidence

**Captures on 15 September.**
- A 1-second poll of `dumpsys thermalservice` showed `north_therm` at 54.9 °C. All other sensors were at their cool baseline: soc 36.8, cam 32.1, usb 32.8, battery 32.1 °C.
- The other 8 thermistors were steady. Their largest jump between readings was 1.6 °C. The jump of `north_therm` was 37 °C.
- There were no kernel or ADC read errors. The sensor returned valid but false values. This points to hardware, not to a driver.
- Spikes also occurred with the screen off (3 of 9). The fault is spontaneous.
- Detection is event-driven. The HAL zone notice came 70 ms before each PowerUI event, so the count of about 8 per hour is a true count.

**Why it started on 15 September: software was excluded.**
- The September GrapheneOS releases (2026090500, 2026090700, 2026091000) contain no thermal, HAL or sensor changes.
- The build date of the phone matched 2026091000, which was active from about 11 September.
- No matching reports existed on the GrapheneOS tracker or forum.
- Note: `ro.runtime.firstboot` changes at each boot. It does not show when a build was installed.

**Heat and spike rate: warm-up test (15 September, 22:40 to 22:50).**
- An 8-thread load ran for 5 minutes. `soc_therm` reached 51 to 53 °C.
- There were zero spikes during the test and 30 minutes with no spike overall.
- Conclusion: board heat, screen-on, video and large power changes do not increase the spike rate.
- `north_therm` rose from 15.5 to 19.9 °C with the board. The sensor is alive and tracks temperature. Only its path is degraded.

**Heat and spike height.** The spike height increased with the resting temperature of the sensor:

| Rest reading of north_therm | Spike |
|---|---|
| 16.2 °C | 54.9 °C |
| 17.5 °C | 55.2 °C |
| about 19.7 °C | about 56.4 °C (VIRTUAL-SKIN 53.95 °C at 22:56 on 15 September, about 1 °C below shutdown) |

Heat does not make spikes more frequent, but it makes them higher. Thus the shutdown risk is higher when the phone is warm.

**Later readings.**
- On 18 September the board was warm (soc 47, battery 38 °C, charging). `north_therm` was stable at about 26 °C and tracked the board, but read about 11 °C below the adjacent `cam_therm` (37 °C). There was no shutdown that day.
- By 21 September the cold offset had grown to about 16 °C.

**Withdrawn claims.**
- "All spikes go straight to status 5, so the fault is bistable." Withdrawn: PowerUI does not log statuses 1 to 4. A real status-1 event produced no log line.
- "The USB drops on the evening of 15 September show a bad port." Withdrawn: GrapheneOS turns off USB data when the phone is locked. (A different fact, from 21 September: the USB link does drop when the phone moves on a cable.)
- "Humidity triggers the spikes." Demoted: 15 September was cold and dry, and the humid day (Sunday, 13 September) had no spikes.

## Shutdown history

| Date | Events |
|---|---|
| 15 September | 4 restarts, none thermal |
| 16 September | first thermal shutdown. The framework shut down at 08:50:49, and the bootloader recorded `shutdown,thermal` at 08:51:24. The battery read 35.2 °C 78 seconds before. A second thermal shutdown occurred at about 21:15. |
| 17 September | 1 thermal shutdown at about 16:50 |
| 18 September | no shutdown |
| 21 September | 5 thermal shutdowns, including 17:43, 17:47 and 19:04 |

The 16 September event was an orderly framework shutdown of a phone at about 35 °C. Implied `north_therm` spike: 57.7 °C or more. After the reboot, the phone showed the notice "Phone turned off due to heat".

## History and cause

**History.** On 7 August the phone fell into a sink for about 5 seconds. Then it was charged while the USB-C port was still wet. The phone failed. On each boot it showed an overheating message and shut down at the lock screen. A shop did a board-level micro-soldering repair of the charging circuit. The two bottom sensors near that repair (`usb_pwr_therm`, `charge_therm`) are the healthiest on the board.

**Best-fit cause (final assessment, 21 September): electrochemical migration.**
- The damage started when the phone charged with a wet port. Water, the charge voltage and ionic contamination together cause electrochemical migration and corrosion.
- The fault shows two signatures on one sensor path. A too-cold rest reading means added series resistance. A too-hot spike means a parallel leakage path. Series resistance alone can only read colder.
- One contaminated, electrochemically active joint explains both. It also explains the delay of about 5 weeks, the progression, and why only one high-impedance sensor line fails.
- The NTC and the ADC are alive, because the reading tracks temperature in both directions. So a one-time electrical "zap" is not the current mechanism.
- A badly seated connector after the repair can only add series resistance. It cannot cause hot spikes. It is at most a small contributor.

**Withdrawn framing.** Earlier notes said "delayed corrosion from the immersion". That was an overstatement. The dunk was short, and the insult was the charge with a wet port.

**Consequences for repair.** A reseat or cleaning can fail again, because the contamination can spread. A microscope inspection for corrosion or dendrites on the `north_therm` net is the definitive test. A desiccant test is a cheaper discriminator. For this test, keep the phone with silica gel or calcium chloride for 24 to 48 hours. Then compare the spike count with a normal cold day.

## Remaining risks after the patch

- **`cam_therm` now carries the weight of `north_therm`** (0.9 in `VIRTUAL-SKIN-SUB-4`). If the fault spreads to `cam_therm`, false spikes and shutdowns come back.
- **`quiet_therm` has the only kernel critical trip on the board (57 °C).** The kernel shuts the phone down at that trip, and the JSON patch cannot stop it. A fix needs an edited `dtbo` image (`avbroot --replace dtbo`).
- **A sensor that fails cold hides real heat.** This makes the overheating protection weaker.

## How to diagnose it again

If the phone shows heat warnings, stutters or shutdowns, do these steps:

1. Connect the phone over adb.
2. Poll `adb shell dumpsys thermalservice` about once per second. Read the section "Current temperatures from HAL".
3. Compare `north_therm`, `cam_therm` and `quiet_therm` with the other sensors.
4. Read the boot reasons with `adb shell getprop persist.sys.boot.reason.history`. A thermal shutdown shows `shutdown,thermal`.
5. Do not look for a cause in apps or load first.

Notes:
- `logcat` shows `pixel-thermal` raw-data lines only while a throttling loop is active.
- adb without root cannot read the thermal sysfs files or `dmesg`. SELinux blocks them.
- Once a month, do the same check to watch for spread of the fault.
