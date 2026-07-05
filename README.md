# collection-dl

Script Python per scaricare file da piattaforme di file hosting.

## Script

| Script | Piattaforma | Esempio |
|--------|-------------|---------|
| `buzzdl.py` | BuzzHeavier / bzzhr.to | `python buzzdl.py https://bzzhr.to/dn4w50msj4on` |
| `mfire.py` | MediaFire | `python mfire.py https://www.mediafire.com/file/.../file` |
| `wupload.py` | WorkUpload | `python wupload.py https://workupload.com/file/...` |
| `gfile.py` | Gofile | `python gfile.py https://gofile.io/d/NCj7TH` |

## Installazione

```bash
pip install -r requirements.txt
```

## Utilizzo

Tutti gli script accettano l'URL completo o l'ID del file:

```bash
python buzzdl.py dn4w50msj4on
python buzzdl.py https://bzzhr.to/dn4w50msj4on -o downloads/
```

Opzioni comuni:
- `-o DIRECTORY` — directory di output (default: corrente)
- Salta automaticamente i file già scaricati
- Barra di progresso con `tqdm`
