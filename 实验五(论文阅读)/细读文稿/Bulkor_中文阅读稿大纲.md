# Bulkor: Enabling Bulk Loading for Path ORAM 中文阅读稿大纲

## 0. 论文基本信息

- 论文题目：Bulkor: Enabling Bulk Loading for Path ORAM
- 作者：Xiang Li, Yunqian Luo, Mingyu Gao
- 会议：IEEE Symposium on Security and Privacy, 2024
- 研究方向：数据安全、隐私保护、ORAM、TEE、安全系统
- 一句话概括：本文研究如何在不泄露访问模式的前提下，高效地把大量已有数据批量构造成 Path ORAM 结构。

## 1. 引言与动机

### 1.1 数据内容加密之外的访问模式泄漏

传统加密和认证技术可以保护数据内容的机密性和完整性，但不能自动隐藏访问模式。攻击者即使看不到明文，也可能通过观察访问了哪些地址、访问顺序和访问频率，推断用户隐私或查询语义。

ORAM 是解决访问模式泄漏的通用密码学机制。它让服务器观察到的访问轨迹与真实访问目标尽量无关，从而隐藏用户到底访问了哪个数据块。

### 1.2 为什么需要 bulk loading

Path ORAM 的正常访问过程已经比较成熟，但现实系统经常遇到另一类问题：已有一大批普通数据，需要一次性构造成 ORAM 树、stash 和 position map。

如果逐条执行 ORAM write 操作来插入 N 个数据块，在 TEE 和 doubly-oblivious 要求下，成本会达到 O(N log^3 N)，初始化阶段可能成为系统瓶颈。

### 1.3 论文给出的三个应用场景

1. 安全查询处理和 oblivious algorithms：某些隐私保护算法会在中间结果上临时构建 ORAM，初始化不能只当作离线预处理。
2. 数据恢复：TEE 或 trusted proxy 崩溃后，需要重建 ORAM 结构。bulk loading 越快，系统不可用时间越短。
3. 云存储布局转换：平时用普通加密布局节省空间，需要隐私访问时再转换为 ORAM 布局，要求转换足够快。

## 2. 背景知识

### 2.1 Path ORAM

Path ORAM 把服务器端存储组织为一棵二叉树。每个数据块被随机分配一个 leaf label，并且必须满足主不变量：数据块要么在 stash 中，要么位于自己 leaf label 对应的根到叶路径上。

一次访问大致包括：查 position map、读取整条路径、在本地找到目标块、重新随机分配 leaf label、把路径重新写回服务器。

### 2.2 position map 与 stash

position map 记录逻辑地址到 leaf label 的映射。stash 是本地临时缓冲区，用于保存暂时无法放回 ORAM 树的块。

由于 position map 可能很大，Path ORAM 通常使用递归 position map：把 position map 本身也作为数据存入更小的 ORAM 中，直到顶层 position map 能放入 controller storage。

### 2.3 TEE 与 doubly-oblivious

TEE 例如 Intel SGX，可以在不可信服务器上提供受保护的 enclave。ORAM controller 可以放进 enclave，从而减少客户端与服务器之间的网络通信。

但是 TEE 不能完全解决访问模式泄漏，因为攻击者可能通过侧信道观察 enclave 内部访问内存的模式。因此本文要求 doubly-oblivious：外部服务器存储访问模式和 enclave 内部访问模式都不能泄漏敏感信息。

## 3. 问题定义与威胁模型

### 3.1 bulk loading 的输入输出

输入包括数据块数组 B、逻辑地址数组 A、ORAM 参数 N、桶容量 Z、stash 容量 Cs、position map 容量 Cp。

输出是一个合法的 Path ORAM 结构 R = (T, S, position)，其中 T 是 ORAM 树，S 是 stash，position 是顶层 position map。

### 3.2 安全目标

bulk loading 过程本身不能泄露输入数据和逻辑地址相关信息。构建完成后的 ORAM，也必须和通过标准逐条插入得到的 ORAM 一样安全。

更直观地说，攻击者即使观察 bulk loading 过程和后续 ORAM 访问轨迹，也不能区分不同输入数据或不同访问序列。

### 3.3 威胁模型

服务器不可信，攻击者可以观察内存、磁盘、网络中的密文数据及其地址访问模式，也可能回滚或篡改数据。处理器硬件和 enclave 内被验证的代码被认为可信，但 enclave 内部访问模式仍然可能通过侧信道泄漏。

本文不考虑拒绝服务攻击，也不重点处理电磁、热、功耗等物理侧信道。

## 4. 设计目标与错误直觉

### 4.1 性能目标

朴素方案是对 N 个块逐个执行 Path ORAM 写入。由于递归 ORAM、路径访问和 TEE 内部 oblivious scan 等因素，总成本约为 O(N log^3 N)。

本文希望降低复杂度，同时不增加 trusted controller storage，仍保持 O(log^2 N) * omega(1) 级别的控制器空间。

### 4.2 安全目标

