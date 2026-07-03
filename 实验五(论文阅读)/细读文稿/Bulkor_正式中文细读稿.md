# Bulkor: Enabling Bulk Loading for Path ORAM 正式中文细读稿

## 论文基本信息

论文题目为 Bulkor: Enabling Bulk Loading for Path ORAM，作者为 Xiang Li、Yunqian Luo 和 Mingyu Gao，主要来自清华大学。根据论文正文和官方报告 slides，该论文发表于 IEEE Symposium on Security and Privacy 2024。论文属于数据安全与隐私保护方向，涉及 ORAM、Path ORAM、可信执行环境 TEE、安全数据库与访问模式保护等主题。

本文关注的问题可以概括为：如何在保证访问模式不泄漏的前提下，高效地把大量已有数据一次性构造成 Path ORAM 结构。已有 ORAM 研究通常更重视正常读写过程的开销，而本文把初始化和重构阶段单独拿出来研究，指出在安全数据库、云存储和 TEE 崩溃恢复等场景中，ORAM 的批量构建本身也可能成为关键性能瓶颈。

## 1. 引言：为什么 ORAM 的批量构建值得研究

现代数据安全系统通常会首先使用加密和认证机制来保护数据内容。例如，用户把数据外包到云服务器时，服务器只能看到密文，无法直接读取明文内容。然而，加密并不能隐藏所有信息。服务器仍然可以观察到用户访问了哪些地址、访问顺序如何、访问频率是否异常、某些数据是否被反复读取。这些信息统称为访问模式。

访问模式本身可能泄露敏感信息。例如，在医疗数据场景中，即使病历内容是加密的，攻击者也可能通过某类记录被频繁访问推测患者的疾病类型。在加密数据库中，即使查询条件和结果都是密文，服务器仍可能通过被访问的索引页和数据页推断查询范围。在云存储中，文件访问频率和访问时间也可能暴露用户行为。因此，数据安全不只是保护数据内容，还需要保护访问行为。

ORAM，即 Oblivious RAM，是隐藏访问模式的一类通用密码学技术。它的目标是让服务器观察到的访问轨迹与用户真实访问的数据目标无关。换句话说，服务器可以看到系统访问了某些位置，但不能据此判断用户真正想读写哪个数据块。Path ORAM 是其中一种经典而实用的方案，它将服务器端存储组织成一棵二叉树，每次访问一条根到叶路径，以此混淆真实访问目标。

不过，本文研究的重点不是 Path ORAM 的普通访问过程，而是另一个容易被忽视的问题：当系统已有大量普通布局的数据时，如何快速、安全地把这些数据构造成一个合法的 Path ORAM。这个过程就是 bulk loading，即批量加载或批量构建。

最直接的方法是对每个数据块执行一次标准 Path ORAM 写入操作，逐条把数据插入 ORAM 中。但在 TEE 场景和 doubly-oblivious 要求下，这种朴素方法的总成本会达到 O(N log^3 N)。当 N 很大时，初始化本身会占据大量时间，甚至让整个安全系统无法实际使用。

论文给出了三个典型应用场景。第一，某些 oblivious algorithms 会把 ORAM 作为内部组件，例如隐私保护查询处理、oblivious join、oblivious search 和图算法。如果中间结果也需要构造成 ORAM，那么 bulk loading 就处于在线执行路径中，不能简单视为离线预处理。第二，TEE 或 trusted proxy 可能崩溃，一旦 ORAM controller 中的状态丢失，系统需要重建 ORAM。重建越慢，服务不可用时间越长。第三，云存储系统可能希望平时用普通加密布局节省空间，只在需要隐私访问时转换为 ORAM 布局。此时布局转换必须足够快，否则空间节省没有实际意义。

因此，本文的核心动机是：ORAM 不仅要访问得安全，也要构建得安全而高效。Bulkor 正是针对 Path ORAM bulk loading 的系统性优化方案。

## 2. 背景知识：Path ORAM、TEE 与 doubly-oblivious

### 2.1 Path ORAM 的基本思想

Path ORAM 将服务器端存储组织为一棵二叉树。树中的每个节点称为一个 bucket，每个 bucket 可以容纳固定数量的数据块。每个真实数据块都有一个逻辑地址，同时会被随机分配一个 leaf label。这个 leaf label 决定了该数据块对应的根到叶路径。

Path ORAM 的核心不变量是：每个数据块要么保存在客户端或 controller 的 stash 中，要么保存在自己 leaf label 对应的根到叶路径上的某个 bucket 中。也就是说，数据块不一定放在叶节点，但必须位于自己那条路径上。

