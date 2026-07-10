# GLM5.1 PD分离decoder退出问题根因分析

**Session ID:** ses_0b36cd21cffe6hKJ9Bz9RezbiC
**Created:** 7/10/2026, 3:09:01 PM
**Updated:** 7/10/2026, 3:16:02 PM

---

## User

该目录下有四个大模型推理引擎相关的仓库：vllm、vllm-ascend、LMCache、LMCache-Ascend；vllm部署时使用的就是四个仓库的falconkv_base分支进行对接。该目录下还有一个pytorch仓库；部署时如果使用torch_npu的2.9.0版本则对应代码就是该仓库的“v7.3.0-pytorch2.9.0”这个tag；部署时如果使用torch_npu的2.9.0.post2版本则对应代码就是该仓库的“v26.0.0-pytorch2.9.0”这个tag。 我在尝试GLM5.1的四机PD分离部署（1P1D，P:TP8 DP2，D:TP8 DP2），使用torch_npu的2.9.0版本，其中prefiller0的启动脚本是“0709-decoder_exit/run_dp_template_prefiller0.sh”，prefiller1的启动脚本是“0709-decoder_exit/run_dp_template_prefiller1.sh”，decoder0的启动脚本是“0709-decoder_exit/run_dp_template_decoder0.sh”，decoder1的启动脚本是“0709-decoder_exit/run_dp_template_decoder1.sh”；两个decoder的vllm进程启动阶段时都会报出非常多形如“0709-decoder_exit/decoder_plog_启动阶段频繁报出.log”的plog日志；两个decoder的vllm进程接收到decode任务时，都会打印“0709-decoder_exit/decoder_plog_推理请求时报出.log”的plog日志，并且两个decoder进程各自打印了“0709-decoder_exit/decoder0_vllm_推理请求时报出.log”和“0709-decoder_exit/decoder1_vllm_推理请求时报出.log”的vllm日志之后vllm进程退出。如果decoder的vllm配置加上“--enforce_eager”或者使用torch_npu的2.9.0.post2版本都可以规避这个问题。请问这个问题的根因是什么，为什么torch_npu的2.9.0会有该问题而torch_npu的2.9.0.post2没有该问题？ 

---

## Assistant

我将首先探索相关文件以了解该问题。让我先从检查目录结构和日志文件开始。

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: read**

---

## Assistant

现在让我读取启动脚本和关键源代码文件。

**Tool: read**

**Tool: read**

**Tool: read**

---

## Assistant

现在让我查看一下关键的源代码文件。让我检查一下 `acl_graph.py` 以及相关的 `worker` 和 `model_runner` 代码。

**Tool: bash**

**Tool: bash**

**Tool: bash**

---

## Assistant

**Tool: bash**

**Tool: bash**

**Tool: read**

---

## Assistant

**Tool: read**

**Tool: read**

**Tool: read**

---

## Assistant

现在让我查看 `pytorch` 仓库，并了解这两个 `torch_npu` 版本之间的区别。

**Tool: bash**

**Tool: bash**

**Tool: bash**

---

## Assistant

我来调查一下这两个 `torch_npu` 版本之间的差异，特别是关于 `graph capture` 和 `memcpy` 的处理。

**Tool: bash**

**Tool: bash**

---

## Assistant

**Tool: bash**

**Tool: bash**

---

## Assistant

**Tool: bash**

**Tool: bash**

**Tool: bash**

---

## Assistant

让我更深入地调查一下图捕获流程。该错误与捕获模式下的同步 `memcpy` 有关。我来看一下相关的代码路径。

**Tool: task**

**Tool: bash**

**Tool: bash**

---

## Assistant

太棒了！现在让我检查一下两个版本之间与图捕获（graph capture）和 tiling 处理相关的关键提交。

**Tool: bash**

**Tool: bash**

**Tool: bash**

**Tool: bash**

---

## Assistant

这个提交 `f83b2829d` 看起来非常关键。让我检查一下它的实际差异（diff），以及任务队列与图捕获（graph capture）之间的关系。

**Tool: bash**

---

## Assistant

这是一个关键发现。让我通过搜索 `shared expert` 多流功能及其 `wait_stream` 的使用情况来验证其联系。

**Tool: grep**

**Tool: grep**

---

## Assistant

让我验证一下 fused_moe 中的共享专家流路径，以确认 `wait_stream` 的使用情况。

**Tool: read**

**Tool: read**

---

## Assistant

让我验证一下 `f83b2829d` commit 是否仅存在于 v26.0.0 tag 中，而不存在于 v7.3.0 中。

**Tool: bash**

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

现在让我验证一下 vllm-ascend 中的 `npu_stream_switch` 工具：

**Tool: grep**

---

## Assistant

**Tool: read**

---

## Assistant

现在我已经有了完整的分析结果，让我总结一下根因。

## 根因分析

### 核心问题

问题出在 **torch_npu 2.9.0（pytorch tag `v7.3.0-pytorch2.9.0`）中，当以下三个特性同时开启时，ACLGraph 捕获阶段的任务队列（task queue）未刷新导致图捕获不完整**：

