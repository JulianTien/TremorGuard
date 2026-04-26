# TremorGuard 历史病例档案与纵向健康报告 PRD

## Problem

当前 TremorGuard 的 AI 助手只能基于患者档案、设备状态、当日监测摘要和文本聊天内容生成回答，无法接收和长期利用患者的历史病例图片。患者因此缺少一个可持续累积的病历档案能力，也无法把“历史病例信息 + TremorGuard 连续监测数据”整合成一份长期追踪、可导出的健康报告。

这直接限制了两个价值面：

- 患者只能得到一次性的对话回答，不能建立纵向病情理解
- 复诊前无法拿出一份同时覆盖历史病历与近期客观监测数据的结构化材料

## Goal

在不改变 TremorGuard 非诊断产品定位的前提下，新增一个长期病历档案与纵向健康报告能力：

- 支持患者上传历史病例图片
- 长期保存病例档案并支持后续追加
- 抽取病例内容并沉淀为可复用的结构化摘要
- 结合 TremorGuard 监测数据和用药记录生成详细健康报告
- 保留报告历史版本
- 支持 PDF 导出

## Non-goals

- 不把 AI 输出包装成诊断、分期、处方、药量调整或医疗裁定
- 不把新能力继续塞进现有 `POST /v1/ai/chat` 文本聊天接口
- 不在第一期建设泛化的“任意文档平台”
- 不要求第一期覆盖所有文档类型；用户授权 OMX 自主决定首期图片格式、大小限制和实现细节

## Principles

- 非诊断边界必须贯穿提示词、存储内容、UI 文案和 PDF。
- 档案、抽取、报告是持久化领域，不与瞬时聊天链路耦合。
- 原始病例、抽取结果、报告版本都必须可追溯。
- 采用 brownfield 兼容增量方案，优先复用现有 FastAPI、SQLAlchemy、DashScope、报告中心骨架。
- 以阶段性交付降低风险：先冻结契约，再做档案与状态机，再做抽取，再做报告，再做 PDF 和硬化。

## Decision Drivers

- 用户明确要求长期病历档案能力，而不是一次性上传分析工具。
- 输出要足够详细、临床风格强，但不能越过非诊断边界。
- 现有代码库已有 DashScope 文本对话和轻量报告中心，适合新增独立域而不是重写。

## Users

- 患者：上传历史病例，持续追加，查看纵向健康报告并导出 PDF
- 复诊沟通场景中的患者/家属：携带结构化报告与医生沟通
- 内部开发/合规团队：验证系统未越过安全边界，且数据可追溯

## User Stories

- 作为患者，我希望把既往检查单、门诊记录、病历图片长期保存到账户中，后续不用重复上传。
- 作为患者，我希望在新增病例后，系统可以基于全部档案和最近监测数据重新生成一版更新后的健康报告。
- 作为患者，我希望能看到每份报告的生成时间和版本历史，并下载 PDF 用于复诊沟通。
- 作为产品方，我希望继续保留现有 AI 聊天能力，不因档案功能引入回归。
- 作为合规控制方，我希望所有报告都显式保持非诊断定位，并能追溯生成所依据的输入。

## Recommended Product Shape

### Experience surfaces

#### 记录档案页

- 展示病历档案列表
- 支持创建档案、查看详情、追加上传

#### 档案详情页

- 展示原始病例图片
- 展示抽取状态与抽取摘要
- 展示与该档案关联的报告历史

#### 报告详情页

- 展示结构化健康报告
- 显示免责声明
- 支持导出 PDF

#### 现有 AI 页面

- 保持文本问答主路径不变
- 可在后续加“查看最近健康报告”入口，但不是档案主入口

#### 现有 `/reports` 页面

- 在本功能范围内继续作为 legacy 监测摘要报告中心
- 不混入新病历联合健康报告

UI 文案需明确区分：

- `/reports` = 监测摘要报告
- `/records/...` = 病历联合健康报告

### Output contract

报告应覆盖以下内容：

- 患者基础信息摘要
- 历史病例整理摘要
- 最近 TremorGuard 监测数据趋势摘要
- 用药记录与监测趋势的并行观察
- 不确定信息与信息缺口
- 建议患者复诊时重点沟通的要点
- 明确的非诊断免责声明

### Explicitly disallowed output

- 疾病确诊/排除
- 分期定级
- 处方建议或药量调整
- 代替医生判断的风险结论

## Recommended Architecture

### Decision

采用独立域方案，不扩展现有聊天接口作为主承载面。

### ADR

**Decision:**

新增一个主边界 medical records，内部再分 documents、document_extractions、report_versions

**Drivers:**

- 需要长期档案、追加上传、再分析和版本化报告
- 必须保持非诊断边界
- 需要保留现有聊天链路稳定性