一次标准 Path ORAM 访问大致包括以下步骤。首先，controller 查询 position map，找到目标逻辑地址当前对应的 leaf label。然后，系统从服务器读取这条 leaf label 对应的整条路径，而不是只读取目标块所在位置。接着，controller 在读入的路径和 stash 中找到目标块，执行读或写。随后，该块会被重新随机分配一个新的 leaf label，并更新 position map。最后，系统尝试把 stash 和路径缓冲区中的块尽量放回树中，同时保持每个块仍在自己的合法路径上。

这个过程的安全直觉是：服务器看到的是一整条路径的访问，而不是单个数据块的位置；同时，数据块每次访问后都会重新随机分配路径，使得连续访问之间难以建立稳定关联。

### 2.2 position map 与 stash

Path ORAM 需要两个重要的 controller-side 数据结构。

position map 记录逻辑地址到 leaf label 的映射。例如，逻辑块 3 当前对应 leaf 0，逻辑块 7 当前对应 leaf 1。没有 position map，controller 就不知道访问某个逻辑地址时应该读取哪条路径。

stash 是一个临时缓冲区。由于每个 bucket 容量有限，有些块在路径写回时可能暂时无法放回树中，这些块就保存在 stash 中。Path ORAM 的理论分析会保证在合适参数下，stash 溢出的概率非常低。

position map 的问题是它本身可能很大。为了减少 controller storage，Path ORAM 通常使用递归 position map：把较大的 position map 也当作数据，存进下一层更小的 ORAM 中；下一层 ORAM 又有自己的 position map，如此递归，直到最顶层 position map 足够小，可以直接保存在 controller 中。这个结构有点类似操作系统中的多级页表。

### 2.3 TEE 的作用与限制

TEE，即 Trusted Execution Environment，例如 Intel SGX，可以在不可信服务器上创建一个受保护的 enclave。enclave 中的数据和代码受到硬件保护，外部软件无法直接读取或篡改。把 ORAM controller 放入服务器侧 TEE 中，可以显著减少客户端与服务器之间的网络通信，因为大量路径读取、写回、加解密和元数据操作都可以在服务器本地完成。

但是，TEE 并不是万能的。大量已有研究表明，TEE 可能遭受侧信道攻击，尤其是访问模式侧信道。即使 enclave 内部的数据值受到保护，攻击者仍可能观察 enclave 访问内存、磁盘或其他资源的地址模式。因此，如果 ORAM controller 在 enclave 内执行的代码根据敏感数据访问不同地址，也可能泄露信息。

这就引出了本文强调的 doubly-oblivious 要求。所谓 doubly-oblivious，是指两个层面的访问模式都要隐藏：第一，enclave 外部对服务器存储的访问模式不能泄露真实数据；第二，enclave 内部的内存访问模式也不能泄露敏感信息。换句话说，既要防外部服务器观察，也要防 TEE 内部侧信道观察。

## 3. 问题定义与威胁模型

本文研究的 bulk loading 问题可以表述为：给定一组数据块 B 和对应的逻辑地址 A，在给定 ORAM 参数 N、bucket 容量 Z、stash 容量 Cs 和 position map 容量 Cp 的情况下，构造出一个合法的 Path ORAM 结构 R = (T, S, position)。其中 T 是 ORAM 树，S 是 stash，position 是顶层 position map。

这个输出必须满足 Path ORAM 的一致性要求。每个输入数据块必须且只能出现一次，要么在 ORAM 树的某个合法 bucket 中，要么在 stash 中。position map 中记录的 leaf label 必须与数据块实际所在路径一致。stash 和 position map 的大小也不能超过设定容量，除非发生概率可忽略的失败事件。

从安全角度看，bulk loading 不只是生成一个结构正确的 ORAM，还必须保证生成过程本身不泄露敏感信息。攻击者观察 bulk loading 的过程和后续 ORAM 访问轨迹时，不能区分不同输入数据、不同逻辑地址排列或不同访问序列。直观地说，通过 bulk loading 构建出来的 ORAM，应该和通过标准安全逐条插入得到的 ORAM 一样安全。

论文的威胁模型假设服务器不可信，攻击者可以观察内存、磁盘、网络中的数据及其地址访问模式，也可能回滚或篡改数据。处理器硬件和 enclave 内经过 attestation 验证的代码被认为可信，但 enclave 内部访问模式仍可能泄漏。论文不重点考虑拒绝服务攻击，也不覆盖电磁、热、功耗等物理侧信道。

这个威胁模型的含义是：Bulkor 不只是一个更快的初始化算法，它必须是一个安全初始化算法。任何数据相关的分支、循环次数、内存访问位置都需要被处理成 oblivious 形式，否则就可能违背 doubly-oblivious 目标。

