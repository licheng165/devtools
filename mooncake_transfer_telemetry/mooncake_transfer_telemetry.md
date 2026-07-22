# Mooncake 分布式传输统计特性

## 概述

本特性为 PD 分离场景下的 Mooncake KV cache 传输提供时延、吞吐、IOPS 和网络类型（NPU 侧 / Host 侧）的打点统计。

统计结果通过两种渠道输出：

1. **结构化 JSON 日志**（`MooncakeIO` 前缀）—— 每次 Mooncake 数据面 API 调用输出一条，包含完整的事件级数据，用于跨节点离线关联分析。
2. **周期性汇总日志**（`KV Transfer metrics:` 前缀）—— 由 vLLM 现有 stats 管线按 `VLLM_LOG_STATS_INTERVAL`（默认 10 秒）周期输出聚合摘要。

本特性不依赖 Prometheus。

## 架构

```
Mooncake 数据面 API 调用
  │
  ├── time.perf_counter_ns() 计时
  ├── classify_network_type() 推断网络类型
  ├── record_mooncake_io() → MooncakeIOStatsCollector（线程安全）
  │     │
  │     └── get_kv_connector_stats() drain
  │           │
  │           └── KVConnectorOutput → worker 聚合 → SchedulerStats
  │                 │
  │                 └── KVConnectorLogging.log()
  │                       → "KV Transfer metrics: p2p_read_success_npu_side_calls=42, ..."
  │
  └── log_mooncake_io_event() → logger.info("MooncakeIO {json}")
        │
        └── 写入 vLLM 日志
              │
              └── 离线解析 JSON，计算时延/吞吐/IOPS/分位数
```

### 数据流不变量

| 规则 | 说明 |
|---|---|
| 在最外层语义 API 调用处统计一次 | 不 monkey-patch 共享的 `GlobalTE` |
| P2P 只在发起 read/write 的一侧统计 | 避免 P/D 双计数 |
| Store put 和 get 分别统计 | 两者是独立的网络阶段 |
| TP 各 rank 的 payload bytes 直接求和 | 不除 TP 或 DP |
| 失败调用的 `completed_bytes` 为 `None` | 同步 batch 无法返回部分完成字节 |
| 不增加任何 `torch.npu.synchronize()` | 计时仅使用 `time.perf_counter_ns` |

## 修改的文件

### vLLM 仓库

| 文件 | 改动 |
|---|---|
| `vllm/distributed/kv_transfer/kv_connector/v1/mooncake/mooncake_metrics.py` | **新增**：通用统计模块（484 行），包含数据模型、网络类型推断、线程安全 collector、结构化日志 |
| `vllm/distributed/kv_transfer/kv_connector/v1/multi_connector.py` | **修复**：`get_kv_connector_stats()` 和 `build_prom_metrics()` 使用 connector 注册名而非 `__class__.__name__`；空 prom_metrics 时返回 None |
| `tests/v1/kv_connector/unit/test_mooncake_metrics.py` | **新增**：单元测试 |

### vLLM-Ascend 仓库

| 文件 | 改动 |
|---|---|
| `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py` | P2P D-read 埋点、transfer_id 传播、metadata 扩展、stats hooks |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/backend.py` | `Backend` 基类增加 `register_buffer_regions()` 和 `get_kv_connector_stats()` |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py` | Store put/get 埋点、结果解析、partial/error 统计 |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py` | 传递 buffer regions、stats delegate |
| `vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/ascend_store_connector.py` | `get_kv_connector_stats` / `build_kv_connector_stats` |
| `vllm_ascend/worker/worker.py` | **修复**：PP 中间 rank 的 stats-only 输出不再被丢弃 |

## 统计指标

### 周期性汇总日志

每隔 `VLLM_LOG_STATS_INTERVAL`（默认 10 秒）输出一行：

```
KV Transfer metrics: p2p_read_success_npu_side_calls=42,
  p2p_read_success_npu_side_attempted_bytes=5368709120,
  p2p_read_success_npu_side_completed_bytes=5368709120,
  p2p_read_success_npu_side_operations=336,
  p2p_read_success_npu_side_descriptors=336,
  p2p_read_success_npu_side_avg_duration_ms=12.345,
  p2p_read_success_npu_side_p99_duration_ms=25.678,
  store_put_success_npu_side_calls=10, ...,
  logical_transfers=42