**Alternatives considered:**

- 继续扩展 `POST /v1/ai/chat`
- 先做通用文档平台

**Why chosen:**

单一主边界更贴合当前仓库体量，同时保留内部持久化分层

**Consequences:**

- 需要新增模型、接口和前端页面
- 聊天链路回归风险最低
- 为后续扩展到更多文档类型保留演进空间

**Follow-ups:**

- 后续再决定是否抽象出通用对象存储适配器

### Primary bounded context

首版对产品和接口暴露一个主边界：medical records

该主边界内部再分三个持久化子层：

#### documents

管理档案容器、源图片文件、上传元数据、归属关系、追加历史

#### document_extractions

管理 OCR / 文档理解结果、结构化摘要、提取状态、错误详情

#### report_versions

管理报告请求、版本、内容、PDF、输入谱系、历史记录

### Data model direction

- `medical_record_archives`
- `medical_record_files`
- `medical_record_extractions`
- `longitudinal_reports`
- `report_input_links`

说明：

- 不立即重载现有 `report_records`
- 现有 `report_records` 继续服务当前监测摘要报告中心
- 新的病历联合健康报告单独建模，并在本计划内保持与 legacy `/reports` 分离

### API direction

- `POST /v1/medical-records/archives`
- `GET /v1/medical-records/archives`
- `GET /v1/medical-records/archives/{archive_id}`
- `POST /v1/medical-records/archives/{archive_id}/files`
- `GET /v1/medical-records/archives/{archive_id}/files`
- `POST /v1/medical-records/archives/{archive_id}/reports`
- `GET /v1/medical-records/archives/{archive_id}/reports`
- `GET /v1/medical-records/reports/{report_id}`
- `GET /v1/medical-records/reports/{report_id}/pdf`

Report center ownership decision for this initiative:

- `GET/POST /v1/reports` 和当前 `/reports` 页面继续保持 legacy-only
- 新病历联合健康报告仅在 medical records 路由族中展示
- 本计划不做 federated report center

### AI pipeline

采用两段式：

#### 抽取阶段

病例图片 -> 文档理解/OCR -> 结构化摘要

#### 综合阶段

结构化摘要 + TremorGuard 监测上下文 + 用药记录 -> 纵向健康报告

原因：

- 方便重用已抽取结果
- 支持新增病例后低成本重新生成报告
- 方便做可追溯性和质量排查

### Execution model contract

即使首版内部实现暂时可以同步执行，对外契约也必须从第一期开始就是“可异步、可重试、可轮询”的。

Required status model:

#### File processing

- `queued`
- `processing`
- `succeeded`
- `failed`

#### Report generation

- `queued`
- `processing`
- `succeeded`
- `failed`

Required behavior:

- 上传成功不等于抽取完成
- 报告创建成功不等于报告已完成
- 查询接口必须返回当前状态
- 前端必须按状态轮询或刷新
- 失败要有错误摘要和明确重试语义
- 关键写请求应具备幂等策略，避免重复点击创建重复任务

### Longitudinal context assembler

长期报告不得直接复用聊天服务里的 `build_monitoring_context()` 作为输入契约，因为它是为“最近一天聊天解释”准备的日级上下文拼装器。

必须新增独立的 longitudinal context assembler：

输入：

- `report_window`
- selected document versions
- selected extraction versions
- `monitoring_window`
- `medication_window`
- `disclaimer_version`
- prompt/model version snapshot

输出：

- 面向纵向健康报告的稳定结构化输入对象

可复用：

- dashboard 的低层统计函数
- 监测摘要计算函数

不可复用：

- chat service 中面向单日聊天的上下文拼装逻辑

### Storage strategy

第一阶段使用私有本地文件存储 + DB 路径引用

用一层简单存储接口包裹，未来可替换为对象存储

持久化内容至少包括：

- 原始病例图片
- 抽取结果
- 报告内容
- PDF 产物

### Data governance and consent policy

病历图片属于高敏感健康数据，本功能在 Phase 0 必须冻结以下规则：

- 上传资格是否依赖现有 `cloud_sync_enabled` / `rag_analysis_enabled`，或需要新增单独 consent
- 数据保留策略
- 用户删除策略
- 用户导出策略
- 审计记录要求

本期要求：

- 至少先定义并记录以上规则
- 若自助删除不进入本期交付，必须显式标记并约定内部处理路径
- PDF 导出属于用户导出能力的一部分，但不等于完整档案导出

## Phased Implementation Plan

### Phase 0: Contract Freeze

目标：

- 冻结领域边界、数据模型命名、接口轮廓、状态机、报告 JSON 契约、免责声明规范、病历数据治理规则

产出：

- 本 PRD
- `test-spec-historical-record-archive.md`
- 新表草图
- 报告结构草图
- job/status/idempotency 契约
- report center ownership 决策
- retention/delete/export/consent policy

