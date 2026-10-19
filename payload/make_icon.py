# -*- coding: utf-8 -*-
"""用仓库 FishLogo SVG 路径生成透明背景的多尺寸 ICO（纯 Python，无第三方库）。
路径含多个子路径（contour），按 contour 分别收集非零环绕事件。
"""
import math, re, struct, zlib

import os, sys
# 迁移改动：源码路径与输出路径不再写死。
#   usage: make_icon.py <FishLogo.tsx> [out.ico] [preview.png]
#   也可用环境变量 ICON_SRC 指定源码路径。
_HERE = os.path.dirname(os.path.abspath(__file__))
_argv = sys.argv[1:]
SRC_PATH = _argv[0] if len(_argv) > 0 else os.environ.get('ICON_SRC', '')
OUT_ICO = _argv[1] if len(_argv) > 1 else os.path.join(_HERE, 'Harness.ico')
OUT_PNG = _argv[2] if len(_argv) > 2 else os.path.join(_HERE, 'whale-256.png')
if not SRC_PATH or not os.path.isfile(SRC_PATH):
    sys.stderr.write('usage: make_icon.py <FishLogo.tsx> [out.ico] [preview.png]\n'
                     '       (or set ICON_SRC to the .tsx path)\n')
    sys.exit(2)
SRC = open(SRC_PATH, encoding='utf-8').read()
D = re.search(r'd="([^"]+)"', SRC).group(1)
VB_W, VB_H = 23.16, 17.04
COLOR = (77, 107, 254)

def parse_path(d):
    toks = re.findall(r'[A-Za-z]|-?\d+\.?\d*(?:[eE][+-]?\d+)?', d)
    i = 0
    contours = []
    cur_pts = []
    cur = None
    while i < len(toks):
        t = toks[i]
        if t in ('M', 'C', 'L', 'Z'):
            cur = t
            i += 1
            if t == 'M' and cur_pts:
                contours.append(cur_pts)
                cur_pts = []
            if t == 'Z':
                if cur_pts:
                    contours.append(cur_pts)
                    cur_pts = []
                    cur = 'Z'
            continue
        if cur in (None, 'Z'):
            break
        if cur == 'M':
            cur_pts.append((float(toks[i]), float(toks[i + 1])))
            i += 2
            cur = 'L'
        elif cur == 'L':
            cur_pts.append((float(toks[i]), float(toks[i + 1])))
            i += 2
        elif cur == 'C':
            pts = []
            while len(pts) < 3 and i + 1 < len(toks):
                pts.append((float(toks[i]), float(toks[i + 1])))
                i += 2
            c1, c2, p = pts
            p0 = cur_pts[-1]
            for (px, py) in flatten_cubic(p0, c1, c2, p):
                cur_pts.append((px, py))
    if cur_pts:
        contours.append(cur_pts)
    return contours

def flatten_cubic(p0, p1, p2, p3, tol=0.003, depth=0):
    dx, dy = p3[0] - p0[0], p3[1] - p0[1]
    L = math.hypot(dx, dy)
    d = 0.0
    if L > 1e-9:
        d = max(abs((p1[0] - p0[0]) * dy - (p1[1] - p0[1]) * dx),
                abs((p2[0] - p0[0]) * dy - (p2[1] - p0[1]) * dx)) / L
    if d < tol or depth >= 18:
        return [p3]
    a = lambda p, q: ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
    ab, bc, cd = a(p0, p1), a(p1, p2), a(p2, p3)
    abc, bcd = a(ab, bc), a(bc, cd)
    mid = a(abc, bcd)
    return (flatten_cubic(p0, ab, abc, mid, tol, depth + 1)
            + flatten_cubic(mid, bcd, cd, p3, tol, depth + 1))

def raster_fill(contours, N):
    alpha = bytearray(N * N)
    xs_all = []
    for y in range(N):
        yy = y + 0.5
        xs = []
        seen_xs = set()
        for contour in contours:
            m = len(contour)
            for k in range(m):
                p0 = contour[k]
                p1 = contour[(k + 1) % m]
                if abs(p0[1] - p1[1]) < 1e-12:
                    continue
                if (p0[1] <= yy < p1[1]) or (p1[1] <= yy < p0[1]):
                    t = (yy - p0[1]) / (p1[1] - p0[1])
                    xs.append((p0[0] + t * (p1[0] - p0[0]), 1 if p1[1] > p0[1] else -1))
        xs.sort(key=lambda v: v[0])
        wind = 0
        base = y * N
        k = 0
        while k < len(xs):
            x0, w0 = xs[k]
            wind += w0
            k += 1
            x1 = x0
            while k < len(xs) and wind != 0:
                wind += xs[k][1]
                x1 = xs[k][0]
                k += 1
            if x1 > x0:
                xa = max(0, int(math.floor(x0)))
                xb = min(N, int(math.ceil(x1)) + 1)
                for x in range(xa, xb):
                    alpha[base + x] = 255
    return alpha

