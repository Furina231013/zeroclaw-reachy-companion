# TODO List

接下来围绕三个目标推进：

## 1. ASR -> LLM -> TTS 流程测试通过，并完成持续监听流程

目标：把当前文本/Enter-to-record 流程推进到真实语音闭环，并支持持续监听。

- [x] 确认可选音频依赖可安装并可在本机运行：`sounddevice`、`silero-vad`、`faster-whisper`、`kokoro-onnx`。
- [x] 验证麦克风输入权限和默认输入设备。
- [x] 验证扬声器输出设备和 TTS 播放链路。
- [x] 跑通单轮真实语音链路：录音 -> ASR 转写 -> LLM 工具选择 -> TTS 输出。
- [x] 把当前 Enter-to-record 流程升级为持续监听。
- [x] 为持续监听增加退出/暂停机制。
- [x] 处理静音、噪声、低置信度 ASR、空转写等情况。
- [x] 增加最小自动化或半自动化测试，至少覆盖 mock audio/VAD 路径。
- [x] 在 README 中补充真实 ASR/TTS 和持续监听的运行命令。
- [x] 在本机实测持续监听模式的误触发率和真实响应体验。

验收标准：

- [x] 不通过键盘输入也能完成一次语音对话。
- [x] 用户说话后，系统能转写、调用 LLM、执行工具，并播放/打印 TTS 回复。
- [x] 持续监听不会在安静环境中频繁误触发。
- [x] 仍保留纯文本和 mock voice 测试路径。

阶段状态：第一阶段暂告一段落。后续如需优化，可继续调 ASR 模型、持续监听阈值和回声抑制。

## 2. 把执行层抽成服务，服务本身仍保持 Python 语言不变

目标：把 Reachy 执行能力从当前进程内调用抽成独立 Python 服务，供外部运行时调用。

- [ ] 明确服务边界：工具注册、工具 schema、工具执行、状态查询、事件注入。
- [ ] 选择服务协议：优先考虑 HTTP/JSON；如后续需要流式能力，再补 WebSocket。
- [ ] 设计 API：
  - [ ] `GET /health`
  - [ ] `GET /tools`
  - [ ] `POST /tools/{name}/execute`
  - [ ] `POST /turns/text`
  - [ ] `POST /events`
  - [ ] `GET /state`
- [ ] 把 `ReachyCompanionRuntime` 封装进服务生命周期。
- [ ] 支持 `dry_run`、`sim`、`real` 三种 Reachy 模式。
- [ ] 保持当前 CLI 路径可用，不因为服务化被破坏。
- [ ] 增加服务级测试：health、tools list、dry-run execute、mock event。
- [ ] 在 README 中补充服务启动命令和 API 示例。

验收标准：

- [ ] Python 服务可独立启动。
- [ ] 通过 HTTP 可以列出工具并执行工具。
- [ ] 通过 HTTP 可以注入 mock event。
- [ ] 当前本地测试仍然通过。

## 3. 让完整的 ZeroClaw 调用这个服务

目标：让真正的 ZeroClaw Rust 运行时通过服务调用 Reachy Companion 执行层。

- [ ] 在 ZeroClaw 侧确认工具接口需要的字段：名称、描述、参数 schema、执行结果结构。
- [ ] 在 Python 服务中提供 ZeroClaw 友好的工具 schema 输出。
- [ ] 在 ZeroClaw 中增加 Python service client。
- [ ] 把服务中的工具映射成 ZeroClaw `Tool` 实现或 bridge tool。
- [ ] 打通 ZeroClaw -> Python service -> Reachy dry-run。
- [ ] 打通 ZeroClaw -> Python service -> Reachy simulator。
- [ ] 对齐错误结构、超时、取消和日志格式。
- [ ] 增加跨进程集成测试或脚本。
- [ ] 在 README 中补充完整 ZeroClaw 调用路径。

验收标准：

- [ ] ZeroClaw 能发现并注册 Python 服务暴露的 Reachy 工具。
- [ ] ZeroClaw 能调用至少 `speak`、`move_head`、`soothe_baby`、`dance`。
- [ ] dry-run 和 simulator 路径均可从 ZeroClaw 触发。
- [ ] Python 服务异常时，ZeroClaw 能得到明确错误而不是静默失败。

## 建议推进顺序

1. 先完成真实 ASR/TTS 单轮测试，确认音频输入输出可用。
2. 再实现持续监听，避免在服务化后才发现音频链路问题。
3. 然后抽 Python 执行层服务，先只覆盖 dry-run。
4. 服务稳定后接 simulator。
5. 最后在完整 ZeroClaw 中接入服务 client 和工具 bridge。
