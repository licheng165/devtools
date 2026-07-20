# 定位GLM5.1长文本MTP精度问题日志点

**Session ID:** ses_0819e6915ffe0hfgGv3wuBvGU3
**Created:** 7/20/2026, 7:15:52 AM
**Updated:** 7/20/2026, 2:28:56 PM

---

## User

该目录下有四个大模型推理引擎相关的仓库：vllm仓库的dsa-two-groups分支，vllm-ascend仓库的sparse分支，LMCache仓库的dev-qzy分支，LMCache-Ascend仓库的dev-qzy分支，特性开发时使用的就是四个仓库的这四个分支进行对接；vllm的基线commit是262ddd0d，vllm-ascend的基线commit是99e1ea0f，LMCache的基线commit是7f326118，LMCache-Ascend的基线commit是3474a0b0。 我在其他机器上使用“0720-mtp_acc/run_1node_8npu_glm51_mtp.sh”部署单机8卡GLM5.1的时候，该脚本开启MTP以后，输入短文本提示词时输出没有什么问题；但输入长文本提示词时输出到一定长度会有重复词语毫无逻辑的现象。现在怀疑当前开发的特性和MTP两者结合有问题导致精度降低，请问可以在哪里添加日志打点来辅助我定位该问题？ 

---

## Assistant

我会先确认四个仓库、目标分支及部署脚本的实际内容，再分别对比各自基线 commit，沿着“长上下文 prefill → KV cache/稀疏计算 → MTP proposer/verify → token 接受与回退”链路定位最有价值的日志点。全程只读分析，不修改文件。

**Tool: read**

**Tool: glob**

**Tool: glob**

---

## Assistant

**Tool: read**

**Tool: read**

**Tool: bash**

**Tool: bash**

**Tool: bash**

**Tool: bash**

**Tool: bash**

**Tool: bash**

**Tool: bash**

**Tool: bash**

---

## Assistant

启动脚本同时打开了 DSA 两组池、prefill latent 缩容、LMCache 稀疏逐层回载以及 `deepseek_mtp`。短提示正常、长提示生成一段后失真，更像是 decode 过程中“主 token 数、MTP token 数、绝对位置、scratch 映射、block table”逐步发生偏移，而不是模型加载阶段的固定精度问题；接下来重点核对这些跨仓库不变量。

**Tool: task**

**Tool: task**

**Tool: task**

**Tool: task**

---

## Assistant

目前静态链路已出现一个高度可疑的确定性时序：首次 post-prefill 的 MTP 校验步里，vLLM/Ascend 已按 decode 做 scratch remap，但 LMCache 以 `num_computed_tokens > prompt_len` 判断，等于 `prompt_len` 时仍判为非 sparse decode，可能形成“索引已改写、KV 却未回载”。我会再核对该条件、释放边界和脚本中 `DECODE_WINDOW_SAVE_WINDOW_SIZE=0` 的实际语义，避免把未启用路径误列为主因。

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: grep**

**Tool: bash**

**Tool: bash**

**Tool: bash**

**Tool: bash**

---

## Assistant

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: grep**

**Tool: read**

**Tool: read**

**Tool: bash**

**Tool: bash**

**Tool: bash**

---

## Assistant

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: grep**

**Tool: bash**

**Tool: bash**

**Tool: bash**

**Tool: bash**

**Tool: bash**

---

## Assistant

已确认脚本中的 `LMCACHE_DECODE_WINDOW_SAVE_WINDOW_SIZE=0` 是“关闭 decode-window save”，所以无需优先排查窗口滚动保存；但 `SHRINK_LATENT=2` 的 prefill 后释放仍然生效。另一个重要发现是三个仓库的 `origin/bug-fix-lmy` 上存在一组尚未进入当前目标分支的 committed-boundary 协同修复，可作为日志验证结果的对照，但不能在未验证前只挑其中一个仓库合入。

**Tool: bash**

**Tool: bash**

**Tool: bash**

**Tool: bash**

**Tool: bash**

**Tool: bash**

**Tool: bash**

**Tool: bash**

**Tool: read**

**Tool: read**

**Tool: read**

---

## Assistant

**Tool: grep**

**Tool: read**

**Tool: read**

**Tool: grep**

**Tool: grep**

**Tool: grep**

---

## Assistant

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: read**

**Tool: grep**

---

## Assistant

**Tool: read**

**Tool: read**

**Tool: grep**

**Tool: grep**

