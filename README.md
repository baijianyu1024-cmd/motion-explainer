# 动态解说工坊 · Motion Explainer

一个把图文稿做成中文解说视频的 Codex Skill。给它一份 Word 文档、一段口述，或者一份 Codex 有权读取的在线文档。它会围绕你想讲清的观点写口播、编排镜头，并按实际旁白的时间生成字幕和 MP4。

## 示例 · 静态与动态 Agent 如何生成 SQL？

“6 月 1 日到 7 日，有多少订单退款成功？”静态方案调用预先写好提示词的退款分析助手，动态方案由主 Agent 根据本次问题和可用字段生成提示词。如果同一订单成功退款两次，两份提示词都要保留“只算一单”的口径。两条路径都可以直接生成 SQL。

[![动画预览：预设 Prompt 与实时生成的 Prompt 怎样汇入 SQL 生成](media/agent-architecture.gif)](media/agent-architecture.mp4)

[观看完整有声样片（MP4）](media/agent-architecture.mp4) · [下载可拖动的离线 HTML](https://raw.githubusercontent.com/baijianyu1024-cmd/motion-explainer/main/skills/motion-explainer/assets/example.html)

## 安装到 Codex

在 Codex 里发送这一句：

```text
请用 $skill-installer 安装 https://github.com/baijianyu1024-cmd/motion-explainer/tree/main/skills/motion-explainer
```

装好后，在下一条消息里输入 `$motion-explainer` 并附上原稿。

## 从一份稿开始

比如，你有一篇对比两种 AI 架构的文章。附上文档，再告诉 Codex：

> 用 $motion-explainer 把这篇做成两分钟的中文视频。听众懂 SQL，但第一次接触这两种架构。讲清两种方案分别在什么时候定义提示词。保留架构图，讲到哪个节点就放大哪个，用豆包配音。

只有文档也可以开工。希望只读文字时，补一句“忽略原图，按正文画图解”。看到样片后，可以按时间提修改，比如“讲到按订单去重时，把两条退款记录放在一起，多停一秒”。成片可以搭配 SRT 字幕、独立旁白和能逐镜检查的离线 HTML。

## 需要准备什么

| 想做的事 | 本机需要 |
| --- | --- |
| 先看看动态分镜 | 用浏览器打开自带的 [离线示例](skills/motion-explainer/assets/example.html)。下载后打开文件即可播放、暂停和拖动。 |
| 读取 Word 文稿和图片 | Python 3。DOCX 提取脚本使用 Python 标准库。 |
| 导出 MP4 | Node.js 20+、Chrome 或 Chromium、带 `libx264` 的 FFmpeg 和 `ffprobe`。浏览器路径可用 `CHROME_BIN` 指定。 |
| 用豆包配音 | 使用自己的火山引擎语音服务凭据。配置方式、合成命令和字幕对齐见[豆包旁白指南](skills/motion-explainer/references/doubao.md)。 |
| 用自己的声音 | 可提供逐句录音，由 Skill 按音轨对齐。macOS 用户也可以用系统中文语音试音。 |

## 工作流程

Skill 先把原文、图注和插图对上，找到作者想让观众记住的一句话。分镜记录每句口播对应哪处原文、画面要出现什么变化，再用真实的音频时间安排推近、标注和字幕。最后把离线 HTML 逐帧渲染成视频，核对关键画面和音画同步。操作细节见[图文稿制作指南](skills/motion-explainer/references/document-video.md)。

项目采用 [MIT 许可](LICENSE)。示例舞台包含 Zara Zhang 的 [Frontend Slides](https://github.com/zarazhangrui/frontend-slides) 固定舞台样式，其许可声明保留在示例 HTML 中。
