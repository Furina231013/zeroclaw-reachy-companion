# Task: Build a Phase 1 + Phase 2 ZeroClaw integration for Baby Reachy Mini Companion capabilities

你是本地 Codex，请在当前开发环境中帮我实现一个实验项目，用 ZeroClaw 框架集成 `baby-reachy-mini-companion` 的 Phase 1 和 Phase 2 能力。

目标不是完整复制 Hugging Face app runtime，而是把它的核心 Reachy 表达能力和本地语音 pipeline 迁移到 ZeroClaw 风格的 agent runtime 中，为后续接入更多 Reachy app 做统一架构。

参考项目：

- Hugging Face Space / GitHub:
  - https://huggingface.co/spaces/ravediamond/baby-reachy-mini-companion
  - https://github.com/ravediamond/baby-reachy-mini-companion
- Reachy Mini SDK / daemon:
  - `reachy-mini`
  - Python SDK / REST API
  - daemon 可运行在 simulation 或真实机器人上

当前范围只做 Phase 1 和 Phase 2：

- Phase 1：文本输入 → ZeroClaw agent → LLM/tool calling → Reachy tools
- Phase 2：本地音频输入输出 → VAD/STT/TTS → ZeroClaw agent → Reachy tools

暂时不要做：

- YOLO danger detection
- YAMNet cry detection
- Signal alert
- VLM scene understanding
- camera snapshot alert flow
- safety event handler
- OpenHarmony 移植
- ROS2
- 多 app 插件市场

---

## 1. 先阅读本地源码

请先检查当前目录下是否已有这些项目：

```bash
ls
zeroclaw/
baby-reachy-mini-companion/
reachy_mini_conversation_app/
```

如果本地没有 `baby-reachy-mini-companion`，请给出 clone 指令，但不要假设已经安装成功：

```bash
git clone https://github.com/ravediamond/baby-reachy-mini-companion.git
```

如果本地没有 ZeroClaw，请提示我把 ZeroClaw repo 放到当前工作区。不要凭空编造 ZeroClaw API。你必须先阅读本地 ZeroClaw 的实际代码，再决定如何注册 provider、tools、runtime、agent loop。

重点阅读：

```text
baby-reachy-mini-companion/
  README.md
  pyproject.toml
  src/reachy_mini_conversation_app/main.py
  src/reachy_mini_conversation_app/tools/
  src/reachy_mini_conversation_app/local/
  src/reachy_mini_conversation_app/audio/
  src/reachy_mini_conversation_app/vision/
```

重点理解：

1. 原 app 如何初始化 `ReachyMini`
2. 原 app 的 tools 有哪些
3. `speak`, `move_head`, `play_emotion`, `story_time`, `soothe_baby`, `dance` 等工具如何实现
4. 原 app 的 `ToolDependencies` 依赖了哪些对象
5. `LocalSessionHandler` / `LocalStream` / STT / TTS / VAD 的调用边界
6. 原 app 是如何接入 Ollama / local LLM 的
7. 哪些代码可以复用，哪些应该重新封装成 ZeroClaw adapter

---

## 2. 总体设计目标

请新建一个独立实验工程，名字可以是：

```text
zeroclaw-reachy-companion/
```

它不要直接把整个 `baby-reachy-mini-companion` app 嵌进来，而是采用三层结构：

```text
ZeroClaw Agent Runtime
        ↓
Reachy Companion Tools Adapter
        ↓
Reachy SDK / daemon / simulation
```

核心原则：

1. ZeroClaw 负责 agent loop、LLM provider、tool registry、prompt/profile、context。
2. Reachy adapter 负责把 ZeroClaw tool call 转成 Reachy SDK 调用。
3. baby-reachy-mini-companion 只作为参考实现和能力来源，不作为主 runtime。
4. 不要让两个 runtime 同时管理 LLM、audio stream、tool loop。
5. Phase 1 先跑通文本输入。
6. Phase 2 再接 VAD/STT/TTS。

---

## 3. 期望目录结构

请尽量生成如下结构。若 ZeroClaw 现有工程风格不同，可以适配，但请保持边界清晰。

```text
zeroclaw-reachy-companion/
  README.md
  pyproject.toml
  .env.example

  src/
    zeroclaw_reachy_companion/
      __init__.py

      app.py
      config.py

      profiles/
        baby_companion.yaml

      reachy/
        __init__.py
        client.py
        motion.py
        emotion.py
        speech_output.py

      tools/
        __init__.py
        speak.py
        move_head.py
        play_emotion.py
        story_time.py
        soothe_baby.py
        dance.py
        stop_motion.py

      audio/
        __init__.py
        vad.py
        stt.py
        tts.py
        audio_io.py
        speech_loop.py

      providers/
        __init__.py
        local_llm.py

      runtime/
        __init__.py
        text_chat_loop.py
        voice_chat_loop.py

  tests/
    test_tools_smoke.py
    test_prompt_profile.py
```