性能优化不能牺牲 ORAM 的安全分布。bulk loaded ORAM 应该等价于通过标准安全方式逐条插入得到的 ORAM。

### 4.3 简单随机 shuffle 为什么不安全

一个看似自然的方案是：把所有数据随机打乱，直接当成 ORAM tree，再根据物理位置反推出 leaf label。

这个方案的问题是：物理地址来自一个排列，不同块的物理位置并非完全独立。由位置反推出的 leaf label 也会产生相关性，破坏 Path ORAM 所需的独立随机分布。

论文用两个访问序列说明这种差异：访问 block 0 再访问 block 1，与访问 block 0 再访问 block 0。安全 ORAM 中两者轨迹应不可区分，但简单 shuffle 会导致两次路径相同的概率不同，因此不满足安全定义。

## 5. Bulkor 方法总览

### 5.1 核心思想

Bulkor 的关键思路是：先为每个数据块独立随机分配 leaf label，保证 Path ORAM 所需的安全随机性；然后在不改变 leaf label 的前提下，obliviously 调整每个块放入的 bucket，解决桶溢出问题。

这与简单 shuffle 的区别是：Bulkor 先保证安全分布，再解决布局；简单 shuffle 是先决定布局，再反推标签。

### 5.2 主流程

1. AssignLeaf：为每个真实数据块独立随机分配 leaf label，并初始化元数据。
2. BuildPosMap：根据逻辑地址到 leaf label 的映射构建 position map；如果太大，则递归构建。
3. OSort：按临时 bucket ID 对元数据进行 oblivious sort。
4. OAdjustBucketID：在不改变 leaf label 的前提下，将溢出的块沿路径向父节点移动。
5. OAssignPhyAddr：为最终 bucket 中的块分配物理地址。
6. OPlace：以 oblivious 的方式把块放到目标物理位置。
7. OAssignPhyAddrDummy：为空位填充 dummy blocks。
8. 根据元数据放置真实数据，输出 ORAM tree、stash 和 position map。

### 5.3 为什么主要操作元数据

真实数据块可能很大，频繁移动代价高。Bulkor 在大部分布局调整阶段只操作较小的 metadata，等物理位置确定之后再移动真实数据，从而提升实际性能。

## 6. 关键算法细节

### 6.1 BuildPosMap

BuildPosMap 将每个逻辑地址对应的 leaf label 作为 position map 的数据。如果 position map 超过 controller storage 容量，就递归调用 BulkLoad，把 position map 本身构造成下一层 ORAM。

这个结构类似操作系统中的多级页表：顶层 position map 较小，可以留在 enclave 中；下面几层通过 ORAM 树存储。

### 6.2 Oblivious Sort 的选择

Bulkor 频繁使用 oblivious sort。论文讨论了 bitonic sort 和 bucket oblivious sort。

bucket oblivious sort 的渐进复杂度更好，可以让总体复杂度达到 O(N log N)，但为了保证很低的溢出概率，常数因子较大。实际实现中，作者选择了更常用、更适合 TEE doubly-oblivious 场景的 bitonic sort，因此总体复杂度为 O(N log^2 N)。

### 6.3 OAdjustBucketID

初始时每个块被放到自己随机 leaf label 对应的叶桶中，但某些桶可能超过容量 Z。OAdjustBucketID 的任务是把溢出的块沿着自己的路径向父节点移动，直到找到有空位的 bucket；如果整条路径都没有空位，则放入 stash。

安全性关键在于：算法不能根据真实溢出情况产生数据相关的访问模式。因此它使用固定循环范围、occupancy counters 和条件移动 cmov，让控制流和内存访问模式不依赖敏感数据。

复杂度为 O(N log N)，控制器空间为 O(log N)。

### 6.4 OPlace

OPlace 解决的是“有空洞的物理布局”问题。即使已经知道每个真实块的目标物理地址，直接排序仍不能完成最终布局，因为中间还需要插入 dummy blocks。

OPlace 借鉴 bitonic sort 的思想，在输入已经按 key 排序的情况下，通过固定模式的交换，把有效块放到正确位置，同时保持 oblivious。

复杂度为 O(N log N)，控制器空间为 O(1)。

## 7. 与 TEE 的结合

Bulkor 的完整 bulk loading 流程运行在 enclave 中。输入数据和地址数组被加载进 enclave 并解密，输出 ORAM tree 加密后存储在 enclave 外部，stash 和顶层 position map 以明文形式保留在 enclave 内。

如果 enclave 内存不足，中间数据需要加密存到外部，并按 chunk 批量加载和处理。论文还考虑完整性和 freshness：chunk 可以附加 MAC，中间结果用 fresh nonce 防止 replay attack，最终 ORAM tree 用 Merkle tree 保护。

## 8. 安全性分析

论文的核心安全结论是：由 Bulkor 构建出的 doubly-oblivious Path ORAM 满足 bulk loading 的 oblivious 安全定义。

直观理由包括：