## 4. 设计目标与错误直觉

### 4.1 性能目标

最直接的 bulk loading 方法是逐条插入 N 个数据块。每次 Path ORAM 访问都需要读取和写回一条长度为 O(log N) 的路径。考虑递归 position map 后，每次访问还会涉及 O(log N) 个递归层级。在 TEE 中，为了满足 doubly-oblivious 要求，controller 内部对 stash 和元数据的操作也需要使用 oblivious scan 等方式，进一步带来 O(log N) 因子。因此，朴素逐条插入的总成本约为 O(N log^3 N)。

本文希望把复杂度降到低于 O(N log^3 N)，同时不增加可信 controller storage。也就是说，Bulkor 不应通过把大量状态直接放进 enclave 来换取性能，而应保持与标准 Path ORAM 类似的空间开销。

### 4.2 安全目标

性能提升只有在不牺牲安全性的前提下才有意义。Bulk loading 构造出的 ORAM 必须满足 Path ORAM 后续访问所需要的随机分布。特别是，每个真实数据块的 leaf label 应该像标准 Path ORAM 中那样独立随机，否则后续访问轨迹可能暴露初始化时的结构偏差。

### 4.3 简单随机 shuffle 为什么不安全

一个很自然的想法是：先把所有真实块和 dummy blocks 随机打乱，直接把打乱后的数组看作 ORAM tree，然后根据每个块落入的物理位置反推出一个合法的 leaf label。这个方案看起来很高效，因为随机打乱本身可以通过成熟方法实现，而且每个块最终也确实位于某条合法路径上。

但论文指出，这个方案并不安全。问题在于，随机打乱产生的是一个排列。不同数据块的物理位置不是相互独立的，因为两个块不可能落在同一个物理地址。若再根据物理地址反推出 leaf label，这些 leaf label 之间也会存在微妙相关性。Path ORAM 所依赖的安全分布要求每个块的 leaf label 独立随机，而简单 shuffle 不能保证这一点。

论文通过两个访问序列解释这种差异。第一种序列是先访问 block 0，再访问 block 1。第二种序列是先访问 block 0，再次访问 block 0。在真正安全的 Path ORAM 中，访问轨迹应该难以区分。但在简单 shuffle 构造中，两个不同块的初始物理位置存在排列相关性，而同一个块在第一次访问后会重新随机分配 leaf label，两者导致“两次访问是否落在同一路径”的概率不同。攻击者可以利用这种统计差异区分访问序列，因此简单 shuffle 不满足论文的安全定义。

这个反例是理解 Bulkor 的关键。它说明 bulk loading 不能只是“把数据随机放进树里”，而必须保持 Path ORAM 所需的独立随机 leaf label 分布。

## 5. Bulkor 的核心思路与整体流程

Bulkor 的核心思路可以概括为一句话：先保证安全分布，再解决物理布局。具体来说，Bulkor 首先为每个真实数据块独立随机分配 leaf label，这一步直接对齐标准 Path ORAM 的安全要求。随后，算法在不改变 leaf label 的前提下，调整每个块实际放入的 bucket，使每个 bucket 不超过容量限制，并保持每个块仍在自己的合法路径上。

这与简单 shuffle 的顺序正好相反。简单 shuffle 是先决定物理位置，再反推出 leaf label；Bulkor 是先独立随机决定 leaf label，再 obliviously 计算合法物理位置。因此，Bulkor 能避免简单 shuffle 中 leaf label 相关性带来的安全问题。

Bulkor 的主流程如下。

第一，AssignLeaf 为每个数据块独立随机分配 leaf label，并生成 metadata。每条 metadata 包含原始数组索引、逻辑地址、leaf label、bucket ID 和最终物理地址等字段。为了隐藏真实数据长度并形成完整 ORAM tree，输入还会被填充 dummy blocks。

第二，BuildPosMap 根据逻辑地址到 leaf label 的映射构建 position map。如果 position map 超过 controller storage 容量，则递归调用 BulkLoad，把 position map 本身也构造成 ORAM。

第三，算法对 metadata 按 bucket ID 执行 oblivious sort。排序的目的不是泄露数据顺序，而是让后续 bucket adjustment 能按路径结构处理块。

第四，OAdjustBucketID 解决 bucket overflow。初始时每个块都被临时放在自己 leaf label 对应的叶桶中，但某些叶桶可能超过容量 Z。OAdjustBucketID 会将溢出的块沿着自己的路径向父节点移动，直到找到有空位的 bucket；如果整条路径都没有空间，则放入 stash。

