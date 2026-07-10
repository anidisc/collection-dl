#!/usr/bin/env python3
"""
PixelDrain downloader.

Uses the public PixelDrain REST API to download files.
Requires only a Referer header — no Cloudflare, no captcha.
"""
import os
import sys
import re
import argparse

import requests
from tqdm import tqdm


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/125.0.0.0 Safari/537.36',
}


def resolve_id(input_str):
    """
    Extract the file ID from a URL or use the raw string as-is.

    Args:
        input_str:  Full URL (e.g. https://pixeldrain.com/u/TssWGxaT)
                    or just the ID.

    Returns:
        File ID string.
    """
    input_str = input_str.strip().rstrip('/')
    if 'pixeldrain.com' in input_str:
        return input_str.split('/')[-1]
    return input_str


def get_filename(file_id, verify=True):
    """
    Fetch the file name from the /info endpoint.

    Args:
        file_id: The PixelDrain file ID.
        verify:  Whether to verify SSL certificates.

    Returns:
        Filename string, or None if unavailable.
    """
    try:
        r = requests.get(
            f'https://pixeldrain.com/api/file/{file_id}/info',
            headers=HEADERS, timeout=15, verify=verify,
        )
        r.raise_for_status()
        return r.json().get('name')
    except Exception:
        return None


def download_file(file_id, output_dir='.', verify=True):
    """
    Stream a file from PixelDrain to disk.

    The filename is taken from the Content-Disposition header returned
    by the API, falling back to the /info endpoint or the raw ID.

    Args:
        file_id:    The PixelDrain file ID.
        output_dir: Local directory to write into.
        verify:     Whether to verify SSL certificates.

    Returns:
        Path to the saved file.
    """
    os.makedirs(output_dir, exist_ok=True)

    api_url = f'https://pixeldrain.com/api/file/{file_id}'
    headers = {
        **HEADERS,
        'Referer': f'https://pixeldrain.com/u/{file_id}',
    }

    resp = requests.get(api_url, headers=headers, stream=True,
                        timeout=30, verify=verify)
    resp.raise_for_status()

    cd = resp.headers.get('Content-Disposition', '')
    m = re.search(r'filename="?([^"]+)"?', cd)
    filename = m.group(1) if m else None
    if not filename:
        filename = get_filename(file_id)
    if not filename:
        filename = file_id
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)

    filepath = os.path.join(output_dir, filename)
    if os.path.exists(filepath):
        print(f"[✓] {filename} — già scaricato")
        return filepath

    total = int(resp.headers.get('Content-Length', 0))
    with open(filepath, 'wb') as f, tqdm(
        total=total, unit='B', unit_scale=True, desc=filename, leave=True
    ) as bar:
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
                bar.update(len(chunk))

    print(f"[✓] Salvato: {filepath}")
    return filepath


def main():
    """CLI entry point: resolve ID, download file."""
    parser = argparse.ArgumentParser(description='Download file da PixelDrain')
    parser.add_argument('input', help='URL o ID (es. https://pixeldrain.com/u/TssWGxaT)')
    parser.add_argument('-o', '--output-dir', default='.', help='Directory di destinazione')
    parser.add_argument('--no-verify', action='store_true',
                        help='Disabilita verifica SSL (certificati self-signed)')
    args = parser.parse_args()

    verify = not args.no_verify
    file_id = resolve_id(args.input)
    print(f"[*] File ID: {file_id}")

    download_file(file_id, args.output_dir, verify=verify)


if __name__ == '__main__':
    main()
