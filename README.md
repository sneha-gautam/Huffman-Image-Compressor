# Huffman Image Compressor

A small tool that compresses an image with Huffman coding, and it all runs in your browser. Drop in a colour image, tell it how big you want the file to be, and it gives you back a compressed `.huff` file. Your image never leaves your computer.

**Try it:** <https://sneha-gautam.github.io/Huffman-Image-Compressor/>

![Uploading image.png…]()


## Why I made this

I started with a MATLAB script for Huffman source coding that worked on grayscale images and just printed numbers. I wanted something I could actually use: pick an image, ask for a size, get a file back. So I rewrote it in Python, then rebuilt it as a web page so anyone can open it without installing anything.

## Using it

1. Choose an image (JPG, PNG, BMP or TIFF), or drag it onto the page.
2. The page shows its details: dimensions, colour mode, file size, and what lossless Huffman would give you.
3. Type the size you want, like `200 KB` or `1.5 MB`, and hit Compress.
4. Download the `.huff` file. You also get a decoded PNG so you can see how it turned out.

## How it works

Each colour channel (R, G and B) gets its own Huffman tree, so colour images stay in colour. If an image is really grayscale, it's stored as one channel instead of three.

Huffman coding itself is lossless. If the size you ask for is at least what lossless can reach, you get the exact same pixels back. If you ask for less, the tool first reduces the number of colour levels (it searches for the largest number of levels that still fits) and then applies Huffman coding. That first step does lose some detail, and the page shows the PSNR so you can see how much.

After encoding, the page decodes the compressed bytes again and checks them against what it encoded, so you'll see "Decode check: Pass" when everything matches.

There's also a stats panel with entropy, average code length, coding efficiency, redundancy and compression ratio, and a table with every value's frequency, probability and code.

## The .huff format

Everything is little-endian. The file starts with a 13-byte header:

- `HUFC` (4 bytes)
- height (4 bytes)
- width (4 bytes)
- number of channels (1 byte, either 1 or 3)

After that comes one block per channel:

- number of distinct values `n` (2 bytes)
- padding bits at the end of the data (1 byte)
- length of the encoded data (4 bytes)
- `n` entries of value (1 byte) and frequency (4 bytes)
- the packed Huffman bits

The decoder rebuilds the same tree from those frequencies. Ties are broken the same way in the encoder and decoder, so they always agree.

## Running it on your machine

There's nothing to install. Open `index.html` in a browser, or serve the folder if you prefer:

```
python3 -m http.server 8000
```

then go to http://localhost:8000.

## Putting it online

It's a static site, so GitHub Pages works well. Push the files to a repo, go to Settings > Pages, pick the `main` branch and the root folder, and save. A minute or so later it's live at `https://<username>.github.io/<repo-name>/`.

## Files

- `index.html` is the page
- `style.css` is the look (white theme, switches to dark automatically)
- `script.js` has the Huffman code, the size fitting, and the page logic

## Things to know

- JPGs and PNGs are already compressed, so Huffman on raw pixels can give a file bigger than the original. This is a way to see source coding in action, not a JPEG replacement.
- Very small targets can't be reached. If that happens, the page tells you the smallest size possible for that image.
- Huge images may take a few seconds.
- The two fonts come from Google Fonts. Offline, it falls back to your system fonts.

## License

MIT. Add a `LICENSE` file to the repo.
