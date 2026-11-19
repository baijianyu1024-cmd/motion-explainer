#!/usr/bin/env node
// Render a single local HTML timeline. Requires Node 20+, Chromium and FFmpeg.
import {spawn, spawnSync} from 'node:child_process';
import {access, mkdtemp, rm, rename, stat} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {basename, dirname, join, resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {parseArgs} from 'node:util';
import {once} from 'node:events';
import {setTimeout as delay} from 'node:timers/promises';

const {positionals, values} = parseArgs({allowPositionals:true, options:{
  audio:{type:'string'}, fps:{type:'string',default:'24'}, width:{type:'string',default:'1920'},
  height:{type:'string',default:'1080'}, chrome:{type:'string'}, help:{type:'boolean'}
}});
const usage = 'node export.mjs input.html output.mp4 [--audio narration.wav] [--fps 24] [--width 1920 --height 1080] [--chrome /path/to/chrome]';
if (values.help || positionals.length !== 2) {
  console.log(usage);
  process.exit(values.help ? 0 : 1);
}

async function chromeBinary() {
  if (values.chrome || process.env.CHROME_BIN) return values.chrome || process.env.CHROME_BIN;
  const candidates = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/usr/bin/google-chrome','/usr/bin/chromium','/usr/bin/chromium-browser'];
  for (const candidate of candidates) {
    try { await access(candidate); return candidate; } catch {}
  }
  throw Error('Chrome or Chromium required. Set --chrome or CHROME_BIN.');
}

// Chromium exchanges zero-terminated DevTools messages over two anonymous pipes.
function connect(browser) {
  let buffer = '';
  let id = 0;
  let closed = false;
  const pending = new Map();
  const input = browser.stdio[3];
  const output = browser.stdio[4];
  const close = () => {
    closed = true;
    for (const request of pending.values()) request.reject(Error('Headless Chrome closed.'));
    pending.clear();
  };
  browser.once('error',close);
  output.once('end',close);
  input.on('error',close);
  output.setEncoding('utf8');
  output.on('data', chunk => {
    buffer += chunk;
    let index;
    while ((index = buffer.indexOf('\0')) !== -1) {
      const message = JSON.parse(buffer.slice(0,index));
      buffer = buffer.slice(index+1);
      const request = pending.get(message.id);
      if (!request) continue;
      pending.delete(message.id);
      if (message.error) request.reject(Error(message.error.message));
      else request.resolve(message.result);
    }
  });
  return async function call(method,params={},sessionId) {
    if (closed) throw Error('Chrome is unavailable.');
    const number = ++id;
    let timer;
    try {
      return await new Promise((resolve,reject)=>{
        pending.set(number,{resolve,reject});
        timer = setTimeout(()=>reject(Error('Chrome timeout in '+method)),30000);
        input.write(JSON.stringify({id:number,method,params,sessionId})+'\0');
      });
    } finally { clearTimeout(timer); pending.delete(number); }
  };
}

async function render() {
  const input = resolve(positionals[0]);
  const target = resolve(positionals[1]);
  const [width,height,fps] = [values.width,values.height,values.fps].map(Number);
  if (![width,height].every(n=>Number.isInteger(n)&&n>0&&n%2===0) ||
      !Number.isInteger(fps)||fps<1||fps>120) throw Error('Use positive even dimensions and an integer frame rate from 1–120.');
  await access(input);
  if (values.audio) await access(values.audio);
  if (target === input || (values.audio && resolve(values.audio)===target)) throw Error('Input and output must differ.');
  if (spawnSync('ffmpeg',['-version'],{stdio:'ignore'}).status!==0) throw Error('Install ffmpeg and make it available on PATH.');
  const binary = await chromeBinary();
  const profile = await mkdtemp(join(tmpdir(),'motion-chrome-'));
  let temp, browser, encoder;
  try {
    temp = await mkdtemp(join(dirname(target),'.motion-render-'));
    const partial = join(temp,'movie.mp4');
    browser = spawn(binary,['--headless','--disable-background-networking','--disable-sync',
      '--no-first-run','--no-default-browser-check','--disable-extensions',
      '--remote-debugging-pipe','--user-data-dir='+profile,'about:blank'],
      {stdio:['ignore','ignore','ignore','pipe','pipe']});
    const call = connect(browser);
    const {targetId} = await call('Target.createTarget',{url:'about:blank'});
    const {sessionId} = await call('Target.attachToTarget',{targetId,flatten:true});
    const page = (method,params)=>call(method,params,sessionId);
    const evaluate = async expression => {
      const result = await page('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
      if (result.exceptionDetails) throw Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
      return result.result.value;
    };
    await page('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});
    await page('Network.enable',{});
    await page('Network.setBlockedURLs',{urls:['http://*','https://*','ws://*','wss://*']});
    const url = pathToFileURL(input);
    url.searchParams.set('render','1');
    await page('Page.navigate',{url:url.href});
    let ready = false;
    for (let attempt=0;attempt<100;attempt++) {
      ready = await evaluate('document.readyState === "complete" && typeof window.seekTo === "function"');
      if (ready) break;
      await delay(70);
    }
    if (!ready) throw Error('The HTML must load offline and expose window.seekTo(seconds).');
    const duration = await evaluate('document.fonts.ready.then(()=>window.DURATION)');
    if (!Number.isFinite(duration)||duration<=0) throw Error('Set window.DURATION to a positive number of seconds.');
    const frames = Math.ceil(duration*fps);
    const args = ['-hide_banner','-loglevel','error','-f','image2pipe','-framerate',String(fps),'-vcodec','mjpeg','-i','pipe:0'];
    if (values.audio) args.push('-i',resolve(values.audio),'-map','0:v:0','-map','1:a:0','-af','apad','-c:a','aac','-b:a','192k');
    args.push('-c:v','libx264','-preset','veryfast','-crf','17','-pix_fmt','yuv420p','-t',String(frames/fps),'-movflags','+faststart',partial);
    encoder = spawn('ffmpeg',args,{stdio:['pipe','ignore','inherit']});
    const done = once(encoder,'close');
    encoder.stdin.on('error',()=>{}); // The pending write callback or exit code reports the failure.
    console.log('Rendering '+frames+' frames, '+width+'×'+height+' at '+fps+' fps.');
    for (let frame=0;frame<frames;frame++) {
      await evaluate('Promise.resolve(window.seekTo('+frame/fps+')).then(()=>document.documentElement.offsetWidth)');
      const {data} = await page('Page.captureScreenshot',{format:'jpeg',quality:98,fromSurface:true,optimizeForSpeed:true});
      await new Promise((resolve,reject)=>encoder.stdin.write(Buffer.from(data,'base64'),err=>err?reject(err):resolve()));
      if ((frame+1)%(fps*10)===0) console.log(Math.round((frame+1)/frames*100)+'%');
    }
    encoder.stdin.end();
    const [code] = await done;
    if (code!==0 || !(await stat(partial)).size) throw Error('FFmpeg failed (exit '+code+').');
    await rename(partial,target);
    console.log('Saved '+basename(target));
  } finally {
    if (encoder && encoder.exitCode===null) encoder.kill();
    if (browser && browser.exitCode===null && browser.signalCode===null) {
      const stopped = once(browser,'close').catch(()=>{});
      browser.kill();
      await stopped;
    }
    if (temp) await rm(temp,{recursive:true,force:true});
    await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:100});
  }
}
render().catch(err=>{console.error(err.message);process.exitCode=1});