第五，OAssignPhyAddr 为每个块分配最终物理地址。第六，OPlace 以 oblivious 的方式把 metadata 或数据放到目标位置。第七，OAssignPhyAddrDummy 为空洞位置填充 dummy blocks，使最终树的每个位置都有块，攻击者无法仅凭空位判断真实数据分布。

Bulkor 的一个重要工程选择是：在大部分布局调整阶段，算法主要操作较小的 metadata，而不是直接移动大数据块。只有当物理位置最终确定后，才根据 metadata 移动真实数据。这降低了实际数据搬运开销，也使排序和 placement 更适合并行化。

## 6. 关键算法细节

### 6.1 BuildPosMap：递归构造位置表

Path ORAM 的 position map 记录每个逻辑地址对应的 leaf label。对于大规模数据，position map 本身可能无法完全放入 enclave。Bulkor 通过 BuildPosMap 构造递归 position map。

在第一层递归中，算法先按逻辑地址对 metadata 排序，并将 leaf label 提取出来，形成 position map 的数据块。如果这些数据块可以放入 controller storage，则递归结束，顶层 position map 直接保存在 enclave 中。否则，算法把这些 position map 数据块作为新的输入，再调用 BulkLoad 构造下一层 ORAM。

论文用一个多层结构图解释该过程。底层 ORAM 存真实数据；上一层 ORAM 存底层 position map 的 leaf labels；再上一层存更高层的映射，直到最顶层足够小。这个结构类似多级页表：每一级通过逻辑地址的一部分索引到下一层信息。

BuildPosMap 的意义在于，Bulkor 不只构建数据 ORAM，也同时构建后续访问所需的递归元数据结构。这使 bulk loaded ORAM 可以直接进入正常访问阶段。

### 6.2 Oblivious Sort：为什么选择 bitonic sort

Bulkor 大量依赖 oblivious sort。普通排序算法的比较和访问模式通常依赖输入数据，因此不能直接用于 doubly-oblivious 场景。Oblivious sort 的访问模式与输入值无关，适合在 ORAM 和 TEE 安全系统中使用。

论文讨论了多种 oblivious sort。Melbourne Shuffle 和 Cache Shuffle 等方法带宽开销低，但不满足 doubly-oblivious 要求，因此不能直接用于本文场景。Bitonic sort 的复杂度为 O(N log^2 N)，访问模式固定，容易实现 doubly-oblivious，因此是许多 oblivious algorithms 中常用的构件。Bucket oblivious sort 的理论复杂度更好，可以达到 O(N log N)，但为了把溢出概率降到足够低，需要较大的参数，实际常数因子较高。

作者最终在实现中选择 bitonic sort。虽然这使 Bulkor 的总体复杂度为 O(N log^2 N)，但实际性能更好。论文也指出，如果使用 bucket oblivious sort，理论上可以进一步降到 O(N log N)，但经验测试中并不划算。

### 6.3 OAdjustBucketID：在不改变 leaf label 的情况下解决溢出

OAdjustBucketID 是 Bulkor 的核心子过程之一。初始时，每个块根据随机 leaf label 被放入对应叶桶。由于 leaf label 是独立随机分配的，某些叶桶可能分到超过 Z 个块，导致 bucket overflow。Path ORAM 允许一个块放在 leaf 到 root 路径上的任意 bucket，因此一个自然的处理方式是把溢出的块向父节点移动。

难点在于，这个调整过程本身必须 oblivious。如果算法根据某个桶是否溢出而执行不同访问模式，攻击者就能观察到数据分布。因此，OAdjustBucketID 使用固定循环范围和条件移动指令 cmov，让控制流和内存访问模式不依赖敏感数据。

算法维护一个 occupancy counter 数组，记录当前路径上各层 bucket 已经放入的块数。metadata 按初始 bucket ID 排序后，算法顺序扫描每个块。对于当前块，算法先比较它和上一个块的 bucket ID，确定两条路径的公共祖先，从而知道哪些 occupancy counters 需要重置。然后，算法从叶子向根扫描，找到第一个仍有容量的 bucket，并用 cmov 更新该块的 bucket ID 和对应计数器。如果整条路径都没有空间，则将该块放入 stash。

该过程保持了 Path ORAM 的主不变量，因为块只会沿着自己的路径向上移动，不会离开合法路径。论文证明，在合适参数下 stash 溢出概率仍然很低，甚至不高于标准 Path ORAM 本身的失败风险。

OAdjustBucketID 的时间复杂度为 O(N log N)，controller storage 为 O(log N)，主要来自每条路径的 occupancy counters。

### 6.4 OPlace：处理带空洞的最终布局

当每个块的最终 bucket 已经确定后，还需要把块放到 ORAM tree 的具体物理位置中。这个问题并非简单排序即可解决，因为真实块之间可能存在空洞，这些空洞需要由 dummy blocks 填充。如果只对真实块按物理地址排序，数组长度和实际 ORAM tree 布局仍然不一致。

