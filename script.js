"use strict";
const $ = id => document.getElementById(id);
let planes, isGray, W, H, fileSize, huffBytes, decodedCanvas, baseName;

/* ---------- helpers ---------- */
const fmt = b => b >= 1048576 ? (b / 1048576).toFixed(2) + " MB" : b >= 1024 ? (b / 1024).toFixed(2) + " KB" : b + " bytes";
const rows = (el, pairs) => el.innerHTML = pairs.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
const download = (blob, name) => { const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000); };
const histOf = p => { const h = new Array(256).fill(0); for (let i = 0; i < p.length; i++) h[p[i]]++; return h; };

/* ---------- Huffman ---------- */
function buildTree(freq) {
  const sym = [], w = [], L = [], R = [];
  for (let s = 0; s < 256; s++) if (freq[s] > 0) { sym.push(s); w.push(freq[s]); L.push(-1); R.push(-1); }
  const n = sym.length; let act = sym.map((_, i) => i);
  while (act.length > 1) {
    act.sort((a, b) => w[a] - w[b] || a - b);
    const a = act.shift(), b = act.shift();
    w.push(w[a] + w[b]); L.push(a); R.push(b); act.push(w.length - 1);
  }
  return { sym, n, w, L, R, root: act[0] };
}
function codesOf(t) {
  const c = new Array(t.w.length); c[t.root] = "";
  for (let id = t.w.length - 1; id >= t.n; id--) { c[t.L[id]] = c[id] + "0"; c[t.R[id]] = c[id] + "1"; }
  const out = {}; t.sym.forEach((s, i) => out[s] = c[i] || "0"); return out;
}
function chanInfo(freq) {
  const t = buildTree(freq), c = codesOf(t); let bits = 0;
  t.sym.forEach(s => bits += freq[s] * c[s].length);
  return { t, c, bits };
}
/* file layout: "HUFC" | height u32 | width u32 | channels u8 | per channel: n u16, pad u8, dataLen u32, n x (symbol u8, freq u32), data */
const chanBytes = freq => { const { t, bits } = chanInfo(freq); return 7 + 5 * t.n + Math.ceil(bits / 8); };
const totalSize = hs => 13 + hs.reduce((a, f) => a + chanBytes(f), 0);

/* ---------- quantisation (lossy step, used only when the target is small) ---------- */
function quantMap(levels) {
  const m = new Uint8Array(256);
  for (let g = 0; g < 256; g++) m[g] = levels >= 256 ? g : Math.round(Math.round(g * (levels - 1) / 255) * 255 / (levels - 1));
  return m;
}
function mapHist(hist, map) { const f = new Array(256).fill(0); for (let g = 0; g < 256; g++) f[map[g]] += hist[g]; return f; }
const mapAll = (hs, map) => hs.map(h => mapHist(h, map));
function findLevels(hs, target) {
  if (totalSize(hs) <= target) return 256;
  if (totalSize(mapAll(hs, quantMap(2))) > target) return null;
  let lo = 2, hi = 255;
  while (lo < hi) { const mid = (lo + hi + 1) >> 1; totalSize(mapAll(hs, quantMap(mid))) <= target ? lo = mid : hi = mid - 1; }
  return lo;
}

