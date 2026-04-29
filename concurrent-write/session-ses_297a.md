# FalconFs无OBS时数据节点与并发写风险

**Session ID:** ses_297ae8e86ffeFGUJP4BJWfVMlk
**Created:** 4/7/2026, 2:21:01 PM
**Updated:** 4/29/2026, 9:26:50 AM

---

## User

请详细介绍一下，FalconFs的文件内容数据，如果不对接OBS对象存储，这些文件内容数据都存储在哪些节点？如果多个客户端同时对一个文件进行并发写，会有什么问题？

---

## Assistant

**Tool: grep**

**Tool: grep**

**Tool: grep**

---

## Assistant

**Tool: read**

**Tool: grep**

**Tool: grep**

---

## Assistant

**Tool: grep**

**Tool: glob**

**Tool: grep**

---

## Assistant

**Tool: read**

**Tool: read**

**Tool: read**

---

## Assistant

**Tool: grep**

**Tool: grep**

**Tool: grep**

---

## Assistant

**Tool: read**

**Tool: read**

**Tool: read**

---

## Assistant

**Tool: read**

**Tool: read**

**Tool: read**

---

## Assistant

**Tool: grep**

**Tool: read**

**Tool: read**

---

## Assistant

**Tool: glob**

**Tool: glob**

**Tool: glob**

---

## Assistant

**Tool: read**

**Tool: read**

**Tool: grep**

---

## Assistant

**Tool: read**

**Tool: read**

**Tool: read**

---

## Assistant

**Tool: glob**

---

## Assistant

**Tool: read**

**Tool: grep**

**Tool: read**

---

## Assistant

**Tool: read**

**Tool: read**

**Tool: grep**

---

## Assistant

**Tool: read**

**Tool: read**

**Tool: grep**

---

## Assistant

**Tool: read**

**Tool: grep**

**Tool: glob**

---

## Assistant

**Tool: read**

---

## Assistant

**Tool: glob**

**Tool: glob**

**Tool: grep**

---

## Assistant

**Tool: read**

**Tool: read**

**Tool: grep**

---

## Assistant

**Tool: read**

---

## Assistant

**Tool: grep**

**Tool: read**

**Tool: grep**

---

## Assistant

**Tool: read**

**Tool: read**

**Tool: grep**

---

## Assistant

可以分成两部分看：一是“不接 OBS 时，文件内容到底落在哪里”；二是“多个客户端并发写同一个文件时，FalconFS 现在能不能保证正确性”。

**数据存放位置**

- 不接 OBS 时，文件内容数据不在元数据节点里，而是在 `falcon_store` 这类文件数据存储节点上；设计文档明确写的是：文件数据由 file data store 存在本地 `DRAM` 和 `SSD`，而 object store 只是“可选后端” `docs/design.md:7` `docs/design.md:35`
- FalconFS 的设计是“每个计算节点内部可以部署一个或多个 file data store 实例”，所以如果你没开 OBS，真正的数据副本就在这些被分配到的 store 节点本地盘上，而不是云上 `docs/design.md:35`
- 代码里也能看到这一点：store 初始化时读取 `falcon_cache_root` 作为本地数据根目录，并把它作为 `dataPath`，同时 `falcon_persist` 决定是否启用对象存储；默认配置里 `falcon_persist` 就是 `false`，也就是默认不落 OBS `falcon_store/src/falcon_store/falcon_store.cpp:42` `falcon_store/src/falcon_store/falcon_store.cpp:49` `falcon_store/src/falcon_store/falcon_store.cpp:60` `config/config.json:6` `config/config.json:18`
- 具体落盘文件名也很直接：按 `inodeId` 映射到某个本地目录，路径形如 ``<falcon_cache_root>/<dir>/<inodeId>-large`` `falcon_store/src/util/utils.cpp:19`
- 一个文件会被分配到某个 store 节点，当前实现里核心选择逻辑是对 `inodeId` 做哈希后选一个节点 `StoreNode::AllocNode(inodeId)`，因此一个文件内容通常有一个“主存放节点” `falcon_store/src/connection/node.cpp:267`
- 从仓库能看到“默认/常见配置下没有数据复制”的信号：README 的性能测试明确说没有启用 data replication `README.md:43`。所以如果你问“不接 OBS 时数据放在哪些节点”，更准确的说法是：放在“被分配到的那个 store 节点的本地 DRAM/SSD 层”上，而不是自动分散成多个副本存到多个节点
- DRAM 在这里更像高速缓冲和读写流水线的一部分，真正长期保留的数据文件还是在 store 节点本地文件系统里；例如写路径最终会 `pwrite` 到本地物理文件，关闭时若不开 OBS 就不会再刷到对象存储 `common/src/write_stream/stream_assembler.cpp:101` `falcon_store/src/falcon_store/falcon_store.cpp:871`

**如果不接 OBS，等价于什么**