---

## Assistant

**Tool: read**

**Tool: read**

**Tool: grep**

---

## Assistant

**Tool: bash**

**Tool: bash**

---

## Assistant

**Tool: read**

---

## Assistant

**Tool: grep**

---

## Assistant

以下分析基于当前本地分支 HEAD：

- vLLM `6e8ea533c`
- vLLM-Ascend `68549a24c`
- LMCache `c954644c`
- LMCache-Ascend `766a1f3`

**最高优先级怀疑**
当前代码存在一个很可疑的首次 post-prefill 时序错位：

1. Prefill 完成时 `num_computed_tokens == prompt_len`。
2. MTP 下一步会调度 2 行 target token。
3. vLLM 已经释放 latent 中间块：
   `vllm/v1/core/single_type_kv_cache_manager.py:508`
4. LMCache 却用严格大于判断 sparse decode：
   `LMCache/lmcache/integration/vllm/vllm_v1_adapter.py:6893`
   ```python
   request.num_computed_tokens > request_tracker.prompt_len
   ```
   此时 `P > P` 为 false，所以没有创建 sparse retriever。
5. vLLM-Ascend 已经把这 2 行判断为 decode，并执行 top-k scratch remap：
   `vllm-ascend/vllm_ascend/attention/sfa_v1.py:441-496`
   `vllm-ascend/vllm_ascend/attention/sfa_v1.py:1680-1848`
6. LMCache 的 `wait_for_layer_load()` 因 retriever 为空直接返回：
   `LMCache/lmcache/integration/vllm/vllm_v1_adapter.py:5398`
7. 最终 FA 使用了已经 remap 的索引，但对应 scratch 没有回载正确 KV：
   `vllm-ascend/vllm_ascend/attention/sfa_v1.py:2065-2073`

长 prompt 的 top-k 通常是历史中的离散位置，错误会很明显；短 prompt 的选择可能接近完整连续区间，错误可能暂时被掩盖。这与现象比较吻合，而且不一定是 MTP 独有问题，MTP 的两行 scratch 会放大问题。

**建议日志点**
| 优先级 | 位置 | 建议字段 | 关键异常 |
|---|---|---|---|
| P0 | `LMCache/.../vllm_v1_adapter.py:6777-6790, 6893-6932` | `req_id, prompt_len, num_computed_tokens, num_scheduled_tokens, all_token_ids_len, tracker_len, new_token_ids_len, is_sparse_decode, load_spec` | 首次 decode 出现 `computed=P, scheduled=2, is_sparse_decode=false` |
| P0 | `LMCache/.../vllm_v1_adapter.py:4733-4773` | metadata 中每个请求的 `is_sparse_decode/load_spec`，最终 `layerwise_retrievers` 数量 | MTP decode 行存在但 retriever 数为 0 |
| P0 | `LMCache/.../vllm_v1_adapter.py:5395-5399` | `layer_name, current_layer, selected_tokens.shape, request_ids, target_slot_mapping.shape, retriever_count` | `selected=[2,2048]`，但执行 `wait skipped: no retrievers` |
| P0 | `vllm-ascend/.../sfa_v1.py:441-496` | `computed, prompt_len, query_start/end, num_decode_rows, scratch_base, request_ids` | MTP 应为 `num_decode_rows=2, scratch_base=[0,2048]` |
| P0 | `vllm-ascend/.../sfa_v1.py:1716-1848` | remap 前后 top-k 的 shape/min/max/hash、`split_boundary`、`lmcache_cached_tokens`、`selected_packed` 和 target slot 摘要 | `lmcache_cached_tokens=None`，但仍发生 remap |
| P1 | `vllm/.../single_type_kv_cache_manager.py:508-547` | `prompt_len, total_computed, block_size, blocks_per_bundle, scratch_blocks, release_start/end, released_block_ids` | LMCache 尚未确认保存完成就释放，或释放边界超过 committed boundary |
| P1 | `vllm/.../scheduler.py:398-530, 1355-1378` | draft ID、调度 token 数、生成 token、accepted/rejected、修正前后 computed | 首次异常是否紧跟 MTP reject 或 computed 回退 |
| P2 | `LMCache-Ascend/.../npu_connectors.py:1844-1878` | selected/target 的 shape、numel、min/max、unique count、hash | 两者数量不等、两行 target slot 重叠 |
| P2 | `LMCache-Ascend/.../npu_connectors.py:1880-1997, 1999-2030` | `layer_id, total_tokens, chunk_size, chunk_count, selected bounds, target bounds, stream id` | `selected >= total_tokens`、chunk coverage 不足、非法 target slot |

