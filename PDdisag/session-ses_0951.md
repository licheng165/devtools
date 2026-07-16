# Create/update AGENTS.md instructions file

**Session ID:** ses_095193495ffecKLlNCsLLQAW41
**Created:** 7/16/2026, 12:28:58 PM
**Updated:** 7/16/2026, 1:00:11 PM

---

## User

Create or update `AGENTS.md` for this repository.

The goal is a compact instruction file that helps future OpenCode sessions avoid mistakes and ramp up quickly. Every line should answer: "Would an agent likely miss this without help?" If not, leave it out.

User-provided focus or constraints (honor these):


## How to investigate

Read the highest-value sources first:
- `README*`, root manifests, workspace config, lockfiles
- build, test, lint, formatter, typecheck, and codegen config
- CI workflows and pre-commit / task runner config
- existing instruction files (`AGENTS.md`, `CLAUDE.md`, `.cursor/rules/`, `.cursorrules`, `.github/copilot-instructions.md`)
- repo-local OpenCode config such as `opencode.json`

If architecture is still unclear after reading config and docs, inspect a small number of representative code files to find the real entrypoints, package boundaries, and execution flow. Prefer reading the files that explain how the system is wired together over random leaf files.

Prefer executable sources of truth over prose. If docs conflict with config or scripts, trust the executable source and only keep what you can verify.

## What to extract

Look for the highest-signal facts for an agent working in this repo:
- exact developer commands, especially non-obvious ones
- how to run a single test, a single package, or a focused verification step
- required command order when it matters, such as `lint -> typecheck -> test`
- monorepo or multi-package boundaries, ownership of major directories, and the real app/library entrypoints
- framework or toolchain quirks: generated code, migrations, codegen, build artifacts, special env loading, dev servers, infra deploy flow
- repo-specific style or workflow conventions that differ from defaults
- testing quirks: fixtures, integration test prerequisites, snapshot workflows, required services, flaky or expensive suites
- important constraints from existing instruction files worth preserving

Good `AGENTS.md` content is usually hard-earned context that took reading multiple files to infer.

## Questions

Only ask the user questions if the repo cannot answer something important. Use the `question` tool for one short batch at most.

Good questions:
- undocumented team conventions
- branch / PR / release expectations
- missing setup or test prerequisites that are known but not written down

Do not ask about anything the repo already makes clear.

## Writing rules

Include only high-signal, repo-specific guidance such as:
- exact commands and shortcuts the agent would otherwise guess wrong
- architecture notes that are not obvious from filenames
- conventions that differ from language or framework defaults
- setup requirements, environment quirks, and operational gotchas
- references to existing instruction sources that matter

Exclude:
- generic software advice
- long tutorials or exhaustive file trees
- obvious language conventions
- speculative claims or anything you could not verify
- content better stored in another file referenced via `opencode.json` `instructions`

When in doubt, omit.

Prefer short sections and bullets. If the repo is simple, keep the file simple. If the repo is large, summarize the few structural facts that actually change how an agent should work.

If `AGENTS.md` already exists at `/root/code/shaaaaaa/kv_cache_adapter`, improve it in place rather than rewriting blindly. Preserve verified useful guidance, delete fluff or stale claims, and reconcile it with the current codebase.

---

## Assistant

**Tool: read**

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

**Tool: bash**

**Tool: read**

**Tool: read**

---

## Assistant

**Tool: read**

---

## Assistant

**Tool: read**

**Tool: read**

---

## Assistant

**Tool: read**

---

## Assistant

**Tool: grep**

---

## Assistant

**Tool: grep**

---

## Assistant

**Tool: read**

---

## Assistant

**Tool: read**

---

## Assistant

**Tool: read**

---

## Assistant

**Tool: read**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: grep**

---

## Assistant

**Tool: read**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

I have enough context. The repo has no `AGENTS.md` yet, no CI/lint/typecheck config — the only config is `setup.py`. The highest-signal, hard-won facts are: the repo root doubles as the `kv_cache_adapter` package, test/bench files use two conflicting import styles, the build produces three conditional native extensions, and `VLLM_ASCEND_ADAPTER_PLAN.md` codifies API invariants and NPU debug discipline.

