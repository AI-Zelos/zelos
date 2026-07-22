# Zelos 对 NEF 白皮书的作用与价值

> 写给决策者的立项论证：为什么 Zelos 值得做，以及它与 NEF (NetX Enterprise Framework) 的关系。

---

## 一、先说清楚 NEF 白皮书在说什么

NEF 白皮书的核心论断：

**当前 AI Agent 的根本危机不是技术性的，而是宪法性的。**

每一个 AI Agent 都在同时做三件事：
1. **自己制定计划**（立法权）
2. **自己执行操作**（行政权）
3. **自己评判结果**（司法权）

这在政治学里叫独裁。人类在三百年前就用三权分立取代了这种架构，但在 AI 领域，我们却在每个 Agent 里重建了它。

结果是什么？白皮书给出了数据：

| 指标 | 数据 |
|------|------|
| 真实 Agent 场景攻击成功率 | **84.3%** |
| Agent 自发产生欺骗行为的比例 | **31.4%**（没有奖励信号，自发习得） |
| 欺骗型 Agent 对诚实 Agent 的财富优势 | **234%** |
| 企业 CXO 2026 年计划增加 Agent 预算的比例 | **91%**（同时在面对接近确定性的安全失败率） |

白皮书的核心主张：**需要构建一个 Agent 数字文明（Agent City）**——有宪法、有三权分立、有公开市场、有司法审计、有文化传承。这套架构叫 NEF (NetX Enterprise Framework)。

---

## 二、NEF 的蓝图很好，但缺了最关键的一层

NEF 白皮书描述了四个层次：

```
┌─────────────────────────────────┐
│  宪法与文化 (Constitution)       │  ← 人类定义
├─────────────────────────────────┤
│  司法与审计 (Judiciary)          │  ← 治理机制
├─────────────────────────────────┤
│  经济与市场 (Economy)            │  ← 激励机制
├─────────────────────────────────┤
│  ？？？执行引擎？？？             │  ← ★ 缺失层 ★
├─────────────────────────────────┤
│  硬件信任层 (TEE / Chain)        │  ← 可信计算
└─────────────────────────────────┘
```

白皮书花了大量篇幅描述 8 合约栈、Agent Marketplace、Judicial DAO、Logic Pedigree 这些上层概念，但对于 **"那个真正把 Goal 变成 Task、把 Task 派给 Agent、把结果收集回来验证、把每一步都记录成不可变审计日志的 Runtime 软件"**——白皮书没有也不打算提供。

**Zelos 要做的，就是填补这个空白。**

---

## 三、Zelos 是什么

一句话：**Zelos 是面向多 Agent 协同的开源编排 Runtime。**

类比：
- Linux 管理 Process
- Kubernetes 管理 Container
- Zelos 管理 Goal（由多个 Agent 协同完成的目标）

它不构建 Agent。它运行 Agent。它的工作流程是：

```
用户提交 Goal（"帮我建一个电商网站"）
  → Planner 分解为执行计划（Task DAG）
    → Scheduler 按能力匹配最佳 Agent（公开招标，不指定供应商）
      → Execution Engine 派发任务、监控心跳、强制执行超时
        → Agent 执行并返回 Artifact
          → Verifier 验证产出物质量（司法审查）
            → Event Bus 记录每一步为不可变事件（完整审计链）
              → Goal 完成
```

---

## 四、Zelos 对 NEF 白皮书的价值——具体到每个概念

以下映射说明了 Zelos 如何把 NEF 的概念变成可运行的软件：

| NEF 白皮书提出的概念 | Zelos 提供的实际实现 |
|---------------------|---------------------|
| **三权分立**（立法/行政/司法不能在同一 Agent 手中） | Planner 定计划 → Scheduler 管执行 → Verifier 判结果。三个独立组件，Agent 永远只能执行 |
| **Task Hub**（把 Goal 分解为 DAG 化的 Task 并招标） | ExecutionPlan → Task Graph Engine：DAG 状态机管理依赖关系 + Scheduler 5 阶段评分招标 |
| **Capability-based Marketplace**（公开市场，声誉驱动） | Capability Registry："我需要 code-generation.python" → 查询所有注册该能力的 Agent → Scheduler 按成功率(30%)+成本(20%)+延迟(15%) 等公开标准评分 |
| **Logging Hub + Logic Pedigree**（不可变加密审计链） | Event Bus：追加写入、不可变、timestamped、correlation_id 串联、causation_id 追踪因果。从 Goal 提交到 Artifact 产出，每一步都可追溯 |
| **Guardian Contract**（语义防火墙，检测 logic drift） | Verifier Plugin：Artifact 进入验证门 → verify() → Accepted/Rejected → Rejected 触发重试或重新规划 |
| **Constitutional Pre-Screening**（合规前置审查） | Policy Plugin：evaluate() → Allow/Reject/Delay。在 Scheduler 决策后、派发前进行宪法性审查 |
| **8-Contract Stack**（合约栈约束 Agent 行为边界） | 15 条 Architecture Invariants：Agent 不能自定规则、不能调用其他 Agent、不能修改执行计划、不能绕过审计 |
| **Progressive Adoption**（Tier1 私有→Tier4 全球） | Phase 1 单节点 → Phase 2 完整平台 → Phase 3 分布式集群。渐进式规模化路线 |
| **AGIL 四支柱**（经济/政府/司法/文化可独立演化） | Plugin Architecture：Planner/Verifier/Policy/Memory/Storage 都是可替换插件。宪法(Kernel)不改，机构(Plugin)可换 |

