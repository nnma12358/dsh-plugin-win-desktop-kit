import sys, json, os, re, zlib

def fallback_extract(path):
    data = open(path, 'rb').read()
    texts = []
    for m in re.finditer(rb'stream\r?\n(.*?)endstream', data, re.S):
        raw = m.group(1)
        dec = raw
        try:
            dec = zlib.decompress(raw)
        except Exception:
            pass
        if b'Tj' not in dec and b'TJ' not in dec:
            continue
        for tm in re.finditer(rb'\[?\((?:[^()\\]|\\.)*\)(?:[-\d.]+)?\]?\s*T[ jJ]', dec):
            seg = tm.group(0)
            for p in re.findall(rb'\((?:[^()\\]|\\.)*\)', seg):
                s = p[1:-1]
                s = s.replace(rb'\(', b'(').replace(rb'\)', b')').replace(rb'\\', b'\\')
                texts.append(s.decode('latin-1', 'replace'))
    return '\n'.join(texts)

def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'usage: pdf-extract.py <file.pdf>'}, ensure_ascii=False),
              file=sys.stderr)
        sys.exit(2)
    path = sys.argv[1]
    if not os.path.isfile(path):
        print(json.dumps({'error': 'not a file: %s' % path}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
    pages = 0
    text = ''
    try:
        from pypdf import PdfReader
        r = PdfReader(path)
        pages = len(r.pages)
        text = '\n'.join((p.extract_text() or '') for p in r.pages)
    except Exception:
        try:
            from PyPDF2 import PdfReader
            r = PdfReader(path)
            pages = len(r.pages)
            text = '\n'.join((p.extract_text() or '') for p in r.pages)
        except Exception:
            raw = open(path, 'rb').read()
            pages = len(re.findall(rb'/Type\s*/Page[^s]', raw))
            text = fallback_extract(path)
    print(json.dumps({'text': text, 'pages': pages}, ensure_ascii=False))

if __name__ == '__main__':
    main()