- 等价于“文件内容只保存在 FalconFS 分配到的 store 节点本地存储层”
- 元数据里只保留命名空间、inode、size、block table 这类信息，不保留完整文件内容 `docs/design.md:5`
- 如果这个 store 节点本地盘坏了、节点丢了，而你又没开 OBS、也没做额外复制，那文件内容就没有一个天然的远端持久副本可回补
- 所以“不接 OBS”更接近高性能本地分布式缓存/本地持久层，而不是“天然多副本对象后端”

**并发写同一个文件会有什么问题**

先说结论：从当前开源实现看，FalconFS 对“多个客户端同时写同一个文件内容”并没有体现出完整的分布式多写者串行化保证。也就是说，目录操作/元数据操作有 ACID 和路径锁，但文件内容并发写本身看起来并不安全，至少没有看到足够的机制去保证标准 POSIX 多写者语义。

**为什么这么说**

- 设计文档里说的 ACID 和 locking，重点是元数据操作、跨元数据节点事务、路径冲突处理，比如 `create/rename/delete` 这类文件系统操作；它没有说明对同一文件内容写入有全局写锁 `docs/design.md:30` `docs/design.md:31`
- FUSE 层明确没有实现 `lock` 和 `flock`，都是 `nullptr`，这意味着常见的文件锁接口在当前实现里并不提供 `falcon_client/fuse_main.cpp:398` `falcon_client/fuse_main.cpp:409`
- 每次 `open` 都会生成自己的 `OpenInstance`；FalconFd 甚至维护了“同一 inode 对应多个 open 实例”的集合，这说明系统默认允许同一文件被多个打开句柄同时存在 `common/src/buffer/dir_open_instance.cpp:194` `common/src/include/buffer/dir_open_instance.h:102`
- 但 `OpenInstance` 里的 `fileMutex` 只是“这个 open 实例内部”的锁，不是“这个 inode 在全局范围内”的锁 `common/src/include/buffer/open_instance.h:67`
- 真正写数据时，路径是 `FalconWrite -> InnerFalconWrite -> FalconStore::WriteFile`，再进入 `WriteStream/PersistToFile`，最终本地是 `pwrite`，远端是 RPC `WriteFile`；这条链路上没有看到针对同一 inode 的全局互斥 `falcon_client/src/falcon_meta.cpp:487` `falcon_client/src/inner_falcon_meta.cpp:9` `falcon_store/src/falcon_store/falcon_store.cpp:268` `common/src/write_stream/stream_assembler.cpp:68`
- store 侧确实有 `FileLock`，但它主要用于“从 OBS 下载到本地缓存”以及读写缓存切换等场景，不是普通写路径的全局文件内容锁；普通 `WriteFile` 并不先拿这个锁 `falcon_store/src/util/file_lock.cpp:44` `falcon_store/src/falcon_store/falcon_store.cpp:640`

**实际会出现什么问题**

- `覆盖写竞态`：两个客户端同时写同一偏移区间，最后结果基本就是“谁最后落盘谁赢”，中间没有看到冲突检测或版本控制
- `交错写/内容不可预期`：如果两个客户端对重叠区域并发 `pwrite`，最终文件内容可能是任一方覆盖后的结果；从分布式视角看，不应指望有事务化的“整段写原子性”
- `文件大小回退/元数据不一致`：这是我觉得最危险的点  
  每个客户端各自维护自己的 `currentSize`，关闭时会把自己的 size 回写给元数据服务 `FalconClose -> conn->Close(path, size, ..., nodeId)` `falcon_client/src/falcon_meta.cpp:232` `falcon_client/src/falcon_meta.cpp:262`  
  如果两个客户端从同一个旧尺寸打开文件，各自扩展到不同大小，后关闭的那个客户端可能把较小的 size 又写回元数据，导致“物理文件其实更大，但元数据 size 被较小值覆盖”
- `append 语义不可靠`：当前没有看到分布式 append 锁；即使应用使用 `O_APPEND`，多个客户端同时 append 也很可能竞争同一个 EOF，造成覆盖或乱序
- `read-after-write 一致性有限`：代码里甚至直接有一句注释：`no guarantee on concurrent read and write from fuse`，说明至少读写并发一致性本身就没有保证 `falcon_store/src/falcon_store/falcon_store.cpp:274`
- `truncate/open 并发也不安全`：代码有明确注释 `User shouldn't ... concurrent truncate and open`，说明这类并发已经被作者显式视为不保证语义的场景 `falcon_client/src/falcon_meta.cpp:669`

**一个具体例子**

假设文件最开始大小是 0：

```text
客户端 A: open(file), 看到 size=0
客户端 B: open(file), 看到 size=0

A 在 offset=0 写 4KB，A.currentSize=4KB
B 在 offset=8KB 写 4KB，B.currentSize=12KB

如果 B 先 close，把元数据 size 更新成 12KB
随后 A 再 close，把元数据 size 更新成 4KB
```