**一句话总结：如果 NEF 是 Agent City 的宪法和蓝图，Zelos 就是它的操作系统。没有 Zelos，Agent City 是一份精美的白皮书；有了 Zelos，它才能真的运转起来。**

---

## 五、为什么现在做 Zelos 是正确的时机

### 1. 市场窗口

- **91% 的企业 CXO 在增加 Agent 预算**，但安全失败率接近 85%
- 欧盟 AI Act 已生效，违规罚款达全球年营收 7%——合规不再是可选项
- MCP (Anthropic) 和 A2A (Google) 协议已发布，Agent 互联互通的基础管道已经就绪——但管道之上缺治理层

### 2. 竞争格局

| 谁 | 在做什么 | 缺什么 |
|----|---------|--------|
| LangChain / LangGraph | Agent 构建工具包 | 不管编排，不管治理 |
| CrewAI / AutoGen | Agent 角色协作 | 不管审计，不管验证 |
| MCP / A2A | Agent 通信协议 | 只是管道，不管谁来治理 |
| Temporal / Airflow | 确定性工作流引擎 | 不适合非确定性的自主 Agent |
| NEF / NetX | 宪法蓝图 + 区块链合约 | 缺实际的 Runtime 执行层 |

**Zelos 的位置是唯一的：上层治理框架（如 NEF）和下层 Agent 执行者之间的 Runtime 层。这是整个 Agent 技术栈中最大的空白。**

### 3. Zelos 已经有完整的架构设计

Phase 0 已交付：
- 15 条 Architecture Invariants（宪法性设计约束）
- 6 个 ADR（架构决策记录，记录所有关键权衡）
- 12 个 Blueprint（覆盖 domain model, kernel, scheduler, event bus, verifier 等全部组件）
- 4 个 RFC（Goal 生命周期、Agent 注册协议、Event Bus 规范、Capability 语义）
- 6 个版本化 JSON Schema（execution plan, task, capability, artifact, event, agent registration）

**一个新工程师可以只读文档就理解整个 Runtime 架构，不需要读代码。**

接下来只需进入 Phase 1：实现单节点 Runtime Kernel。

---

## 六、建议

### 我们要做什么

**实现 Zelos Runtime Kernel v0.1.0**（Phase 1）：

| 组件 | 工作量估算（人月） |
|------|-------------------|
| Event Bus (in-process pub/sub, event persistence) | 1-2 |
| Capability Registry (registration, indexing, query) | 1 |
| Task Graph Engine (state machine, dependency resolution) | 2 |
| Scheduler (capability matching, scoring, FIFO dispatch) | 2 |
| Execution Engine (dispatch, heartbeat, timeout, retry) | 2 |
| Plugin Lifecycle Manager (load, configure, health check) | 1 |
| Runtime API + HTTP Adapter | 1.5 |
| Python SDK (Agent base class + Goal submission client) | 1.5 |
| 测试 + 文档 | 2 |
| **合计** | **约 14-16 人月** |

### 产出物

一个可运行的单节点 Runtime，能够：
1. 接受 Goal → 手工定义 ExecutionPlan → 启动 Task Graph
2. Agent 通过 Python SDK 注册 Capability 并接收 Task
3. Scheduler 按 Capability 匹配 + 评分选择 Agent
4. Execution Engine 派发 Task、监控心跳、处理超时和重试
5. Event Bus 记录所有状态变化，形成不可变审计链
6. Verifier Plugin 验证 Artifact 质量

### 战略意义

