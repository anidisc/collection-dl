#!/usr/bin/env python3
"""
BuzzHeavier / Bzzhr / FuckingFast / FlashBang / TrashBytes downloader.

Resolves short IDs and page URLs to direct download links, then downloads
the file with a progress bar.  Supports multiple mirror domains.
"""
import os
import sys
import re
import argparse
from urllib.parse import urlparse, unquote

from lxml.html import fromstring
from curl_cffi import requests as curl_requests
from tqdm import tqdm

# All domains that use the same BuzzHeavier front-end.
SUPPORTED_DOMAINS = [
    'buzzheavier.com', 'bzzhr.co', 'bzzhr.to',
    'fuckingfast.net', 'fuckingfast.co',
    'flashbang.sh', 'trashbytes.net',
]


def resolve_url(input_str):
    """
    Convert a user-supplied URL or 12-char ID into a full page URL.

    Args:
        input_str: Either a full URL containing a supported domain or a
                   12-character alphanumeric file ID.

    Returns:
        Normalised page URL.

    Raises:
        ValueError if the input cannot be parsed.
    """
    input_str = input_str.strip()
    if input_str.startswith('http'):
        for domain in SUPPORTED_DOMAINS:
            if domain in input_str:
                return input_str.rstrip('/')
        raise ValueError(f"Dominio non supportato: {input_str}")
    if re.match(r'^[a-zA-Z0-9]{12}$', input_str):
        return f'https://{SUPPORTED_DOMAINS[0]}/{input_str}'
    raise ValueError(f"Input non valido: {input_str}")


def extract_filename(tree, direct_url=None):
    """
    Try to obtain the real file name from the page <title>, the Content-
    Disposition header, or a <span> with class 'text-2xl'.

    Args:
        tree:       lxml HTML tree of the download page.
        direct_url: Direct download URL (used to send a HEAD request).

    Returns:
        Sanitised file name, or None if nothing was found.
    """
    # 1) <title> element on the page.
    title_el = tree.xpath('//title')
    if title_el:
        name = title_el[0].text_content().strip()
        if name:
            return re.sub(r'[<>:"/\\|?*]', '', name)
    # 2) Content-Disposition header from a HEAD request to the direct URL.
    if direct_url:
        resp = curl_requests.head(direct_url, impersonate='chrome')
        cd = resp.headers.get('content-disposition', '')
        m = re.search(r'filename\*?=([^;]+)', cd)
        if m:
            name = m.group(1).strip().strip('"\'')
            if name.startswith("UTF-8''"):
                name = name[7:]
            name = unquote(name)
            if name:
                return re.sub(r'[<>:"/\\|?*]', '', name)
    # 3) Fallback: <span class="text-2xl"> with the file name.
    span = tree.xpath('//span[contains(@class, "text-2xl")]')
    if span:
        name = span[0].text_content().strip()
        if name:
            return re.sub(r'[<>:"/\\|?*]', '', name)
    return None


def get_direct_url(url):
    """
    Fetch the download page, extract the hx-get download link, follow it,
    and read the final hx-redirect header that points to the actual file.

    Args:
        url: Full BuzzHeavier-style page URL.

    Returns:
        Tuple of (direct_download_url, lxml_html_tree).
    """
    resp = curl_requests.get(url, impersonate='chrome')
    resp.raise_for_status()
    tree = fromstring(resp.text)

    # Find the first <a> that has an hx-get attribute containing "download"
    # but NOT "alt=true" (the alt link is an alternative mirror).
    els = tree.xpath('//a[contains(@hx-get, "download") and not(contains(@hx-get, "alt=true"))]')
    if not els:
        raise RuntimeError("Nessun link di download trovato nella pagina")

    hx_get = els[0].get('hx-get')
    download_url = f'https://{urlparse(url).netloc}{hx_get}'

    # HTMX-style request that triggers the server-side redirect logic.
    hx_resp = curl_requests.get(download_url, headers={
        'hx-current-url': url,
        'hx-request': 'true',
        'referer': url,
    }, impersonate='chrome', allow_redirects=False)

    # The server responds with a custom hx-redirect header instead of a
    # regular HTTP 3xx redirect.
    direct = hx_resp.headers.get('hx-redirect')
    if not direct:
        raise RuntimeError("Nessun redirect (hx-redirect) nella risposta")

    return direct, tree


def download_file(url, filename, output_dir='.'):
    """
    Stream the file from *url* to disk, showing a tqdm progress bar.

    Args:
        url:         Direct download URL.
        filename:    Local file name to save under.
        output_dir:  Target directory (created if it does not exist).

    Returns:
        Absolute path to the saved file.
    """
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)

    if os.path.exists(filepath):
        print(f"[✓] {filename} — già scaricato")
        return filepath

    resp = curl_requests.get(url, impersonate='chrome', stream=True)
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
    """CLI entry point: parse args, resolve URL, obtain direct link, download."""
    parser = argparse.ArgumentParser(description='Download file da BuzzHeavier')
    parser.add_argument('input', help='URL o ID del file (es. https://bzzhr.to/dn4w50msj4on)')
    parser.add_argument('-o', '--output-dir', default='.', help='Directory di destinazione')
    args = parser.parse_args()

    url = resolve_url(args.input)
    print(f"[*] URL: {url}")

    direct, tree = get_direct_url(url)
    print(f"[*] Link diretto ottenuto")

    filename = extract_filename(tree, direct)
    if not filename:
        filename = url.rstrip('/').split('/')[-1]
    print(f"[*] Nome file: {filename}")

    download_file(direct, filename, args.output_dir)


if __name__ == '__main__':
    main()