这时可能出现：

- store 节点上的物理文件其实已经有 12KB 内容
- 但元数据层记录的文件大小却变成了 4KB
- 后续打开文件时，客户端按元数据 size 读，只能看到前 4KB，后面的真实数据等于“丢失可见性”

从现有代码路径看，这类风险是存在的。

**所以应该怎么理解 FalconFS 当前的并发写能力**

- 它对“元数据并发操作”做得比较强，尤其是目录、创建、删除、rename 这类
- 但对“同一普通文件被多个客户端并发写内容”这一点，当前开源实现更像是：
  - 支持并发访问
  - 但不提供强多写者一致性保证
  - 需要上层应用自己序列化写入，或者通过单写者模型避免冲突

**一句话结论**

- 不接 OBS 时，文件内容数据存放在被分配到的 `falcon_store`/store 节点本地 `DRAM + SSD` 层，最终持久位置是该节点 `falcon_cache_root` 下的本地文件，而不是元数据节点，也不是云对象存储 `docs/design.md:35` `config/config.json:6`
- 多客户端并发写同一个文件时，当前实现没有看到全局内容写锁、`flock/fcntl` 也没接，存在覆盖写、append 竞态、close 时文件大小回退、元数据与物理文件不一致等问题；实务上应把它视为“不支持安全的多写者并发更新同一文件”

如果你愿意，我下一步可以继续帮你做两件事里的任意一个：
1. 结合代码把“一个文件从 `open -> write -> flush -> close` 的完整数据路径”画成流程图
2. 进一步分析“如果要支持安全多客户端并发写，FalconFS 现在最少还缺哪些机制”

---

## User

2

---

## Assistant

---

## User

2

---

## Assistant

先补几处关键实现细节，确认 FalconFS 现在对“同一文件多写者”的边界，再给你一个最小可行的机制清单。

**Tool: grep**

**Tool: grep**

**Tool: grep**

---

## Assistant

我再确认一下 `close` 更新元数据时是不是“盲写 size”，以及元数据层现有锁是否能复用到文件内容并发控制上。

**Tool: read**

**Tool: read**

**Tool: read**

---

## Assistant

已经确认 `close` 请求只带 `path/size/mtime/nodeId`，元数据辅助函数也支持“直接覆写 `st_size`”。我再看一下 `CLOSE` 处理里有没有版本比较或条件更新，这决定最小方案能不能只补元数据层。

**Tool: grep**

**Tool: grep**

**Tool: read**

---

## Assistant

我已经确认了 `close` 的 size 更新是“客户端带着自己看到的结果去回写”。再补一段 `CLOSE` 处理和目录路径锁的边界，然后给你一个分层方案：最小修补版、工程可用版、完整 POSIX 版。

**Tool: read**

**Tool: read**

**Tool: read**

---

## Assistant

如果要让 FalconFS 安全支持“多客户端并发写同一个文件”，现在最少还缺三层机制。按投入从小到大，我建议这样理解和分期。

**先说结论**

当前开源实现里，文件内容并发写的问题不只是“少了一个锁”这么简单，而是三件事同时缺失：

1. `元数据 close 更新没有并发保护`
2. `数据面写入没有全局单写者/写范围协调`
3. `FUSE/POSIX 锁接口没接进来`

所以如果目标是“先把最危险的数据错乱堵住”，最小方案是先补元数据层和单写者控制；如果目标是“接近 POSIX 多进程/多机语义”，就还要补锁协议和租约恢复。

**我确认到的几个关键事实**

- `close` 时客户端只把 `path/size/mtime/nodeId` 传回元数据层，没有把“我是在什么版本上写的”带回去 `falcon_client/src/connection.cpp:322`
- 元数据层 `FalconCloseHandle` 最终会把客户端上报的 `st_size` 直接传给 `SearchAndUpdateInodeTableInfo(...)` 去更新 inode 行 `falcon/metadb/meta_handle.c:1033` `falcon/metadb/meta_handle.c:1117`
- `SearchAndUpdateInodeTableInfo(...)` 的确支持维护 `update_version` 字段，但 `CLOSE` 路径现在没有把“旧版本”带进来做条件检查，看起来只是普通更新 `falcon/metadb/meta_handle_helper.c:122` `falcon/metadb/meta_handle_helper.c:128`
- 路径锁现在只覆盖目录项/路径级别冲突，不是文件内容写串行化；它保护的是 `parentId + name` 这种目录查找项 `falcon/dir_path_shmem/dir_path_hash.c:397`
- FUSE 层没有实现 `.lock` 和 `.flock`，所以应用层如果依赖 `fcntl/flock` 做协调，当前实现是落空的 `falcon_client/fuse_main.cpp:398` `falcon_client/fuse_main.cpp:409`

基于这些事实，我会把方案分成 3 档。

**方案一：最小修补版**