建议在 `wait_for_layer_load():5398` 的静默返回位置至少打印一条强告警。它是最快确认上述问题的打点：

```text
[DSA_MTP_NO_RETRIEVER]
req=... layer=... current_layer=...
selected_shape=[2,2048] target_shape=[2,2048]
request_ids=[req,req] metadata_is_sparse=false
```

**必须验证的不变量**
```text
发生 scratch remap
=> 该请求必须 is_sparse_decode=true
=> load_spec.can_load=true
=> layerwise_retrievers 非空
=> 每层 selective reload 实际执行
```

```text
selected_tokens.numel() == target_slot_mapping.numel()
0 <= selected_tokens < lmcache_cached_tokens
每个 MTP row 的 target slots 互不重叠
scratch_base[row] + index_topk <= split_boundary[row]
```

MTP=1 时还应检查：

```text
num_scheduled_tokens == 2
scratch_base == [0, index_topk]
scratch_blocks * block_size >= 2 * index_topk
```

vLLM 当前已经按 2 行计算 scratch 容量，见：

- `vllm/v1/core/kv_cache_coordinator.py:190-213`
- `vllm/v1/core/dsa_shared_pool.py:31-44`

因此“scratch 总容量少算一行”目前不是第一嫌疑。但 `vllm-ascend/.../model_runner_v1.py:2309-2321` 只检查 `prompt_len < topk`，MTP 实际还应诊断 `prompt_len < 2 * topk` 的 scratch/live 区域重叠风险。

**现有开关**
可先不改代码，增加：

```bash
VLLM_LOGGING_LEVEL=DEBUG
LMCACHE_LOG_LEVEL=DEBUG
VLLM_ASCEND_DSA_LMCACHE_TRACE=1
VLLM_ASCEND_DSA_POOL_LOG_INTERVAL=1
VLLM_COMPUTE_NANS_IN_LOGITS=1
```

调试时建议临时增加 `--enforce-eager`，排除图模式和日志异步顺序干扰。`VLLM_ASCEND_DSA_LMCACHE_TRACE=1` 已会打印第 0 层 connector wait，但目前不会暴露“内部没有 retriever”，所以仍需要上述 LMCache 打点。

**日志限流**
- Scheduler 日志只由主进程打印。
- Worker 只打印 TP rank 0；必要时再加 rank 7 比较。
- 只打印最后一个 prefill step、前 4 个 decode step、首次异常及之后每 128 step。
- 层只打印 target 第 0 层、最后一层和所有 MTP 层。
- Tensor 只打印 shape/dtype/device/min/max/hash/前后 4 个值，不打印完整内容。

**最小 A/B**
| 配置 | 定位意义 |
|---|---|
| MTP on，`SHRINK_LATENT=0`，sparse off | 验证纯 MTP 基线 |
| MTP off，`SHRINK_LATENT=1`，sparse on | 验证单行 remap/reload |
| MTP on，`SHRINK_LATENT=1`，sparse on | 验证 MTP 两行路由，不释放 latent |
| MTP on，`SHRINK_LATENT=2`，sparse on | 加入 latent 释放 |

如果 stage 1 已错，优先查首次 sparse 分类和 retriever；如果只有 stage 2 错，优先查释放边界和 block table。

另外，`origin/bug-fix-lmy` 上存在尚未进入当前目标分支的一组协调修改：

- vLLM `f0f0494c8`
- LMCache `2c806910`、`9ca433cf`
- vLLM-Ascend `34159f35c`、`26f2ccee0`

它们围绕“按 LMCache committed boundary 释放/remap”，说明该边界确实是已知高风险点。但当前四个分支演进较多，不建议单独 cherry-pick；应先通过上述日志确认首次 decode 分类和 committed boundary，再整体移植或重新实现。

---

## User

wait_for_layer_load():5398的静默返回位置已增加打印，推理过程中确实会频繁打印，这种现象就可以确定是上述问题吗？

---

## Assistant

不能仅凭“频繁打印”就确定。`wait_for_layer_load()` 每层都会调用，一次 decode 就可能打印几十次；prefill、无缓存命中等场景也可能合法地没有 retriever。

**可以确认问题的条件**
同一个请求、同一个推理 step 同时满足以下条件，基本可以确定存在“已 remap、未回载”：

