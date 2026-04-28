# ZeroClaw Reachy Companion

这是一个 Phase 1 + Phase 2 的实验适配层，用来把
`baby-reachy-mini-companion` 里核心的 Reachy Mini 表达能力迁移到
ZeroClaw 风格的 Agent 运行时中。

项目刻意保持得比较小：

```text
ZeroClaw 风格 Agent 运行时
        ↓
Reachy Companion 工具适配层
        ↓
Reachy SDK / daemon / simulator / dry-run
```

本地 `../zeroclaw/zeroclaw` 是一个 Rust 运行时，其中 `Tool` trait 大致由
`name()`、`description()`、`parameters_schema()` 和 `execute()` 组成。本项目先用
Python 复刻这层工具接口，方便后续把 Reachy 工具迁移进 ZeroClaw 本体，而不需要把
原 Hugging Face app 的运行时整体嵌进去。

## 迁移来源

本项目参考了本地原 app 的这些文件：

- `../baby-reachy-mini-companion/baby-reachy-mini-companion/src/reachy_mini_conversation_app/main.py`
- `tools/{speak,move_head,play_emotion,story_time,soothe_baby,dance,stop_dance}.py`
- `local/{handler,llm,stt,tts,vad}.py`

当前保留的高层能力包括：说话、转头、播放情绪、讲故事、安抚、跳舞、停止动作。

当前没有迁移原 app 的完整 runtime loop、Signal 流程、相机流程、YOLO、YAMNet 和 VLM
逻辑。这些属于 Phase 1/2 之外的范围。

## 环境准备

基础依赖：

```bash
cd zeroclaw-reachy-companion
uv sync
cp .env.example .env
```

macOS 上如果要安装 Reachy SDK、daemon 和 simulator，通常还需要系统库：

```bash
brew install pkg-config cairo gobject-introspection
```

Reachy 相关 Python 包没有默认安装在 `uv sync` 里，需要时手动安装：

```bash
uv pip install reachy-mini reachy_mini_dances_library python-socks mujoco
```

本机如果没有 `python` 命令，统一使用 `uv run python ...`。

## Phase 1：文本 dry-run

dry-run 不需要真实机器人，也不需要 simulator，适合先验证 Agent 和工具调用流程。

```bash
uv run python -m zeroclaw_reachy_companion.app \
  --mode text \
  --reachy-mode dry_run
```

可以试这些输入：

```text
Tell me a short bedtime story.
Can you nod gently?
Can you soothe the baby?
Do a small happy dance.
Stop moving.
```

如果没有配置 Ollama，`--llm auto` 会退回到确定性的本地命令映射，dry-run 仍然可用。
也可以强制使用 mock：

```bash
uv run python -m zeroclaw_reachy_companion.app \
  --mode text \
  --reachy-mode dry_run \
  --llm mock
```

## 使用 LM Studio 本地模型

默认 `.env` 面向 Ollama：

```env
LOCAL_LLM_URL=http://localhost:11434
LOCAL_LLM_MODEL=ministral-3:3b
TOOL_MODE=json
```

如果使用 LM Studio，先在 LM Studio 中启动本地 OpenAI-compatible server，并加载模型。
当前测试过的模型是：

```text
qwen/qwen3-vl-8b
```

常用环境变量：

```bash
export LM_STUDIO_URL=http://127.0.0.1:1234/v1
export LM_STUDIO_MODEL=qwen/qwen3-vl-8b
```

工具调用支持两种模式：

- `--tool-mode json`：要求模型返回 `{"speak": "...", "tools": [...]}`。
- `--tool-mode native`：把函数规格发给 OpenAI-compatible 的原生 tool calling 接口。

如果 JSON 解析失败，运行时会把模型文本当成普通回复输出，而不是直接崩溃。

## Phase 2：无真实音频的语音流程

这条路径不需要麦克风、扬声器、VAD、STT 或 TTS 依赖。

```bash
uv run python -m zeroclaw_reachy_companion.app \
  --mode voice \
  --reachy-mode dry_run \
  --vad disabled \
  --stt mock \
  --tts print
```

## Phase 2：真实本地音频

真实音频依赖记录在 `pyproject.toml` 的
`tool.zeroclaw-reachy-companion.optional-runtime-dependencies` 中，没有默认启用。
原因是 `uv` 在 lock 时会解析所有依赖组，而部分 Reachy 和音频包需要平台系统库。

需要真实音频时先安装：

```bash
uv pip install numpy sounddevice soundfile torch silero-vad faster-whisper kokoro-onnx huggingface-hub
```

然后运行：