/* ---------- encode / decode ---------- */
function encodeChannel(q, freq) {
  const { t, c, bits } = chanInfo(freq);
  const data = new Uint8Array(Math.ceil(bits / 8)), pad = data.length * 8 - bits;
  let pos = 0;
  for (let i = 0; i < q.length; i++) {
    const code = c[q[i]];
    for (let k = 0; k < code.length; k++, pos++) if (code.charCodeAt(k) === 49) data[pos >> 3] |= 128 >> (pos & 7);
  }
  const out = new Uint8Array(7 + 5 * t.n + data.length), dv = new DataView(out.buffer);
  dv.setUint16(0, t.n, true); dv.setUint8(2, pad); dv.setUint32(3, data.length, true);
  let p = 7; t.sym.forEach(s => { dv.setUint8(p, s); dv.setUint32(p + 1, freq[s], true); p += 5; });
  out.set(data, p);
  return { out, t, c, bits };
}
function pack(parts) {
  const buf = new Uint8Array(13 + parts.reduce((a, x) => a + x.length, 0)), dv = new DataView(buf.buffer);
  buf.set([72, 85, 70, 67]);                          // "HUFC"
  dv.setUint32(4, H, true); dv.setUint32(8, W, true); dv.setUint8(12, parts.length);
  let p = 13; parts.forEach(x => { buf.set(x, p); p += x.length; });
  return buf;
}
function decode(buf) {
  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  if (String.fromCharCode(...buf.subarray(0, 4)) !== "HUFC") throw new Error("Not a valid .huff file");
  const h = dv.getUint32(4, true), w = dv.getUint32(8, true), nc = dv.getUint8(12); let p = 13;
  const out = [];
  for (let c = 0; c < nc; c++) {
    const n = dv.getUint16(p, true), pad = dv.getUint8(p + 2), len = dv.getUint32(p + 3, true); p += 7;
    const freq = new Array(256).fill(0);
    for (let i = 0; i < n; i++, p += 5) freq[dv.getUint8(p)] = dv.getUint32(p + 1, true);
    const data = buf.subarray(p, p + len); p += len;
    const t = buildTree(freq), px = new Uint8Array(w * h);
    if (t.n === 1) px.fill(t.sym[0]);
    else {
      const total = len * 8 - pad; let node = t.root, o = 0;
      for (let b = 0; b < total && o < px.length; b++) {
        node = (data[b >> 3] >> (7 - (b & 7))) & 1 ? t.R[node] : t.L[node];
        if (t.L[node] < 0) { px[o++] = t.sym[node]; node = t.root; }
      }
    }
    out.push(px);
  }
  return { planes: out, w, h };
}