1. `TASK_QUEUE_ENABLE=1` — Ascend 任务队列
2. `multistream_overlap_shared_expert=true` — 共享专家多流重叠
3. `cudagraph_mode: "FULL_DECODE_ONLY"` — 全图捕获模式

### 触发链路

`multistream_overlap_shared_expert` 开启后，MoE 层的共享专家计算会切换到旁路流 `shared_experts_calculation_stream()` 上执行，计算完成后主流通过 `wait_stream()` 等待旁路流完成（`vllm_ascend/ops/fused_moe/fused_moe.py:708`）：

```python
with npu_stream_switch(shared_experts_calculation_stream(), enabled=self.multistream_overlap_shared_expert):
    ...
# 主流等待旁路流完成
if self.multistream_overlap_shared_expert:
    torch.npu.current_stream().wait_stream(shared_experts_calculation_stream())
```

`wait_stream()` 内部调用 torch_npu 的 `NPUEvent::block()`。

### torch_npu 2.9.0 的 Bug

在 torch_npu 2.9.0 中，`NPUEvent::block()` 的实现是：

```cpp
void NPUEvent::block(const NPUStream& stream) {
    ...
    c10_npu::queue::LaunchWaitEventTask(event_, stream, flags_);
    // ← 缺少：没有检查是否处于 ACLGraph capture 状态，也没有刷新 task queue
    ...
}
```

`LaunchWaitEventTask` 只是将等待事件**入队**到 task queue 中，但由于 `TASK_QUEUE_ENABLE=1`，事件并未真正提交给设备。在 ACLGraph 捕获期间，这导致：

1. **启动阶段报错**（`decoder_plog_启动阶段频繁报出.log`）：主流与旁路流之间的 `wait_stream` 未真正执行，ACL 运行时看到不一致的捕获上下文状态，导致 `aclrtMemcpy`（同步拷贝）失败：`rtMemcpy:ErrCode=107030, desc=[the current capture mode does not support this operation]`

2. **推理阶段崩溃**（`decoder_plog_推理请求时报出.log`）：由于图捕获时流间同步不完整，捕获到的 ACLGraph 中 MTE（Memory Transfer Engine）指令引用了无效/过期的 DDR 地址。Replay 时触发硬件异常：`aivec error: The DDR address of the MTE instruction is out of range`，并伴随 SMMU fault（`isSmmuFault is 1`），最终 `AclrtSynchronizeStreamWithTimeout` 失败（error code 507011），vllm 进程退出。

### torch_npu 2.9.0.post2 的修复

commit `f83b2829d`（"fix: fix task queue aclgraph bug"，**仅存在于** pytorch tag `v26.0.0-pytorch2.9.0`，不存在于 `v7.3.0-pytorch2.9.0`）修复了此问题：

```cpp
void NPUEvent::block(const NPUStream& stream) {
    ...
    c10_npu::queue::LaunchWaitEventTask(event_, stream, flags_);
    // 新增：如果当前设备正在 ACLGraph capture，刷新 task queue
    if (c10_npu::NPUCachingAllocator::hasCapturesUnderway(stream.device_index())) {
        c10_npu::emptyAllNPUStream();  // 将 task queue 中所有待执行任务刷新到设备
    }
    ...
}
```

修复方案：
1. 新增 `hasCapturesUnderway(device)` 接口查询当前设备是否有正在进行的 ACLGraph 捕获
2. 在 `NPUEvent::block()` 中，`LaunchWaitEventTask` 之后判断是否处于捕获状态，若是则调用 `emptyAllNPUStream()` **刷新整个 task queue**
3. 这确保捕获期间所有待执行的流同步操作（包括 `wait_stream`）都被正确提交到设备，图捕获完整正确

该 commit 的 PR 描述明确写道：**"修复了多流场景下（主流与旁路流通过 wait_stream 交互时）capture replay 结果不正确的问题"**，并新增了测试用例 `test_shared_expert_stream_capture_replay` 直接验证 shared-expert 旁路流模式下的 capture/replay 正确性。

### 为什么两种规避方式都有效

| 规避方式 | 原理 |
|---------|------|
| `--enforce_eager` | 完全禁用 ACLGraph 捕获。没有捕获，`NPUEvent::block()` 不需要在捕获期间刷新 task queue，未刷新的 wait 事件在正常执行中最终会被刷新，不影响正确性 |
| torch_npu 2.9.0.post2 | `NPUEvent::block()` 在捕获期间自动调用 `emptyAllNPUStream()` 刷新 task queue，确保图捕获完整 |

### 为什么只有 decoder 受影响

prefiller 脚本使用了 `--enforce-eager`（`run_dp_template_prefiller0.sh:71`），不进行 ACLGraph 捕获，因此不受此 bug 影响。只有 decoder 同时开启了 `TASK_QUEUE_ENABLE=1` + `multistream_overlap_shared_expert=true` + `FULL_DECODE_ONLY` 图捕获模式，三个条件同时满足才触发该问题。

---

