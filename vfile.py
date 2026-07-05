#!/usr/bin/env python3
import os
import sys
import re
import subprocess
import atexit
import signal
import argparse
from urllib.parse import urlparse

from tqdm import tqdm

try:
    from curl_cffi import requests as curl_requests
    HAS_CURL = True
except ImportError:
    HAS_CURL = False

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


VIRTUAL_DISPLAY = None


def start_virtual_display():
    global VIRTUAL_DISPLAY
    if os.environ.get('DISPLAY'):
        return

    try:
        from pyvirtualdisplay import Display
        VIRTUAL_DISPLAY = Display(visible=False, size=(1280, 720))
        VIRTUAL_DISPLAY.start()
        return
    except ImportError:
        pass

    try:
        proc = subprocess.Popen(
            ['Xvfb', ':99', '-screen', '0', '1280x720x24'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        os.environ['DISPLAY'] = ':99'
        VIRTUAL_DISPLAY = proc

        def cleanup():
            if VIRTUAL_DISPLAY and hasattr(VIRTUAL_DISPLAY, 'poll') and VIRTUAL_DISPLAY.poll() is None:
                VIRTUAL_DISPLAY.terminate()
                VIRTUAL_DISPLAY.wait()

        atexit.register(cleanup)
        signal.signal(signal.SIGTERM, lambda *a: (cleanup(), sys.exit(0)))
        signal.signal(signal.SIGINT, lambda *a: (cleanup(), sys.exit(0)))
        return
    except FileNotFoundError:
        pass

    print("[!] Nessun display disponibile e Xvfb non trovato.")
    print("    Installa xvfb-run o pyvirtualdisplay:")
    print("      apt install xvfb  (o zypper install xorg-x11-server)")
    print("      pip install pyvirtualdisplay")
    print("    Oppure usa: xvfb-run python vfile.py ...")
    sys.exit(1)


def stop_virtual_display():
    global VIRTUAL_DISPLAY
    if VIRTUAL_DISPLAY is None:
        return
    if hasattr(VIRTUAL_DISPLAY, 'stop'):
        VIRTUAL_DISPLAY.stop()
    elif hasattr(VIRTUAL_DISPLAY, 'terminate'):
        if VIRTUAL_DISPLAY.poll() is None:
            VIRTUAL_DISPLAY.terminate()
            VIRTUAL_DISPLAY.wait()
    VIRTUAL_DISPLAY = None


def resolve_url(input_str):
    input_str = input_str.strip()
    if 'vikingfile.com' in input_str or 'vik1ngfile.site' in input_str:
        return input_str.rstrip('/')
    if re.match(r'^[a-zA-Z0-9]{8,}$', input_str):
        return f'https://vikingfile.com/f/{input_str}'
    raise ValueError(f"Input non valido: {input_str}")


def get_filename_from_url(url):
    return url.rstrip('/').split('/')[-1]


def browser_flow(url):
    if not HAS_PLAYWRIGHT:
        return None, None

    start_virtual_display()

    download_url = None
    filename = None

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled'],
        )
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/125.0.0.0 Safari/537.36'
            ),
        )
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)
        page = context.new_page()

        def handle_response(response):
            nonlocal download_url
            if response.request.method == 'POST' and response.url == page.url:
                try:
                    data = response.json()
                    if data.get('link'):
                        download_url = data['link']
                except Exception:
                    pass

        page.on('response', handle_response)
        page.goto(url, wait_until='networkidle')

        title_el = page.query_selector('title')
        if title_el:
            filename = title_el.text_content().strip()
        if not filename:
            fn = page.query_selector('#filename')
            if fn:
                filename = fn.text_content().strip()
        if filename:
            filename = re.sub(r'[<>:"/\\|?*]', '', filename)

        print(f"[*] File: {filename or 'sconosciuto'}")
        print("[*] Browser aperto (display virtuale). Risolvi il captcha...")
        print("[*] Attendendo...")

        while not download_url:
            try:
                page.wait_for_timeout(500)
            except KeyboardInterrupt:
                print("\n[*] Interrotto dall'utente")
                browser.close()
                stop_virtual_display()
                sys.exit(1)

        print("[*] Captcha risolto, link diretto ottenuto!")
        browser.close()

    stop_virtual_display()

    return download_url, filename


def download_file(url, filename, output_dir='.'):
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)

    if os.path.exists(filepath):
        print(f"[✓] {filename} — già scaricato")
        return filepath

    if HAS_CURL:
        session, kwargs = curl_requests, {'impersonate': 'chrome', 'stream': True}
    else:
        session, kwargs = requests, {'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/125.0.0.0 Safari/537.36',
        }, 'stream': True}

    resp = session.get(url, **kwargs)
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
    parser = argparse.ArgumentParser(
        description='Download file da VikingFile (richiede captcha Turnstile)',
    )
    parser.add_argument('input', help='URL o ID del file (es. https://vikingfile.com/f/BMElZBYuAc)')
    parser.add_argument('-o', '--output-dir', default='.', help='Directory di destinazione')
    parser.add_argument('--direct', metavar='URL', help='Link diretto (salta il captcha)')
    args = parser.parse_args()

    url = resolve_url(args.input)
    print(f"[*] URL: {url}")

    if args.direct:
        direct = args.direct
        filename = get_filename_from_url(url)
    elif HAS_PLAYWRIGHT:
        direct, filename = browser_flow(url)
        if not direct:
            print("[!] Impossibile ottenere il link diretto via browser")
            sys.exit(1)
    else:
        print("[!] Playwright non installato.")
        print()
        print("  pip install playwright && playwright install chromium")
        print()
        print("  Oppure usa --direct (vedi --help)")
        sys.exit(1)

    if not filename:
        filename = get_filename_from_url(url)
    print(f"[*] Nome file: {filename}")

    download_file(direct, filename, args.output_dir)


if __name__ == '__main__':
    main()