Let me verify one more detail about the import-style split before writing.

**Tool: bash**

---

## Assistant

Now I'll write the `AGENTS.md`.

**Tool: write**

---

## Assistant

Created `AGENTS.md` at the repo root. It's a compact, verified instruction file focused on the things an agent would most likely get wrong without help:

- **The repo-root-is-the-package quirk** and the two conflicting import styles (package-qualified vs bare `adapter`), with the exact dual-`PYTHONPATH` invocation needed to run the full suite.
- **Conditional native extension build** — three extensions, each with its own trigger, plus the gitignored `.so` sidecar that must be rebuilt after checkout.
- **`KVCA_SLOT_META_BITS` build/runtime match** requirement (silent breakage on mismatch).
- **Runtime path selection** rules and the `prefer_native_extension=False` footgun on CUDA/NPU.
- **Test quirks**: skip conditions, `importorskip` chains, the NPU kernel test path requirements, and the explicit absence of any lint/typecheck/CI config.
- **API invariants and NPU debug discipline** condensed from `VLLM_ASCEND_ADAPTER_PLAN.md`, since that doc is the source of truth for hot-path and debugging rules.

Every section is grounded in `setup.py`, `adapter.py`, the test files, and the plan doc — nothing speculative.

---

## User

请将“AGENTS.md”翻译为简体中文。

---

## Assistant

**Tool: read**

---

## Assistant

**Tool: write**

---

## Assistant

已将 `AGENTS.md` 翻译为简体中文，保留了原有结构、代码块、命令和技术术语（如 `runtime_path`、`prefer_native_extension`、`sys.path` 等保留英文以确保准确）。

---

## User

请面向完全没有AI背景的程序员，详细分析一下这个项目的原理和架构，这个方案有什么优点和缺点，适用于什么场景。

---

## Assistant

我已对仓库有了较深入的了解。在面向零 AI 背景程序员讲解前，我先把关键的实现细节再读透一些——尤其是 KV cache 适配的核心数据结构、驱逐/加载流程、以及 NPU kernel 的作用。让我并行读取几处关键代码。

**Tool: read**

**Tool: read**

---

## Assistant

**Tool: read**

**Tool: grep**

---

## Assistant

**Tool: read**

**Tool: read**

---

## Assistant

**Tool: read**

---

## Assistant

下面我尽量用「没有 AI 背景、但懂编程」的视角，把这个项目讲透。我先读了 `adapter.py`（核心 2830 行）、`setup.py`、`VLLM_ASCEND_ADAPTER_PLAN.md`、`csrc/` 下的原生扩展头文件，分析全部基于实际代码。

---

## 一、先补一点背景：KV cache 是什么，为什么它是个大麻烦

大语言模型（LLM）推理时，有一个非常占显存的东西叫 **KV cache**。

- Transformer 的注意力机制里，每个 token 在每一层都会算出一个 **Key 向量**和一个 **Value 向量**。
- 生成第 N 个 token 时，需要把前面 1…N-1 个 token 的 K、V 全部重新拿来用。为了避免重复计算，推理引擎会把历史 token 的 K/V 缓存下来——这就是 **KV cache**。
- 它的特点是：**随序列长度线性增长**，而且必须常驻在加速器（GPU/NPU）显存里，因为每一步都要高速访问。

于是 KV cache 成了推理显存的大头。为了让显存能装下更多请求、支持更长上下文，推理框架（vLLM 等）发明了 **PagedAttention / 分块 KV**：把 KV cache 切成一个个固定大小的 **block**（一个 block 存若干 token 的 K/V），用一个「块表（block table）」来记录每个请求用了哪些块——非常像操作系统的分页内存管理。

这个项目 `kv_cache_adapter` 就是卡在 vLLM 的分块 KV 内存管理这一层的一个**适配器（adapter）**。它解决的是一个非常具体的工程矛盾，下面展开。

---

## 二、这个项目要解决的核心矛盾

vLLM 的调度器（scheduler）有一个习惯：它假设自己拥有一**很大**的 KV block 池，并按「逻辑 block id」来记账（哪个请求占了几号 block）。