1. **填补 Agent 技术栈最大的结构性空白**——上层治理框架和下层 Agent 执行者之间的 Runtime 层
2. **与 NEF 方向高度互补**——Zelos 可以作为 NEF 生态的 Runtime 执行引擎，也可以独立运行
3. **先发优势**——目前市场上没有任何一个项目在做"Agent 编排 Runtime"这个定位
4. **开源 + Apache 2.0**——基础设施不应该是私有的，开源是最快的生态建设路径

---

## 七、一句话

> 当所有人都在抢着造更好的 Agent（更快的车），Zelos 要做的是造 Agent City 的市政基础设施（道路、电网、警察局、法院）。NEF 白皮书描述了一座宏伟的城市蓝图，Zelos 是让这座城市的引擎真正转动起来的那一层软件。市场窗口是现在——MCP/A2A 管道已铺好，欧盟 AI Act 合规时钟在倒计时，而 Agent 编排 Runtime 这个赛道目前是空的。

---

> 📄 **此文档位置：** `docs/zelos-for-nef-whitepaper.md`



~~~
 最好的做法是 阶梯式处理，分别针对三种不同场景：                                                                                                                
                                                                                                                                                                     
      第一层：等一等（可能是 Agent 正在热加入）                                                                                                                      
                                                                                                                                                                     
      在编排循环中给 READY Task 加一个 stuck_since 计时。如果 Task 在 READY 状态停留 < 60 秒 → 什么都不做，继续重试。这给了热加入 Agent 的时间窗口。                 
                                                                                                                                                                     
      第二层：超时 → 标记失败，让 Goal 能结束                                                                                                                        
                                                                                                                                                                     
      如果超过 60 秒仍无可调度 Agent，将 Task 标记为 FAILED，原因写清楚是 "no agent provides capability: xxx"。这样 Goal 至少能到达终端状态而不是永远挂起。          
                                                                                                                                                                     
      第三层：触发 Planner 重规划（Phase 2）                                                                                                                         
                                                                                                                                                                     
      Task 失败后，编排循环调用 Planner.replan()，让 LLM 重新分解——比如把 code-generation.rust 拆成 code-generation.python + 手动转译。         
      
      这样改完之后：                                                                                                                                               
      - 正常场景：Agent 在 60 秒内可用 → Task 被调度 → 一切正常                                                                                                    
      - 热加入场景：Agent 延迟几秒上线 → 等一等就绪 → 自动调度                                                                                                     
      - 真正缺失：60 秒还没 Agent → Task 失败 → Goal 结束（不会永远挂起）                                                                                          
      - Phase 2 重规划：Task 失败触发 Planner.replan() → LLM 重新找一个能完成的路
      
      
      
 OPENAI_API_KEY="sk-d4770f2db9244fde9fbf292bec1cbfc5" OPENAI_API_BASE="https://api.deepseek.com/v1" OPENAI_MODEL="deepseek-v4-flash"
 
 
 Murmur
  3. 第三层：3 节点集群 leader 选举 < 5s，工作窃取正确                                                                                         
     4. 第四层：TypeScript SDK npm 包可安装，Demo 可运行                                                                                          
     5. 第五层：mTLS 握手成功，审计日志可导出                                                                                                     
     6. 第六层：Jaeger 可见 Span，Grafana 可见指标                                                                                                
     7. 第七层：基准测试报告自动生成                                                                                                              
     8. 第八层：文档站点可公开访问                                                                                                                
                                  
                                  
                
~~~

~~~
┌───────────┬────────────────────────────────────────────────────────────────────────┐                                                    
      │   缺口    │                                  影响                                  │                                                    
      ├───────────┼────────────────────────────────────────────────────────────────────────┤                                                    
      │ etcd 集成 │ 领导者选举目前是内存模拟，多节点部署时没有真正的分布式协调，会出现脑裂 │                                                    
      ├───────────┼────────────────────────────────────────────────────────────────────────┤                                                    
      │ 消息队列  │ EventBus 是进程内的，跨节点事件无法扇出，分布式 Runtime 只能用单节点   │                                                    
      ├───────────┼────────────────────────────────────────────────────────────────────────┤                                                    
      │ Go SDK    │ 只有 Python + TypeScript，缺少云原生生态最主流的语言                   │                                                    
      ├───────────┼────────────────────────────────────────────────────────────────────────┤                                                    
      │ 性能优化  │ 基准测试跑过了但没根据结果优化，TaskGraph 全量扫描、Scheduler 无缓存   需要完成上面的工作，补充相关的测试和文档 功能和文档都要做完整实现 不要省略，最后进行自查
~~~

