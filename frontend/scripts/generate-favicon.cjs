/* eslint-disable no-console */
const fs = require('node:fs');
const path = require('node:path');

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function mix(a, b, t) {
  return a + (b - a) * t;
}

function mix3(a, b, t) {
  return [mix(a[0], b[0], t), mix(a[1], b[1], t), mix(a[2], b[2], t)];
}

function smoothstep(edge0, edge1, x) {
  const t = clamp((x - edge0) / (edge1 - edge0), 0, 1);
  return t * t * (3 - 2 * t);
}

function palette(t) {
  const stops = [
    [0.0, [34, 211, 238]],
    [0.33, [99, 102, 241]],
    [0.66, [244, 114, 182]],
    [1.0, [34, 211, 238]],
  ];
  const clamped = ((t % 1) + 1) % 1;
  for (let i = 0; i < stops.length - 1; i++) {
    const [t0, c0] = stops[i];
    const [t1, c1] = stops[i + 1];
    if (clamped >= t0 && clamped <= t1) {
      const local = (clamped - t0) / (t1 - t0);
      return mix3(c0, c1, local);
    }
  }
  return stops[stops.length - 1][1];
}

function distToSegment(px, py, ax, ay, bx, by) {
  const abx = bx - ax;
  const aby = by - ay;
  const apx = px - ax;
  const apy = py - ay;
  const abLen2 = abx * abx + aby * aby;
  const t = abLen2 === 0 ? 0 : clamp((apx * abx + apy * aby) / abLen2, 0, 1);
  const cx = ax + abx * t;
  const cy = ay + aby * t;
  const dx = px - cx;
  const dy = py - cy;
  return Math.sqrt(dx * dx + dy * dy);
}

function circleAlpha(px, py, cx, cy, radius, aa = 0.9) {
  const dx = px - cx;
  const dy = py - cy;
  const d = Math.sqrt(dx * dx + dy * dy);
  return 1 - smoothstep(radius - aa, radius + aa, d);
}

function lineAlpha(px, py, ax, ay, bx, by, width, aa = 0.9) {
  const d = distToSegment(px, py, ax, ay, bx, by);
  return 1 - smoothstep(width / 2 - aa, width / 2 + aa, d);
}

function roundedCornerAlpha(x, y, size, radius) {
  const left = x;
  const right = size - 1 - x;
  const top = y;
  const bottom = size - 1 - y;
  const ux = Math.min(left, right);
  const uy = Math.min(top, bottom);
  if (ux >= radius || uy >= radius) return 1;
  const px = ux + 0.5;
  const py = uy + 0.5;
  const cx = radius;
  const cy = radius;
  const dx = px - cx;
  const dy = py - cy;
  const d = Math.sqrt(dx * dx + dy * dy);
  return 1 - smoothstep(radius - 1.0, radius + 1.0, d);
}

function blend(base, overlayRgb, overlayAlpha) {
  const a = clamp(overlayAlpha, 0, 1);
  return [
    overlayRgb[0] * a + base[0] * (1 - a),
    overlayRgb[1] * a + base[1] * (1 - a),
    overlayRgb[2] * a + base[2] * (1 - a),
    base[3] + a - base[3] * a,
  ];
}

