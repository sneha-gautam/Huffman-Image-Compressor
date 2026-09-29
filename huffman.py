"""
Huffman Image Source Coding (Python version of the MATLAB code)
Flow: image upload -> image ki details (size KB/MB etc.) -> target size poocho
      -> Huffman se compress -> .huff + decoded image save

Install:  pip install numpy pillow matplotlib
Run    :  python huffman_image.py            (file dialog khulega)
          python huffman_image.py photo.jpg  (direct path)
"""
import sys, os, heapq, struct
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt


# ------------------------------------------------------------------ Huffman
class Node:
    def __init__(self, weight, symbol=None, left=None, right=None):
        self.weight, self.symbol, self.left, self.right = weight, symbol, left, right


def build_tree(symbols, freqs):
    """Deterministic Huffman tree (same tree encoder + decoder dono me banta hai)."""
    heap = [(int(f), i, Node(int(f), int(s))) for i, (s, f) in enumerate(zip(symbols, freqs))]
    heapq.heapify(heap)
    counter = len(heap)
    while len(heap) > 1:
        w1, _, a = heapq.heappop(heap)      # sabse chhote 2 nodes
        w2, _, b = heapq.heappop(heap)
        heapq.heappush(heap, (w1 + w2, counter, Node(w1 + w2, None, a, b)))
        counter += 1
    return heap[0][2]


def generate_codes(root):
    codes = {}
    def walk(node, code):
        if node.symbol is not None:
            codes[node.symbol] = code or "0"   # sirf 1 unique pixel ho to code "0"
            return
        walk(node.left, code + "0")
        walk(node.right, code + "1")
    walk(root, "")
    return codes


# --------------------------------------------------------------- Encode/Decode
def encode_pixels(pixels, codes):
    syms = sorted(codes)
    lens = np.array([len(codes[s]) for s in syms], dtype=np.int32)
    maxlen = lens.max()
    table = np.zeros((256, maxlen), dtype=np.uint8)
    lenlut = np.zeros(256, dtype=np.int32)
    for s in syms:
        c = codes[s]
        table[s, :len(c)] = [int(ch) for ch in c]
        lenlut[s] = len(c)
    chunks, step = [], 1_000_000
    for i in range(0, len(pixels), step):
        p = pixels[i:i + step]
        mask = np.arange(maxlen)[None, :] < lenlut[p][:, None]
        chunks.append(table[p][mask])
    bits = np.concatenate(chunks)
    pad = (-len(bits)) % 8
    bits = np.concatenate([bits, np.zeros(pad, dtype=np.uint8)])
    return np.packbits(bits).tobytes(), pad


def save_huff(path, rows, cols, symbols, freqs, data, pad):
    with open(path, "wb") as f:
        f.write(b"HUFF")
        f.write(struct.pack("<IIHB", rows, cols, len(symbols), pad))
        for s, fr in zip(symbols, freqs):
            f.write(struct.pack("<BI", int(s), int(fr)))
        f.write(data)


def load_and_decode(path):
    with open(path, "rb") as f:
        assert f.read(4) == b"HUFF", "Ye valid .huff file nahi hai"
        rows, cols, n, pad = struct.unpack("<IIHB", f.read(11))
        symbols, freqs = [], []
        for _ in range(n):
            s, fr = struct.unpack("<BI", f.read(5))
            symbols.append(s); freqs.append(fr)
        data = f.read()
    codes = generate_codes(build_tree(symbols, freqs))
    rev = {v: k for k, v in codes.items()}
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    if pad:
        bits = bits[:-pad]
    out, cur, total = [], "", rows * cols
    for b in bits.tolist():
        cur += "1" if b else "0"
        if cur in rev:
            out.append(rev[cur]); cur = ""
            if len(out) == total:
                break
    return np.array(out, dtype=np.uint8).reshape(rows, cols)