OPlace 解决的就是这种带空洞 placement 问题。它要求输入已经按 key 排序，然后通过固定模式的交换，把有效元素放到对应位置。算法灵感来自 bitonic sort，访问和交换模式不依赖敏感数据，因此可以保持 oblivious。

OPlace 在 Bulkor 中至少有两个用途。一是按照逻辑地址整理 metadata，以便 BuildPosMap 生成正确顺序的 position map。二是按照最终物理地址放置 metadata 和数据，使真实块进入 ORAM tree 的正确位置，并为 dummy blocks 留出空间。

OPlace 的时间复杂度为 O(N log N)，controller storage 为 O(1)。它是 Bulkor 中与实际布局强相关的关键过程，也是作者实现中主要并行优化的对象之一。

## 7. Bulkor 与 TEE 的结合

Bulkor 面向的主要部署场景是服务器端存在 TEE，例如 Intel SGX。完整 BulkLoad 过程运行在 enclave 中。输入数据块和地址数组被加载到 enclave 并解密，公共参数 N、Z、Cs、Cp 可以公开。输出时，初始化好的 ORAM tree 被加密后存储在 enclave 外部，stash 和顶层 position map 保存在 enclave 内部明文中，作为后续 ORAM controller 的状态。

如果 enclave 内存足够大，中间 metadata 和数据可以直接保存在 enclave 内部。若内存不足，中间数据需要加密写到 enclave 外部，再按 chunk 批量加载回来处理。对于 AssignLeaf 等顺序扫描过程，批处理较直接；对于 OSort 和 OPlace 这类访问模式更复杂的过程，作者设计了相应的 chunk loading 方法，以减少频繁 enclave swap 的开销。

论文还考虑了完整性和 freshness。因为外部存储不可信，chunk 需要附加 MAC 来防止篡改。对于中间结果，如果数据会被多轮读写，攻击者可能发起 replay attack，把旧版本 chunk 替换为新版本。为此，Bulkor 在生成新一轮数据时使用 fresh nonce，并将 nonce 保存在 enclave 中用于验证。最终 ORAM tree 也使用类似标准 Path ORAM 的 Merkle tree 机制保护完整性和新鲜性。

这部分说明 Bulkor 不是只停留在算法层面，而是考虑了在真实 TEE 系统中落地时必须面对的加密、认证、内存限制和外部存储不可信问题。

## 8. 安全性分析

论文的核心安全结论是：由 Bulkor 构造出的 doubly-oblivious Path ORAM 满足其定义的 bulk loading obliviousness。

直观证明思路如下。对于 bulk loading 阶段，算法中的循环边界和分支条件都由公开参数决定，例如输入规模、树高、bucket 容量等，而不是由数据内容或逻辑地址决定。那些必须依赖敏感数据的条件操作，例如是否更新某个 bucket ID，则通过 cmov 等 oblivious primitives 实现，不改变可观察的控制流和访问模式。

同时，Bulkor 中的主要内存操作，包括扫描、oblivious sort、OAdjustBucketID 和 OPlace，都被设计为固定访问模式。攻击者观察到的地址序列只与公开参数有关，而与具体输入数据无关。因此，bulk loading 阶段的 trace 可以由一个只知道公开参数的模拟器生成。

对于后续正常 ORAM 访问，Bulkor 依赖已有 doubly-oblivious Path ORAM 构造，例如 ZeroTrace，来保护 enclave 内外访问模式。由于 Bulkor 在初始化时为每个真实块独立随机分配 leaf label，并保持 Path ORAM 主不变量，后续访问看到的 ORAM 状态与标准安全构造一致。因此，bulk loading 阶段和后续访问阶段合并起来也满足安全定义。

这部分可以理解为：Bulkor 的安全性来自两个方面。第一，初始化过程本身不泄露。第二，初始化输出的 ORAM 状态分布正确，不会给后续访问留下可区分的统计偏差。

## 9. 系统实现

作者使用 Intel SGX 和 Rust 实现 Bulkor。整个实现约 7900 行代码，其中约 5400 行 enclave code 属于 TCB。选择 Rust 的原因主要是性能和内存安全，TEE 开发中内存错误可能带来严重安全风险。

基础 oblivious 操作使用 x86 汇编实现，主要依赖 CMOV 和 CMOVZ 指令。这样可以在不产生数据相关分支的情况下完成条件赋值。加密和解密使用 Intel AES-NI 加速。leaf assignment 和 nonce generation 使用 SGX 提供的真随机数生成器。

