import { createHash, randomUUID } from 'node:crypto';
import { link, mkdir, readFile, rm, unlink, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { createInterface } from 'node:readline';
import { Readable } from 'node:stream';
import { parseArgs } from 'node:util';

const endpoint = 'https://openspeech.bytedance.com/api/v3/tts/unidirectional';
const resource = 'seed-tts-2.0';
const usage = 'node scripts/tts_doubao.mjs dry-run|synthesize --text-file narration.txt [--output doubao.mp3] [--voice ID] [--rate 8] [--language zh-cn|en] [--direction TEXT]';
const digest = data => createHash('sha256').update(data).digest('hex');

async function collect(response) {
  if (!response.ok) throw new Error('豆包请求失败，HTTP ' + response.status);
  const chunks = [];
  const sentences = [];
  let completed = false;
  for await (const line of createInterface({input: Readable.fromWeb(response.body), crlfDelay: Infinity})) {
    if (!line.trim()) continue;
    let record;
    try {
      record = JSON.parse(line);
    } catch {
      throw new Error('豆包返回了无法解析的响应。');
    }
    if (record.code === 20000000) completed = true;
    else if (record.code !== 0) throw new Error('豆包合成失败，错误码 ' + Number(record.code));
    if (record.data) chunks.push(Buffer.from(record.data, 'base64'));
    if (record.sentence?.words?.length) {
      const words = record.sentence.words.map(({word, startTime, endTime}) => {
        if (typeof word !== 'string' || !Number.isFinite(startTime) ||
            !Number.isFinite(endTime) || startTime < 0 || endTime < startTime)
          throw new Error('豆包返回了无效的字词时间戳。');
        return {word, startTime, endTime};
      });
      sentences.push({words});
    }
  }
  const audio = Buffer.concat(chunks);
  if (!completed || !audio.length || !sentences.length)
    throw new Error('豆包响应不完整，缺少完成标记、音频或字词时间戳。');
  return {audio, sentences};
}

async function maybeRead(file) {
  try {
    return await readFile(file);
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw error;
  }
}

async function synthesize(output, request) {
  const meta = output + '.doubao.json';
  const body = JSON.stringify(request);
  const requestSha256 = digest(resource + '\n' + body);
  await mkdir(dirname(output), {recursive: true});
  const staging = output + '.in-progress';
  try {
    await mkdir(staging, {mode: 0o700});
  } catch (error) {
    if (error.code === 'EEXIST') throw new Error('同一路径已有合成任务。若上次进程已退出，请换一个工作目录再试。');
    throw error;
  }
  try {
    const [audioFile, metaFile] = await Promise.all([maybeRead(output), maybeRead(meta)]);
    if (metaFile && audioFile) {
      const cached = JSON.parse(metaFile);
      if (cached.requestSha256 === requestSha256 && cached.audioSha256 === digest(audioFile)) {
        console.log('已复用相同配音。');
        return;
      }
    }
    if (audioFile || metaFile) throw new Error('此路径已有其他版本或不完整的配音，请为新版本指定新路径。');
    const apiKey = process.env.DOUBAO_TTS_API_KEY?.trim();
    if (!apiKey) throw new Error('请在当前进程配置 DOUBAO_TTS_API_KEY。');
    const response = await fetch(endpoint, {
      method: 'POST', redirect: 'error', signal: AbortSignal.timeout(600000),
      headers: {'Content-Type': 'application/json', 'X-Api-Key': apiKey,
        'X-Api-Resource-Id': resource, 'X-Api-Request-Id': randomUUID()},
      body
    });
    const {audio, sentences} = await collect(response);
    const metadata = {requestSha256, audioSha256: digest(audio), sentences};
    const tempAudio = join(staging, 'audio');
    const tempMeta = join(staging, 'timestamps');
    await writeFile(tempAudio, audio, {mode: 0o600});
    await writeFile(tempMeta, JSON.stringify(metadata), {mode: 0o600});
    await link(tempAudio, output);
    try {
      await link(tempMeta, meta);
    } catch (error) {
      await unlink(output);
      throw error;
    }
    console.log('已写入配音与字词时间戳。');
  } finally {
    await rm(staging, {recursive: true, force: true});
  }
}

async function main() {
  const [command, ...args] = process.argv.slice(2);
  if (command === '--help' || !command) {
    console.log(usage);
    return;
  }
  const {values} = parseArgs({args, options: {
    'text-file': {type: 'string'}, output: {type: 'string'}, voice: {type: 'string', default: 'zh_female_vv_uranus_bigtts'},
    rate: {type: 'string', default: '0'}, language: {type: 'string', default: 'zh-cn'}, direction: {type: 'string'}
  }});
  if (!['dry-run', 'synthesize'].includes(command) || !values['text-file'] ||
      (command === 'synthesize' && !values.output)) throw new Error(usage);
  const text = (await readFile(values['text-file'], 'utf8')).trim();
  const rate = Number(values.rate);
  if (!text || !values.voice.trim() || !values.rate.trim() || !Number.isInteger(rate) || rate < -50 || rate > 100 ||
      !['zh-cn', 'en'].includes(values.language)) throw new Error('请检查旁白文案、音色、语速（-50 到 100）和语种（zh-cn 或 en）。');
  const additions = {explicit_language: values.language, aigc_metadata: {enable: true}};
  if (values.direction?.trim()) additions.context_texts = [values.direction.trim()];
  const request = {req_params: {
    text, speaker: values.voice,
    audio_params: {format: 'mp3', sample_rate: 24000, bit_rate: 160000, speech_rate: rate, enable_subtitle: true},
    additions: JSON.stringify(additions)
  }};
  if (command === 'dry-run') console.log(JSON.stringify({resource, characters: [...text].length, voice: values.voice, rate, language: values.language}));
  else await synthesize(resolve(values.output), request);
}

main().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