# -------------------------------------------------------------- Tree drawing
def draw_tree(symbols, freqs, top=12):
    order = np.argsort(-freqs)[:min(top, len(symbols))]
    ts, tf = symbols[order], freqs[order]
    if len(ts) < 2:
        return
    root = build_tree(ts, tf)
    pos, leaf_x = {}, [0]
    def layout(node, depth):
        if node.symbol is not None:
            pos[id(node)] = (leaf_x[0], -depth); leaf_x[0] += 1
        else:
            layout(node.left, depth + 1); layout(node.right, depth + 1)
            pos[id(node)] = ((pos[id(node.left)][0] + pos[id(node.right)][0]) / 2, -depth)
    layout(root, 0)
    fig, ax = plt.subplots(figsize=(12, 6), num="Huffman Tree Visualization")
    def draw(node):
        x, y = pos[id(node)]
        if node.symbol is not None:
            ax.text(x, y, f"{node.symbol}\n({node.weight})", ha="center", va="center",
                    bbox=dict(boxstyle="round", fc="lightyellow"))
            return
        for child, lab in ((node.left, "0"), (node.right, "1")):
            cx, cy = pos[id(child)]
            ax.plot([x, cx], [y, cy], "k-", lw=1, zorder=0)
            ax.text((x + cx) / 2, (y + cy) / 2, lab, color="red", fontweight="bold")
            draw(child)
        ax.plot(x, y, "o", color="steelblue")
    draw(root)
    ax.axis("off")
    ax.set_title("Huffman Tree - Most Frequent Pixel Values")
    fig.text(0.5, 0.02, f"Top {len(ts)} pixel values shown. Calculations use all "
             f"{len(symbols)} unique values.", ha="center")


# ------------------------------------------------------------ Size helpers
def fmt_size(b):
    if b >= 1024 * 1024: return f"{b / (1024 * 1024):.2f} MB"
    if b >= 1024:        return f"{b / 1024:.2f} KB"
    return f"{b} bytes"


def parse_size(text):
    t = text.strip().lower().replace(" ", "")
    mult = 1024                                   # unit na ho to KB maan lenge
    if t.endswith("mb"):   mult, t = 1024 * 1024, t[:-2]
    elif t.endswith("kb"): mult, t = 1024, t[:-2]
    elif t.endswith("b"):  mult, t = 1, t[:-1]
    return int(float(t) * mult)


def huff_file_size(pix):
    """Bina encode kiye .huff file ki exact size (header + table + data)."""
    sym, fr = np.unique(pix, return_counts=True)
    codes = generate_codes(build_tree(sym, fr))
    lens = np.array([len(codes[int(s)]) for s in sym])
    bits = int((fr * lens).sum())
    return 15 + 5 * len(sym) + (bits + 7) // 8


def quantize(g, levels):
    """Gray levels kam karna (lossy). levels=256 => koi change nahi."""
    if levels >= 256:
        return g
    idx = np.round(g.astype(np.float64) * (levels - 1) / 255)
    return np.round(idx * 255 / (levels - 1)).astype(np.uint8)


def find_levels(g, target):
    """Sabse zyada gray levels jinpe .huff size <= target ho (binary search)."""
    if huff_file_size(g.ravel()) <= target:
        return 256
    if huff_file_size(quantize(g, 2).ravel()) > target:
        return None
    lo, hi = 2, 255                               # lo hamesha fit hota hai
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if huff_file_size(quantize(g, mid).ravel()) <= target:
            lo = mid
        else:
            hi = mid - 1
    return lo


