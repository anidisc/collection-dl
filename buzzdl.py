#!/usr/bin/env python3
import os
import sys
import re
import argparse
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False

SUPPORTED_DOMAINS = [
    'buzzheavier.com', 'bzzhr.co', 'bzzhr.to',
    'fuckingfast.net', 'fuckingfast.co',
    'flashbang.sh', 'trashbytes.net',
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}


def get_session():
    if HAS_CLOUDSCRAPER:
        return cloudscraper.create_scraper()
    return requests.Session()


def resolve_url(input_str):
    input_str = input_str.strip()
    if input_str.startswith('http'):
        for domain in SUPPORTED_DOMAINS:
            if domain in input_str:
                return input_str.rstrip('/')
        raise ValueError(f"Dominio non supportato: {input_str}")
    if re.match(r'^[a-zA-Z0-9]{12}$', input_str):
        return f'https://{SUPPORTED_DOMAINS[0]}/{input_str}'
    raise ValueError(f"Input non valido: {input_str}")


def get_filename(session, url):
    try:
        resp = session.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        title = soup.title.string.strip() if soup.title else None
        if title:
            name = re.sub(r'[<>:"/\\|?*]', '', title)
            if name:
                return name
        span = soup.find('span', class_='text-2xl')
        if span and span.text.strip():
            return re.sub(r'[<>:"/\\|?*]', '', span.text.strip())
    except Exception:
        pass
    return None


def get_direct_url(session, url):
    download_url = url + '/download'
    hx_headers = {
        **HEADERS,
        'referer': url,
        'hx-current-url': url,
        'hx-request': 'true',
    }
    resp = session.get(download_url, headers=hx_headers, allow_redirects=False, timeout=30)
    direct = resp.headers.get('Hx-Redirect') or resp.headers.get('location')
    if direct:
        if direct.startswith('http'):
            return direct
        parsed = urlparse(url)
        return f'{parsed.scheme}://{parsed.netloc}{direct}'
    if resp.status_code in (301, 302, 303, 307, 308):
        return resp.headers.get('location')
    return None


def download_file(session, url, filename, output_dir='.'):
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)

    if os.path.exists(filepath):
        print(f"[✓] {filename} — già scaricato")
        return filepath

    resp = session.get(url, headers=HEADERS, stream=True, timeout=60)
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
    parser = argparse.ArgumentParser(description='Download file da BuzzHeavier')
    parser.add_argument('input', help='URL o ID del file (es. https://bzzhr.to/dn4w50msj4on)')
    parser.add_argument('-o', '--output-dir', default='.', help='Directory di destinazione')
    parser.add_argument('--no-cloudscraper', action='store_true', help='Non usare cloudscraper')
    args = parser.parse_args()

    url = resolve_url(args.input)
    print(f"[*] URL: {url}")

    session = get_session()

    filename = get_filename(session, url)
    print(f"[*] Nome file: {filename or 'sconosciuto'}")

    direct = get_direct_url(session, url)
    if not direct:
        print("[!] Impossibile ottenere il link diretto")
        sys.exit(1)
    print(f"[*] Link diretto ottenuto")

    if not filename:
        filename = url.rstrip('/').split('/')[-1]

    download_file(session, direct, filename, args.output_dir)


if __name__ == '__main__':
    main()