退出条件：

- 开发团队无需重新打开需求访谈即可开始实现

### Phase 1: Archive Foundation

目标：

- 患者可创建/查看病历档案并上传病例图片，且上传状态契约已落地

后端：

- 新增 archive/file 模型与迁移
- 新增上传接口和列表接口
- 新增 queued/processing/succeeded/failed 文件状态机
- 增加基础审计日志

前端：

- 新增档案列表页与详情页
- 新增图片上传入口与状态反馈
- 新增状态轮询/刷新逻辑

退出条件：

- 病例图片上传后刷新页面仍可见
- 新老登录会话后仍可访问所属档案

### Phase 2: Extraction Foundation

目标：

- 每个上传文件都能获得可持久复用的抽取摘要，并沿用正式状态机契约

后端：

- 新增 extraction 模型
- 接入 DashScope 文档理解 / OCR 处理
- 沉淀结构化摘要与失败状态
- 冻结重试语义和错误摘要格式

前端：

- 展示处理状态、成功/失败、抽取摘要

退出条件：

- 用户能看到每份文件的抽取结果或失败提示
- 抽取结果可被后续报告生成接口读取

### Phase 3: Longitudinal Report Generation

目标：

- 基于全量历史档案 + TremorGuard 监测上下文生成详细健康报告

后端：

- 新增长期报告模型与谱系关联
- 新增独立 longitudinal context assembler
- 生成结构化报告 JSON 与正文
- 保留历史版本
- 落实报告生成状态机与重试契约

前端：

- 新增报告详情与版本历史
- 支持重新生成

退出条件：

- 可以从已有档案生成第一版报告
- 追加病例后生成新版本且旧版仍可查看

### Phase 4: PDF Export

目标：

- 选择任一报告版本导出稳定 PDF

后端：

- PDF 渲染服务
- PDF 文件存储与下载接口

前端：

- 报告详情页导出按钮

退出条件：

- 导出的 PDF 含清晰免责声明和稳定格式

### Phase 5: Hardening

目标：

- 提升稳定性、可观测性、恢复能力

工作：

- 重试/失败恢复完善
- 上传格式和大小校验增强
- 审计与谱系强化
- 如有必要，升级为异步任务

退出条件：

- 关键失败场景可恢复、可追踪

## Risks

- 安全边界漂移
  - 通过统一免责声明、提示词守卫、禁用短语检查控制
- 上传和报告逻辑重新耦合进聊天接口
  - 通过独立 API 和服务模块避免
- OCR/抽取质量不稳定
  - 保留原图、原始抽取结果和置信度摘要，支持后续重跑
- PDF 成为唯一真实来源
  - 结构化报告 JSON 是源，PDF 只是渲染目标
- 首期同步处理导致慢体验
  - 第一阶段设置文件约束，后续为异步留接口

## Success Metrics

- 患者可成功创建和访问长期病历档案
- 上传病例后能得到抽取结果和纵向报告
- 新病例追加后能成功生成新版本报告
- PDF 导出成功率稳定
- 新能力上线后现有文本聊天功能零回归
- 报告和 PDF 中无越界诊断措辞
- `/reports` 继续稳定承载 legacy 监测摘要，不出现新旧报告混淆

## Acceptance Criteria

- 已登录患者可以创建或访问长期病历档案。
- 患者可以向档案中上传一张或多张病例图片，并可后续继续追加。
- 系统会持久保存原始病例图片及后续报告所需的抽取结果。
- 系统可以基于病例档案和 TremorGuard 监测数据生成详细但非诊断的健康报告。
- 系统在新增病例后可生成新版报告，且保留旧版历史。
- 患者可以查看报告历史和单个报告版本。
- 患者可以导出指定报告版本的 PDF。
- UI、API、持久化报告内容和 PDF 均带有明确非诊断边界文案。
- 现有 `POST /v1/ai/chat` 文本聊天能力保持不变。
- 新功能的 `/records` 报告与现有 `/reports` legacy 报告在产品文案和数据来源上明确区分。
- 现有 legacy `POST /v1/reports` 生成监测摘要报告的能力保持可用，且与新 medical records 报告写路径严格分离。

## Available Agent Types Roster

- planner: 拆阶段、定里程碑、维护依赖关系
- architect: 收敛领域边界、数据模型、接口和演进路径
- executor: 分阶段实现后端、前端、PDF、集成逻辑
- designer: 规划档案/报告 UX 与信息架构
- test-engineer: 建测试矩阵、回归策略、验收用例
- verifier: 做最终证据核查、边界检查、回归确认
- security-reviewer: 检查隐私、鉴权、文件访问和审计风险
- code-reviewer: 在大阶段完成后做整体质量检查