# ---------------------------------------------------------------------- Main
def main():
    print("=" * 56); print("            HUFFMAN IMAGE SOURCE CODING"); print("=" * 56)

    # ---------- 1. upload
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        print("\nPlease upload an image to begin Huffman Coding.")
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
        image_path = filedialog.askopenfilename(
            title="Upload Image",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp *.tif *.tiff")])
    if not image_path:
        print("\nNo image selected. Program terminated."); return

    img = Image.open(image_path)
    orig_size = os.path.getsize(image_path)
    g = np.array(img.convert("L"), dtype=np.uint8)
    rows, cols = g.shape
    raw_gray = g.size

    # ---------- 2. image details
    print("\nImage uploaded successfully!")
    print("\n---------------- IMAGE INFORMATION ----------------")
    print(f"Image Name        : {os.path.basename(image_path)}")
    print(f"Format            : {img.format}")
    print(f"Colour Mode       : {img.mode}")
    print(f"Dimensions        : {cols} x {rows} pixels (width x height)")
    print(f"Total Pixels      : {g.size}")
    print(f"File Size         : {orig_size} bytes = {fmt_size(orig_size)}")
    print(f"Grayscale Raw Size: {fmt_size(raw_gray)} (8 bits/pixel)")
    lossless = huff_file_size(g.ravel())
    print(f"Huffman (lossless): ~{fmt_size(lossless)} (bina quality loss ke)")

    # ---------- 3. target size poocho
    while True:
        try:
            target = parse_size(input(
                "\nKitni size me image chahiye? (e.g. 200KB, 1.5MB, 500) : "))
            if target < 100:
                print("Size bahut chhoti hai, thodi badi daalo."); continue
            break
        except ValueError:
            print("Galat format. Aise likho: 200KB ya 1.5MB")

    # ---------- 4. compress
    levels = find_levels(g, target)
    if levels is None:
        min_size = huff_file_size(quantize(g, 2).ravel())
        print(f"\nIs image ko Huffman se {fmt_size(target)} tak nahi la sakte.")
        print(f"Sabse chhoti possible size ~{fmt_size(min_size)} hai. Isse zyada size daalo.")
        return
    gq = quantize(g, levels)
    if levels == 256:
        print("\nTarget size lossless Huffman se hi achieve ho gayi - quality loss ZERO.")
    else:
        print(f"\nTarget ke liye gray levels 256 -> {levels} kiye (thoda quality loss).")

    pixels = gq.ravel()
    symbols, freqs = np.unique(pixels, return_counts=True)
    n = len(symbols); prob = freqs / freqs.sum()
    codes = generate_codes(build_tree(symbols, freqs))

    print("\n-------------- PIXEL FREQUENCY TABLE --------------")
    print(f"{'Pixel':>10}{'Frequency':>15}{'Probability':>15}")
    for s, f, p in zip(symbols, freqs, prob):
        print(f"{s:>10}{f:>15}{p:>15.6f}")
    print("\n---------------- HUFFMAN CODE TABLE ----------------")
    print(f"{'Pixel':>10}{'Frequency':>12}{'Huffman Code':>20}{'Length':>8}")
    for s, f in zip(symbols, freqs):
        print(f"{s:>10}{f:>12}{codes[int(s)]:>20}{len(codes[int(s)]):>8}")

    lengths = np.array([len(codes[int(s)]) for s in symbols])
    avg_len = float((prob * lengths).sum())
    entropy = float(-(prob * np.log2(prob)).sum())
    efficiency = entropy / avg_len * 100 if avg_len > 0 else 0

    print("\nEncoding image pixels...")
    data, pad = encode_pixels(pixels, codes)
    base = os.path.splitext(os.path.basename(image_path))[0]
    out_dir = os.path.dirname(os.path.abspath(image_path))
    huff_path = os.path.join(out_dir, base + "_compressed.huff")
    save_huff(huff_path, rows, cols, symbols, freqs, data, pad)
    print("Image encoding completed successfully.")

    decoded = load_and_decode(huff_path)
    ok = np.array_equal(decoded, gq)
    dec_path = os.path.join(out_dir, base + "_decoded.png")
    Image.fromarray(decoded, "L").save(dec_path)
    huff_size = os.path.getsize(huff_path)

    mse = np.mean((g.astype(float) - decoded.astype(float)) ** 2)
    psnr = "inf (lossless)" if mse == 0 else f"{10 * np.log10(255 ** 2 / mse):.2f} dB"

    print("\n" + "=" * 56); print("                   HUFFMAN RESULTS"); print("=" * 56)
    print(f"Unique Pixel Values   : {n}")
    print(f"Average Code Length   : {avg_len:.3f} bits/pixel")
    print(f"Entropy               : {entropy:.3f} bits/pixel")
    print(f"Coding Efficiency     : {efficiency:.2f} %")
    print(f"Coding Redundancy     : {100 - efficiency:.2f} %")
    print(f"Compression Ratio     : {raw_gray * 8 / int(sum(freqs * lengths)):.3f}  (8 bpp raw vs Huffman)")
    print(f"\nRequested Size        : {fmt_size(target)}")
    print(f"Compressed .huff Size : {fmt_size(huff_size)}  ({huff_size} bytes)")
    print(f"Original File Size    : {fmt_size(orig_size)}")
    print(f"Decode Check          : {'PASS' if ok else 'FAIL'}")
    print(f"Quality (PSNR)        : {psnr}")
    print(f"\nSaved compressed file : {huff_path}")
    print(f"Saved decoded image   : {dec_path}  (viewable image, PNG size {fmt_size(os.path.getsize(dec_path))})")
    print("=" * 56)

    fig, ax = plt.subplots(1, 3, figsize=(14, 5), num="Images")
    ax[0].imshow(img); ax[0].set_title("Original Image")
    ax[1].imshow(g, cmap="gray", vmin=0, vmax=255); ax[1].set_title("Grayscale Image")
    ax[2].imshow(decoded, cmap="gray", vmin=0, vmax=255); ax[2].set_title("Decoded from .huff")
    for a in ax: a.axis("off")
    draw_tree(symbols, freqs)
    plt.show()


if __name__ == "__main__":
    main()