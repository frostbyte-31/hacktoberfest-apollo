"""Real Chromium test served only on localhost; no application UI is built.
Usage: python3 browser_validate.py /tmp/wbuild/yaAGC.wasm evidence-directory rope
"""
import asyncio,json,sys,threading
from pathlib import Path
from http.server import HTTPServer,BaseHTTPRequestHandler
from playwright.async_api import async_playwright
wasm=Path(sys.argv[1]); evidence=Path(sys.argv[2]).resolve();rope=Path(sys.argv[3])
PAGE=b'''<!doctype html><title>AGC browser validation</title><pre id="status">Ready</pre><script type="module">
import {runCycles} from '/cycle_wasm.mjs';
window.runTest=async name=>{const r=await runCycles(await (await fetch('/yaAGC.wasm')).arrayBuffer(),new Uint8Array(await (await fetch('/rope.bin')).arrayBuffer()),await (await fetch('/'+name+'_inputs.txt')).text());document.querySelector('#status').textContent=JSON.stringify({test:name,cycles:r.cycles,isolated:crossOriginIsolated,shared:typeof SharedArrayBuffer,imports:r.imports,wasiCalls:r.wasiCalls},null,2);return r;};
</script>'''
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path=self.path.split('?')[0]; isolated=not path.startswith('/plain')
        files={'/yaAGC.wasm':wasm,'/rope.bin':rope,'/cycle_wasm.mjs':evidence/'cycle_wasm.mjs',**{f'/{n}_inputs.txt':evidence/f'{n}_inputs.txt' for n in ['clock','p63']}}
        if path in ('/','/plain'):data=PAGE;kind='text/html'
        elif path in files:data=files[path].read_bytes();kind='text/javascript' if path.endswith('.mjs') else 'application/octet-stream'
        else:self.send_error(404);return
        self.send_response(200);self.send_header('Content-Type',kind)
        if isolated:self.send_header('Cross-Origin-Opener-Policy','same-origin');self.send_header('Cross-Origin-Embedder-Policy','require-corp')
        self.end_headers();self.wfile.write(data)
    def log_message(self,*args):pass
async def main():
    server=HTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
    url=f'http://localhost:{server.server_port}'
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        context=await browser.new_context(viewport={'width':1280,'height':1800});page=await context.new_page()
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto(url+'/plain');await page.wait_for_function('typeof window.runTest === "function"')
        plain=await page.evaluate('async()=>{try{await window.runTest("clock");return {ok:true}}catch(e){return {ok:false,error:String(e),isolated:crossOriginIsolated,shared:typeof SharedArrayBuffer}}}')
        print('WITHOUT_ISOLATION',json.dumps(plain));assert plain['ok'] is False
        await page.goto(url+'/');await page.wait_for_function('typeof window.runTest === "function"')
        print('BROWSER',browser.version)
        for name in ['clock','p63']:
            r=await page.evaluate('(name)=>window.runTest(name)',name)
            (evidence/f'44_browser_{name}.jsonl').write_text(r.pop('transcript'))
            print('ISOLATED',name,json.dumps(r))
            await page.locator('#status').screenshot(path=f'/tmp/browser/phase2/{name}.png')
        print('PAGE_ERRORS',json.dumps(errors));assert not errors
        await browser.close()
    server.shutdown()
asyncio.run(main())