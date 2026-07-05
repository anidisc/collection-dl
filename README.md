# start project

Script per scaricare file da piattaforme di file hosting.

## Script

| Script | Piattaforma | Dipendenze |
|--------|-------------|------------|
| `buzzdl.py` | BuzzHeavier | curl-cffi, lxml, tqdm |
| `mfire.py` | MediaFire | requests, beautifulsoup4, tqdm |
| `wupload.py` | WorkUpload | requests, tqdm |
| `gfile.py` | Gofile | requests, tqdm |

## Installazione

```bash
pip install -r requirements.txt
```

## Utilizzo

```bash
python buzzdl.py https://bzzhr.to/dn4w50msj4on
python mfire.py https://www.mediafire.com/file/.../file
python wupload.py https://workupload.com/file/...
python gfile.py https://gofile.io/d/NCj7TH
```