但物理现实是：加速器显存装不下那么大一个池子。真正常驻在显存里的，只是**当前这一步前向计算**真正要用到的那一小部分 block——这叫**物理常驻 block 池**。

于是就有两个 id 空间：

- **逻辑 block id**：调度器看到的、虚拟的、很大的 id 空间（比如 1024 个）。
- **物理 block id / 物理 slot**：显存里真实存在的那一小撮 slot（比如 128 个）。

`adapter.py:317` 的注释一句话点题：

> Maps n logical ids onto m resident physical slots in actual block tensors.（把 n 个逻辑 id 映射到 m 个常驻物理 slot 上）

而且 `num_actual_blocks <= num_logical_blocks`（`adapter.py:351`）。**这是一个「虚拟内存 → 物理内存」的映射层**，类比的话，它非常像 OS 里的 page cache + 换页机制：

| OS 概念 | 本项目对应 |
|---|---|
| 虚拟页号 | 逻辑 block id |
| 物理页帧 | 物理 slot |
| 页表 | `logical_to_physical` 映射表 |
| 缺页中断 | cache miss → 从后端加载 |
| 换出（写回磁盘） | 驱逐 dirty block → `save_slots` 存回后端 |
| 换入 | `load()` 从后端读回显存 |
| 磁盘/swap 区 | `BlockStoreBackend`（如 LMCache 的 CPU 内存池） |

**调度器继续用逻辑 id 记账，仿佛有一个巨大的 KV cache；而底层算子只接触物理 id，只看得到一小块显存。** 适配器负责两者之间的翻译、按需加载、和满载时的驱逐换页。这就是整个项目的灵魂。

---

## 三、整体架构

```
        vLLM 调度器 (用逻辑 block id 记账)
                      │
                      │  load(logical_ids) / release(logical_ids)
                      ▼
           ┌──────────────────────┐
           │   KVCacheAdapter     │  ← 本项目核心
           │  (logical→physical   │
           │   映射 + 驱逐 + 计数) │
           └──────────┬───────────┘
                      │  物理 slot id
        ┌─────────────┼──────────────┐
        ▼             ▼              ▼
   物理 KV 张量    原生扩展        BlockStoreBackend
  (显存里真实      (CUDA/NPU       (KV 的“磁盘”)
   常驻的 block)   kernel，做       ├─ InMemoryBlockStoreBackend
                   元数据fusion)    └─ LMCacheBackend (CPU pinned 池)
```

三层职责：

1. **上层接口**：`load()` / `release()` / `mark_dirty()`，入参出参都是逻辑 id（外加物理 slot id 给算子）。
2. **映射与调度核心**：几张元数据表 + 驱逐策略，决定谁常驻、谁被换出。
3. **后端**：`BlockStoreBackend` 协议，决定被换出的 block 去哪存、miss 时从哪读。

---

## 四、核心数据结构（`adapter.py:317-403`）

一个 `KVCacheAdapter` 实例持有这几张表（都在显存里）：

### 1. `logical_to_physical`：逻辑 → 物理 slot 的「页表」
- 长度 = `num_logical_blocks`，dtype int64。
- 值 `>=0`：该逻辑 block 当前常驻在哪个物理 slot。
- 值 `-1`（`_PHYSICAL_SLOT_FREE`）：不在显存里（被换出了，或从没加载过）。
- 值 `-2`（`_PHYSICAL_SLOT_PENDING`）：异步驱逐中，slot 还没真正释放（数据正在往 CPU 存）。

### 2. `physical_to_logical`：物理 slot → 逻辑 id 的反向表
- 长度 = `num_actual_blocks`。
- 用于驱逐时反查「这个 slot 现在装的是哪个逻辑 block」。

### 3. `slot_meta`：每个物理 slot 的状态，**打包进一个 uint8/uint16**（`adapter.py:19-54`）
这是性能关键。一个 slot 的元数据被位压缩成一个字节（或两个字节）：

```
| request_hit(1) | dirty(1) | usage_count | pin_count |
```

- **pin_count**（默认 3 bit）：被几个「引用」钉着。>0 就**不能被驱逐**（这一步前向还要用）。
- **usage_count**（默认 3 bit）：LRU 风格的「最近使用程度」，用来挑驱逐受害者。
- **dirty**（1 bit）：被改过没？驱逐时如果是脏的，必须 `save_slots` 写回后端；干净的直接丢弃。
- **request_hit**（1 bit）：本轮 load 是否命中。