目标：先消灭最危险的“文件大小回退、最后 close 覆盖元数据”的问题，并明确系统只支持单写者。

这版要做的最少机制：

1. `open-for-write` 时拿文件级独占写租约
2. `close` 时做版本校验或条件更新
3. 明确拒绝第二个写者，而不是让两个写者都成功

**怎么做**

- 在元数据层增加“文件写租约”字段，例如：
  - `writer_client_id`
  - `writer_session_id`
  - `writer_lease_expire_at`
  - 或者最简单先只做 `is_write_open / owner`
- `FalconOpen`/`FalconCreate` 遇到写模式时：
  - 如果没有当前写租约，原子地获取
  - 如果已有别的客户端持有，就返回 `-EBUSY` / `-EAGAIN`
- `FalconClose` 时：
  - 只有持有该租约的客户端才能提交 size/nodeId/mtime
  - 同时释放写租约
- `CLOSE` 更新 inode 时增加条件：
  - `where inode = ? and update_version = open_seen_version`
  - 或者更弱一点：`st_size = max(old_size, client_size)`，至少不让 size 回退

**优点**

- 改动面最小
- 能立刻阻止“两个客户端同时写一个文件导致元数据错乱”
- 实现复杂度比完整分布式锁小很多

**缺点**

- 这不支持真正的多写者
- append、非重叠区并发写、共享写句柄这些都仍然不支持
- 更像“单写者，多读者”

**这是我最推荐的第一步。**

因为 FalconFS 现在最致命的问题其实不是“性能”，而是“并发写会不会把文件状态写坏”。先把这一点封住，收益最大。

**方案二：工程可用版**

目标：支持“单文件单写者”但做到更稳，处理客户端崩溃、网络闪断、租约泄漏。

在方案一基础上，再补：

1. `租约续期`
2. `租约超时回收`
3. `写者 fencing token`
4. `store 节点拒绝过期写者`

**关键点**

- 只在元数据层加锁还不够，因为旧写者可能还握着旧 `physicalFd`，继续向 store 节点写
- 所以需要一个单调递增的 `fencing token`
  - 每次成功获取写租约，token++
  - token 下发给客户端
  - 客户端之后所有 `WriteFile/CloseFile/TruncateFile` RPC 都带这个 token
  - store 节点只接受“当前最新 token”的写请求
- 这样即使旧客户端没有及时停掉，新的写者拿到更高 token 后，旧写者的 RPC 也会被 store 拒绝

**为什么这层很重要**

如果只做“元数据单写者”，但 store 侧不验 token，可能出现：

- A 拿到写权并打开文件
- A 卡顿
- A 租约超时
- B 拿到新写权开始写
- A 恢复后继续往本地/远端 store 写

这时即使元数据上只有 B 是合法写者，数据面也可能被 A 污染。  
所以工程上，`fencing token` 基本是必须的。

**方案三：完整 POSIX 倾向版**

目标：允许多个客户端同时打开同一个文件，并通过显式锁实现可控并发。

这就不再是“单写者模型”，而是要补一整套分布式文件锁能力：

1. 实现 FUSE `.lock` / `.flock`
2. 元数据层维护 inode 级或 byte-range 锁表
3. 支持：
   - 共享锁/独占锁
   - 阻塞/非阻塞获取
   - 锁拥有者与 fd 语义
4. 客户端断开、进程退出、节点故障后的锁清理
5. 与 truncate/rename/unlink 的冲突规则

**这版的工程量最大**

因为它不仅要做“能上锁”，还要定义很多语义：

- `rename` 一个被锁文件怎么办
- `unlink` 后仍打开的文件如何处理
- `close(fd1)` 是否释放这个进程在该 inode 上的某些锁
- 同一客户端多 fd 重入如何算
- `fcntl` byte-range lock 和 `flock` 全文件锁如何共存

这已经接近做一个真正的分布式 POSIX 锁管理器了。  
如果你们当前重点是 AI workload、高吞吐训练数据，不一定值得第一阶段就上这套。

**我建议的实际路线**

如果让我给一个务实的演进路线，我会选：

1. `先做方案一`
   - 明确 FalconFS 当前只支持单写者
   - 任何第二个写者直接失败
   - `close` 改成条件更新，避免 size 回退
2. `再补方案二`
   - 增加租约续期和 fencing token
   - 让 store 节点也能拒绝旧写者
3. `最后视业务需求决定是否做方案三`
   - 只有当你们真的需要标准 `fcntl/flock` 生态兼容时再做

**最少缺哪些具体机制**

如果你要的是一个“最少缺失项清单”，我会列这 6 个：

1. `写打开仲裁`
   - 写模式 `open/create/truncate` 必须经过元数据层抢占独占写权
2. `open 版本号`
   - `open` 返回当前 `update_version`
3. `条件 close`
   - `close` 只能在预期版本上提交，不能盲写 size
