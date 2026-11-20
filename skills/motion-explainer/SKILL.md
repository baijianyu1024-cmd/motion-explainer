---
name: motion-explainer
description: 视频后期制作。需要用豆包合成旁白、按字词时间戳对齐中文字幕或把已有画面与音轨导出为 MP4 时使用。
---

# 视频后期制作

用户只给文章时，先根据文章、受众和本次要求自由完成创作。口播稿就绪即可合成旁白，画面可以随后按实际音轨制作。按任务需要使用以下步骤。

## 豆包配音与字幕对齐

将口播稿保存为 `cues.json`。每项的 `spoken` 是读音文本，`caption` 是屏幕文字。分段只用于对齐，同一个镜头可以跨多段口播。按[豆包调用说明](references/doubao.md)生成 `doubao.mp3` 和字词时间戳，再生成 `subtitles.srt` 与 `timeline.json`。只改画面时可复用原音轨和字幕。

已有逐句录音时，也可用 `python3 scripts/align.py manifest.json output-dir` 按每段录音的实际时长对齐字幕。清单每项包含 `text`、录音路径 `file` 和可选的句后停顿秒数 `pause`。

## 导出视频

沿用作品已有的制作工具和画幅。下列命令在 Skill 目录执行，路径换成本期文件。

已有与旁白等长的无声 H.264 视频时，可直接合成 MP4。此命令保留画面并写入可开关的中文字幕轨。

```sh
ffmpeg -i visual.mp4 -i doubao.mp3 -i subtitles.srt \
  -map 0:v:0 -map 1:a:0 -map 2:s:0 -c:v copy -c:a aac -c:s mov_text \
  -metadata:s:s:0 language=zho -movflags +faststart final.mp4
```

使用离线 HTML 制作画面时，页面提供 `window.DURATION`（秒）和 `window.seekTo(seconds)`。任意时间点应能直接还原画面，异步绘制用 Promise 表示完成。在 `?render=1` 时隐藏播放器控件。页面可按 `timeline.json` 的 `captions` 绘制字幕。

```sh
node scripts/export.mjs episode.html final.mp4 --audio doubao.mp3
```

可用 `--width`、`--height`、`--fps` 指定作品尺寸和帧率。导出前按成片需要留足最后一句旁白的播放时间；导出后核对音轨、字幕起止和片尾。