```text
selected_tokens is not None
selected_tokens.numel() > 0
dsa_shrink_latent != 0
SFA 已执行 prepare_sparse_indices
layerwise_retrievers == 0
最终走 trace_label="native" 的 sparse FA
```

MTP=1 时典型异常日志应类似：

```text
num_computed_tokens = prompt_len
num_scheduled_tokens = 2
is_sparse_decode = false
load_spec = None / can_load=false

num_decode_rows = 2
selected_tokens.shape = [2, 2048]
target_slot_mapping.shape = [2, 2048]
scratch_base = [0, 2048]

wait_for_layer_load:
selected_tokens_present = true
retriever_count = 0
```

这组证据意味着：

1. `prepare_sparse_indices()` 已把绝对 top-k 位置改成 scratch 位置。
2. LMCache 没有创建 retriever。
3. `wait_for_layer_load()` 没有把选中的 KV 写入 scratch。
4. FA 随后从未正确填充的 scratch 读取 KV。

在当前配置下，这已经是确定的正确性问题，即使某些短输入恰好没有表现出输出错误。

**如何解读“频繁”**
按 `layer_name` 和推理 step 分组：

| 日志分布 | 判断 |
|---|---|
| 只在 prefill 出现，且 `selected_tokens=None` | 可能正常 |
| 只在首次 post-prefill step，覆盖所有 target/MTP 层 | 高度符合 `>` 判断导致首次 decode 未建 retriever |
| 每个 decode step 的第一层就出现 | sparse metadata 或 `load_spec.can_load` 一直未生效 |
| target 层正常，只从第一个 MTP 层开始出现 | 更像 `num_layers/current_layer` 提前结束，MTP 层未计入 retriever生命周期 |
| `selected_tokens=[2,2048]` 时出现 | 对 MTP 场景属于明确异常 |

**下一步最小日志**
在 `LMCache/.../vllm_v1_adapter.py:6893` 同时打印：

```text
req_id
num_computed_tokens
prompt_len
num_scheduled_tokens
is_sparse_decode
load_spec.can_load
lmcache_cached_for_sparse
```

在静默返回处打印：

```text
layer_name
current_layer
num_layers
selected_tokens.shape
target_slot_mapping.shape
request_ids
metadata 中对应请求的 is_sparse_decode/load_spec
```

如果得到：

```text
num_computed_tokens == prompt_len
num_scheduled_tokens == 2
is_sparse_decode == false
selected_tokens.shape == [2, 2048]
layerwise_retrievers == 0
```

就可以确认此前分析的首次 post-prefill 分类问题。

还可以临时采用 fail-closed 验证：当 `selected_tokens` 非空但 retriever 为空时直接抛异常，而不是静默返回。如果服务恰好在首次 MTP decode 中止，定位就完全闭环了。

---

## User

请直接给出两处最小日志的代码

---

## Assistant

以下代码均加在 `LMCache/lmcache/integration/vllm/vllm_v1_adapter.py`。

**第一处：`build_connector_meta()` 第 6893 行附近**

放在 `is_sparse_decode` 计算后、`if is_sparse_decode:` 前：

```python
is_sparse_decode = self.enable_sparse_attention and (
    request.num_computed_tokens > request_tracker.prompt_len
)

if request.num_computed_tokens == request_tracker.prompt_len:
    logger.warning(
        "[DSA_MTP_BOUNDARY] req=%s computed=%d prompt=%d "
        "scheduled=%d all_tokens=%d tracker_tokens=%d "
        "new_tokens=%d sparse=%s load_spec=%s",
        req_id,
        request.num_computed_tokens,
        request_tracker.prompt_len,
        scheduler_output.num_scheduled_tokens[req_id],
        len(request.all_token_ids),
        len(request_tracker.token_ids),
        len(new_token_ids),
        is_sparse_decode,
        load_spec,
    )

if is_sparse_decode:
```

**第二处：`wait_for_layer_load()` 第 5398 行静默返回处**

替换原来的：

```python
if not self.layerwise_retrievers:
    return
```

为：

