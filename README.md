rooted-graphene
===

> This repository is a fork of [schnatterer/rooted-graphene](https://github.com/schnatterer/rooted-graphene).
> It builds rootless OTAs for one Pixel 8 Pro (`husky`).
>
> The fork adds these changes:
>
> - The build verifies the downloaded OTA with the GrapheneOS keys in [`trust/`](trust/README.md). If GrapheneOS did not sign the OTA, the build stops.
> - The build verifies the patched OTA with our public keys in [`trust/`](trust/README.md). If the signatures do not match, the release stops.
> - By default, the build applies [`modules/norththermrewire.py`](modules/norththermrewire.py). This module removes the faulty `north_therm` sensor from the vendor thermal configuration. Set `NORTH_THERM_REWIRE=false` to turn it off.
> - The patch in [`patches/`](patches/) adds this module to my-avbroot-setup.
> - A change to the fork applies from the next GrapheneOS release.
> - The workflow [`release-husky.yaml`](.github/workflows/release-husky.yaml) builds a rootless OTA for husky every 6 hours.
> - The workflows pin each GitHub Action to a commit SHA.