存储结构方面，作者实现了三层结构：enclave trusted memory、untrusted server memory 和 disk。ORAM tree 的顶部可以缓存在 enclave 中，避免频繁加解密；中间部分可以缓存在不可信内存中，访问速度快于磁盘；底部大部分数据保存在磁盘上。这种设计对应现实系统中 enclave 内存有限、服务器内存较大、持久化存储更慢的层次结构。

并行化方面，作者观察到 oblivious sort 和 placement 占总执行时间超过 95%，因此重点对这两个部分做多线程并行。其他子过程虽然目前实现为顺序执行，但不构成主要瓶颈。论文也提到，未来如果结合多磁盘和 locality-friendly bitonic sort，磁盘场景性能仍有进一步提升空间。

## 10. 实验评估

### 10.1 实验设置

实验平台使用 Intel Xeon Gold 5317 处理器，支持 64 GB SGX EPC，配备 377 GB DDR4 内存和单块 2.4 TB、10 kRPM、12 Gbit/s HDD。作者在不同数据块大小、不同存储层次和不同线程数下评估 Bulkor。

对比对象包括 C++ ZeroTrace、作者重实现的 Rust ZeroTrace 和 Oblix。ZeroTrace 类 baseline 通过对每个块执行一次 ORAM 写入来完成初始化，因此代表逐条插入方案。Oblix 是此前与 doubly-oblivious 数据结构相关的重要系统，论文将其作为已有优化方案进行比较。由于 Oblix 没有公开完整代码，作者用 Rust 进行了重实现。

### 10.2 总体性能

在磁盘场景、1 kB 数据块、in-memory ratio 为 1/16 的设置下，单线程 Bulkor 相比 Rust ZeroTrace 加速 22.8 倍到 34.2 倍，相比 Oblix 加速 15.5 倍到 21.9 倍。16 线程 Bulkor 相比 Rust ZeroTrace 加速 139.1 倍到 160.6 倍，相比 16 线程 Oblix 加速 8.7 倍到 10.1 倍。

当 in-memory ratio 提高时，所有系统性能都会改善，因为对慢速磁盘的访问减少。Bulkor 相对 ZeroTrace 的优势略有下降，这是因为 Bulkor 的规则访问和顺序化优势在磁盘上更明显，而内存对随机访问更友好。不过即便在内存场景中，Bulkor 仍明显快于 ZeroTrace 和 Oblix。

对于 64 B 和 1 kB 数据块，论文都测试了完全内存场景和完全 enclave 内缓存场景。结果显示，随着 N 增大，Bulkor 的加速比通常提高，这与其渐进复杂度优势一致。小块场景下，ZeroTrace 受递归层级影响更大，因此 Bulkor 的相对优势更明显。

### 10.3 应用案例

论文进一步评估了 Bulkor 在实际应用中的潜在收益。

在 oblivious join 中，某些查询处理中间结果需要在在线阶段构造 ORAM。Bulkor 将三个 sort-merge join benchmark 的端到端延迟分别降低 47.9%、44.4% 和 42.8%。这说明初始化不是一个可以忽略的小开销，而可能占据接近一半时间。

在 oblivious search 中，系统面临线性扫描和“构建 ORAM 后二分搜索”的权衡。如果查询次数少，线性扫描更划算；如果查询次数多，构建 ORAM 的成本可以被后续快速查询摊销。Bulkor 显著降低了这个分界点，使得更多场景下使用 ORAM 搜索变得划算。

在 oblivious BFS 中，作者展示 Bulkor 还可以启发新的 ORAM-based oblivious algorithm 设计。相比已有 DOGA 和 ObliBFS，结合 Bulkor 的新算法在多个真实图数据上取得更好性能。论文报告中，Bulkor 将该算法相对 DOGA 的加速范围从 0.8 倍到 9.1 倍提升到 1.2 倍到 13.7 倍。

此外，在数据恢复和云存储转换场景中，Bulkor 也能把原本不可接受的重构或转换时间降到可用范围。例如论文讨论 20 GB 云存储数据在普通加密布局和 ORAM 布局之间转换时，Rust ZeroTrace 可能需要约 4 * 10^5 秒，而 Bulkor 可在一小时内完成，从而让按需转换节省空间的方案更现实。

## 11. 相关工作中的位置

本文与三类工作密切相关。

第一类是 tree-based ORAM，包括 Path ORAM、Ring ORAM 等。这些工作主要关注正常访问时的带宽开销、客户端存储和理论安全性。Bulkor 没有替代这些 ORAM 协议，而是优化它们的初始化和重构阶段。