```python
if not self.layerwise_retrievers:
    if selected_tokens is not None:
        metadata = self._parent._get_connector_metadata()
        request_states = [
            (
                req.req_id,
                req.is_sparse_decode,
                getattr(req.load_spec, "can_load", None),
                getattr(req.load_spec, "lmcache_cached_tokens", None),
            )
            for req in metadata.requests
        ]
        logger.error(
            "[DSA_MTP_NO_RETRIEVER] layer=%s current_layer=%d "
            "num_layers=%d selected_shape=%s target_shape=%s "
            "request_ids=%s request_states=%s",
            layer_name,
            self.current_layer,
            self.num_layers,
            getattr(selected_tokens, "shape", None),
            getattr(target_slot_mapping, "shape", None),
            request_ids,
            request_states,
        )
    return
```

如果日志配对出现：

```text
[DSA_MTP_BOUNDARY] computed=P prompt=P scheduled=2 sparse=False
[DSA_MTP_NO_RETRIEVER] selected_shape=[2, 2048]
```

即可确认首次 MTP decode 已执行 sparse remap，但 LMCache 没有创建 retriever。

---

## User

已确认推理开始时打印了一条：LMCache WARNING: [DSA_MTP_BOUNDARY] req=cmpl-bf35fe05a391c33b-0-b59b4539 computed=3745 prompt=3745 scheduled=2 all_tokens=3745 tracker_tokens=3745 new_tokens=0 sparse=False load_spec=None (vllm_v1_adapter.py:6921:lmcache.integration.vllm.vllm_v1_adapter)
然后推理过程中打印非常多条形如：LMCache ERROR: [DSA_MTP_NO_RETRIEVER] layer=model.layers.0.self_attn.attn current_layer=0 num_layers=79 selected_shape=torch.Size([2, 2048]) target_shape=torch.Size([2, 2048]) request_ids=['cmpl-bf35fe05a391c33b-0-b59b4539', 'cmpl-bf35fe05a391c33b-0-b59b4539'] request_states=[] (vllm_v1_adapter.py:5410:lmcache.integration.vllm.vllm_v1_adapter) 

---

## Assistant

**Tool: grep**

---

## Assistant

**Tool: read**

---

## Assistant

**结论**
这些日志已经闭环确认“已执行 scratch remap，但 LMCache 没有创建 retriever”的问题。

证据链完整：

```text
computed=3745 == prompt=3745
scheduled=2
sparse=False
load_spec=None
```

同时：

```text
selected_shape=[2, 2048]
target_shape=[2, 2048]
layerwise_retrievers=0
request_states=[]
```

其中 `selected_tokens` 非空说明 `prepare_sparse_indices()` 已经执行；`request_states=[]` 说明 LMCache 最终没有生成任何 `ReqMeta`，worker 收到的是空 connector metadata。因此 FA 使用了 remap 后的 scratch 索引，但没有任何组件填充对应 scratch KV。

`current_layer` 一直为 0 也是结果之一：静默返回后没有执行 `current_layer += 1`，所以每层调用都会重复打印 0。

**还有第二个问题**
该请求还违反了 MTP scratch 边界要求：

```text
prompt_len = 3745
index_topk = 2048
MTP rows = 2
需要的 scratch 范围 = 2 * 2048 = 4096
```

两行 scratch 范围是：

```text
row 0: [0, 2048)
row 1: [2048, 4096)
```

而 LMCache 实际可用于 sparse direct retrieve 的完整 chunk 边界是：

```text
floor(3745 / 256) * 256 = 3584
```

因此：

```text
scratch_base(row1) + topk = 4096 > committed_boundary 3584
```

第二个 MTP row 的 scratch 会越过 LMCache boundary，并可能落到当前 decode slot或未分配的 block-table padding 上。

**修复不能只改 `>` 为 `>=`**
只把：

```python
request.num_computed_tokens > request_tracker.prompt_len
```

改成：

```python
request.num_computed_tokens >= request_tracker.prompt_len
```

虽然能创建 retriever，但对于这个 3745-token 请求，LMCache 随后会向 `[2048, 4096)` 写 scratch，仍然存在覆盖风险。

正确处理需要两部分：

1. 修复首次 post-prefill 的 sparse decode 分类，使 connector metadata 与 SFA decode 分类一致。
2. SFA remap 前检查：
   ```text
   scratch_base[row] + index_topk <= lmcache_committed_boundary[row]
   ```
   不满足时必须跳过 remap/retrieve，回退到原始 absolute top-k 和 resident latent KV。

当前请求小于 4096 token，vLLM 实际不会释放 latent 中间块，因为需要保留的 MTP scratch 已经达到 32 个 block，所以具备回退到 resident/native attention 的条件。