def downsample_box(src, sw, sh, dw, dh):
    out = bytearray(dw * dh)
    for dy in range(dh):
        y0 = dy * sh // dh
        y1 = max(y0 + 1, (dy + 1) * sh // dh)
        for dx in range(dw):
            x0 = dx * sw // dw
            x1 = max(x0 + 1, (dx + 1) * sw // dw)
            s = 0
            for yy in range(y0, y1):
                base = yy * sw
                for xx in range(x0, x1):
                    s += src[base + xx]
            out[dy * dw + dx] = s // ((y1 - y0) * (x1 - x0))
    return out

def crop_bbox(alpha, w, h, thresh=3):
    xs = [x for x in range(w) if any(alpha[y * w + x] > thresh for y in range(h))]
    ys = [y for y in range(h) if any(alpha[y * w + x] > thresh for x in range(w))]
    if not xs or not ys:
        return 0, 0, w, h
    return xs[0], ys[0], xs[-1] + 1, ys[-1] + 1

def write_png(path, w, h, rgba):
    def chunk(typ, data):
        c = typ + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    raw = b''.join(b'\x00' + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    out = (b'\x89PNG\r\n\x1a\n'
           + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(raw, 9))
           + chunk(b'IEND', b''))
    open(path, 'wb').write(out)

def make_rgba(alpha, w, h, color):
    rgba = bytearray(w * h * 4)
    for i in range(w * h):
        a = alpha[i]
        o = i * 4
        rgba[o] = color[0]; rgba[o + 1] = color[1]; rgba[o + 2] = color[2]; rgba[o + 3] = a
    return bytes(rgba)

def main():
    contours = parse_path(D)
    print('contours:', len(contours), 'points:', [len(c) for c in contours])
    N = 4096
    scale = (N * 0.9) / max(VB_W, VB_H)
    ox = (N - VB_W * scale) / 2
    oy = (N - VB_H * scale) / 2
    mapped = [[(x * scale + ox, y * scale + oy) for (x, y) in c] for c in contours]
    alpha = raster_fill(mapped, N)
    master = downsample_box(alpha, N, N, 1024, 1024)
    x0, y0, x1, y1 = crop_bbox(master, 1024, 1024)
    x0 = max(0, x0 - 8); y0 = max(0, y0 - 8)
    x1 = min(1024, x1 + 8); y1 = min(1024, y1 + 8)
    cw, ch = x1 - x0, y1 - y0
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = []
    for S in sizes:
        sc = min((S * 0.88) / cw, (S * 0.88) / ch)
        dw = max(1, int(round(cw * sc)))
        dh = max(1, int(round(ch * sc)))
        crop = bytearray(cw * ch)
        for yy in range(ch):
            crop[yy * cw:(yy + 1) * cw] = master[(y0 + yy) * 1024 + x0:(y0 + yy) * 1024 + x0 + cw]
        small = downsample_box(crop, cw, ch, dw, dh)
        frame = bytearray(S * S)
        offx = (S - dw) // 2
        offy = (S - dh) // 2
        for yy in range(dh):
            frame[(offy + yy) * S + offx:(offy + yy) * S + offx + dw] = small[yy * dw:(yy + 1) * dw]
        frames.append((S, make_rgba(frame, S, S, COLOR)))
    preview = frames[4][1]
    for y in range(64):
        row = ''.join('#' if preview[(y * 64 + x) * 4 + 3] > 100 else ('+' if preview[(y * 64 + x) * 4 + 3] > 30 else '.') for x in range(64))
        print(row)
    write_png(OUT_PNG, 256, 256, frames[6][1])
    entries = b''
    blobs = b''
    offset = 6 + 16 * len(frames)
    for (S, rgba) in frames:
        def chunk(typ, data):
            c = typ + data
            return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
        raw = b''.join(b'\x00' + rgba[y * S * 4:(y + 1) * S * 4] for y in range(S))
        png = (b'\x89PNG\r\n\x1a\n'
               + chunk(b'IHDR', struct.pack('>IIBBBBB', S, S, 8, 6, 0, 0, 0))
               + chunk(b'IDAT', zlib.compress(raw, 9))
               + chunk(b'IEND', b''))
        entries += struct.pack('<BBBBHHII', 0 if S >= 256 else S, 0 if S >= 256 else S, 0, 0, 1, 32, len(png), offset)
        blobs += png
        offset += len(png)
    ico = struct.pack('<HHH', 0, 1, len(frames)) + entries + blobs
    open(OUT_ICO, 'wb').write(ico)
    print('ICO written:', len(ico), 'bytes')

main()
