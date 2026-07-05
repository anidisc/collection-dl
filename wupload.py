#!/usr/bin/env python3
"""
WorkUpload downloader.

Solves a proof-of-work (SHA-256 hashcash-style) puzzle that the site uses
as a CAPTCHA, then calls the internal API to obtain a direct download URL.
"""
import os
import sys
import re
import time
import hashlib
import argparse

import requests
from tqdm import tqdm


# Standard browser User-Agent used for all requests.
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/125.0.0.0 Safari/537.36',
}


class WorkuploadDownloader:
    """Holds a requests.Session and provides WorkUpload-specific methods."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _request(self, method, url, **kwargs):
        """
        Send an HTTP request with automatic retries on connection errors.

        Up to 3 attempts with a 2-second delay between retries.
        """
        for attempt in range(3):
            try:
                return self.session.request(method, url, timeout=30, **kwargs)
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt == 2:
                    raise
                time.sleep(2)

    def _solve_pow(self):
        """
        Solve the WorkUpload proof-of-work (PoW) CAPTCHA.

        The server provides:
          - puzzle: a random string
          - range:  an integer N
          - find:   a set of target SHA-256 hashes

        We hash f"{puzzle}{i}" for i in [0, N) and collect the indices
        whose hex digest matches any of the target hashes.  The solution
        is sent back to the /captcha endpoint.
        """
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
        """
        Retrieve the direct download URL for a given WorkUpload page.

        If the page is very short or mentions "captcha", the PoW puzzle
        is solved first, then the page is re-fetched.

        The direct URL is obtained from the internal JSON API:
          GET /api/{type}/getDownloadServer/{fileId}

        Args:
            url: Full WorkUpload page URL (e.g. https://workupload.com/file/...).

        Returns:
            Tuple of (direct_download_url, page_html).
        """
        resp = self._request('GET', url)

        # Detect if a PoW challenge is present (small page or "captcha" keyword).
        if len(resp.text) < 10000 or 'captcha' in resp.text.lower()[:2000]:
            self._solve_pow()
            resp = self._request('GET', url)

        # Extract the type ("file", "folder", etc.) and the ID from the URL.
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
        """
        Resolve the direct URL, determine the file name, and stream the file.

        Args:
            url:        WorkUpload page URL.
            output_dir: Target directory for the downloaded file.
        """
        os.makedirs(output_dir, exist_ok=True)

        print("[*] Risoluzione link diretto...")
        dl_url, html = self.get_direct_url(url)

        print("[*] Download...")
        resp = self._request('GET', dl_url, stream=True)
        resp.raise_for_status()

        # Extract the file name from Content-Disposition or the page <title>.
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
    """CLI entry point: parse args, create downloader, start download."""
    parser = argparse.ArgumentParser(description='Download file da WorkUpload')
    parser.add_argument('input', help='URL del file (es. https://workupload.com/file/MHsspmhk9NW)')
    parser.add_argument('-o', '--output-dir', default='.', help='Directory di destinazione')
    args = parser.parse_args()

    dl = WorkuploadDownloader()
    dl.download(args.input, args.output_dir)


if __name__ == '__main__':
    main()
