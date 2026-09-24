# Trust anchors

`rooted-ota.sh` passes the GrapheneOS files to `patch.py --verify-public-key-avb/--verify-cert-ota`,
so a downloaded OTA is only patched if GrapheneOS signed it. A device without a file here fails the
build. After patching, `avbroot ota verify` checks the output against the `signing-*` files: the
public halves of our own keys, pinned here so a wrong or swapped secret fails the build.

| File | SHA-256 | How to check it yourself |
|---|---|---|
| `husky-avb_pkmd.bin` | `896db2d09d84e1d6bb747002b8a114950b946e5825772a9d48ba7eb01d118c1c` | Equals the Pixel 8 Pro hash published at <https://grapheneos.org/install/cli> |
| `grapheneos-ota.crt` | `1ab8eeccd9357a5526c51dda37a5647b7c95276befb0684beb69bff691ee4bdd` | The only cert in `/system/etc/security/otacerts.zip` of a stock GrapheneOS husky build whose vbmeta verifies against the key above; also equals `META-INF/com/android/otacert` in the official OTA. `CN=GrapheneOS`, SHA-256 fingerprint `FA:3D:6F:FE:48:05:16:BF:AA:AF:9F:74:3A:48:5F:64:5A:C0:CE:2A:E7:77:AA:70:F7:E3:8B:2F:E6:41:EC:C2` |
| `signing-avb_pkmd.bin` | `c3ef1787cd19af246bb93081221a976bbf18a24ce24773e119872308d4082482` | Our AVB public key: the fingerprint the phone's yellow boot screen shows |
| `signing-ota.crt` | `111a37b0a6eef6de1ced681ec0f45152845dd8123ad1bfbe8248391eb140be63` | Our OTA certificate, matching the `CERT_OTA_BASE64` secret |

```bash
sha256sum trust/*
```