/* ---------- step 1: upload ---------- */
const drop = $("drop");
$("file").addEventListener("change", e => e.target.files[0] && load(e.target.files[0]));
["dragover", "dragenter"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", e => e.dataTransfer.files[0] && load(e.dataTransfer.files[0]));

function load(file) {
  const img = new Image();
  img.onload = () => {
    W = img.naturalWidth; H = img.naturalHeight; fileSize = file.size;
    baseName = file.name.replace(/\.[^.]+$/, "");
    const c = $("preview"); c.width = W; c.height = H;
    const ctx = c.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(img, 0, 0);
    const d = ctx.getImageData(0, 0, W, H).data, n = W * H;
    const R = new Uint8Array(n), G = new Uint8Array(n), B = new Uint8Array(n); let same = true;
    for (let i = 0; i < n; i++) {
      R[i] = d[4 * i]; G[i] = d[4 * i + 1]; B[i] = d[4 * i + 2];
      if (same && (R[i] !== G[i] || G[i] !== B[i])) same = false;
    }
    isGray = same; planes = same ? [R] : [R, G, B];      // colour images keep all three channels
    const lossless = totalSize(planes.map(histOf));
    rows($("details"), [
      ["Name", file.name], ["Format", file.type || "unknown"],
      ["Colour mode", isGray ? "Grayscale (1 channel)" : "Colour RGB (3 channels)"],
      ["Dimensions", `${W} × ${H} px`], ["Total pixels", n.toLocaleString()],
      ["File size", `${fmt(file.size)} (${file.size.toLocaleString()} bytes)`],
      ["Raw size", `${fmt(n * planes.length)} (8 bits per channel)`], ["Lossless Huffman size", "≈ " + fmt(lossless)],
    ]);
    $("hint").textContent = `Lossless Huffman gives about ${fmt(lossless)}. Ask for less and the colour detail is reduced to fit.`;
    $("msg").textContent = ""; $("s4").hidden = true;
    $("s2").hidden = $("s3").hidden = false;
    $("target").focus();
  };
  img.onerror = () => alert("This file could not be read as an image.");
  img.src = URL.createObjectURL(file);
}

/* ---------- step 3: compress ---------- */
$("go").addEventListener("click", () => {
  const msg = $("msg"); msg.textContent = "";
  const target = Math.floor(parseFloat($("target").value) * ($("unit").value === "MB" ? 1048576 : 1024));
  if (!(target >= 100)) { msg.textContent = "Enter a size of at least 100 bytes, for example 200 KB."; return; }
  $("go").disabled = true; $("go").textContent = "Compressing…";
  setTimeout(() => { try { run(target); } catch (e) { msg.textContent = "Something went wrong: " + e.message; } $("go").disabled = false; $("go").textContent = "Compress image"; }, 30);
});

function run(target) {
  const hs = planes.map(histOf), nc = planes.length, N = W * H;
  const names = isGray ? ["Gray"] : ["R", "G", "B"];
  const levels = findLevels(hs, target);
  if (levels === null) {
    $("msg").textContent = `Huffman cannot reach ${fmt(target)} for this image. The smallest possible is about ${fmt(totalSize(mapAll(hs, quantMap(2))))}. Enter a larger size.`;
    return;
  }
  const map = quantMap(levels), qs = planes.map(p => p.map(v => map[v])), fs = mapAll(hs, map);
  const encs = qs.map((q, c) => encodeChannel(q, fs[c]));
  const buf = pack(encs.map(e => e.out)); huffBytes = buf;

  const dp = decode(buf).planes;                        // decode from the file bytes to verify
  const ok = dp.every((pl, c) => pl.every((v, i) => v === qs[c][i]));
  let mse = 0; dp.forEach((pl, c) => { for (let i = 0; i < N; i++) { const d = planes[c][i] - pl[i]; mse += d * d; } });
  mse /= N * nc;
  const psnr = mse === 0 ? "∞ (lossless)" : (10 * Math.log10(65025 / mse)).toFixed(2) + " dB";

  let avg = 0, ent = 0, bits = 0;
  encs.forEach((e, c) => {
    e.t.sym.forEach(s => { const p = fs[c][s] / N; avg += p * e.c[s].length / nc; ent -= p * Math.log2(p) / nc; });
    bits += e.bits;
  });
  const eff = avg > 0 ? ent / avg * 100 : 0;

  decodedCanvas = $("out"); decodedCanvas.width = W; decodedCanvas.height = H;
  const ctx = decodedCanvas.getContext("2d"), im = ctx.createImageData(W, H);
  for (let i = 0; i < N; i++) {
    im.data[4 * i] = dp[0][i]; im.data[4 * i + 1] = dp[nc === 3 ? 1 : 0][i]; im.data[4 * i + 2] = dp[nc === 3 ? 2 : 0][i]; im.data[4 * i + 3] = 255;
  }
  ctx.putImageData(im, 0, 0);

  $("summary").textContent = levels === 256
    ? `Done. ${fmt(fileSize)} → ${fmt(buf.length)} with no quality loss.`
    : `Done. Compressed to ${fmt(buf.length)} (requested ${fmt(target)}). Colour levels per channel reduced from 256 to ${levels}.`;
  rows($("stats"), [
    ["Requested size", fmt(target)], [".huff size", `${fmt(buf.length)} (${buf.length.toLocaleString()} bytes)`],
    ["Original file", fmt(fileSize)], [`Unique values (${names.join(" / ")})`, encs.map(e => e.t.n).join(" / ")],
    ["Average code length", avg.toFixed(3) + " bits/sample"], ["Entropy", ent.toFixed(3) + " bits/sample"],
    ["Coding efficiency", eff.toFixed(2) + " %"], ["Coding redundancy", (100 - eff).toFixed(2) + " %"],
    ["Compression ratio", (N * nc * 8 / bits).toFixed(3)], ["PSNR", psnr], ["Decode check", ok ? "Pass" : "Fail"],
  ]);
  $("tbl").innerHTML = "<tr><th>Channel</th><th>Value</th><th>Frequency</th><th>Probability</th><th>Huffman code</th><th>Length</th></tr>" +
    encs.flatMap((e, c) => e.t.sym.map(s => `<tr><td>${names[c]}</td><td>${s}</td><td>${fs[c][s]}</td><td>${(fs[c][s] / N).toFixed(6)}</td><td>${e.c[s]}</td><td>${e.c[s].length}</td></tr>`)).join("");
  $("s4").hidden = false; $("s4").scrollIntoView({ behavior: "smooth" });
}

$("dlHuff").addEventListener("click", () => download(new Blob([huffBytes]), baseName + "_compressed.huff"));
$("dlPng").addEventListener("click", () => decodedCanvas.toBlob(b => download(b, baseName + "_decoded.png")));