```

指标字段命名规则：`{component}_{operation}_{outcome}_{network_type}_{metric}`

| 指标 | 含义 |
|---|---|
| `calls` | API 调用次数 |
| `attempted_bytes` | 提交的 payload 字节数 |
| `completed_bytes` | 成功完成的 payload 字节数（失败时为 0） |
| `operations` | 逻辑操作数（P2P descriptor 数 / Store key 数） |
| `descriptors` | 物理 buffer descriptor 数 |
| `avg_duration_ms` | 平均 API 调用耗时 |
| `p99_duration_ms` | P99 API 调用耗时 |
| `logical_transfers` | 去重后的逻辑 P/D 传输数 |

### 吞吐和 IOPS 计算

从周期性日志或 JSON 日志离线计算：

```text
吞吐 (bytes/s) = completed_bytes / 统计窗口秒数
Batch IOPS = calls / 统计窗口秒数
Logical IOPS (P2P) = operations / 统计窗口秒数
Object IOPS (Store) = operations / 统计窗口秒数
```

## 结构化 JSON 日志

每次 Mooncake 数据面 API 调用输出一条 JSON 日志：

```
INFO: MooncakeIO {"attempted_bytes":134217728,"call_seq":27,"completed_bytes":134217728,
  "component":"p2p","descriptors":56,"duration_ns":18300000,"engine_id":"engine-uuid",
  "event":"d_transfer_end","network_type":"npu_side","network_type_source":"path_inference",
  "operations":56,"outcome":"success","remote_request_id":"p-internal-id",
  "request_id":"d-internal-id","schema":"mooncake_io.v1","tp_rank":3,"transfer_id":"uuid-xxx",
  "wall_time_ns":1784700000000000000}
```

### 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema` | str | 固定 `"mooncake_io.v1"` |
| `event` | str | 事件名：`d_transfer_end`、`store_put_end`、`store_get_end` |
| `wall_time_ns` | int | 墙钟时间戳（纳秒），用于跨节点关联 |
| `duration_ns` | int | Mooncake API 调用耗时（纳秒） |
| `call_seq` | int | 进程内递增序号 |
| `component` | str | `"p2p"` 或 `"store"` |
| `operation` | str | `"read"`、`"write"`、`"get"`、`"put"` |
| `outcome` | str | `"success"`、`"partial"`、`"error"` |
| `network_type` | str | `"npu_side"`、`"host_side"`、`"none"`、`"unknown"` |
| `network_type_source` | str | `"path_inference"` 或 `"unresolved"` |
| `attempted_bytes` | int | 本次调用提交的 payload 字节数 |
| `completed_bytes` | int/缺失 | 成功完成的字节数；失败时缺失 |
| `operations` | int | 逻辑操作数 |
| `descriptors` | int | buffer descriptor 数 |
| `transfer_id` | str | 跨 P/D 关联的 opaque ID |
| `request_id` | str | 本侧内部请求 ID |
| `remote_request_id` | str | 对侧内部请求 ID（P2P） |
| `engine_id` | str | KV connector engine ID |
| `tp_rank` | int | Tensor parallel rank |

## 网络类型推断

`network_type` 基于运行时 connector 路径和注册的 buffer 内存类型推断，不读取 IP、网卡名、环境变量或 Mooncake 配置文件。

| 推断结果 | 条件 |
|---|---|
| `none` | 未调用 Mooncake API 或 payload 为 0 |
| `npu_side` | P2P：本地和远端 buffer 均为 NPU 内存；Store：本地 buffer 均为 NPU 内存 |
| `host_side` | P2P：本地和远端 buffer 均为 host 内存；Store：本地 buffer 均为 host 内存 |
| `unknown` | 混合内存类型、peer metadata 缺失或地址无法匹配 |

