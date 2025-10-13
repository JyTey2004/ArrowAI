// Upscale all frames from ./public/frames to ./public/frames_4k
// Usage: node scripts/upscale.js 3840 2160   (width height)

import fs from 'node:fs/promises';
import path from 'node:path';
import fg from 'fast-glob';
import sharp from 'sharp';

const [, , W = '3840', H = '2160'] = process.argv;
const inDir = path.resolve('public/frames');
const outDir = path.resolve(`public/frames_${W}x${H}`);

await fs.mkdir(outDir, { recursive: true });

const files = await fg(['frame_*.jpg', 'frame_*.png'], { cwd: inDir, onlyFiles: true, absolute: true });

console.log(`Upscaling ${files.length} files → ${W}x${H} …`);
let done = 0;

await Promise.all(files.map(async (src) => {
    const name = path.basename(src);
    const dst = path.join(outDir, name);
    await sharp(src)
        .resize(Number(W), Number(H), { fit: 'cover', kernel: sharp.kernel.lanczos3 })
        .jpeg({ quality: 92, mozjpeg: true }) // or .png()
        .toFile(dst);
    if (++done % 25 === 0) console.log(`  ${done}/${files.length}`);
}));

console.log('✅ Done:', outDir);