修复后的预期行为应是：

```text
首次 post-prefill: sparse=True
prompt/committed boundary不足4096: native fallback
不调用 selective wait
不产生 DSA_MTP_NO_RETRIEVER
```

对 prompt 的 committed boundary 大于等于 4096 的请求，则应创建 retriever并正常执行两行 selective reload。

---

## User

请详细总结一下该问题的根因是什么，以及给出一些修复方案。

---

## Assistant

**根因结论**
这不是普通浮点精度下降，而是 DSA、LMCache 和 MTP 对“当前是否已进入 decode、哪些 KV 已经可回载、scratch 是否有效”的判断不一致，最终导致稀疏注意力读取了错误的 KV 地址。

当前复现同时暴露了两个确定的正确性问题，以及一个相关的释放风险。

## 1. 首次 Decode 状态判断不一致

Prefill 完成后的首次 MTP step，实际状态是：

```text
prompt_len               = 3745
num_computed_tokens       = 3745
num_scheduled_tokens      = 2
all_token_ids length      = 3745
new_token_ids length      = 0
```

`scheduled=2` 是 MTP target model 要处理的两行，但 speculative token 尚未成为 finalized token，所以没有出现在 `all_token_ids` 中。

### LMCache 的判断

`LMCache/lmcache/integration/vllm/vllm_v1_adapter.py` 使用：

```python
request.num_computed_tokens > request_tracker.prompt_len
```

此时：

```text
3745 > 3745 == False
```

因此 LMCache 得到：

```text
is_sparse_decode = False
load_spec = None
```

由于该 step 既不需要保存，也没有 load spec，`ReqMeta.from_request_tracker()` 最终没有产生请求 metadata，所以 worker 侧看到：

```text
request_states=[]
layerwise_retrievers=[]
```

### vLLM-Ascend 的判断

SFA 根据 query rows、prompt length 和 computed tokens 判断，认为这两行已经是 decode：

```text
num_decode_rows = 2
scratch_base = [0, 2048]
```

随后 `prepare_sparse_indices()` 已经把绝对 top-k 索引改写成 scratch 索引：

```text
selected_shape = [2, 2048]
target_shape   = [2, 2048]
```

但是 LMCache 没有 retriever，`wait_for_layer_load()` 静默返回，scratch 没有被填充。

最终 FA 使用的是改写后的 scratch 索引，而对应位置仍是旧数据、无效数据或者其他位置的 KV。

### 本质问题

两个组件使用了不同的 decode 判定标准：

```text
LMCache：num_computed_tokens > prompt_len
SFA：    num_computed_tokens >= prompt_len 且当前有 decode query row
```

同时，SFA 只根据“存在 KV connector”判断是否需要构建 LMCache payload，没有确认“本请求是否真的创建了 sparse retriever”。

这形成了典型的状态分裂：

```text
SFA：已经进入 sparse decode
LMCache：仍然认为不是 sparse decode
```

## 2. MTP 两行 Scratch 空间不足

当前配置：

```text
index_topk = 2048
num_speculative_tokens = 1
MTP decode rows = 2
```

所需 scratch 空间：

```text
row 0: [0, 2048)
row 1: [2048, 4096)
总需求: 4096 token slots
```

但当前请求：

```text
prompt_len = 3745
```

LMCache sparse direct 路径只能使用完整的 256-token chunk，因此实际 committed boundary 是：

```text
floor(3745 / 256) * 256 = 3584
```

第二行 scratch 的结束位置为：

```text
scratch_base + topk = 2048 + 2048 = 4096
```

不变量已经被破坏：

```text
4096 > 3584
```

这意味着第二个 MTP row 的 scratch 范围越过了 LMCache 可提供的 KV 范围。

更严重的是，请求本身可能只分配了大约：

```text
ceil(3745 / 128) = 30 blocks
```

而两行 scratch 需要：

```text
4096 / 128 = 32 blocks
```

`_dsa_build_target_slot_mapping()` 当前只会把逻辑 block index clamp 到 block table 宽度，不会验证对应 block 是否真的为该请求分配。结果可能是：

- 写入 block table padding 对应的 block 0。
- 覆盖当前 decode token 的 KV。
- 写入已释放或属于其他用途的共享 bundle。
- 不触发异常，但输出逐渐失真。

当前代码只警告：

```text
prompt_len < index_topk
```

MTP=1 时真正需要检查的是：

```text
committed_boundary >= 2 * index_topk
```