`network_type_source` 进一步标注置信度：

| 值 | 含义 |
|---|---|
| `path_inference` | 基于 connector 类型 + 内存类型推断 |
| `unresolved` | 信息不足，无法推断 |

> **注意**：`network_type` 是路径推断结果，不是 Mooncake C++ 原生报告。Mooncake Python API 不暴露实际 transport（HCCS/RoCE/TCP）或 host staging 路径。如需精确的物理链路信息，需结合 Mooncake 原生日志（`ASCEND_TRANSPORT_PRINT=1`）或 CANN profiler 交叉验证。

## transfer_id 跨节点关联

### 传播路径

```
Proxy 生成 UUID（或 P 在 request_finished 中生成）
  → kv_transfer_params["transfer_id"]
  → Proxy 转发给 D
  → D MooncakeConnectorMetadata.add_new_req
  → ReqMeta.transfer_id
  → KVCacheRecvingThread.add_request
  → 后台线程结构化日志
```

### 兼容性

- 如果 Proxy 未提供 `transfer_id`，P 侧自动生成 UUID 并放入返回参数。
- 如果 P 侧代码未升级，D 侧 `kv_transfer_params` 中不会有 `transfer_id`，日志中该字段缺失。

### 请求级时延计算

人工或脚本匹配 P/D 两端日志：

```text
P → D 数据面跨度 = max(D d_transfer_end.wall_time_ns) - min(D d_transfer_end.wall_time_ns)
P → D handoff 时延 = max(D d_transfer_end.wall_time_ns) - P kv_ready.wall_time_ns
请求吞吐 = sum(D completed_bytes) / (max(D d_transfer_end) - min(D d_transfer_begin))
```

> 跨节点时间差计算需要 NTP/chrony 时钟同步。

## P2P 传输路径

当前非 layerwise 部署中，D 侧主动从 P 的 NPU KV buffer 读取：

| 阶段 | 计时 | 说明 |
|---|---|---|
| descriptor 构造 | `prepare_duration` | 构建 `src_list`、`dst_list`、`length_list` |
| Mooncake API | `duration_ns` | `batch_transfer_sync_read` 同步调用 |
| NPU 后处理 | 不单独统计 | GQA 拼接 / NZ 转换（不进入 `duration_ns`） |

P 侧不调用任何 Mooncake 数据面 API，只通过 ZMQ 处理控制消息。

## Store 传输路径

P 侧将 NPU KV cache 写入 Mooncake Store：

| 操作 | API | 返回值语义 |
|---|---|---|
| `put` | `batch_put_from_multi_buffers` | `0` = 成功，`<0` = 失败 |
| `get` | `batch_get_into_multi_buffers` | `>=0` = 实际读取字节数，`<0` = 失败 |

结果分类：

| 场景 | outcome |
|---|---|
| 全部 key 成功 | `success` |
| 部分 key 成功 | `partial`（`completed_bytes` 按成功 key 精确累加） |
| 全部失败 | `error` |
| 返回空向量 | `error` / `invalid_result` |
| 异常 | `error` / `exception` |

当前部署中 D 侧默认 `consumer_is_to_load=False`，不从 Store 加载。

## 包含的 Bug 修复

本特性附带修复了三个已有 bug：

### 1. MultiConnector stats identity 错误

**文件**：`multi_connector.py`

**问题**：`get_kv_connector_stats()` 使用 `__class__.__name__` 作为 stats dict key。vLLM-Ascend 注册名 `"MooncakeConnectorV1"` 对应 Python 类名 `MooncakeConnector`，stats 重建时会错误命中上游 vLLM 的 `MooncakeConnector`。

**修复**：使用 `kv_transfer_config.kv_connector` 注册名作为 key。

### 2. PP 中间 rank stats 丢失

**文件**：`vllm_ascend/worker/worker.py`

**问题**：PP 中间 rank 的 `KVConnectorOutput` 只有 `kv_connector_stats`、没有 `finished_sending/finished_recving` 时，被旧代码丢弃。