> ⚠️ `KVCA_SLOT_META_BITS`（8 或 16）是**编译期宏，同时固化进 `.so`、又在 `adapter.py` 导入时读取**——两边必须一致，否则位打包会静默错位。这是 `setup.py` 和 `adapter.py:19` 共同约定的契约。

### 4. `search_start`：一个标量游标，加速「找空闲 slot」的扫描。

---

## 五、工作流程：一次 `load()` 发生了什么（`adapter.py:445-516`）

这是热路径，理解它就理解了项目。假设调度器说：「我这一步要用逻辑 block `[5, 2, 2, 7]`」（注意 2 重复，因为 prefix 共享/block 表展开）。

```
load([5,2,2,7], unique_logical_block_ids=[5,2,7])
   │
   1. 元数据操作只用 unique 集合 [5,2,7]（去重在调用方做，热路径不做 torch.unique）
   │
   2. inspect_load_requests: 查 logical_to_physical
      → 5 不在(miss)、2 在(slot=3)、7 不在(miss)
      → hit_slot_ids=[3], miss_logical_ids=[5,7]
   │
   3. pop_reusable_slots: 给每个 miss 找一个空闲/可驱逐的物理 slot
      → 若空闲 slot 不够，挑 pin_count==0 且 usage_count 最低的受害者驱逐
   │
   4. build_eviction_plan + save_eviction_plan:
      → 被驱逐的 slot，若 dirty=True，调 backend.save_slots 写回后端
   │
   5. 若 load_missing=True：backend.load_blocks 把 [5,7] 的 KV 从后端读进新 slot
      若 load_missing=False：只占位不读取，调用方自己初始化这个 slot（新分配的写 block 走这条）
   │
   6. commit_load_metadata: 原子更新映射表 + slot_meta(pin+1, usage 置新, dirty 清)
   │
   7. 返回物理 id：logical_to_physical.index_select([5,2,2,7]) → [新slot, 3, 3, 新slot]
      （重复的逻辑 id 自然映射到同一个物理 slot，block 表展开就这么处理）
```

配套的几个 API：

- **`release(logical_ids)`**（`adapter.py:801`）：前向算完后，对每个 unique 逻辑 id 把 pin_count 减 1。pin 归零的 slot 才重新可被驱逐。
- **`mark_dirty(logical_ids)`**（`adapter.py:732`）：把对应 slot 的 dirty 位置 1。算子改写了 KV 内容后必须调用，否则驱逐时会丢数据。
- **`save_slots(logical_ids, actual_blocks, physical_slot_ids)`**：运行时驱逐写回的官方 API（`adapter.py:105` 协议、`1784` 实现）。注意 `put_blocks()` 只用于初始化/测试，**不要在热路径上用 `index_select` 保存**——这是计划文档明确禁止的。

### 两种驱逐模式

1. **同步驱逐**（普通 `load()`）：miss 时当场挑受害者、当场把脏数据 `save_slots` 写回、再加载新数据。简单但每步都可能阻塞在前后端搬运上。
2. **异步驱逐**（`load_with_async_eviction`，`adapter.py:637`，实验性）：load 只用当前空闲 slot，**不**同步驱逐；之后后台慢慢把脏 block 异步存回（`save_slots_async` 返回 `SaveSlotsAsyncHandle`，`poll_async_evictions` 轮询回收）。靠水位线（`async_eviction_free_ratio` / `target_free_ratio`）控制何时触发补充空闲 slot。脏驱逐期间 slot 标 `-2 PENDING`，存完才真释放。

---

## 六、后端层：`BlockStoreBackend`（KV 的「磁盘」）

`BlockStoreBackend` 是个 `Protocol`（`adapter.py:104`），只要实现 `save_slots` / `load_blocks` 即可。内置两个实现：

### `InMemoryBlockStoreBackend`（`adapter.py:1459`）
- 就是个 `dict[logical_id -> tensor]`，纯内存，用于测试和单机简单场景。