更一般地，每行都应满足：

```text
scratch_base[row] + index_topk <= committed_boundary[row]
```

## 3. 为什么不是立即乱码，而是生成一段后重复

错误 KV 通常仍然是合法 BF16/FP16 数值，因此：

- 不一定出现 NaN。
- NPU kernel 不一定报越界。
- logits 仍然可以正常采样。
- 最初几步可能只是概率分布发生小幅偏移。

一旦错误 token 被接受并进入自回归历史，后续每一步都会基于错误历史继续推理。误差逐步放大后，模型容易进入高概率重复循环，最终表现为重复词语和无逻辑输出。

短 prompt 看起来正常也不能说明路径正确。短上下文的 top-k 可能接近完整连续前缀，compact rank 与原 token 位置偶然接近；长上下文中 top-k 通常是离散历史位置，错误映射更容易暴露。

## 4. 相关释放风险

当前 `VLLM_ASCEND_DSA_SHRINK_LATENT=2` 会在 prompt 计算完成后释放 latent 中间块：

`vllm/v1/core/single_type_kv_cache_manager.py:508-538`

释放依据是：

```text
num_computed_tokens >= prompt_len
```

而不是：

```text
LMCache 已确认保存完成的 committed boundary
```

这意味着 vLLM 可能在 LMCache 保存失败、保存未完成或只保存了部分 chunk 时提前释放 latent。

本次 3745-token 请求因为 scratch 需要保留 32 blocks，而 prompt 本身不足 32 blocks，实际上可能没有释放中间块，因此可以回退到 resident KV。但对于更长 prompt，这个释放时序会成为另一个正确性风险。

---

# 修复方案

## 方案一：立即规避

临时设置：

```bash
VLLM_ASCEND_DSA_SHRINK_LATENT=0
```

这会关闭 compact scratch remap 和 prefill 后 latent 释放，让注意力继续使用 resident latent KV。

优点：

- 改动最小。
- 可以立即验证输出是否恢复。
- MTP 可以继续开启。

缺点：

- 失去 DSA latent 显存缩容收益。
- 不解决代码中的状态契约问题。

仅关闭 MTP 不足以彻底规避，因为单行 decode 仍可能遇到首次 `computed == prompt_len` 的分类缺口。

## 方案二：最小代码修复

适合先恢复正确性，再逐步完善。

### 修复首次 Decode 分类

LMCache 将：

```python
request.num_computed_tokens > request_tracker.prompt_len
```

改为：

```python
request.num_computed_tokens >= request_tracker.prompt_len
```

对于 chunked prefill，最后一个 prefill chunk 在调度前仍满足 `computed < prompt_len`，所以不会被错误判断为 decode。

### SFA 增加 per-request 有效性判断

不能再用“connector 存在”作为 remap 条件。需要至少确认：

```text
request metadata 存在
is_sparse_decode = true
load_spec.can_load = true
committed_boundary > 0
```

如果没有 LMCache sparse metadata：

```text
不修改 topk_indices
不构建 selected_packed
不调用 selective wait
直接使用 resident latent KV
```

### 增加 MTP scratch 边界保护

remap 前逐行检查：

```python
scratch_base[row] + index_topk <= committed_boundary[row]
```

不满足时回退到原始 absolute top-k。

对本次请求：

```text
committed_boundary=3584
required=4096
```

应直接进入 native/resident fallback。

### `wait_for_layer_load()` 改为 fail closed

如果出现：

```text
selected_tokens 非空
layerwise_retrievers 为空
```

不应继续静默推理。调试阶段直接抛异常；生产阶段至少回退或终止该请求。

不能继续使用已经 remap 的索引。

### 方案效果

对于当前 3745-token prompt：

```text
LMCache 能正确识别首次 decode
SFA 发现 committed boundary < 4096
跳过 remap和回载
使用仍然驻留的完整 latent KV
```

对于 committed boundary 大于等于 4096 的 prompt：

```text
正常创建两行 scratch
正常执行 LMCache selective reload
```

## 方案三：推荐的完整协调修复

这是长期正确方案，涉及 vLLM、vLLM-Ascend 和 LMCache 三个仓库。

### 引入统一的 committed boundary

LMCache 在 latent 数据真正保存完成后，上报：

```text
dsa_committed_end
```

这个值必须：

```text
按 LMCache chunk 对齐
按 vLLM block 对齐
按 shared bundle 对齐
不大于已保存 token 数
```

