# Motion Explainer · 视频后期制作

给 Codex 一篇文章就能开始。模型根据内容和你的要求决定怎么讲、怎么呈现。`$motion-explainer` 提供三项可以单独使用的后期能力：

- **豆包配音**：按口播稿合成 MP3，并取得同一次合成的字词时间戳。
- **字幕对齐**：用实际发音生成 SRT 字幕和供剪辑使用的 JSON 时间轴。
- **视频导出**：合成已有视频、音轨和字幕，或逐帧导出自定义 HTML 动画。

## 在 Codex 里使用

安装时发送：

```text
请用 $skill-installer 安装 https://github.com/baijianyu1024-cmd/motion-explainer/tree/main/skills/motion-explainer
```

附上文章，再说：

> 把这篇文章做成中文解说视频，讲法和画面你来定。用 $motion-explainer 做豆包配音、字幕和 MP4 导出。

有成稿或现成画面时也可以从中途开始，例如“旁白已经合成，用已有时间戳重新生成字幕”。

## 运行环境

豆包合成使用 Node.js 20+ 和使用者自己的火山引擎语音服务凭据。字幕对齐使用 Python 3 和 ffprobe。视频合成使用 FFmpeg；从 HTML 导出时还需要 Chrome 或 Chromium 和带 libx264 的 FFmpeg。[豆包配置与调用](skills/motion-explainer/references/doubao.md) · [视频导出命令](skills/motion-explainer/SKILL.md#导出视频)

可在仓库单独观看此前制作的 [Agent 架构示例](media/agent-architecture.mp4) 或下载[离线 HTML](media/agent-architecture.html)。示例沿用的 Frontend Slides 固定舞台样式保留了原作者的 MIT 许可声明。项目采用 [MIT 许可](LICENSE)。