- bulk loading 中循环边界和分支条件由公开参数决定。
- 依赖敏感数据的条件操作用 oblivious primitives 实现，例如 cmov。
- 内存读写地址序列由公开参数决定，而不是由输入数据决定。
- 后续正常 ORAM 访问依赖已有 doubly-oblivious Path ORAM 实现，例如 ZeroTrace。

## 9. 实现

作者使用 Intel SGX 和 Rust 实现 Bulkor。实现约 7900 行代码，其中约 5400 行 enclave code 属于 TCB。

关键工程点包括：

- 使用 Rust SGX SDK。
- 使用 x86 CMOV/CMOVZ 实现基础 oblivious 操作。
- 使用 AES-NI 加速加密和解密。
- 使用 SGX 随机数生成器进行 leaf assignment 和 nonce generation。
- 采用三层存储结构：enclave trusted memory、untrusted server memory、disk。
- 对 oblivious sort 和 placement 做多线程并行，因为二者占总执行时间超过 95%。

## 10. 实验评估

### 10.1 实验设置

实验平台使用 Intel Xeon Gold 5317，支持 64 GB SGX EPC，外部存储为单块 HDD。

对比对象包括：

- C++ ZeroTrace：逐条插入 baseline。
- Rust ZeroTrace：作者重实现的逐条插入 baseline。
- Oblix：已有 bulk loading 相关方案，作者用 Rust 重实现。
- Bulkor：本文方案，测试单线程和 16 线程。

### 10.2 总体性能结果

磁盘、1 kB block、in-memory ratio 为 1/16 时，单线程 Bulkor 相比 Rust ZeroTrace 加速 22.8x 到 34.2x，相比 Oblix 加速 15.5x 到 21.9x。

16 线程 Bulkor 相比 Rust ZeroTrace 加速 139.1x 到 160.6x，相比 16 线程 Oblix 加速 8.7x 到 10.1x。

内存场景中，Bulkor 仍然明显快于 ZeroTrace 和 Oblix，但相对磁盘场景优势略小，因为内存随机访问代价低于磁盘。

### 10.3 应用案例

论文评估了三个应用场景：

1. Oblivious algorithms：在 oblivious join 中，Bulkor 将端到端延迟降低约 42.8% 到 47.9%。
2. Oblivious search：Bulkor 显著降低“先建 ORAM 再二分搜索”相对“线性扫描”的查询数量分界点。
3. Oblivious BFS：Bulkor 改善基于 ORAM 的 BFS 性能，使其在一些真实图数据上优于已有算法。

此外，论文还讨论了数据恢复和云存储转换。对于 20 GB 云存储数据转换，ZeroTrace 可能需要约 4 * 10^5 秒，而 Bulkor 可在一小时内完成，从而使空间节省方案变得可行。

## 11. 相关工作

相关工作主要包括三类：

1. Tree-based ORAM：Path ORAM、Ring ORAM 等，重点优化带宽和客户端存储。
2. TEE + ORAM：ZeroTrace 首先将 tree-based ORAM 与 Intel SGX 结合，Oblix 提出 doubly-oblivious 要求。
3. Oblivious data processing：Opaque、ObliDB 等系统使用 oblivious sort、oblivious query processing 等技术。

Bulkor 的位置是：从系统角度优化 ORAM 初始化和 bulk loading，补足已有 ORAM 系统中初始化阶段的性能短板。

## 12. 结论

Bulkor 是一个面向 Path ORAM 的高效 bulk loading 算法。它在 TEE 场景下支持 double obliviousness，将复杂度从朴素 doubly-oblivious 逐条插入的 O(N log^3 N) 降到 O(N log^2 N)，并通过 SGX 实现证明了显著的实际性能收益。

## 13. 初步思考

### 13.1 工作优点

- 选题具体但重要，关注 ORAM 初始化这一容易被忽视的性能瓶颈。
- 兼顾理论复杂度、安全定义和系统实现。
- 方法设计抓住了核心安全分布：先独立随机分配 leaf label，再 obliviously 调整物理放置。
- 实验覆盖磁盘、内存、不同块大小、多线程和应用案例，比较完整。

### 13.2 可能不足

- 论文主要基于 Intel SGX 实现，其他 TEE 平台上的实际表现仍需进一步验证。
- bitonic sort 虽然实用，但 O(N log^2 N) 对超大规模数据仍可能较重。
- 实验平台使用单块硬盘，未充分验证多盘或更现代存储设备下的 locality 优化。
- 系统假设不覆盖拒绝服务攻击和更多物理侧信道。
- Bulkor 优化的是初始化和重构阶段，正常访问阶段仍然依赖既有 Path ORAM 的开销。

### 13.3 未来想法

- 探索更适合 TEE 的低常数 oblivious sort 或 placement 算法。
- 研究面向 SSD/NVMe/分布式存储的 bulk loading 优化。
- 将 Bulkor 与安全数据库系统结合，评估复杂查询流水线中的整体收益。
- 研究动态场景：数据持续插入、删除、更新时，是否能增量维护 ORAM 而不是完整重建。
- 扩展到更多 ORAM 变体和更多 TEE 平台，验证通用性。

