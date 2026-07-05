#!/usr/bin/env python3
"""
MediaFire downloader.

Accepts a MediaFire page URL or a file key and produces a direct download
link, then downloads the file with a progress bar.
"""
import os
import sys
import re
import argparse
import time
from urllib.parse import urlparse, unquote

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# Standard browser headers used for all requests to MediaFire.
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) '
                  'Gecko/20100101 Firefox/131.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

MEDIAFIRE_DOMAIN = 'mediafire.com'


def resolve_url(input_str):
    """
    Normalise a user-supplied URL or file key into a full MediaFire page URL.

    Args:
        input_str: A URL containing 'mediafire.com' or a 13+-char alphanumeric key.

    Returns:
        Full MediaFire page URL.

    Raises:
        ValueError if the input does not match any known pattern.
    """
    input_str = input_str.strip()
    if MEDIAFIRE_DOMAIN in input_str:
        return input_str.rstrip('/')
    if re.match(r'^[a-zA-Z0-9]{13,}$', input_str):
        return f'https://www.{MEDIAFIRE_DOMAIN}/file/{input_str}/file'
    raise ValueError(f"Input non valido: {input_str}")


def get_download_button_href(soup):
    """
    Extract the download link from the page's #downloadButton anchor.

    MediaFire stores the real URL either directly in the `href` attribute
    or as a base64-encoded string in `data-scrambled-url`.

    Args:
        soup: BeautifulSoup object of the page.

    Returns:
        Decoded download URL, or None.
    """
    btn = soup.find('a', {'id': 'downloadButton'})
    if not btn:
        return None
    href = btn.get('href')
    if href:
        return href
    scrambled = btn.get('data-scrambled-url')
    if scrambled:
        import base64
        return base64.b64decode(scrambled).decode('utf-8')
    return None


def get_direct_url(url):
    """
    Fetch the MediaFire page and locate the real download URL.

    If the server returns a binary blob (e.g. the file itself) instead of
    HTML, the response URL is already the direct link.

    Args:
        url: Full MediaFire page URL.

    Returns:
        Tuple of (direct_download_url, BeautifulSoup_soup_or_None).
    """
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    # MediaFire sometimes gzips even non-HTML responses, so check both
    # Content-Type and Content-Encoding.
    is_html = (
        'text/html' in resp.headers.get('Content-Type', '')
        or resp.headers.get('Content-Encoding') == 'gzip'
    )

    if not is_html:
        return resp.url, None

    soup = BeautifulSoup(resp.text, 'html.parser')
    direct = get_download_button_href(soup)

    # Fallback: regex-based extraction from raw HTML if the button parser
    # did not find anything.
    if not direct:
        match = re.search(r'href="((https?://download[^"]+))"', resp.text)
        if match:
            direct = match.group(1)

    if not direct:
        raise RuntimeError("Impossibile trovare il link di download nella pagina")

    return direct, soup


def extract_filename(soup, direct_url):
    """
    Determine the real file name, preferring the Content-Disposition header.

    Args:
        soup:       BeautifulSoup object (may be None).
        direct_url: Direct download URL used for a HEAD request.

    Returns:
        File name string, or None.
    """
    # 1) Content-Disposition header (most reliable).
    resp = requests.head(direct_url, headers=HEADERS, timeout=30)
    cd = resp.headers.get('content-disposition', '')
    m = re.search(r'filename\*?=([^;]+)', cd)
    if m:
        name = m.group(1).strip().strip('"\'')
        if name.startswith("UTF-8''"):
            name = name[7:]
        name = unquote(name)
        if name:
            return name
    # 2) Page <title> with "MediaFire" stripped out.
    title_el = soup.find('title') if soup else None
    if title_el:
        name = title_el.string.strip() if title_el.string else ''
        if name:
            name = re.sub(r'\s*MediaFire\s*', '', name, flags=re.IGNORECASE).strip()
            if name:
                return name
    return None


def download_file(url, filename, output_dir='.'):
    """
    Stream a file from *url* to disk, displaying a tqdm progress bar.

    Args:
        url:         Direct download URL.
        filename:    Local file name.
        output_dir:  Output directory (created if missing).

    Returns:
        Absolute path to the saved file.
    """
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)

    if os.path.exists(filepath):
        print(f"[✓] {filename} — già scaricato")
        return filepath

    resp = requests.get(url, headers=HEADERS, stream=True, timeout=120)
    resp.raise_for_status()
    total = int(resp.headers.get('content-length', 0))

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
    """CLI entry point: parse args, resolve, extract direct link, download."""
    parser = argparse.ArgumentParser(description='Download file da MediaFire')
    parser.add_argument('input', help='URL del file MediaFire (es. https://www.mediafire.com/file/.../file)')
    parser.add_argument('-o', '--output-dir', default='.', help='Directory di destinazione')
    args = parser.parse_args()

    url = resolve_url(args.input)
    print(f"[*] URL: {url}")

    direct, soup = get_direct_url(url)
    print(f"[*] Link diretto ottenuto")

    filename = extract_filename(soup, direct)
    if not filename:
        filename = url.rstrip('/').split('/')[-2]
    print(f"[*] Nome file: {filename}")

    download_file(direct, filename, args.output_dir)


if __name__ == '__main__':
    main()
