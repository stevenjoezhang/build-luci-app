# build-luci-app

A reusable GitHub Actions Composite Action to compile an OpenWrt LuCI package into `.ipk` and `.apk` artifacts, extract the package version, and upload the results for downstream jobs or releases.

## Features

- **Automatic Version Extraction**  
  Reads `PKG_VERSION` from your `Makefile` and exposes it as an output.
- **SDK Download & Setup**  
  Fetches a legacy SDK plus an APK SDK from an official release or snapshot.
- **Compile for Multiple SDKs**  
  Builds your LuCI package against both SDKs in one run.
- **Artifact Collection & Upload**  
  Gathers compiled `.ipk` and `.apk` files plus a `version.txt` and uploads them via `actions/upload-artifact`.

## Inputs

| Name       | Required | Description                                                          |
|------------|----------|----------------------------------------------------------------------|
| `package`  | yes      | The folder name of your LuCI package (e.g. `luci-app-tailscale`).   |
| `sdk-url`  | yes      | URL to the legacy OpenWrt SDK archive (`.tar.xz` format).                  |
| `apk-sdk-version` | no | Set to `stable` to track the latest official release, or a fixed release such as `25.12.6`. Requires an APK-based release (25.12 or newer). Overrides both `snapsdk-*` inputs. Empty by default to preserve existing workflows. |
| `snapsdk-profiles-url` | no | URL to the snapshot `profiles.json` used to resolve the current SDK archive. Defaults to the x86/64 snapshot profiles. |
| `snapsdk-url` | no   | Fallback URL to the snapshot OpenWrt SDK archive (`.tar.zst` format). Used only when `snapsdk-profiles-url` is empty. |

Release SDK downloads use the official `.versions.json` index for `stable`, then
GNU Wget's filename filter to discover the x86/64 SDK for a Linux x86_64 host from
the release directory. No GCC version is hard-coded. The download must contain
exactly one matching archive and pass the official `sha256sums` check before
extraction. The checksum list is fetched over verified HTTPS; its detached
signature is not checked. A directory, download or checksum error stops the
build rather than silently switching releases. The resolved version and archive
URL are printed in the build log. Tracking `stable` does not pin future builds;
use an explicit version when needed.

## Outputs

| Name      | Description                                     |
|-----------|-------------------------------------------------|
| `version` | Version string parsed from your `Makefile`.    |

## Usage

Create a workflow in your repository, for example `.github/workflows/ci.yml`:

```yaml
name: Build & Release LuCI App

on:
  push:
    branches: [ master ]
    tags: [ 'v*' ]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Build LuCI Package
        id: build
        uses: stevenjoezhang/build-luci-app@v1
        with:
          package: luci-app-your-app
          sdk-url:  https://archive.openwrt.org/releases/19.07.0/.../OpenWrt-SDK.tar.xz
          apk-sdk-version: stable

      - name: Create GitHub Release
        if: startsWith(github.ref, 'refs/tags/')
        uses: softprops/action-gh-release@v2
        with:
          files: ./artifacts/*
          name: Release v${{ steps.build.outputs.version }}
          tag_name: ${{ github.ref_name }}
```
