#!/usr/bin/env python3
"""LINE Creators Market 入稿 ZIP の規格チェック。

使い方:  python3 check_zip.py 限界オペレーター.zip [--sheet out.png]
必要:    pip install pillow

判定項目: main.png 240x240 / tab.png 96x74 / 本体 370x320 以内・偶数px /
          背景透過(四隅 α=0) / 枚数 8,16,24,32,40 / 各 1MB 未満 / zip 直下フラット配置
"""
import io, sys, zipfile
from PIL import Image, ImageDraw

def check(path, sheet=None):
    z = zipfile.ZipFile(path)
    names = [n for n in z.namelist() if not n.endswith('/')]
    fails = []
    if any('/' in n for n in names):
        fails.append('zip 直下にフラット配置されていない（フォルダあり）')
    stickers = sorted(n for n in names if n[:2].isdigit() and n.lower().endswith('.png'))
    imgs = {}
    for n in names:
        data = z.read(n)
        if len(data) >= 1_000_000:
            fails.append(f'{n}: 1MB 以上')
        try:
            im = Image.open(io.BytesIO(data)); im.load()
        except Exception as e:
            fails.append(f'{n}: 画像として読めない ({e})'); continue
        if im.format != 'PNG':
            fails.append(f'{n}: PNG ではない ({im.format})')
        im = im.convert('RGBA'); imgs[n] = im
        w, h = im.size
        if n == 'main.png' and (w, h) != (240, 240): fails.append(f'main.png: {w}x{h} (240x240 必須)')
        elif n == 'tab.png' and (w, h) != (96, 74): fails.append(f'tab.png: {w}x{h} (96x74 必須)')
        elif n in stickers:
            if w > 370 or h > 320: fails.append(f'{n}: {w}x{h} (370x320 以内)')
            if w % 2 or h % 2: fails.append(f'{n}: 奇数ピクセル {w}x{h}')
        corners = [im.getpixel(p)[3] for p in [(0,0),(w-1,0),(0,h-1),(w-1,h-1)]]
        if any(a != 0 for a in corners): fails.append(f'{n}: 四隅が透明でない')
    if 'main.png' not in imgs: fails.append('main.png が無い')
    if 'tab.png' not in imgs: fails.append('tab.png が無い')
    if len(stickers) not in (8, 16, 24, 32, 40): fails.append(f'本体 {len(stickers)} 枚（8/16/24/32/40 のみ可）')
    print(f'{path}: {len(names)} ファイル, 本体 {len(stickers)} 枚')
    for f in fails: print('  NG', f)
    if not fails: print('  OK 全項目クリア')
    if sheet and stickers:
        cols, s = 8, 0.6; cw, ch = int(370*s), int(320*s)+22
        rows = -(-len(stickers)//cols)
        out = Image.new('RGB', (cols*cw, rows*ch), 'white'); d = ImageDraw.Draw(out)
        for i, n in enumerate(stickers):
            im = imgs[n].resize((cw, int(320*s))); x, y = (i%cols)*cw, (i//cols)*ch
            out.paste(im, (x, y), im); d.text((x+4, y+int(320*s)+4), n, fill='black')
        out.save(sheet); print('  一覧画像:', sheet)
    return not fails

if __name__ == '__main__':
    args = sys.argv[1:]
    sheet = None
    if '--sheet' in args:
        i = args.index('--sheet'); sheet = args[i+1]; del args[i:i+2]
    ok = all(check(p, sheet) for p in args)
    sys.exit(0 if ok else 1)