**修复**：改用 `kv_connector_output.is_empty()` 判断，与上游 vLLM 行为一致。

### 3. MultiConnector 空 prom_metrics 导致 observe 崩溃

**文件**：`multi_connector.py`

**问题**：子 connector 不实现 `build_prom_metrics` 时，`MultiConnector` 仍返回空 `MultiKVConnectorPromMetrics`，首次 stats 上报时 `observe()` 断言失败。

**修复**：`prom_metrics` 为空时返回 `None`。

## 环境无关性

实现不依赖以下部署特定信息：

- IP 地址、端口范围
- TP/DP/PP 大小
- 网卡名称
- Mooncake master 地址
- 环境变量（`HCCL_INTRA_ROCE_ENABLE`、`ASCEND_TRANSPORT_PRINT` 等）
- Mooncake 配置文件中的 `protocol` 字段

网络类型推断仅依赖：
- 运行时创建的 connector/backend Python 类型
- 注册的 KV buffer tensor 的 `device.type`
- P/D 握手 metadata 中携带的远端 buffer 内存类型

## 使用方式

### 启用统计

无需额外配置。当 `kv-transfer-config` 包含 `MooncakeConnectorV1` 或 `AscendStoreConnector`（backend=mooncake）时，统计自动启用。

### 查看周期性汇总

```bash
# 日志中搜索
grep "KV Transfer metrics:" /workspace/FalconKV/logs/glm5_log_*
```

### 查看结构化事件

```bash
# 日志中搜索 JSON 事件
grep "MooncakeIO " /workspace/FalconKV/logs/glm5_log_* | python3 -c "
import sys, json
for line in sys.stdin:
    idx = line.index('{')
    payload = json.loads(line[idx:])
    print(f\"{payload['event']:20s} {payload['component']:6s} {payload['operation']:6s}\"
          f\" {payload['outcome']:8s} {payload['network_type']:10s}\"
          f\" {payload['attempted_bytes']:>12d} bytes\"
          f\" {payload['duration_ns']/1e6:>8.2f} ms\")
"
```

### 调整统计周期

```bash
export VLLM_LOG_STATS_INTERVAL=5  # 默认 10 秒
```

### 离线分析示例

从 JSON 日志计算窗口内吞吐：

```python
import json

events = []
with open("glm5_log_00000") as f:
    for line in f:
        if "MooncakeIO " not in line:
            continue
        payload = json.loads(line[line.index("{"):])
        events.append(payload)

# 按时间窗口聚合
window_start = min(e["wall_time_ns"] for e in events)
window_end = max(e["wall_time_ns"] for e in events)
window_sec = (window_end - window_start) / 1e9

total_bytes = sum(e.get("completed_bytes", 0) for e in events
                  if e["outcome"] == "success")
total_calls = len(events)

print(f"窗口: {window_sec:.1f}s")
print(f"吞吐: {total_bytes / window_sec / 1e6:.1f} MB/s")
print(f"IOPS: {total_calls / window_sec:.1f} calls/s")
```

## 测试

### 单元测试

```bash
cd vllm
pytest tests/v1/kv_connector/unit/test_mooncake_metrics.py -v
```

覆盖场景：
- 网络类型分类器（NPU/host/mixed/empty）
- stats record + drain（不丢不重）
- 失败调用 `completed_bytes` 处理
- 多 worker aggregate + transfer_id 去重
- reduce 不依赖 numpy
- 并发 record/drain 线程安全

### 端到端验证

| 场景 | 预期结果 |
|---|---|
| P2P NPU→NPU | `network_type=npu_side`，`source=path_inference` |
| Store put NPU buffer | `network_type=npu_side` |
| Prefix 全命中 | 不产生 MooncakeIO 事件 |
| 传输失败 | `outcome=error`，`completed_bytes` 缺失 |
| Partial put | `outcome=partial`，`completed_bytes` 为精确成功字节 |
| P 侧 P2P | 无 P2P stats（P 不调用数据面 API） |
| D 侧 Store | 无 Store stats（默认 `consumer_is_to_load=False`） |
