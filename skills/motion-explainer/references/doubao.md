# 豆包中文旁白

随包的 `scripts/tts_doubao.mjs` 使用 Node.js 20+ 直接调用火山引擎。使用者需在自己的火山引擎账号开通豆包语音合成 2.0，并把语音控制台的 API Key 注入运行 Codex 的进程环境变量 `DOUBAO_TTS_API_KEY`。合成会将本次口播文本发送给豆包，费用记在该账号上。字词时间戳和音频由同一个请求返回。[火山引擎 HTTP 语音合成文档](https://docs.volcengine.com/docs/doubao-voice/unidirectional-streaming-text-to-speech-http?lang=zh)

## 合成一版旁白

从本 Skill 目录运行，给每版配音准备一个工作目录。在工作目录写入 `cues.json`，每个元素是一段待对齐的口播。例如 `[{"spoken":"六月十二日才首次推送。","caption":"6 月 12 日才首次推送。"}]`。字幕沿用正式名称，口播可按实际发音拼写。

```sh
episode=/path/to/work/this-voice-version
adapter=scripts/tts_doubao.mjs
python3 scripts/doubao_timeline.py --dir "$episode" --prepare
node "$adapter" dry-run --text-file "$episode/narration.txt" --language zh-cn --voice zh_female_vv_uranus_bigtts --rate 8
node "$adapter" synthesize --text-file "$episode/narration.txt" --language zh-cn --voice zh_female_vv_uranus_bigtts --rate 8 --output "$episode/doubao.mp3"
python3 scripts/doubao_timeline.py --dir "$episode"
```

`dry-run` 在本地检查文本及声音参数。示例使用 Vivi 2.0 音色，语速和音色都可调整。需要口播语气引导时，两条命令均传 `--direction`。相同文案、音色与设置可以复用同目录已有音轨；修改后请使用新的版本目录。

**沿用已有的钥匙串配置。** 如果这台 Mac 已通过 `product-demo-video` 在钥匙串配置过豆包，并且希望继续使用原凭据，把上例的 `adapter=...` 换成下行，其余命令相同。也可通过 `DOUBAO_TTS_ADAPTER` 指定自己已经配置好的兼容适配器。系统凭据仍由原适配器读取。

```sh
adapter="${DOUBAO_TTS_ADAPTER:-${CODEX_HOME:-$HOME/.codex}/skills/product-demo-video/scripts/tts-doubao.mjs}"
```

## 对齐与出片

合成产生 `doubao.mp3` 和 `doubao.mp3.doubao.json`。时间轴脚本用 `ffprobe` 读取时长，结合字词时间戳写出 `timeline.json` 与 `subtitles.srt`。`lines` 保存各段口播的起止时间，`captions` 保存屏幕字幕的起止时间。若音频与元数据不匹配，或字词与口播匹配不足，请先核对版本，再决定是否重新合成。

口播修改后，使用对应版本的音轨与时间戳重新对齐。[视频导出](../SKILL.md#导出视频)可以直接使用合成的 MP3。