```bash
uv run python -m zeroclaw_reachy_companion.app \
  --mode voice \
  --reachy-mode dry_run \
  --vad silero \
  --stt faster-whisper \
  --tts kokoro
```

当前真实音频循环是按 Enter 开始和结束一次录音。Silero、Faster-Whisper 和 Kokoro 只会在
被选中时懒加载。

## 连接 Reachy simulator 或真机

### 启动无窗口 simulator

无窗口模式适合自动化测试：

```bash
uv run reachy-mini-daemon --sim --no-media --headless --log-level INFO
```

另开一个终端运行 Agent：

```bash
uv run python -m zeroclaw_reachy_companion.app \
  --mode text \
  --reachy-mode sim \
  --llm mock
```

### 启动可视化 simulator

在 macOS 上，带 MuJoCo 图形窗口的 simulator 需要通过 `mjpython` 启动：

```bash
uv run mjpython .venv/bin/reachy-mini-daemon \
  --sim \
  --no-media \
  --log-level INFO
```

启动成功后会出现 MuJoCo 图形窗口。另开一个终端运行 Agent：

```bash
uv run python -m zeroclaw_reachy_companion.app \
  --mode text \
  --reachy-mode sim \
  --llm mock
```

如果遇到 `libpython3.12.dylib` 找不到的问题，可以先补一个 `.venv` 内的软链接：

```bash
ln -sf /Users/huyh/.local/share/uv/python/cpython-3.12.13-macos-aarch64-none/lib/libpython3.12.dylib \
  .venv/libpython3.12.dylib
```

### 连接真机

真机 daemon：

```bash
uv run reachy-mini-daemon --no-media --log-level INFO
```

Agent：

```bash
uv run python -m zeroclaw_reachy_companion.app \
  --mode text \
  --reachy-mode real
```

`sim` 和 `real` 都会使用与原 app 相同的 Reachy SDK 入口初始化 `ReachyMini()`。
当前 `move_head` 会调用 `ReachyMini.goto_target(...)`；`dance` 使用
`reachy_mini_dances_library.dance_move.DanceMove`；`play_emotion` 使用
`RecordedMoves("pollen-robotics/reachy-mini-emotions-library")`。如果 recorded library
加载失败，会退回到轻量动作序列。

## 音频设备注意事项

macOS 上，Reachy daemon 和本项目如果同时打开同一个 USB 音频设备，可能会互相冲突。
早期 Phase 2 测试建议优先用 MacBook 自带麦克风和扬声器，或者普通外接 USB
麦克风和扬声器。

启动 daemon 时建议使用：

```bash
uv run reachy-mini-daemon --sim --no-media
```

真机测试时，尽量避免 daemon 和本项目同时占用同一个音频输入设备。

## 自动化测试

安装测试依赖：

```bash
uv sync --group dev
```

默认测试：

```bash
uv run --group dev pytest
```

默认测试覆盖：

- `ReachyClient` dry-run 初始化。
- `speak` 工具 dry-run。
- `move_head` 参数校验。
- `baby_companion.yaml` 加载。
- JSON 命令 fallback 解析。
- `vad=disabled`、`stt=mock`、`tts=print` 的单轮语音 fallback。
- Phase 1/2 场景清单和工具迁移清单。

## Phase 1/2 对标场景

场景清单在 `scenarios/reachy_phase12.yaml`。它记录了原 app 默认 profile 的工具名、
本项目已迁移的工具，以及 Phase 1/2 中有意排除的工具。

运行确定性的 dry-run 场景：

```bash
uv run python scripts/run_phase12_scenarios.py \
  --reachy-mode dry_run \
  --llm mock
```

运行同一组场景到 simulator：

```bash
uv run reachy-mini-daemon --sim --no-media --headless --log-level INFO
```

另开一个终端：

```bash
uv run python scripts/run_phase12_scenarios.py \
  --reachy-mode sim \
  --llm mock
```

运行 simulator 效果测试，确认 SDK 工具调用确实改变 simulator 状态：

```bash
uv run reachy-mini-daemon --sim --no-media --headless --log-level INFO
```

另开一个终端：

```bash
RUN_REACHY_SIM_TESTS=1 uv run --group dev pytest tests/test_sim_effects.py -s
```

## LM Studio 自动化测试

先启动 LM Studio 本地服务并加载 `qwen/qwen3-vl-8b`。如需覆盖地址和模型，可以设置
`LM_STUDIO_URL` 和 `LM_STUDIO_MODEL`。

运行真实本地模型 dry-run 测试：