function render(size) {
  const rgba = new Uint8Array(size * size * 4);
  const cx = (size - 1) / 2;
  const cy = (size - 1) / 2;

  const borderThickness = Math.max(2, Math.round(size * 0.095));
  const cornerRadius = Math.max(3, Math.round(size * 0.26));

  const coreR = size * 0.23;
  const nodeR = size * 0.095;
  const lineW = size * 0.085;

  const nodes = [
    { x: size * 0.33, y: size * 0.36, rgb: [244, 114, 182] },
    { x: size * 0.72, y: size * 0.33, rgb: [34, 211, 238] },
    { x: size * 0.58, y: size * 0.77, rgb: [245, 158, 11] },
  ];

  const lineRgb = [165, 180, 252];

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const u = x / Math.max(1, size - 1);
      const v = y / Math.max(1, size - 1);

      const bgTop = [11, 16, 34];
      const bgBottom = [5, 8, 22];
      let color = [...mix3(bgTop, bgBottom, v), 1];

      const hx = u - 0.22;
      const hy = v - 0.2;
      const hd = Math.sqrt(hx * hx + hy * hy);
      const h = Math.pow(clamp(1 - hd / 0.9, 0, 1), 1.6);
      const glow = [168, 85, 247];
      color = blend(color, glow, 0.22 * h);

      const edgeDist = Math.min(x, y, size - 1 - x, size - 1 - y);
      if (edgeDist < borderThickness) {
        const angle = Math.atan2(y - cy, x - cx);
        const t = (angle + Math.PI) / (2 * Math.PI);
        const bcol = palette(t);
        color = blend(color, bcol, 0.92);
      }

      for (const node of nodes) {
        const alpha = lineAlpha(x + 0.5, y + 0.5, node.x, node.y, cx, cy, lineW);
        if (alpha > 0) color = blend(color, lineRgb, 0.9 * alpha);
      }

      const coreAlpha = circleAlpha(x + 0.5, y + 0.5, cx, cy, coreR);
      if (coreAlpha > 0) {
        const dx = (x + 0.5 - cx) / coreR;
        const dy = (y + 0.5 - cy) / coreR;
        const d = clamp(Math.sqrt(dx * dx + dy * dy), 0, 1);
        const coreOuter = [244, 114, 182];
        const coreInner = [255, 255, 255];
        const coreBase = mix3(coreOuter, coreInner, 0.55 * (1 - d));
        const coreTint = palette((Math.atan2(dy, dx) + Math.PI) / (2 * Math.PI));
        const coreRgb = mix3(coreBase, coreTint, 0.45);
        color = blend(color, coreRgb, coreAlpha);
      }

      for (const node of nodes) {
        const alpha = circleAlpha(x + 0.5, y + 0.5, node.x, node.y, nodeR);
        if (alpha > 0) {
          const nx = (x + 0.5 - node.x) / nodeR;
          const ny = (y + 0.5 - node.y) / nodeR;
          const nd = clamp(Math.sqrt(nx * nx + ny * ny), 0, 1);
          const highlight = Math.pow(clamp(1 - nd, 0, 1), 1.8);
          const rgb = mix3(node.rgb, [255, 255, 255], 0.28 * highlight);
          color = blend(color, rgb, alpha);
        }
      }

      const ringAlpha = 1 - smoothstep(coreR + size * 0.05, coreR + size * 0.08, Math.hypot(x + 0.5 - cx, y + 0.5 - cy));
      if (ringAlpha > 0) color = blend(color, [255, 255, 255], 0.11 * ringAlpha);

      const maskA = roundedCornerAlpha(x, y, size, cornerRadius);
      const finalA = clamp(maskA, 0, 1);

      const idx = (y * size + x) * 4;
      rgba[idx] = clamp(Math.round(color[0]), 0, 255);
      rgba[idx + 1] = clamp(Math.round(color[1]), 0, 255);
      rgba[idx + 2] = clamp(Math.round(color[2]), 0, 255);
      rgba[idx + 3] = clamp(Math.round(255 * finalA), 0, 255);
    }
  }

  return rgba;
}

function makeDib(size, rgba) {
  const header = Buffer.alloc(40);
  header.writeUInt32LE(40, 0);
  header.writeInt32LE(size, 4);
  header.writeInt32LE(size * 2, 8);
  header.writeUInt16LE(1, 12);
  header.writeUInt16LE(32, 14);
  header.writeUInt32LE(0, 16);
  header.writeUInt32LE(size * size * 4, 20);
  header.writeInt32LE(0, 24);
  header.writeInt32LE(0, 28);
  header.writeUInt32LE(0, 32);
  header.writeUInt32LE(0, 36);

  const pixel = Buffer.alloc(size * size * 4);
  for (let y = 0; y < size; y++) {
    const srcY = y;
    const dstY = size - 1 - y;
    for (let x = 0; x < size; x++) {
      const src = (srcY * size + x) * 4;
      const dst = (dstY * size + x) * 4;
      const r = rgba[src];
      const g = rgba[src + 1];
      const b = rgba[src + 2];
      const a = rgba[src + 3];
      pixel[dst] = b;
      pixel[dst + 1] = g;
      pixel[dst + 2] = r;
      pixel[dst + 3] = a;
    }
  }

  const maskRowBytes = Math.ceil(size / 32) * 4;
  const mask = Buffer.alloc(maskRowBytes * size);
  return Buffer.concat([header, pixel, mask]);
}

function buildIco(images) {
  const count = images.length;
  const header = Buffer.alloc(6 + count * 16);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(count, 4);

  let offset = header.length;
  for (let i = 0; i < count; i++) {
    const img = images[i];
    const entry = 6 + i * 16;
    header.writeUInt8(img.size === 256 ? 0 : img.size, entry);
    header.writeUInt8(img.size === 256 ? 0 : img.size, entry + 1);
    header.writeUInt8(0, entry + 2);
    header.writeUInt8(0, entry + 3);
    header.writeUInt16LE(1, entry + 4);
    header.writeUInt16LE(32, entry + 6);
    header.writeUInt32LE(img.dib.length, entry + 8);
    header.writeUInt32LE(offset, entry + 12);
    offset += img.dib.length;
  }

  return Buffer.concat([header, ...images.map((img) => img.dib)]);
}

function main() {
  const outPath = path.join(__dirname, '..', 'public', 'favicon.ico');
  const sizes = [16, 32, 48];
  const images = sizes.map((size) => ({ size, dib: makeDib(size, render(size)) }));
  const ico = buildIco(images);
  fs.writeFileSync(outPath, ico);
  console.log(`Wrote ${path.relative(process.cwd(), outPath)} (${ico.length} bytes)`);
}

main();