4. `size 单调性保护`
   - 至少保证 `st_size` 不回退
5. `fencing token`
   - 所有写 RPC 带 token，store 只认最新 token
6. `故障回收`
   - 心跳/租约过期后释放写权，并使旧 token 失效

**如果只修一个点，优先修哪个**

优先修 `close` 的条件更新和单写者仲裁。

因为当前最容易造成“静默数据损坏”的路径是：

- 多个客户端都能写
- 最后谁 close 谁改元数据
- 没有版本校验

这是最先该堵上的洞。

**一个推荐的最小语义定义**

为了降低实现复杂度，可以先明确规定：

- 同一文件允许多个只读打开
- 同一时刻只允许一个写打开
- 写打开包括：
  - `O_WRONLY`
  - `O_RDWR`
  - `truncate`
  - `create` 后写
- 其他客户端如果也想写，返回 `-EBUSY`
- 不承诺多写者并发覆盖/append 正确性
- `fcntl/flock` 暂不支持，或明确返回 `-EOPNOTSUPP`

这个语义很保守，但对当前架构最匹配。

**给你的执行计划**

如果后面你想让我继续到“设计落地”的程度，我建议下一步分这 3 步展开：

1. 定义最小语义
   - 选“单写者模型”还是“显式锁模型”
2. 做接口设计
   - `open/close/write/truncate` 需要新增哪些字段
   - 是否引入 `lease_id` / `fencing_token` / `open_version`
3. 做代码落点拆解
   - 元数据层改哪些文件
   - client/store/brpc RPC 各改哪些结构和校验点

如果你愿意，我下一条可以直接给你一份“按代码文件拆开的实施设计”，例如分别改 `falcon_client`、`falcon_store`、`falcon/metadb` 哪些点。

---

## User

好的请继续

---

## Assistant

我先把实现落点补全到“文件级实施设计”粒度，重点确认元数据协议、inode 版本字段、以及 store RPC 里哪些地方需要带写租约/栅栏令牌。

**Tool: grep**

**Tool: glob**

**Tool: grep**

---

## Assistant

**Tool: read**

**Tool: grep**

**Tool: grep**

**Tool: grep**

---

## Assistant

**Tool: read**

**Tool: read**

**Tool: read**

---

## Assistant

我已经拿到了协议结构和返回结构。接下来再核一下 create/open 端是否天然适合返回 `update_version`，以及 store 端是否已经有现成字段可挂 `fencing token`。

**Tool: grep**

**Tool: grep**

**Tool: read**

**Tool: read**

---

## Assistant

我补一下 FlatBuffers 侧的落点，确认协议字段应该改生成头还是上游 schema 文件，然后给你一份可直接执行的分阶段实施计划。

**Tool: grep**

**Tool: read**

**Tool: read**

---

## Assistant

可以，下面我把方案收敛成一份“可实施设计”，按代码模块拆开，并明确推荐顺序、协议变更点、风险点和验收方式。

我建议目标先定为：

- `第一阶段`: 把 FalconFS 变成“单文件单写者，多个读者”
- `第二阶段`: 把单写者做成可靠的租约 + fencing 方案
- `第三阶段`: 视需求再做完整 `fcntl/flock` 分布式锁

这是最符合当前代码结构的路线。

**为什么建议从单写者开始**

因为现有代码已经天然是“每个 open 一个 `OpenInstance`，每个 writer 本地维护自己的 size/状态”，它没有为多写者协作准备共享状态中心：

- `OpenInstance` 是每个 fd 私有的 `common/src/include/buffer/open_instance.h:14`
- `close` 是客户端把自己的 `size/nodeId` 回写元数据 `falcon_client/src/connection.cpp:322`
- 元数据 `close` 处理当前会直接按请求里的 `st_size` 更新 inode `falcon/metadb/meta_handle.c:1117`

所以最小正确改法不是去“让多个写者同时正确协作”，而是先禁止它们并发成功。

**总体设计**

我建议引入两类机制：

1. `元数据层写租约`
2. `数据层 fencing token`

两者分工：

- 写租约：决定“谁有资格写”
- fencing token：决定“旧写者即使还活着，也不能再写成功”

只做 1 不够稳，只做 2 不够完整，最好都做，但可以分阶段。

---

**第一阶段设计：单写者 + 条件 close**

目标：先解决最危险的“多写者静默写坏文件”。

**语义定义**

- 允许多个 `O_RDONLY` 打开
- 同一文件同一时刻只允许一个写打开
- 写打开包括：
  - `O_WRONLY`
  - `O_RDWR`
  - `create` 后随后的写
  - `truncate`
- 第二个写者返回 `EBUSY` 或等价错误
- 暂不支持依赖 `fcntl/flock` 的用户锁语义

**元数据层需要新增的字段**

当前 inode 表已有：

- `update_version`
- `primary_nodeid`
- `backup_nodeid`