第二类是 TEE 与 ORAM 的结合。ZeroTrace 将 Path ORAM 和 Circuit ORAM 引入 Intel SGX，并设计 oblivious memory primitives 来避免 enclave 内部访问模式泄漏。Oblix 进一步明确提出 doubly-oblivious 要求，并构建高级 oblivious 数据结构。Bulkor 继承这些系统的安全目标，但专门解决 bulk loading 这一性能瓶颈。

第三类是 oblivious data processing 系统，例如 Opaque 和 ObliDB。这些系统支持加密数据分析和查询处理，常常依赖 oblivious sort、oblivious join、oblivious index 等组件。Bulkor 可以作为这些系统的底层构件，优化中间结果构建、数据恢复和布局转换。

因此，Bulkor 的贡献不是提出一个全新的安全模型，而是在已有 ORAM 和 TEE 安全系统之间补上一个重要缺口：安全而高效的 ORAM 批量构建。

## 12. 论文贡献总结

本文的贡献可以总结为四点。

第一，论文系统研究了 Path ORAM bulk loading 问题，并将其定义为一个安全关键的构建过程，而不是普通实现细节。它指出，在安全查询、数据恢复和云存储转换等场景中，初始化开销会直接影响系统可用性和端到端性能。

第二，论文指出简单随机 shuffle 构造并不安全。这个反例很有价值，因为它说明 ORAM 初始化必须保持 leaf label 独立随机分布，不能只追求“看起来随机”的物理布局。

第三，论文提出 Bulkor 算法。Bulkor 先为每个块独立随机分配 leaf label，再通过 OAdjustBucketID 和 OPlace 等 oblivious 子过程解决 bucket overflow 和最终布局问题。使用 bitonic sort 时，整体复杂度从朴素 doubly-oblivious 逐条插入的 O(N log^3 N) 降到 O(N log^2 N)。

第四，论文完成了 Intel SGX 上的系统实现，并在磁盘、内存、enclave 内缓存、多线程和实际应用案例中进行了评估。实验结果表明，Bulkor 相比 ZeroTrace 和 Oblix 有显著性能提升。

## 13. 个人理解与思考

### 13.1 我对本文核心价值的理解

我认为本文最重要的价值在于，它抓住了安全系统中一个容易被忽略但很现实的问题：初始化也是系统运行的一部分。如果一个安全机制正常访问时性能可以接受，但初始化或恢复需要很长时间，那么系统在实际部署中仍然可能不可用。

传统上，我们容易把 ORAM construction 当成预处理，认为只要最终 ORAM 能安全访问即可。但本文指出，很多场景下 ORAM 是在线构建的。例如安全数据库处理中间结果、TEE 崩溃后的恢复、云存储按需转换等。在这些场景中，bulk loading 的性能直接决定用户是否愿意使用该方案。

另外，本文也展示了安全系统设计中“随机”并不等于“安全”。简单 shuffle 看起来已经随机化了物理位置，但它没有保持 Path ORAM 所需的独立 leaf label 分布，仍然可能通过后续访问轨迹泄漏信息。这说明密码学系统中的随机性往往有非常具体的分布要求，不能只凭直觉设计。

### 13.2 本文的优点

本文的第一个优点是问题选择具体且重要。它没有泛泛地说要优化 ORAM，而是聚焦 Path ORAM 的批量构建阶段。这个问题足够窄，便于给出清晰算法；同时又足够实际，因为许多系统都需要初始化、恢复或布局转换。

第二个优点是兼顾理论和系统。论文不仅给出复杂度分析和安全证明，还实现了 SGX 系统，并与 ZeroTrace 和 Oblix 比较。对于安全系统论文来说，这种从安全定义到工程实现再到实验评估的闭环比较完整。

第三个优点是方法思路清晰。Bulkor 的核心设计顺序是先确定安全随机性，再调整物理布局。这个思路抓住了 Path ORAM 的关键不变量，也解释了为什么简单 shuffle 不行。

第四个优点是实验覆盖较广。论文测试了磁盘、内存、不同块大小、不同线程数，还讨论了 oblivious join、oblivious search、oblivious BFS、数据恢复和云存储转换等案例，说明 Bulkor 不只是一个微基准优化。

### 13.3 可能的不足

本文也存在一些可以进一步讨论的地方。

第一，系统实现主要基于 Intel SGX。虽然论文说其他 TEE 可以类似使用，但不同 TEE 的内存模型、侧信道风险、可用安全指令和性能特征并不完全相同。因此，Bulkor 在 Intel TDX、AMD SEV、ARM TrustZone 等平台上的实际表现仍需要进一步验证。

第二，bitonic sort 虽然适合 doubly-oblivious 实现，但 O(N log^2 N) 对非常大规模数据仍然不低。论文提到 bucket oblivious sort 可以在理论上降低到 O(N log N)，但实际常数较大。未来是否能设计低常数、适合 TEE 的 oblivious sort，是一个值得继续研究的问题。