---

## 4. Phase 1: 文本输入 + Reachy tools

先实现 Phase 1，不要急着接音频。

### 4.1 Reachy client

实现一个 `ReachyClient`，封装 Reachy Mini SDK。

要求：

* 支持真实 Reachy daemon
* 支持 simulation
* 支持 dry-run/mock 模式
* dry-run 模式下不连接机器人，只打印动作，方便我在 Mac 上先测 agent tool calling

建议接口：

```python
class ReachyClient:
    def __init__(self, mode: str = "dry_run", host: str = "localhost", port: int | None = None):
        ...

    async def connect(self) -> None:
        ...

    async def close(self) -> None:
        ...

    async def speak(self, text: str) -> str:
        ...

    async def move_head(self, yaw: float = 0, pitch: float = 0, roll: float = 0, duration: float = 1.0) -> str:
        ...

    async def play_emotion(self, emotion: str) -> str:
        ...

    async def dance(self, style: str = "gentle", duration: float = 5.0) -> str:
        ...

    async def stop_motion(self) -> str:
        ...
```

注意：

* 真实 SDK 调用要根据本地 `reachy-mini` 实际 API 来写，不要胡编。
* 如果不确定真实 API，先保留 TODO，并实现 dry-run。
* `dry_run` 必须可运行。
* 所有工具都要返回简短字符串，方便 agent 观察 tool result。

### 4.2 Tools

实现这些 ZeroClaw tools：

```text
speak(text: str)
move_head(yaw: float, pitch: float, roll: float, duration: float)
play_emotion(emotion: str)
story_time(topic: str | None)
soothe_baby(style: str)
dance(style: str, duration: float)
stop_motion()
```

每个 tool 都要：

1. 有清晰 docstring，让 LLM 知道什么时候调用。
2. 参数少而明确。
3. 对非法参数做最小校验。
4. 不要在 tool 内部直接创建全局 Reachy 连接，应该从 runtime/context/dependency 注入 `ReachyClient`。
5. dry-run 模式下可以打印出类似：

```text
[DRY-RUN] speak: Once upon a time...
[DRY-RUN] move_head: yaw=10 pitch=-5 roll=0 duration=1.2
```

### 4.3 Baby companion profile

实现一个 profile：

```text
src/zeroclaw_reachy_companion/profiles/baby_companion.yaml
```

内容包括：

```yaml
name: baby_companion
description: A gentle local companion profile for Reachy Mini.

system_prompt: |
  You are controlling a small expressive companion robot called Reachy Mini.
  You are gentle, warm, concise, and child-friendly.
  You can speak, move your head, play simple emotions, tell stories, soothe, and dance.
  Prefer short spoken responses because TTS will read them aloud.
  When a physical expression would help, call one or more tools.
  Do not claim to see the room unless a camera or vision tool is explicitly available.
  Do not claim to detect crying, danger, or people in this Phase 1/2 build.
  For story requests, use story_time or speak with a short original story.
  For comfort requests, use soothe_baby.
  For movement requests, use move_head or dance.
```

注意：

* Phase 1/2 没有 camera / VLM / danger / cry，所以 prompt 里必须禁止模型假装自己能看见、能检测危险、能检测哭声。
* 回复要短，因为 Phase 2 会 TTS 播放。

### 4.4 Text loop

实现一个文本交互入口：

```bash
python -m zeroclaw_reachy_companion.app --mode text --reachy-mode dry_run
```

预期行为：

```text
User> Tell me a bedtime story.
Agent> ...
Tool call: story_time(topic="bedtime")
[DRY-RUN] speak: ...
```

也支持：

```bash
python -m zeroclaw_reachy_companion.app --mode text --reachy-mode sim
python -m zeroclaw_reachy_companion.app --mode text --reachy-mode real
```

如果 ZeroClaw 已有 CLI 风格，请融入 ZeroClaw 的 CLI；如果没有，就先实现独立 CLI。

---

## 5. Phase 2: 本地 VAD / STT / TTS

Phase 2 在 Phase 1 可运行后再实现。

目标链路：

```text
microphone
  ↓
VAD
  ↓
STT
  ↓
ZeroClaw text agent
  ↓
tool calling / response
  ↓
TTS
  ↓
speaker
```

### 5.1 音频策略

优先实现最小可用：

* VAD: Silero VAD
* STT: Faster-Whisper
* TTS: Kokoro ONNX 或项目中已有的 Kokoro TTS 封装
* Audio IO: 本机麦克风和扬声器

