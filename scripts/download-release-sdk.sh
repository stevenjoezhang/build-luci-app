#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <stable|release-version> <destination>" >&2
    exit 1
fi

version=$1
destination=$2
host=https://downloads.openwrt.org

if [ "$version" = stable ]; then
    version=$(curl --fail --silent --show-error --location --proto '=https' \
        --connect-timeout 30 --retry 2 "$host/.versions.json" |
        jq -er '.stable_version | strings')
fi

if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Invalid stable release version: $version" >&2
    exit 1
fi

base_url="$host/releases/$version/targets/x86/64/"
download_dir=$(mktemp -d)
trap 'rm -rf "$download_dir"' EXIT

echo "Downloading OpenWrt $version SDK from $base_url"
# Wget discovers the archive from directory links, without assuming a GCC version.
wget --recursive --level=1 --no-parent --no-directories --https-only \
    --accept="openwrt-sdk-${version}-x86-64_*.Linux-x86_64.tar.zst" \
    --directory-prefix="$download_dir" --timeout=30 --tries=3 --no-verbose \
    "$base_url"

shopt -s nullglob
archives=("$download_dir"/openwrt-sdk-"$version"-x86-64_*.Linux-x86_64.tar.zst)
if [ "${#archives[@]}" -ne 1 ]; then
    echo "Expected exactly one SDK archive, found ${#archives[@]}" >&2
    exit 1
fi
archive=${archives[0]}
filename=${archive##*/}

# The checksum list verifies the selected file; it is not used to discover it.
curl --fail --silent --show-error --location --proto '=https' \
    --connect-timeout 30 --retry 2 "${base_url}sha256sums" \
    --output "$download_dir/sha256sums"
checksum=$(awk -v file="$filename" \
    '$2 == file || $2 == "*" file { print $1 }' "$download_dir/sha256sums")
if [[ ! "$checksum" =~ ^[[:xdigit:]]{64}$ ]]; then
    echo "Missing, invalid or duplicate SHA-256 entry for $filename" >&2
    exit 1
fi
(
    cd "$download_dir"
    printf '%s  %s\n' "$checksum" "$filename" | sha256sum --check -
)

mkdir -p "$destination"
tar --zstd -xf "$archive" --strip-components=1 -C "$destination"
echo "Installed verified SDK: ${base_url}${filename}"