第三，实验平台使用单块 HDD。现代服务器中常见 SSD、NVMe、多盘阵列和分布式存储，这些环境下随机访问、顺序访问和并行 I/O 的代价结构不同。Bulkor 的 locality 和并行优化在这些平台上的效果可能会有所变化。

第四，本文不考虑拒绝服务攻击，也不覆盖电磁、热、功耗等物理侧信道。这在学术论文中是合理边界，但实际部署中仍需要结合更完整的系统防护。

第五，Bulkor 优化的是初始化和重构阶段，并不能消除 Path ORAM 正常访问阶段的固有开销。如果某些应用需要持续高频访问 ORAM，后续访问性能仍然可能是瓶颈。

### 13.4 未来想法

一个可能的未来方向是设计更适合 TEE 的 oblivious sort 和 placement 原语。Bulkor 的主要时间开销集中在 sort 和 placement，如果能在保持 doubly-oblivious 的同时降低常数因子，整体性能会继续提升。

第二个方向是面向现代存储体系重新优化 Bulkor。论文已经提到多磁盘和 locality-friendly bitonic sort，但没有在当前实现中集成。未来可以针对 SSD、NVMe、RDMA 或分布式存储设计更合适的数据布局和批处理策略。

第三个方向是研究增量式 ORAM bulk maintenance。Bulkor 适合一次性构建或重构 ORAM，但现实系统中数据可能持续插入、删除和更新。是否能在不完全重建的情况下，以 oblivious 方式批量维护 ORAM，是一个有价值的问题。

第四个方向是将 Bulkor 更深入地集成到安全数据库系统中。很多安全查询系统会产生中间结果，如果 Bulkor 能作为查询优化器中的一个物理算子或初始化算子，系统可以根据数据规模、查询次数和安全要求自动决定是否构建 ORAM。

第五个方向是扩展到更多 tree-based ORAM 变体。论文已经讨论了 Ring ORAM 的适配方式，但不同 ORAM 协议的元数据和 eviction 规则不同。系统性研究 bulk loading 对不同 ORAM 协议的适配，可能形成更通用的 ORAM construction framework。

## 14. 面向 PPT 的提炼

如果把本文做成课程汇报 PPT，建议主线不要陷入过多公式，而是围绕一个故事展开：云上敏感数据不仅要加密内容，还要隐藏访问模式；ORAM 可以隐藏访问模式，但大量已有数据构建 ORAM 很慢；TEE 可以提升效率，却带来内部访问模式侧信道；因此 bulk loading 必须 doubly-oblivious；简单 shuffle 看似自然但不安全；Bulkor 通过先随机 leaf label、再 obliviously 调整 bucket placement，在保持安全性的同时显著加速。

PPT 的重点可以放在四个问题上。第一，为什么访问模式泄漏是问题。第二，为什么 Path ORAM 初始化不能简单逐条插入或随机 shuffle。第三，Bulkor 如何解决：AssignLeaf、BuildPosMap、OAdjustBucketID、OPlace。第四，实验说明它带来了多大的收益，以及我们如何评价它的局限和未来方向。

在讲方法时，不需要逐行解释伪代码。更适合课程汇报的方式是画出一棵简化 ORAM 树，展示若干块被随机分配到叶桶后出现溢出，然后把溢出块沿路径向上移动；再说明这个移动过程必须使用固定访问模式和 cmov 才能满足 doubly-oblivious。这样听众更容易理解论文的核心思想。

## 15. 总结

Bulkor 研究的是 Path ORAM 的批量构建问题。ORAM 用来隐藏访问模式，但当系统已有大量数据时，逐条插入构建 ORAM 会非常慢。尤其在 TEE 场景中，enclave 内部访问模式也可能泄漏，因此构建过程需要 doubly-oblivious。

Bulkor 的核心思路是先为每个数据块独立随机分配 leaf label，保证 Path ORAM 所需的安全分布，再通过 oblivious sort、bucket adjustment 和 oblivious placement 把数据块放到合法位置。这样既避免了简单随机 shuffle 的安全问题，又将复杂度从朴素方案的 O(N log^3 N) 降到 O(N log^2 N)，并在 Intel SGX 实现中取得明显性能提升。

从课程汇报角度看，这篇论文适合作为数据安全与隐私保护主题，因为它同时涉及访问模式泄漏、ORAM、TEE 侧信道、算法安全性和系统性能优化。它的启发是：安全系统不仅要关注正常操作的安全性，也要关注初始化、恢复和转换这些工程阶段是否同样安全、可用且高效。