### `LMCacheBackend`（`adapter.py:1694`）
- 包装 [LMCache](https://github.com/LMCache/LMCache) 的 `LocalCPUBackend`，把被驱逐的 KV 存到 **CPU pinned memory** 池子里。
- 关键设计：**一个逻辑 block 对应一个 LMCache 对象**（不是 per-token、也不是 per-K/V-tensor）。
- 支持把**多个 actual 张量打包成一个 32 字节对齐的 uint8 bundle**（`_BlockBundleLayout`，`adapter.py:262`）。这样 DSA/MLA 这种 K 和 V 形状不同的分离布局，也能共用同一套「逻辑→物理」映射。
- **NPU 专用快路径**（`adapter.py:1800` `_save_slots_npu`）：不走 LMCache 老的 token 级融合传输，而是用原生 `block_bundle_save` / `block_bundle_load` op，直接在 NPU slot 和 pinned host bundle 之间拷贝，并**按 block 把工作切到多个 AICore**上并行。

---

## 七、为什么要写原生扩展（C++/CUDA/Ascend C++）

这是理解项目「为什么不只是个 Python 类」的关键。

元数据操作（命中/缺失划分、找空闲 slot、LRU 老化、构造驱逐计划）如果用纯 Python + PyTorch 写，会大量出现 `torch.nonzero`、`index_select`、`index_put_` 这类**小张量、控制流密集**的操作。它们每一次都会触发 device→host 同步（要把结果 `.tolist()` 才能做分支），在 NPU/GPU 上是性能毒药——热路径上几十微秒的 kernel 调用，被几百微秒的同步吃掉。

于是项目把这一整套元数据操作融合成几个原生 kernel（见 `csrc/ascend/adapter_meta_kernels.h`）：

- `prepare_load_metadata` / `prepare_async_load_metadata`：把「命中压缩、miss 压缩、可复用 slot 选择、usage 老化、驱逐计划」**一次性**算成定长设备张量输出，Python 只读一个很小的 counts 张量来驱动后续 backend 调用。
- `commit_load_metadata` / `commit_async_load_metadata`：原子提交映射表和 slot_meta 更新。
- `release_metadata` / `mark_dirty_metadata`：同上。
- `pop_reusable_slots`：选可复用 slot 并就地老化 usage。
- `block_bundle_save/load`、`direct_block_bundle_save/load`、`host_to_staging`/`staging_to_host`：NPU 上 KV payload 的搬运 kernel。

于是有了三条运行时路径（`adapter.py:888` `_detect_native_extension`）：

- `cuda_ext_meta`：有 CUDA 扩展时。
- `npu_ext_meta`：有 NPU 扩展时。
- `strict`：纯 Python 兜底，**仅 CPU**。

⚠️ 一个强约束：**CUDA/NPU 设备上必须用原生扩展**。在 cuda/npu 设备上设 `prefer_native_extension=False` 会直接抛错（`adapter.py:895/902`）——因为纯 Python 路径在小张量同步上会慢到不可用，项目不让你「降级跑」来自欺欺人。

---

## 八、优点

1. **解耦「调度器视角」和「显存现实」**。调度器仍按大逻辑池记账，几乎不用改；显存占用却被压到「当前步实际需要」的规模。这是经典的虚拟化思想，侵入性小。
2. **显存能跑更大 batch / 更长上下文**。物理池小，省下的显存可以多塞请求，直接提升吞吐。
3. **按需加载 + 后端缓存 = 跨请求/跨前缀复用**。prefix cache、长上下文重计算等场景，命中的 block 直接从 CPU 池取回，省重算。
4. **热路径元数据操作被 kernel 融合**，避免 device→host 同步，这是在 NPU/GPU 上能真正用起来的关键。
5. **支持 K/V 分离的多张量布局**（DSA/MLA），bundle 打包让一套映射通吃多种注意力变体。
6. **异步驱逐路径**让搬运和计算重叠，脏 block 写回不阻塞当前步。
7. **可插拔后端**：`BlockStoreBackend` 协议清晰，未来接分布式缓存（如本工作区里的 Mooncake）只是写一个新 Backend。
8. **后端中性**：CPU/CUDA/NPU 三条路径，虽然主力是 Ascend，但 CUDA/CPU 也能跑和测。

---

## 九、缺点 / 风险

1. **复杂度集中在适配器**。映射表、位打包元数据、同步+异步两套驱逐、水位线、pending 队列——这些都是容易出微妙 bug 的地方。计划文档反复强调「不要用单核回退掩盖多核 bug」「诊断要 env 门控」，说明 NPU kernel 调试成本很高。
2. **非线程安全**（`adapter.py:324`）。调用方必须串行化，多 stream 并发用要自己加锁。
3. **编译期/运行期耦合**。`KVCA_SLOT_META_BITS` 等宏既进 `.so` 又在 import 时读，不一致就静默错位——非常隐蔽的坑（`AGENTS.md` 已记录）。
4. **异步驱逐是实验性的**，且增加了一致性复杂度：pending 期间 slot 标 `-2`，若同一逻辑 id 在存回完成前又被请求，需要正确处理「命中一个 pending slot」的语义。
5. **miss 路径有不可控的搬运延迟**。冷启动或低命中率时，每步都要从 CPU 取数据，可能比「全显存」还慢——它押注于**命中率足够高**。若工作集远大于物理池且局部性差，会反复抖动（thrashing），类似 OS 的颠簸。
6. **物理容量硬上限**：单步前向所需 unique 常驻 block 不能超过物理池大小（计划文档不变量），否则只能改 attention 算法做流式——这是架构天花板。
7. **构建依赖重**。NPU 自定义 op 要 CANN 工具包、`npu-smi`/`SOC_VERSION`、cmake、ninja、pybind11，还要 source `set_env.sh`，环境搭起来门槛高；`.so` 还 gitignore，干净 checkout 后必须重新编译。
8. **强绑定 vLLM-Ascend 的集成形态**。逻辑/物理 block 数要写进 `KVCacheConfig`、block table 物理化、`new_block_ids_to_zero` 翻译……集成改动面不小，且文档里很多还是 TODO。

---

## 十、适用场景

✅ **非常适合**
- vLLM-Ascend（华为昇腾 NPU）上的 LLM 推理服务，尤其是**长上下文、高并发、prefix 复用明显**的场景（如多轮对话、RAG、共享 system prompt）。这时 KV cache 远大于显存，但访问有强局部性，按需加载+CPU 缓存收益巨大。
- 显存成为吞吐瓶颈、想用「小显存 + 大 CPU 内存」撑更大并发 batch 的部署。
- 需要 prefix cache 跨请求复用、又不想把所有 prefix 常驻显存的场景。

⚠️ **谨慎使用**
- 短上下文、低并发、KV cache 本来就装得下的场景——额外映射和搬运是纯开销，不如直接全显存。
- 访问局部性差、工作集远大于物理池的场景——会 thrashing，性能可能不升反降。
- 非 vLLM 系或非 Ascend/CUDA 的后端——需要自己写集成胶水和 Backend 实现。
- 强实时、对尾延迟敏感的场景——miss 时的搬运延迟不可控。

---

## 十一、一句话总结

**`kv_cache_adapter` 是 LLM 推理 KV cache 的一层「虚拟内存管理器」**：它让调度器以为自己有一个巨大的 KV block 池，实际显存里只常驻当前步要用的那一小块，缺页时从 CPU 缓存按需换入、满载时按 LRU 换出（脏页写回），并用 NPU/CUDA 原生 kernel 把元数据管理融合到设备侧以避免同步开销。它本质上是把 OS 的 demand paging 思想搬到了推理引擎的 KV cache 上，换取「用小显存跑大上下文、高并发」的能力，代价是实现复杂度和对命中率的依赖。

---

如果你想进一步深入，我建议按这个顺序读源码：`adapter.py` 的 `KVCacheAdapter.load()`（445 行）→ `release()`/`mark_dirty()`（732/801 行）→ `LMCacheBackend.save_slots`（1784 行）→ `csrc/ascend/adapter_meta_kernels.h`（看融合了哪些 op）→ `VLLM_ASCEND_ADAPTER_PLAN.md`（看设计意图和约束）。

需要我对其中某一块（比如异步驱逐的状态机、或 NPU bundle 搬运的并行策略）再展开讲吗？

---

