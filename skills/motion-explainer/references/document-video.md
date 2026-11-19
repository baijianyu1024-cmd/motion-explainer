# 用一份图文稿做一集视频

## 读原稿

在已有任务工作目录保存原稿的读取结果。以下命令从 Skill 目录运行，路径换成实际位置。

```sh
python3 scripts/read_docx.py /path/to/source.docx /path/to/work/source
```

脚本输出 manifest.json 和 media/。按 blocks 的顺序阅读文字和题注，根据 parts 的图片标识查 assets 的相对路径，打开图片看实际内容。原稿若使用 Word 原生形状、浮动对象、组合图、带裁剪的图片或复杂排版，同时检查渲染后的文档页。必要时从页面截取完整图组，保留箭头、图例和标注的相对位置。

仅按正文制作时从源文提取主线和例子，依据文字绘制图解，跳过附件取图。对于 PDF，从能访问的页渲染图和文字开始，保留页码及裁切位置。对于带链接的在线文档，用当前授权的文档入口读取正文与内嵌图片。只有文字、图片无法取得时，说明缺哪一张图、它影响哪句话；仍可先完成其他分镜。未见过的界面不能当作真实产品证据。

## 改编

读完整篇，再决定视频从哪里开场。长稿先分清核心判断、必要背景与旁支。同一份稿包含多个独立观点时，按用户的时长决定是否分章或只讲一条，交付时说明取舍。保留原文的条件、数字、出处与不确定性，整理成听起来像人说话的短句。原图的图注优先用来定位素材；观众需要哪一句，再写进旁白。

工作分镜可按「口播 | 原文段落或页码 | 原图与焦点 | 动作」记录。例如，假想一份核对 AI 引用的原稿。口播讲“它声称周末两天都营业”时，先给回答全貌，移到回答的那一行；讲“原文写周日休息”时，再移到来源栏。观众应能在原图上读出这个差别。框架图节点、箭头的方向和分支含义以文档为准。用户的图像如果分辨率低，优先放大关键局部，必要时加忠实的文字摘录。

## 生成旁白与时间轴

按语义停顿组织逐句清单。每个元素包含 text 和 pause（句后静音秒数）。数字范围、英文缩写按口语处理，术语和原图中的名称保持一致。用户指定豆包时，使用[整段配音和实际字词时间戳](doubao.md)。以下示例适用于用户选择本地 macOS 合成音或已有逐句录音的情况。将带 file 的逐句清单交给 scripts/align.py，得到实际时长驱动的 narration.wav、timeline.json 和 subtitles.srt。

下面的两句口播对应随后示例中的两个镜头。将它们保存为 `voice-lines.json`。macOS 可以用 `say -v "?"` 查看已安装的中文语音，把命令中的 `Tingting` 换成列表中的名称。

```json
[
  {"text": "助手说，周末两天都开门。", "pause": 0.4},
  {"text": "点开它引用的公告，原文写着周日休息。", "pause": 0.4}
]
```

```sh
python3 scripts/tts_macos.py /path/to/work/voice-lines.json /path/to/work/tts-clips --voice Tingting --rate 195
python3 scripts/align.py /path/to/work/tts-clips/manifest.json /path/to/work/audio
```

## 让原图跟着旁白走

可用下面的构图计划直接生成离线 HTML。它适合原图全貌、推近局部、框选细节和跨图切换。需要逐节点重组、复杂对照或新解释图时，可以定制舞台。截图内已有状态仍按原图展示。将计划保存为 `shots.json`，把图像路径替换为读取结果中 `assets` 对应的实际文件，再按原图位置调整取景和高亮坐标。

```json
{
  "title": "核对 AI 回答里的引用",
  "byline": "动态解说工坊",
  "figures": {
    "ui": {"file": "source/media/img001-c09e1482ec9bd7c8.png", "label": "图 1 · 原稿中的问答与公告示意"}
  },
  "shots": [
    {"cue": 1, "figure": "ui", "title": "周末两天都开门？"},
    {"cue": 2, "figure": "ui", "title": "公告写着周日休息", "view": [0.54, 0.42, 0.95, 0.80], "mark": [0.56, 0.62, 0.93, 0.77]}
  ]
}
```

figures 的 file 相对计划文件，使用可直接显示的 PNG、JPEG 或 WebP。cue 是从 1 开始的旁白句序，offset 是相对本句开头的秒数，可在一句里设置第二个镜头。镜头按起始时间排列，第一镜从零开始。view 与 mark 都是原图上的 [左, 上, 右, 下] 归一化坐标，0 到 1。先看图再量坐标，缺省 view 显示全图。换图直接切，同图变更 view 时平滑推移。旁白较长时在语义停顿处分句，避免挤小字幕。

```sh
python3 scripts/compose_figures.py /path/to/work/shots.json /path/to/work/audio/timeline.json /path/to/episode.html --audio /path/to/work/audio/narration.wav
node scripts/export.mjs /path/to/episode.html /path/to/episode.mp4 --audio /path/to/work/audio/narration.wav
```

重点检查每句口播指向的原图和位置，有无裁掉单位、否定词、限定条件或图中的关键连线。试听术语读音，抽看开始指图、焦点落定和字幕换句时刻，再核对 MP4 音视频轨。用户通常只需交一份文档；选图、写稿、生成语音、编排时间轴和出片均由 Skill 完成。