```bash
RUN_LOCAL_LM_STUDIO_TESTS=1 \
uv run --group dev pytest tests/test_lm_studio_integration.py -s
```

这组测试会用真实 LM Studio 模型验证 native tool calling 和 JSON command fallback。
Reachy 使用 `dry_run`，所以输出里可以直接看到模型选择了哪些工具。

## LM Studio + simulator 自动化测试

先启动 LM Studio，再启动 Reachy simulator daemon。

可视化 simulator：

```bash
uv run mjpython .venv/bin/reachy-mini-daemon --sim --no-media --log-level INFO
```

无窗口 simulator：

```bash
uv run reachy-mini-daemon --sim --no-media --headless --log-level INFO
```

另开一个终端运行：

```bash
RUN_LOCAL_LM_STUDIO_SIM_TESTS=1 \
uv run --group dev pytest tests/test_lm_studio_sim_integration.py -s
```

这组测试会同时验证真实本地模型的工具选择，以及真实 Reachy SDK simulator 效果，包括会
产生动作的工具是否带来关节状态变化。

## 行为测试

行为测试分三类：语义测试检查自然语言隐含意图；克制测试检查机器人不会对普通输入过度
动作；mock 事件测试在没有真实 ASR、TTS、camera、YAMNet、YOLO 或 Signal 的情况下模拟
外部传感事件。

已有的直接命令集成测试：

```bash
RUN_LOCAL_LM_STUDIO_SIM_TESTS=1 \
uv run --group dev pytest tests/test_lm_studio_sim_integration.py -s
```

新的语义行为测试：

```bash
RUN_LOCAL_LM_STUDIO_SIM_TESTS=1 \
uv run --group dev pytest tests/test_lm_studio_sim_semantic_behavior.py -s
```

新的克制行为测试：

```bash
RUN_LOCAL_LM_STUDIO_SIM_TESTS=1 \
uv run --group dev pytest tests/test_lm_studio_sim_restraint_behavior.py -s
```

mock 事件测试不需要 LM Studio 或 simulator：

```bash
uv run --group dev pytest tests/test_mock_event_router.py -s
```

## 工具迁移状态

当前与原 app 默认 profile 的对标状态：

| 原工具 | 当前状态 |
| --- | --- |
| `speak` | 已迁移；SDK 没有内置说话接口，所以 sim/real 中会输出外部 TTS 文本 |
| `move_head` | 已迁移；sim/real 中调用 `ReachyMini.goto_target(...)` |
| `story_time` | 已迁移；本地短故事加语音输出 |
| `soothe_baby` | 已迁移；平静表情、轻柔动作和语音输出 |
| `dance` | 已迁移；sim/real 中使用 `reachy_mini_dances_library.dance_move.DanceMove`，失败时退回轻量动作序列 |
| `stop_dance` | 已迁移；作为 `stop_motion` 的别名 |
| `do_nothing` | 已迁移 |
| `play_emotion` | 已迁移；sim/real 中使用 `RecordedMoves("pollen-robotics/reachy-mini-emotions-library")`，失败时退回轻量动作序列 |
| `stop_emotion` | 已迁移；作为 `stop_motion` 的别名 |
| `camera` | Phase 1/2 中有意排除 |
| `send_signal` | Phase 1/2 中有意排除 |
| `send_signal_photo` | Phase 1/2 中有意排除 |
| `check_baby_crying` | Phase 1/2 中有意排除 |
| `check_danger` | Phase 1/2 中有意排除 |

## 示例输出

```text
$ uv run python -m zeroclaw_reachy_companion.app --mode text --reachy-mode dry_run --llm mock

Profile: baby_companion
Reachy mode: dry_run
User> Tell me a short bedtime story.
Agent> I'll tell a tiny bedtime story.
Tool: play_emotion({"emotion": "gentle"})
[DRY-RUN] play_emotion: gentle
Tool: story_time({"topic": "bedtime"})
[DRY-RUN] play_emotion: gentle
[DRY-RUN] speak: Once upon a time, a little star watched over a sleepy robot...
```

## TODO

- 把这些 Python 工具定义迁移成 ZeroClaw Rust `Tool` 实现，或者通过 ZeroClaw-compatible
  bridge 暴露出来。
- 增加非阻塞动作队列，让 `stop_motion` 可以中断较长的 recorded move，而不是等当前
  工具调用结束后才执行。
- 在可选音频栈安装和验证完成后，把当前 Enter-to-record 的真实音频流程替换成连续
  VAD 分段。
- 如果后续要继续对标原 app，需要补相机、Signal、哭声检测、危险检测和 VLM 相关能力。
