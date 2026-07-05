# collection-dl

Set di script Python per scaricare file da diverse piattaforme di file hosting.

## Script

| Script | Piattaforma | Dipendenze | Note |
|--------|-------------|------------|------|
| `buzzdl.py` | [BuzzHeavier](https://buzzhr.to) | `curl-cffi`, `lxml`, `tqdm` | Cloudflare, necessita `curl-cffi` per TLS fingerprint |
| `mfire.py` | [MediaFire](https://mediafire.com) | `requests`, `beautifulsoup4`, `tqdm` | Nessun captcha, solo scraping HTML |
| `wupload.py` | [WorkUpload](https://workupload.com) | `requests`, `tqdm` | Proof-of-work SHA256 (risolto in Python) |
| `gfile.py` | [Gofile](https://gofile.io) | `requests`, `tqdm` | API con X-Website-Token (SHA256), supporta cartelle |

## Installazione

```bash
pip install -r requirements.txt
```

Per `buzzdl.py` serve anche `curl-cffi` (incluso in requirements.txt).

## Utilizzo

```bash
# BuzzHeavier
python buzzdl.py https://bzzhr.to/dn4w50msj4on

# MediaFire
python mfire.py https://www.mediafire.com/file/eopoiwribvac639/file.zip/file

# WorkUpload
python wupload.py https://workupload.com/file/MHsspmhk9NW

# Gofile (file singolo o cartella)
python gfile.py https://gofile.io/d/NCj7TH
```

Tutti gli script supportano:
- ID al posto dell'URL completo (dove possibile)
- `-o DIRECTORY` per specificare la directory di output
- Barra di progresso con `tqdm`
- Salto file già scaricati

## Licenza

MIT
