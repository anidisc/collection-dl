#!/usr/bin/env python3
"""
Gofile downloader.

Creates a guest account via the Gofile API, then fetches the content tree
(files/folders) for a given content ID and downloads everything recursively.
"""
import os
import sys
import re
import time
import fnmatch
import hashlib
import argparse
from urllib.parse import urlparse

import requests
from tqdm import tqdm


# Standard browser headers; the Origin and Referer are required by the API.
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/125.0.0.0 Safari/537.36',
    'Origin': 'https://gofile.io',
    'Referer': 'https://gofile.io/',
}

API_SERVER = 'api.gofile.io'


def _wt(token=''):
    """
    Generate the Gofile X-Website-Token (a time-based, user-agent-dependent
    SHA-256 hash).

    The slot changes every 4 hours (14400 seconds).  The token helps the
    server verify that the request comes from a genuine browser session.

    Args:
        token: The current account token (empty string for guest creation).

    Returns:
        SHA-256 hex digest string.
    """
    slot = int(time.time()) // 14400
    raw = f"{HEADERS['User-Agent']}::en-US::{token}::{slot}::9844d94d963d30"
    return hashlib.sha256(raw.encode()).hexdigest()


def get_guest_token(session):
    """
    Create a new guest account with Gofile and return its token.

    Args:
        session: requests.Session with headers already set.

    Returns:
        Guest account token string.
    """
    r = session.post(f'https://{API_SERVER}/accounts', headers={
        'X-Website-Token': _wt(),
        'X-BL': 'en-US',
    })
    return r.json()['data']['token']


def get_content(session, content_id, token):
    """
    Fetch the content tree (files and folders) for a given content ID.

    Args:
        session:    requests.Session.
        content_id: The content/folder ID from the URL.
        token:      Guest account token for authorisation.

    Returns:
        Dictionary with the content tree (the 'data' portion of the API response).
    """
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


def flatten_tree(node, prefix=""):
    """
    Flatten a content tree into a list of (relative_path, node) tuples for display and selection.

    Args:
        node:   A Gofile content node (folder or file).
        prefix: Path prefix accumulated from parent folders.

    Returns:
        List of (relative_path, node) tuples (only files, folders are expanded).
    """
    items = []
    if node['type'] == 'folder':
        folder_name = re.sub(r'[<>:"/\\|?*]', '', node.get('name', node['id']))
        path = os.path.join(prefix, folder_name) if prefix else folder_name
        for child_id, child in node.get('children', {}).items():
            items.extend(flatten_tree(child, path))
    else:
        items.append((prefix, node))
    return items


def list_files(data):
    """
    Print the file tree with indices for selection.

    Args:
        data: Content data from the API (folder node).
    """
    items = flatten_tree(data)
    print(f"\nContenuto di \"{data.get('name', data['id'])}\":")
    print(f"{'#'*60}")
    for i, (path, node) in enumerate(items, 1):
        name = node['name']
        size = node.get('size', 0)
        size_str = f"{size / 1024 / 1024:.1f} MB" if size > 0 else ""
        print(f"  [{i:3d}] {os.path.join(path, name)}  {size_str}")
    print(f"{'#'*60}")
    print(f"Totale: {len(items)} file\n")


def build_select_filter(select_arg, items):
    """
    Convert the --select argument into a set of matching file indices (1-based).

    Supports:
      - Comma-separated numbers: 1,3,5
      - Ranges: 1-5, 3-7
      - Glob patterns: *.zip, *apk* (matched against filename)

    Args:
        select_arg: Raw string from --select.
        items:      List of (path, node) tuples from flatten_tree().

    Returns:
        Set of 1-based indices to download.
    """
    selected = set()

    # Split on comma to handle multiple expressions
    parts = [p.strip() for p in select_arg.split(',')]

    for part in parts:
        # Range: 3-7
        m = re.match(r'^(\d+)\s*-\s*(\d+)$', part)
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            selected.update(range(start, end + 1))
            continue

        # Single number
        m = re.match(r'^(\d+)$', part)
        if m:
            selected.add(int(m.group(1)))
            continue

        # Glob pattern — match against filenames
        for i, (path, node) in enumerate(items, 1):
            if fnmatch.fnmatch(node['name'], part):
                selected.add(i)

    return selected


