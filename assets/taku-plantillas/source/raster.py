import asyncio, glob, os, re
from playwright.async_api import async_playwright

async def main():
    files = sorted(glob.glob("../svg/*.svg"))
    os.makedirs("../png", exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for f in files:
            s = open(f).read()
            w = int(re.search(r'width="(\d+)"', s).group(1))
            h = int(re.search(r'height="(\d+)"', s).group(1))
            pg = await b.new_page(viewport={"width": w, "height": h},
                                  device_scale_factor=1)
            await pg.set_content(
                "<style>html,body{margin:0;padding:0}svg{display:block}</style>" + s)
            await pg.screenshot(path="../png/" + os.path.basename(f).replace(".svg", ".png"))
            await pg.close()
        await b.close()
    print(f"rendered {len(files)}")

asyncio.run(main())
