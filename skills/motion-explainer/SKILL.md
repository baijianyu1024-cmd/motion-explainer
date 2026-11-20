---
name: motion-explainer
description: 用户想先看讲解视频的配色小样，或需要豆包旁白、按实际发音对齐的中文字幕、MP4 导出时使用。
---

# 视频后期制作

把文章做成视频时，根据内容、受众和本次要求决定开场、讲法和动效。口播稿就绪即可合成旁白，画面可以随后按实际音轨制作。

## 可选的配色预览

用户说「先看配色」「给我几个方案选」时，读完素材，挑本期两个有代表性的镜头，例如一张需要跟着线路读的图和一张文字密集的界面。结合本期内容和用户给的参考设计三套配色。在每套中渲染同样的两个镜头，保持文案、构图、字幕和动效取帧时刻一致，让用户能看清正文、当前重点和背景的关系。

小样用静帧和预排字幕即可。展示带 A、B、C 标记的实际画面对照图。只要小样时，交付到这里。已委托整片并要求先选色时，等用户选定、混搭或微调后继续，例如「架构用 A，界面用 B」。用户说「直接出片」「你来定」，或只要求做视频时，自主选色并继续。单独要求配音、字幕或导出时，直接执行所需步骤。

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