请优先参考 `baby-reachy-mini-companion` 的本地音频实现，而不是从零乱写。

如果依赖安装复杂，请提供可运行 fallback：

* `--stt mock`: 用户在终端输入文本，模拟 STT
* `--tts print`: 只打印要说的话，不播放音频
* `--vad disabled`: 按回车开始/结束录音，或直接终端输入文本

### 5.2 Voice loop CLI

实现：

```bash
python -m zeroclaw_reachy_companion.app --mode voice --reachy-mode dry_run
```

支持可配置：

```bash
python -m zeroclaw_reachy_companion.app \
  --mode voice \
  --reachy-mode dry_run \
  --vad silero \
  --stt faster-whisper \
  --tts kokoro
```

也支持 fallback：

```bash
python -m zeroclaw_reachy_companion.app \
  --mode voice \
  --reachy-mode dry_run \
  --vad disabled \
  --stt mock \
  --tts print
```

### 5.3 音频设备注意事项

请在 README 中明确说明：

1. Mac 上如果 Reachy daemon 和本实验项目同时抢 USB audio，可能会有冲突。
2. 推荐 Phase 2 初期使用 MacBook mic/speaker 或外接普通 USB 麦克风/音箱。
3. 如果运行 Reachy daemon，建议先用：

```bash
reachy-mini-daemon --sim --deactivate-audio
```

或真实设备下尽量避免 daemon 和本项目同时打开同一个音频输入设备。

---

## 6. LLM provider

请实现或接入本地 LLM provider。

优先支持 Ollama：

```env
LOCAL_LLM_URL=http://localhost:11434
LOCAL_LLM_MODEL=ministral-3:3b
```

要求：

1. provider 接口遵循 ZeroClaw 本地已有 provider 设计。
2. 如果 ZeroClaw 已经有 OpenAI-compatible provider，优先复用。
3. 如果没有，则实现一个最小 Ollama chat provider。
4. tool calling 如果本地小模型不稳定，可以先支持两种模式：

### 模式 A：原生 tool calling

如果 provider/model 支持 tool calling，就使用 ZeroClaw 的 tool mechanism。

### 模式 B：JSON command fallback

如果不支持原生 tool calling，让 LLM 输出 JSON：

```json
{
  "speak": "Sure, I can tell you a short story.",
  "tools": [
    {
      "name": "story_time",
      "arguments": {
        "topic": "bedtime"
      }
    }
  ]
}
```

然后 runtime 解析 JSON 并执行 tools。

要求：

* JSON 解析失败时，不要崩溃。
* fallback 到普通 `speak`。
* 所有错误要打印清楚。

---

## 7. 配置文件

实现 `.env.example`：

```env
# LLM
LOCAL_LLM_URL=http://localhost:11434
LOCAL_LLM_MODEL=ministral-3:3b

# Reachy
REACHY_MODE=dry_run
REACHY_HOST=localhost

# Audio
VAD_BACKEND=disabled
STT_BACKEND=mock
TTS_BACKEND=print
AUDIO_INPUT_DEVICE=
AUDIO_OUTPUT_DEVICE=

# Runtime
PROFILE=baby_companion
LOG_LEVEL=INFO
```

实现 `config.py` 读取 env 和 CLI 参数。CLI 参数优先级高于 env。

---

## 8. README 要包含的运行步骤

请生成清晰 README，至少包含：

### 8.1 准备原 app baseline

```bash
git clone https://github.com/ravediamond/baby-reachy-mini-companion.git
cd baby-reachy-mini-companion
uv sync
ollama pull ministral-3:3b
cp .env.example .env
uv run reachy-mini-daemon --sim --deactivate-audio
uv run reachy-mini-conversation-app --dashboard
```

### 8.2 运行本项目 Phase 1 dry-run

```bash
cd zeroclaw-reachy-companion
uv sync
cp .env.example .env

python -m zeroclaw_reachy_companion.app \
  --mode text \
  --reachy-mode dry_run
```

测试输入：

```text
Tell me a short bedtime story.
Can you nod gently?
Can you soothe the baby?
Do a small happy dance.
Stop moving.
```

### 8.3 运行 Phase 2 fallback voice

```bash
python -m zeroclaw_reachy_companion.app \
  --mode voice \
  --reachy-mode dry_run \
  --vad disabled \
  --stt mock \
  --tts print
```

### 8.4 运行 Phase 2 real local audio

```bash
python -m zeroclaw_reachy_companion.app \
  --mode voice \
  --reachy-mode dry_run \
  --vad silero \
  --stt faster-whisper \
  --tts kokoro
```