见 `falcon/metadb/inode_table.c:21`

建议新增：

- `write_lease_owner bigint`
- `write_lease_expire timestamptz`
- `write_fence_token bigint`

如果想更保守，第一阶段甚至可以只加：

- `write_lease_owner bigint`
- `write_fence_token bigint`

但我建议直接带上过期时间，不然客户端崩溃后的回收不好做。

**对应代码落点**

- inode 表定义：`falcon/metadb/inode_table.c`
- inode 表字段常量：`falcon/include/metadb/inode_table.h`
- inode 查询更新帮助函数：`falcon/metadb/meta_handle_helper.c`

**元数据请求协议要补哪些字段**

现在 `CloseParam` 只有：

- `path`
- `st_size`
- `st_mtim`
- `node_id`

见：
- `falcon/include/hcom_comm_adapter/falcon_meta_service_interface.h:180`
- `falcon/connection_pool/fbs/falcon_meta_param_generated.h:534`

建议扩展：

- `open_version`
- `write_fence_token`
- `is_write_close` 或者直接由 open flags 在客户端本地判断，不必下发
- 可选：`lease_owner`

更重要的是 `OpenResponse/CreateResponse` 需要带回：

- `update_version`
- `write_fence_token`
- 是否成功获取写租约

当前 `OpenResponse/CreateResponse` 还不含这些字段：
- `falcon/include/hcom_comm_adapter/falcon_meta_service_interface.h:468`
- `falcon/include/hcom_comm_adapter/falcon_meta_service_interface.h:493`

**第一阶段的请求流程**

1. `FalconOpen/FalconCreate`
- 读打开：照旧
- 写打开：
  - 元数据检查该 inode 当前是否已有有效写租约
  - 没有则分配
    - `write_lease_owner = client/session`
    - `write_fence_token = write_fence_token + 1`
  - 返回给客户端：
    - `inodeId`
    - `size`
    - `nodeId`
    - `update_version`
    - `write_fence_token`

2. `FalconWrite`
- 客户端仅在本地 `OpenInstance` 中保存 `write_fence_token`
- 第一阶段可以先不把 token 传到 store，只用于 `close` 校验
- 这时语义已经是“单写者”，理论上第二个写者拿不到 open

3. `FalconClose`
- 客户端把：
  - `path`
  - `st_size`
  - `node_id`
  - `open_version`
  - `write_fence_token`
  发送到元数据
- 元数据执行条件更新：
  - 该 inode 仍由这个 writer 持有租约
  - `write_fence_token` 匹配
  - `update_version` 与 open 时看到的版本符合预期，或者允许 `>=` 某条件但必须避免回退

**close 的最小正确更新策略**

这里有两种选择。

**方案 A：严格版本匹配**
- 条件：`update_version == open_version`
- 成功后：
  - `st_size = client_size`
  - `update_version = update_version + 1`
  - 释放写租约

优点：
- 最干净
- 很容易发现并发冲突

缺点：
- 如果中途有别的元数据更新也 bump version，close 可能失败，需要更细分版本策略

**方案 B：单独引入内容版本**
- 把 `update_version` 留给通用 inode 变更
- 新增 `content_version`
- 写 open 返回 `content_version`
- close 只检查 `content_version`
- close 成功时更新：
  - `st_size`
  - `content_version++`

我更推荐 `方案 B`。  
因为 `update_version` 将来可能被 chmod/chown/utimens/rename 类操作一起消费，语义容易混乱。

**如果不想加 `content_version`，至少要做的兜底**

即使先不做严格版本，也至少要防止 `st_size` 回退：

- 更新 size 时使用 `max(old_size, client_size)`

但这只能防止“文件变小”，不能防止“重叠覆盖写”或“写到错误 epoch”。  
所以它只能当临时止血，不应作为最终方案。

---

**第二阶段设计：租约续期 + fencing token 下沉到 store**

目标：解决“旧写者失去写权后还继续往 store 写”的问题。

这是工程上必须补的一层。

**为什么要下沉到 store**

当前远程 store 写 RPC 只带：

- `physical_fd`
- `offset`

见 `remote_connection_def/proto/brpc_io.proto:74`

远程 open 返回也只带：

- `physical_fd`

见 `remote_connection_def/proto/brpc_io.proto:47`

所以 store 现在并不知道“这个 writer 是否仍然合法”。

**要改的 store 协议**

`brpc_io.proto` 需要为这些请求补 `fence_token`：

- `OpenRequest`
- `OpenReply`
- `WriteRequest`
- `CloseRequest`
- `TruncateOpenInstanceRequest`
- `TruncateFileRequest`

推荐最小字段：

- `OpenRequest`
  - `fence_token`
- `OpenReply`
  - 可不回，如果客户端 already knows
- `WriteRequest`
  - `fence_token`
- `CloseRequest`
  - `fence_token`
- `Truncate*Request`
  - `fence_token`

