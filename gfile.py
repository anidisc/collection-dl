#!/usr/bin/env python3
import os
import sys
import re
import time
import hashlib
import argparse
from urllib.parse import urlparse

import requests
from tqdm import tqdm


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/125.0.0.0 Safari/537.36',
    'Origin': 'https://gofile.io',
    'Referer': 'https://gofile.io/',
}

API_SERVER = 'api.gofile.io'


def _wt(token=''):
    slot = int(time.time()) // 14400
    raw = f"{HEADERS['User-Agent']}::en-US::{token}::{slot}::9844d94d963d30"
    return hashlib.sha256(raw.encode()).hexdigest()


def get_guest_token(session):
    r = session.post(f'https://{API_SERVER}/accounts', headers={
        'X-Website-Token': _wt(),
        'X-BL': 'en-US',
    })
    return r.json()['data']['token']


def get_content(session, content_id, token):
    r = session.get(
        f'https://{API_SERVER}/contents/{content_id}',
        headers={
            'Authorization': f'Bearer {token}',
            'X-Website-Token': _wt(token),
            'X-BL': 'en-US',
        },
    )
    data = r.json()
    if data['status'] != 'ok':
        raise RuntimeError(f"API error: {data}")
    return data['data']


def download_node(session, node, base_dir):
    if node['type'] == 'folder':
        folder_name = re.sub(r'[<>:"/\\|?*]', '', node.get('name', node['id']))
        folder_path = os.path.join(base_dir, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        for child_id, child in node.get('children', {}).items():
            download_node(session, child, folder_path)
    elif node['type'] == 'file':
        filename = re.sub(r'[<>:"/\\|?*]', '', node['name'])
        filepath = os.path.join(base_dir, filename)
        dl_url = node['link']

        if os.path.exists(filepath):
            print(f"[✓] {filename} — già scaricato")
            return

        resp = session.get(dl_url, stream=True, timeout=30)
        resp.raise_for_status()

        total = int(resp.headers.get('Content-Length', 0))
        with open(filepath, 'wb') as f, tqdm(
            total=total, unit='B', unit_scale=True, desc=filename, leave=True
        ) as bar:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    bar.update(len(chunk))
        print(f"[✓] Salvato: {filepath}")


def main():
    parser = argparse.ArgumentParser(description='Download file da Gofile')
    parser.add_argument('input', help='URL o ID (es. https://gofile.io/d/NCj7TH)')
    parser.add_argument('-o', '--output-dir', default='.', help='Directory di destinazione')
    args = parser.parse_args()

    content_id = args.input.strip().rstrip('/').split('/')[-1]
    print(f"[*] Content ID: {content_id}")

    session = requests.Session()
    session.headers.update(HEADERS)

    print("[*] Creazione account guest...")
    token = get_guest_token(session)
    session.cookies.set('accountToken', token, domain='.gofile.io', path='/')

    print("[*] Richiesta informazioni contenuto...")
    data = get_content(session, content_id, token)

    print(f"[*] Nome: {data.get('name', content_id)}")
    download_node(session, data, args.output_dir)


if __name__ == '__main__':
    main()
