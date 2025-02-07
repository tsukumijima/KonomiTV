const Spritesmith = require("spritesmith");
const sharp = require("sharp");
const fs = require("fs");
const { dirname } = require("path");
const crypto = require("crypto");
const baseDir = dirname(__dirname) + "/server/static/logos/";

let channelMapper = {};

fs.readdirSync(baseDir).forEach((filename) => {
    if (filename !== "community-channels") {
        channelMapper[filename.replace(".png", "")] = filename;
    }
});
fs.readdirSync(baseDir + "community-channels").forEach((filename) => {
    channelMapper[filename.replace(".png", "")] =
        "community-channels/" + filename;
});
let hashMapper = {};

let channelDupper = {};

let channelXY = {};
let css = `.ch-sprite {
    --ch-sprite-x: 0;
    --ch-sprite-y: 0;
    /* logo default size = 256*/
    --ch-sprite-real-width: 256;
    --ch-sprite-real-height: 256;
    --ch-sprite-scale-ratio: calc(var(--ch-sprite-width) / var(--ch-sprite-real-width));
    --ch-sprite-real-croped-height: calc(var(--ch-sprite-height) / var(--ch-sprite-scale-ratio));
  
    width: calc(var(--ch-sprite-real-width) * 1px);
    height: calc(var(--ch-sprite-real-croped-height) * 1px);
    background-position: calc(-1 * var(--ch-sprite-x) * 1px) calc(-1 * (var(--ch-sprite-y) + (var(--ch-sprite-real-height) - var(--ch-sprite-height) / var(--ch-sprite-scale-ratio)) / 2) * 1px);
    border-radius: calc(var(--ch-sprite-border-radius) / var(--ch-sprite-scale-ratio) * 1px);
    zoom: var(--ch-sprite-scale-ratio);
    transform-origin: top left;
    background-image: url(/assets/images/channel-logo-sprite.webp);
}
.ch-sprite>img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}
`;
async function run() {
    for (const key in channelMapper) {
        const path = baseDir + channelMapper[key];
        const hash = await hashFile(path);
        if (hash in hashMapper) {
            if (!channelDupper[hashMapper[hash]]) {
                channelDupper[hashMapper[hash]] = [key];
            } else {
                channelDupper[hashMapper[hash]].push(key);
            }
            delete channelMapper[key];
        } else {
            hashMapper[hash] = key;
            // console.log("ch", key, hash);
        }
    }
    const channelMapperPathReverse = Object.fromEntries(
        Object.entries(channelMapper).map(([key, value]) => [
            baseDir + value,
            key,
        ])
    );
    // console.log(channelDupper);
    Spritesmith.run(
        {
            src: Object.keys(channelMapper)
                // .filter((ch) => {
                //     // //                   = BS                     = BS4K                = CS                     = CS                     = CS
                //     // return ch.startsWith('NID4-') || ch.startsWith('NID11-') || ch.startsWith('NID6-') || ch.startsWith('NID7-') || ch.startsWith('NID10-')
                //     // return ch === "default" || !ch.startsWith("NID3");
                //     return true;
                // })
                .map((ch) => baseDir + channelMapper[ch]),
        },
        async function (err, result) {
            if (err) throw err;
            // fs.writeFileSync(__dirname + '/public/assets/images/BSCS-sprite.png',result.image);

            Object.entries(result.coordinates).forEach(([path, value]) => {
                const key = channelMapperPathReverse[path];
                channelXY[key] = { x: value.x, y: value.y };
                if (channelDupper[key]) {
                    channelDupper[key].forEach((dupch) => {
                        channelXY[dupch] = channelXY[key];
                        // console.log('dup',dupch,key)
                    });
                }
            });
            Object.entries(channelXY).forEach(([id, xy]) => {
                //                      with exploit LOL
                css += `.ch-sprite[chid=${id}] {--ch-sprite-x: ${xy.x};--ch-sprite-y: ${xy.y};}`;
                css += `.ch-sprite[chid=${id}] > img{display:none;}`;
                css += "\n";
            });

            fs.writeFileSync(__dirname + "/src/styles/channel-logo.css", css);
            console.log(channelXY);
            sharp(result.image)
                .png({ compressionLevel: 9 })
                .webp({ quality: 80 })
                .toFile(
                    __dirname + "/public/assets/images/channel-logo-sprite.webp"
                );
        }
    );
}
run();

async function hashFile(path) {
    const fileBuffer = fs.readFileSync(path);
    const hash = crypto.createHash("sha256").update(fileBuffer).digest("hex");
    return hash;
}