代码落点：

- 协议定义：`remote_connection_def/proto/brpc_io.proto`
- client stub：`falcon_store/src/connection/falcon_io_client.h/.cpp`
- server side：`falcon_store/src/brpc/brpc_main.cpp`

**OpenInstance 需要增加的字段**

当前 `OpenInstance` 里没有版本或 token 字段 `common/src/include/buffer/open_instance.h:14`

建议新增：

- `uint64_t content_version` 或 `open_version`
- `uint64_t fence_token`
- `bool is_write_owner`

这样 client 和 store 端 open 实例都能带着同一份上下文走完全流程。

**store 端怎么验 token**

在 store 端维护一个按 inode 或 physical fd 绑定的“当前合法 token”：

- `OpenFile` 时记录 `inodeId -> fence_token`
- `WriteFile/CloseFile/Truncate*` 时校验：
  - 请求 token 必须等于当前 token
- 如果 token 过期：
  - 返回 `-ESTALE` 或 `-EIO`/自定义错误

建议按 `inodeId` 校验，而不是只按 `physicalFd`。  
因为 `physicalFd` 只是本地打开句柄，不能表达“新老写者世代”。

**租约续期机制**

第一阶段如果不做续期，写者崩溃后锁可能长期卡住。  
第二阶段需要：

- client 周期性向元数据续租
- 元数据维护 `write_lease_expire`
- 超时后允许新的 writer 抢租约，并 bump `fence_token`

续租可以是：

- 独立 `RENEW_LEASE` RPC
- 或 piggyback 在写/flush/fsync 上

我更建议独立 RPC，逻辑更清楚。

---

**第三阶段设计：完整锁语义**

目标：兼容更多 POSIX 上层应用，而不只是“FalconFS 自己规定单写者”。

这阶段才需要做：

- FUSE `.lock`
- FUSE `.flock`
- 元数据侧 inode lock / byte-range lock manager
- 锁 owner 和 fd/session 绑定
- 崩溃恢复
- 与 truncate/unlink/rename 交互

当前 FUSE 这里是空的：

- `.lock = nullptr`
- `.flock = nullptr`

见 `falcon_client/fuse_main.cpp:398` `falcon_client/fuse_main.cpp:409`

这阶段工程量很大，不建议作为第一步。

---

**按文件拆开的实施计划**

下面是我建议的具体改造清单。

**A. 元数据协议层**

1. `falcon/include/hcom_comm_adapter/falcon_meta_service_interface.h`
- 扩展 `CloseParam`
  - `open_version`
  - `fence_token`
- 扩展 `CreateResponse`
  - `content_version/open_version`
  - `fence_token`
- 扩展 `OpenResponse`
  - `content_version/open_version`
  - `fence_token`

2. FlatBuffers schema / 生成代码
- 需要修改 schema 源，而不是直接改 generated header
- 当前仓库里暴露的是生成产物 `falcon/connection_pool/fbs/falcon_meta_param_generated.h`
- 构建里有 `flatc` 生成链路 `cmake/Flatbuffers.cmake:1`
- 实施时要找到上游 `.fbs` 源文件并从源 regenerate

这里有一个待确认点：仓库里没直接搜到 schema 源文件，只看到了 generated header。  
执行前需要先确认 `.fbs` 真正位置，或者仓库是否把 schema 漏掉了。

**B. 元数据内部数据结构**

1. `falcon/include/metadb/meta_process_info.h`
- 增加字段：
  - `uint64_t open_version`
  - `uint64_t fence_token`
  - `uint64_t lease_owner`
  - 可选 `bool write_open`

2. `falcon/metadb/meta_serialize_interface_helper.cpp`
- 参数反序列化：读出新字段
- 响应序列化：把新字段写回 `CreateResponse/OpenResponse`

3. `falcon/metadb/inode_table.c`
- 增加表字段
  - 推荐 `content_version`
  - `write_lease_owner`
  - `write_lease_expire`
  - `write_fence_token`

4. `falcon/include/metadb/inode_table.h`
- 增加字段列号宏

5. `falcon/metadb/meta_handle_helper.c`
- 扩展 inode 查询/更新 helper
- 支持条件更新：
  - 比对 `content_version`
  - 比对 `write_fence_token`
  - 更新租约字段

6. `falcon/metadb/meta_handle.c`
- `FalconCreateHandle`
  - 写创建时分配租约与 token
- `FalconOpenHandle`
  - 写打开时尝试获取租约
- `FalconCloseHandle`
  - 做条件 close 与释放租约

**C. 客户端层**

1. `falcon_client/src/connection.cpp`
- `Open` / `Create` 解析响应里的新字段
- `Close` 发送新字段

2. `falcon_client/src/falcon_meta.cpp`
- `FalconCreate`
- `FalconOpen`
- `FalconClose`
- `FalconTruncate`
- 都要把 `open_version/fence_token` 放到 `OpenInstance`

