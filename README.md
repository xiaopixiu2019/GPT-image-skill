# GPT Image 2 Codex Skill

一个可安装到 Codex 的图片生成 Skill，通过 OpenAI-compatible 图像接口调用 `gpt-image-2`，并要求对生成结果进行实际检查，而不是只返回提示词或接口状态。

## 安全提醒

默认网关 `https://kuaikuaiai.top` 是第三方服务，并非 OpenAI 官方域名。

- 只配置该服务专用的 `IMAGE2_API_KEY`，不要使用或共享 Codex、OpenAI 或其他系统的通用密钥。
- 不要提交真实政府视频、个人信息、内部地址、账号、案件材料或其他敏感数据。
- 仓库不会读取 `OPENAI_API_KEY` 或 `~/.codex/auth.json`，也不会打印 API 密钥。
- API 调用会产生费用；由密钥持有人自行管理额度、审计和吊销。

## 安装

需要 Python 3.9+ 和支持本地 Skills 的 Codex。

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/xiaopixiu2019/GPT-image-skill.git \
  ~/.codex/skills/image2-generator
```

配置专用密钥：

```bash
export IMAGE2_API_KEY='<your-dedicated-image-api-key>'
```

如需使用其他兼容网关或模型名：

```bash
export IMAGE2_BASE_URL='https://your-compatible-provider.example'
export IMAGE2_MODEL='gpt-image-2'
```

重新启动 Codex，让它发现新安装的 Skill。

## 在 Codex 中使用

明确调用：

```text
使用 $image2-generator 生成一张无文字、无水印的现代城市治理指挥中心横版图片。
```

也可以直接描述图片任务；Skill 支持隐式触发：

```text
生成一张 1536x1024 的产品主视觉，真实摄影风格，不要文字和标识。
```

生成完成后，Codex 应检查实际图片是否可解码、非空、构图可用，以及是否存在水印、错误文字或明显视觉缺陷。

## 命令行使用

先用 dry-run 检查请求；这一步不会调用 API，也不会产生费用：

```bash
python3 ~/.codex/skills/image2-generator/scripts/generate_image.py \
  --prompt "A safe synthetic city operations center, no text, no watermark" \
  --size 1536x1024 \
  --quality medium \
  --output "$HOME/Pictures/image2-test.png" \
  --dry-run
```

确认无误后移除 `--dry-run` 进行实际生成：

```bash
python3 ~/.codex/skills/image2-generator/scripts/generate_image.py \
  --prompt "A safe synthetic city operations center, no text, no watermark" \
  --size 1536x1024 \
  --quality medium \
  --output "$HOME/Pictures/image2-test.png"
```

支持的尺寸：

- `1024x1024`
- `1536x1024`
- `1024x1536`

支持 `png`、`jpeg`、`webp`，以及 `low`、`medium`、`high` 三档质量。使用 `--help` 查看全部参数。

## 常见问题

- `No API key found`：当前终端没有设置 `IMAGE2_API_KEY`。
- HTTP `401` / `403`：密钥无效、无权限，或密钥与网关不匹配。
- HTTP `429`：额度不足或触发限流，请稍后重试或联系服务提供方。
- 请求超时：检查网络和网关状态；脚本会对部分临时错误进行有限重试。
- 图片中文字错误：图像模型不适合保证精确文字，应生成无文字视觉层，再使用 Pillow、ImageMagick 或前端渲染工具确定性排字。

## 更新

```bash
git -C ~/.codex/skills/image2-generator pull --ff-only
```

## 开发验证

```bash
python3 -m py_compile scripts/generate_image.py
python3 -m unittest discover -s tests -v
python3 scripts/generate_image.py \
  --prompt "Safe synthetic test image, no text" \
  --output /tmp/image2-dry-run.png \
  --dry-run
```
