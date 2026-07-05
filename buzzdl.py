#!/usr/bin/env python3
import os
import sys
import re
import argparse
from urllib.parse import urlparse, unquote

from lxml.html import fromstring
from curl_cffi import requests as curl_requests
from tqdm import tqdm

SUPPORTED_DOMAINS = [
    'buzzheavier.com', 'bzzhr.co', 'bzzhr.to',
    'fuckingfast.net', 'fuckingfast.co',
    'flashbang.sh', 'trashbytes.net',
]


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


def extract_filename(tree, direct_url=None):
    title_el = tree.xpath('//title')
    if title_el:
        name = title_el[0].text_content().strip()
        if name:
            return re.sub(r'[<>:"/\\|?*]', '', name)
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
    span = tree.xpath('//span[contains(@class, "text-2xl")]')
    if span:
        name = span[0].text_content().strip()
        if name:
            return re.sub(r'[<>:"/\\|?*]', '', name)
    return None


def get_direct_url(url):
    resp = curl_requests.get(url, impersonate='chrome')
    resp.raise_for_status()
    tree = fromstring(resp.text)

    els = tree.xpath('//a[contains(@hx-get, "download") and not(contains(@hx-get, "alt=true"))]')
    if not els:
        raise RuntimeError("Nessun link di download trovato nella pagina")

    hx_get = els[0].get('hx-get')
    download_url = f'https://{urlparse(url).netloc}{hx_get}'

    hx_resp = curl_requests.get(download_url, headers={
        'hx-current-url': url,
        'hx-request': 'true',
        'referer': url,
    }, impersonate='chrome', allow_redirects=False)

    direct = hx_resp.headers.get('hx-redirect')
    if not direct:
        raise RuntimeError("Nessun redirect (hx-redirect) nella risposta")

    return direct, tree


def download_file(url, filename, output_dir='.'):
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
