# collection-dl

Script Python per scaricare file da piattaforme di file hosting.

## Script

| Script | Piattaforma |
|--------|-------------|
| `buzzdl` | BuzzHeavier / bzzhr.to |
| `mfire` | MediaFire |
| `wupload` | WorkUpload |
| `gfile` | Gofile |
| `pdrain` | PixelDrain |

## Installazione

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Utilizzo

### Tramite il launcher `./dl` (consigliato)

Il launcher usa l'interprete configurato in `buzzdl.conf` (o `python3` di default).

```bash
# Mostra aiuto
./dl

# Scaricare un file
./dl buzzdl https://bzzhr.to/dn4w50msj4on
./dl mfire https://www.mediafire.com/file/.../file
./dl wupload https://workupload.com/file/...
./dl gfile https://gofile.io/d/NCj7TH
./dl pdrain https://pixeldrain.com/u/TssWGxaT
```

### Configurazione interprete

Modificare `buzzdl.conf` per usare un interprete specifico (es. virtual environment):

```ini
python=/home/user/project/.venv/bin/python3
```

### Direttamente con Python

```bash
python3 buzzdl.py https://bzzhr.to/dn4w50msj4on
python3 gfile.py https://gofile.io/d/NCj7TH -s "*.zip"
```

Opzioni comuni:
- `-o DIRECTORY` — directory di output
- `-s SELEZIONE` — seleziona file per indice/pattern (gfile.py)
- `--list` — elenca file senza scaricare (gfile.py)
- `--no-verify` — disabilita verifica SSL (pdrain.py)

## Dipendenze

```bash
pip install -r requirements.txt
```
