# build-luci-app

A reusable GitHub Actions Composite Action to compile an OpenWrt LuCI package into `.ipk` and `.apk` artifacts, extract the package version, and upload the results for downstream jobs or releases.

## Features

- **Automatic Version Extraction**  
  Reads `PKG_VERSION` from your `Makefile` and exposes it as an output.
- **SDK Download & Setup**  
  Fetches both legacy and snapshot OpenWrt SDKs.
- **Compile for Multiple SDKs**  
  Builds your LuCI package against both SDKs in one run.
- **Artifact Collection & Upload**  
  Gathers compiled `.ipk` and `.apk` files plus a `version.txt` and uploads them via `actions/upload-artifact`.

## Inputs

| Name       | Required | Description                                                          |
|------------|----------|----------------------------------------------------------------------|
| `package`  | yes      | The folder name of your LuCI package (e.g. `luci-app-tailscale`).   |
| `sdk-url`  | yes      | URL to the legacy OpenWrt SDK archive (`.tar.xz` format).                  |
| `snapsdk-url` | yes   | URL to the snapshot OpenWrt SDK archive (`.tar.zst` format).                |

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
        uses: stevenjoezhang/build-luci-app@v0
        with:
          package: luci-app-your-app
          sdk-url:  https://archive.openwrt.org/releases/19.07.0/.../OpenWrt-SDK.tar.xz
          snapsdk-url: https://downloads.openwrt.org/snapshots/.../openwrt-sdk.tar.zst

      - name: Create GitHub Release
        if: startsWith(github.ref, 'refs/tags/')
        uses: softprops/action-gh-release@v2
        with:
          files: ./artifacts/*
          name: Release v${{ steps.build.outputs.version }}
          tag_name: ${{ github.ref_name }}
```