vLLM、SFA 和 LMCache 必须使用同一个值：

```text
LMCache：决定能加载哪些 token
SFA：决定哪些 top-k 位置需要 remap
vLLM：决定哪些 latent blocks 可以释放
```

不能分别使用 `prompt_len`、chunk frontier 和 computed tokens。

### 只释放 committed blocks

vLLM 不再在 `num_computed >= prompt_len` 时立即释放。

应改成：

```text
LMCache worker 完成保存
→ connector output 上报 committed_end
→ scheduler 收到 committed_end
→ DSALatentManager 只释放 committed_end 覆盖的 blocks
```

如果保存失败或边界为 0，不释放任何 latent block。

### 引入 per-request sparse eligibility

每个请求计算：

```text
required_scratch_tokens =
    num_decode_rows_for_request * index_topk
```

只有满足：

```text
committed_end >= required_scratch_tokens
```

才允许进入 compact scratch 模式。

不满足时：

```text
保留 resident latent
保持 absolute top-k
不创建 sparse retriever，或创建后明确取消
```

这需要支持同一 batch 中部分请求 sparse、部分请求 native。

### 校验物理 target slots

构造 `decode_target_slot_mapping` 时增加检查：

```text
逻辑 scratch block 已实际分配
physical_block_id 不是 padding/null block
target slots 不越过 KV capacity
不同 MTP rows 的 target slots 不重叠
```

当前 `_dsa_build_target_slot_mapping()` 的 clamp 只能防止 tensor gather 越界，不能证明 block 有效。

### NPU kernel 增加边界防护

LMCache-Ascend 调用 direct kernel 前检查：

```text
selected_tokens.numel() == target_slots.numel()
0 <= selected_token < committed_end
selected_token // chunk_size < chunk_count
0 <= target_slot < KV capacity
```

prepared fast path也应具备相同检查，至少在每请求首次或 debug 模式执行。

## 方案四：独立 Scratch Pool

如果业务要求“小于 4096 token 的 prompt 也必须使用 MTP+稀疏回载”，可以给 MTP scratch 分配独立物理空间，不再复用请求前缀位置。

可选设计：

| 设计 | 特点 |
|---|---|
| 独立 scratch KV pool | 最清晰、隔离性最好，但改动较大 |
| 每个 MTP row 独立 block table | 可重复使用逻辑 `[0,K)`，需要 FA 支持 per-row table |
| 将 scratch 放到额外逻辑 block 区 | 需要扩展 block table和索引命名空间 |
| 分行执行 MTP attention | 实现简单但性能损失较大 |

该方案可以消除：

```text
prompt/committed boundary >= rows * topk
```

的限制，但涉及内存管理和注意力算子接口变化，不适合作为第一阶段修复。

---

# 推荐顺序

1. 先用 `SHRINK_LATENT=0` 验证输出恢复，确认问题与 compact scratch 路径相关。
2. 修复 LMCache 首次 decode 的 `>`/`>=` 状态差异。
3. SFA 增加“无 sparse metadata 不 remap”和 `base + topk <= committed_end` 检查。
4. 对 boundary 不足的请求回退 resident/native attention。
5. 改造 latent 释放，使其完全由 LMCache committed boundary 驱动。
6. 最后再考虑独立 scratch pool，支持短 prompt 的 MTP 稀疏优化。

`origin/bug-fix-lmy` 上的 vLLM `f0f0494c8`、LMCache `2c806910/9ca433cf`、vLLM-Ascend `34159f35c/26f2ccee0` 可以作为 committed-boundary 设计参考，但它们没有完整解决此次暴露的首次 MTP decode 分类和两行 scratch 边界问题，不应单独 cherry-pick 后直接认为问题已解决。

# 验收标准

至少覆盖以下 prompt token 长度：

```text
2047, 2048, 3584, 3745, 4095, 4096, 4097, 8192
```

每种长度比较：

```text
MTP off/on
SHRINK 0/1/2
固定 seed、greedy sampling
生成 token IDs 与 SHRINK=0 基线逐 token 对比
```

修复后应满足：

```text
selected_tokens 非空时 retriever 必定存在
无 retriever时 topk_indices 保持 absolute
每行 scratch_base + topk <= committed_end
target slots 全部属于当前请求
current_layer 正常从 0 推进到 78
不存在 DSA_MTP_NO_RETRIEVER
输出与 resident KV 基线一致
```

---