3. `common/src/include/buffer/open_instance.h`
- 新增：
  - `uint64_t content_version`
  - `uint64_t fence_token`
  - `bool write_owner`

4. `common/src/buffer/dir_open_instance.cpp`
- attach/open instance 初始化这些字段

**D. store / BRPC 数据面**

1. `remote_connection_def/proto/brpc_io.proto`
- 为 open/write/close/truncate 增加 `fence_token`

2. `falcon_store/src/include/connection/falcon_io_client.h`
3. `falcon_store/src/connection/falcon_io_client.cpp`
- 各 RPC 带 token

4. `falcon_store/src/brpc/brpc_main.cpp`
- `OpenFile`
- `WriteFile`
- `CloseFile`
- `TruncateOpenInstance`
- `TruncateFile`
- 校验 token

5. `common/src/write_stream/stream_assembler.cpp`
- 远程 `client->WriteFile(...)`
- `client->CloseFile(...)`
- 要把 token 传下去

6. `falcon_store` 内部需增加 token 校验状态
- 可以挂在 `OpenInstance`
- 也可以加全局 `inode -> latest_fence_token`

我推荐双层：
- `OpenInstance` 保存自己打开时的 token
- store 全局再维护 inode 当前最新 token，写入时对比

---

**推荐的分阶段交付**

**阶段 1A：止血版**
- 不做 fencing token 下沉
- 做：
  - 写 open 互斥
  - close 条件更新
  - size 不回退
- 用于快速阻止静默元数据损坏

**阶段 1B：可用版**
- 在 1A 基础上补：
  - token 下沉到 store
  - truncate 也带 token
- 这是我认为最值得上线的一版

**阶段 2：可靠版**
- 补续租、超时、重连恢复
- 增加 lease reclaim 逻辑

**阶段 3：完整版**
- 锁 API 兼容
- byte-range locks
- flock/fcntl

---

**测试计划**

这块必须提前设计，不然很容易“看起来逻辑对了”，但仍有写坏角落。

**阶段 1 至少要有的测试**

1. `两个客户端并发写打开同一文件`
- 预期：只有一个成功，另一个失败

2. `两个客户端先后写同一文件`
- A close 后 B 才能 open-for-write 成功

3. `读者并发存在`
- A 写打开时，B 只读打开仍可成功

4. `close size 不回退`
- 构造旧 writer 后 close 的情况，确保元数据不被较小 size 覆盖

5. `truncate 与 open-for-write 冲突`
- 预期：按单写者模型互斥

**阶段 1B 增加的测试**

1. `旧 writer 失权后继续 write`
- store 必须拒绝

2. `旧 writer 失权后继续 truncate`
- store 必须拒绝

3. `token bump 后 close`
- 旧 token close 不得覆盖新状态

**阶段 2 增加的测试**

1. `writer 崩溃不 close`
- 租约过期后新 writer 可接管

2. `网络闪断后恢复`
- 老 writer 不得复活成合法写者

---

**风险与注意事项**

1. `schema 生成链要先确认`
- 当前仓库里看到 generated FlatBuffers header，但没直接看到 schema 源
- 实施前要先查清生成来源，否则协议改不干净

2. `update_version` 最好别直接复用为内容版本`
- 它已经是 inode 通用字段
- 后续 chmod/chown/utimens 可能污染语义
- 建议新增 `content_version`

3. `rename/unlink 与写租约`
- 第一阶段建议保守处理：
  - 正在被写租约持有的文件，不允许 rename/unlink
  - 或至少要定义清楚行为
- 否则路径变了但 writer 还按旧 path close，会很乱

4. `O_APPEND` 不要假装支持强语义`
- 在没有全局 append 序列化前，不应承诺并发 append 正确
- 单写者模型下自然规避了这问题

---

**我最推荐的最终方案**

如果让我替你们定一个现实可落地版本，我会选：

1. 新增 `content_version`
2. 新增 `write_fence_token`
3. 新增 `write_lease_owner/write_lease_expire`
4. 写 open 独占租约
5. close 按 `content_version + fence_token` 条件提交
6. store RPC 全链路带 `fence_token`
7. 暂不实现 `flock/fcntl`

这样既能把最危险的问题堵上，也不会把工程一下拉进完整分布式 POSIX 锁的深坑。

**两个还需要你拍板的设计点**

1. `第一阶段是否接受“写打开冲突直接失败”`
- 我的建议：接受，这是最稳的
- 替代方案是阻塞等待，但实现复杂且对 lease/recovery 要求更高

2. `内容版本是复用 update_version，还是新增 content_version`
- 我的建议：新增 `content_version`
- 这样语义更清晰，后续更不容易踩坑

你如果确认这两个点，我下一步可以继续给你一份更细的“实施顺序 checklist”，精确到“先改哪几个结构体，再改哪几个 RPC，再改哪几个 handler”。

---

