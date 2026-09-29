# Huffman Image Compressor

Compress images with Huffman coding, right in your browser. Upload a colour
image, choose the size you need, and download the compressed .huff file.
Each RGB channel is encoded with its own Huffman tree, then decoded back
to verify the result.

Huffman coding is lossless. When the requested size is smaller than the
lossless size, colour levels are reduced first so the file fits the target.
The page also shows entropy, average code length, coding efficiency,
redundancy, compression ratio and PSNR.

Live demo: <link yahan daalna>