def download_node(session, node, base_dir, select=None, items=None):
    """
    Recursively download nodes from the Gofile content tree, with optional selection.

    When ``select`` is set, only files whose 1-based index in ``items`` is present
    in the set will be downloaded.  If ``select`` is None, everything is downloaded.

    Args:
        session:  requests.Session.
        node:     Dictionary representing a Gofile content node.
        base_dir: Local directory to write into.
        select:   Set of 1-based indices to download, or None for all.
        items:    Flattened list of (path, node) — required when ``select`` is used.
    """
    if node['type'] == 'folder':
        folder_name = re.sub(r'[<>:"/\\|?*]', '', node.get('name', node['id']))
        folder_path = os.path.join(base_dir, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        for child_id, child in node.get('children', {}).items():
            download_node(session, child, folder_path, select, items)
    elif node['type'] == 'file':
        filename = re.sub(r'[<>:"/\\|?*]', '', node['name'])
        filepath = os.path.join(base_dir, filename)
        dl_url = node['link']

        if select is not None and items is not None:
            idx = next((i for i, (_, n) in enumerate(items, 1) if n['id'] == node['id']), None)
            if idx is not None and idx not in select:
                return

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


def collect_ids_from_args(args, parser):
    """
    Collect content IDs from CLI arguments and/or a file.

    Args:
        args:   Parsed CLI arguments.
        parser: ArgumentParser (used to raise errors consistently).

    Returns:
        List of content ID strings.
    """
    ids = []

    if args.input:
        for raw in args.input:
            ids.append(raw.strip().rstrip('/').split('/')[-1])

    if args.file:
        try:
            with open(args.file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        ids.append(line.rstrip('/').split('/')[-1])
        except FileNotFoundError:
            parser.error(f"File non trovato: {args.file}")

    if not ids:
        parser.error("Nessun ID fornito. Usa argomenti nella riga di comando o --file.")

    return ids


def main():
    """CLI entry point: parse args, create guest account, fetch tree, download."""
    parser = argparse.ArgumentParser(description='Download file da Gofile')
    parser.add_argument('input', nargs='*', help='URL o ID (es. https://gofile.io/d/NCj7TH)')
    parser.add_argument('-o', '--output-dir', default='.', help='Directory di destinazione')
    parser.add_argument('-f', '--file', help='File con un link/ID per riga')
    parser.add_argument('--list', action='store_true',
                        help='Mostra i file disponibili senza scaricare')
    parser.add_argument('-s', '--select',
                        help='Seleziona file specifici (es. 1,3,5 / 1-3 / *.zip)')
    args = parser.parse_args()

    content_ids = collect_ids_from_args(args, parser)
    print(f"[*] Totale contenuti da scaricare: {len(content_ids)}")

    session = requests.Session()
    session.headers.update(HEADERS)

    print("[*] Creazione account guest...")
    token = get_guest_token(session)
    session.cookies.set('accountToken', token, domain='.gofile.io', path='/')

    for idx, content_id in enumerate(content_ids, 1):
        print(f"\n{'='*60}")
        print(f"[{idx}/{len(content_ids)}] Content ID: {content_id}")
        print(f"{'='*60}")

        data = get_content(session, content_id, token)
        print(f"[*] Nome: {data.get('name', content_id)}")

        items = flatten_tree(data)

        if args.list:
            list_files(data)
            continue

        select_set = None
        if args.select:
            select_set = build_select_filter(args.select, items)
            if not select_set:
                print("[!] Nessun file corrisponde alla selezione.")
                continue

        download_node(session, data, args.output_dir, select=select_set, items=items)


if __name__ == '__main__':
    main()