### 8.5 连接 Reachy simulation / real robot

如果用 simulation：

```bash
reachy-mini-daemon --sim --deactivate-audio
python -m zeroclaw_reachy_companion.app --mode text --reachy-mode sim
```

如果用真实机器人：

```bash
reachy-mini-daemon --deactivate-audio
python -m zeroclaw_reachy_companion.app --mode text --reachy-mode real
```

---

## 9. 测试要求

至少实现 smoke tests：

```bash
pytest
```

测试内容：

1. `ReachyClient` dry-run 可以初始化。
2. `speak` tool dry-run 返回成功。
3. `move_head` 参数校验有效。
4. `baby_companion.yaml` 可以加载。
5. JSON command fallback 可以解析一个包含 `speak` 和 `move_head` 的 JSON。
6. voice fallback 模式下 `stt=mock`, `tts=print`, `vad=disabled` 不需要真实音频依赖也能跑通。

---

## 10. 验收标准

完成后请给我：

1. 修改/新增文件列表。
2. 如何运行 Phase 1。
3. 如何运行 Phase 2 fallback。
4. 如何运行 Phase 2 real local audio。
5. 哪些地方是 dry-run，哪些地方已接真实 Reachy SDK。
6. 哪些地方参考了 baby-reachy-mini-companion。
7. 哪些 API 因为本地 ZeroClaw 或 Reachy SDK 不确定而留下 TODO。
8. 当前最小 demo 的一次示例输出。

Phase 1 必须能在没有真实 Reachy、没有真实麦克风的情况下跑起来。

Phase 2 至少必须能用 fallback 路径跑起来：

```bash
--vad disabled --stt mock --tts print
```

如果真实 VAD/STT/TTS 依赖安装失败，不要阻塞 Phase 1 和 Phase 2 fallback。

---

## 11. 重要约束

请严格遵守：

1. 不要大改 ZeroClaw 核心框架，优先以 extension / adapter / example app 的方式接入。
2. 不要把 baby-reachy-mini-companion 的整个 runtime 嵌进 ZeroClaw。
3. 不要同时让 ZeroClaw 和原 app 管同一个 LLM/tool loop。
4. 不要在 Phase 1/2 中实现 camera、YOLO、YAMNet、Signal。
5. 不要让 agent 假装有视觉或安全检测能力。
6. 不要强依赖真实 Reachy 硬件。
7. dry-run 必须是第一等运行模式。
8. 代码要尽量小，方便未来迁移到 OpenHarmony 或改写为 C++/native service。
9. 所有外部依赖都要写进 `pyproject.toml`，但音频大依赖尽量 optional。
10. 所有启动失败要给出可读错误，不要只有 stack trace。

---

## 12. 推荐实现顺序

请按这个顺序做：

1. 阅读 ZeroClaw 本地源码，确认 tool/provider/runtime 扩展方式。
2. 阅读 baby-reachy-mini-companion 的 tools 和 local audio 相关代码。
3. 创建 `zeroclaw-reachy-companion` 工程骨架。
4. 实现 config / profile 加载。
5. 实现 `ReachyClient` dry-run。
6. 实现 Phase 1 tools。
7. 实现文本 loop。
8. 接入本地 LLM provider 或 ZeroClaw 已有 provider。
9. 实现 JSON command fallback。
10. 写 smoke tests。
11. 实现 Phase 2 fallback voice loop：`vad disabled + stt mock + tts print`。
12. 再接 Silero VAD / Faster-Whisper / Kokoro TTS。
13. 更新 README。
14. 给出运行结果和 TODO。

---

## 13. 期望最终效果示例

Phase 1 dry-run：

```text
$ python -m zeroclaw_reachy_companion.app --mode text --reachy-mode dry_run

Profile: baby_companion
Reachy mode: dry_run
User> Tell me a short bedtime story.

Agent> I’ll tell a tiny bedtime story.
Tool: play_emotion({"emotion": "gentle"})
[DRY-RUN] play_emotion: gentle
Tool: story_time({"topic": "bedtime"})
[DRY-RUN] speak: Once upon a time, a little star watched over a sleepy robot...
```

Phase 2 fallback：

```text
$ python -m zeroclaw_reachy_companion.app --mode voice --vad disabled --stt mock --tts print --reachy-mode dry_run

Voice mode: fallback
Mock STT input> Can you soothe the baby?

Agent> Of course. I’ll be gentle.
Tool: soothe_baby({"style": "gentle"})
[DRY-RUN] play_emotion: calm
[DRY-RUN] move_head: yaw=0 pitch=-5 roll=0 duration=2.0
[TTS-PRINT] Shhh, it’s okay. I’m here with you.
```
