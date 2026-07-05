#!/usr/bin/env python3
import os
import sys
import re
import time
import hashlib
import argparse

import requests
from tqdm import tqdm


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/125.0.0.0 Safari/537.36',
}


class WorkuploadDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _request(self, method, url, **kwargs):
        for attempt in range(3):
            try:
                return self.session.request(method, url, timeout=30, **kwargs)
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt == 2:
                    raise
                time.sleep(2)

    def _solve_pow(self):
        p = self._request('GET', 'https://workupload.com/puzzle').json()
        puzzle = p['data']['puzzle']
        rng = p['data']['range']
        targets = set(p['data']['find'])

        found = []
        for i in range(rng):
            h = hashlib.sha256(f'{puzzle}{i}'.encode()).hexdigest()
            if h in targets:
                found.append(str(i))
                if len(found) == len(targets):
                    break

        self._request('POST', 'https://workupload.com/captcha',
                       data={'captcha': ' '.join(found)})

    def get_direct_url(self, url):
        resp = self._request('GET', url)

        if len(resp.text) < 10000 or 'captcha' in resp.text.lower()[:2000]:
            self._solve_pow()
            resp = self._request('GET', url)

        m = re.search(r'workupload\.com/(\w+)/(\w+)', url)
        if not m:
            raise ValueError(f"URL non valida: {url}")
        typ, fid = m.group(1), m.group(2)

        api = self._request(
            'GET',
            f'https://workupload.com/api/{typ}/getDownloadServer/{fid}'
        )
        data = api.json()
        if not data.get('success'):
            raise RuntimeError(f"API error: {data}")
        return data['data']['url'], resp.text

    def download(self, url, output_dir='.'):
        os.makedirs(output_dir, exist_ok=True)

        print("[*] Risoluzione link diretto...")
        dl_url, html = self.get_direct_url(url)

        print("[*] Download...")
        resp = self._request('GET', dl_url, stream=True)
        resp.raise_for_status()

        cd = resp.headers.get('Content-Disposition', '')
        m = re.search(r'filename="?(.+?)"?(\s|;|$)', cd)
        filename = m.group(1) if m else None
        if not filename:
            m = re.search(r'<title>(.+?)<', html)
            filename = m.group(1).strip() if m else url.rstrip('/').split('/')[-1]
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
    parser = argparse.ArgumentParser(description='Download file da WorkUpload')
    parser.add_argument('input', help='URL del file (es. https://workupload.com/file/MHsspmhk9NW)')
    parser.add_argument('-o', '--output-dir', default='.', help='Directory di destinazione')
    args = parser.parse_args()

    dl = WorkuploadDownloader()
    dl.download(args.input, args.output_dir)


if __name__ == '__main__':
    main()
