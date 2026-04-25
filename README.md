# TremorGuard

TremorGuard（震颤卫士）是一个围绕帕金森震颤监测与康复支持的项目原型仓库，当前仓库覆盖三个交付面：

- 患者侧 Web 前端原型
- FastAPI 后端与演示数据
- ESP32 + MPU6050 设备侧 I2C bring-up 工具

项目目标是把硬件采集、云端数据处理、AI 辅助解读和患者应用串成一条可演示、可迭代的闭环。当前仓库更适合作为课程项目、原型验证和接口联调基础，而不是生产级医疗系统。

## 项目范围

当前实现聚焦一期能力：

- 患者注册、登录与 onboarding 流程
- 震颤概览、趋势查看和设备状态展示
- 用药记录与康复指导页面
- 医疗档案上传、结构化处理与报告导出
- AI 问答与行动卡片式交互
- 设备数据接入接口与演示数据种子

项目明确保留医疗安全边界：

- 不应将本项目描述为诊断系统
- 不应将 AI 输出描述为处方或临床结论
- 当前 AI 能力用于健康信息解释、康复建议整理和报告辅助生成

## 仓库结构

```text
TremorGuard/
├── tremor-guard-frontend/    # Vite + React + TypeScript 前端原型
├── tremor-guard-backend/     # FastAPI + SQLAlchemy 2 后端
├── I2C_Scanner/              # ESP32 I2C 扫描 Arduino 草图
├── docs/                     # 系统架构、项目介绍与 PRD 参考文档
├── docker-compose.yml        # 本地全栈容器编排
└── README.md
```

关键参考文件：

- [docs/system_architecture.md](/Users/peng/Documents/trae_projects/TremorGuard/docs/system_architecture.md)
- [tremor-guard-backend/README.md](/Users/peng/Documents/trae_projects/TremorGuard/tremor-guard-backend/README.md)
- [tremor-guard-frontend/README.md](/Users/peng/Documents/trae_projects/TremorGuard/tremor-guard-frontend/README.md)

## 技术栈

- 前端：React 19、TypeScript、Vite、React Router、Tailwind CSS
- 后端：FastAPI、SQLAlchemy 2、Alembic、Pydantic Settings、Uvicorn
- 数据层：默认可直接使用本地 SQLite 演示库，也支持通过 `docker-compose.yml` 启动 PostgreSQL / TimescaleDB
- AI 集成：预留 DashScope 兼容接口，用于 AI 聊天、康复建议和医疗记录处理
- 硬件：ESP32、MPU6050、Arduino Sketch

## 系统分层

仓库内文档将 TremorGuard 拆成四层：

1. 硬件层：ESP32 + MPU6050 负责运动数据采集、边缘预处理和缓存
2. 云端层：接收数据、存储、特征提取、认证与 API 暴露
3. AI 层：知识检索、问答生成、报告辅助生成与安全边界控制
4. 应用层：患者端 Web / App 交互、数据可视化、报告与康复指导

完整设计说明见 [docs/system_architecture.md](/Users/peng/Documents/trae_projects/TremorGuard/docs/system_architecture.md)。

如果你需要先理解患者侧一期的主业务、信息架构和 AI 服务边界，再看技术实现，优先阅读 [docs/patient_business_architecture.md](/Users/peng/Documents/trae_projects/TremorGuard/docs/patient_business_architecture.md)。该文档负责说明“患者接入、监测与记录、AI 解读、康复建议、复诊沟通”这条主业务链如何拆成业务域和页面结构。

## 本地启动

### 方式一：分别启动前后端

后端：

```bash
cd /Users/peng/Documents/trae_projects/TremorGuard/tremor-guard-backend
./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

前端：

```bash
cd /Users/peng/Documents/trae_projects/TremorGuard/tremor-guard-frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

访问地址：

- 前端：[http://127.0.0.1:5173/login](http://127.0.0.1:5173/login)
- 后端 API 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- 后端健康检查：[http://127.0.0.1:8000/healthz](http://127.0.0.1:8000/healthz)

说明：

- 后端需优先使用仓库内 `tremor-guard-backend/.venv`，因为项目要求 Python 3.12。
- 前端默认请求 `http://127.0.0.1:8000`，无需额外配置即可联调本地后端。

### 方式二：使用 Docker Compose

如果你想连同数据库容器一起启动，可在仓库根目录执行：

```bash
cd /Users/peng/Documents/trae_projects/TremorGuard
docker compose up --build
```

这个方案会启动：

- API 服务：`8000`
- 临床数据库：宿主机 `5433`
- 身份数据库：宿主机 `5434`

## 首次初始化

如果后端虚拟环境或数据库尚未准备好，可在后端目录执行：

```bash
cd /Users/peng/Documents/trae_projects/TremorGuard/tremor-guard-backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m app.scripts.run_migrations
python -m app.scripts.seed
```

前端首次安装依赖：

```bash
cd /Users/peng/Documents/trae_projects/TremorGuard/tremor-guard-frontend
npm install
```

## 演示账号

默认演示账号：

- 邮箱：`patient@tremorguard.local`
- 密码：`tg-demo-password`

默认演示设备信息：

- 可绑定设备序列号：`TG-V1.0-ESP-7B31`
- 演示设备密钥：`tg-device-demo-key`

更多信息可参考后端配置与登录页默认值：

- [tremor-guard-backend/app/core/config.py](/Users/peng/Documents/trae_projects/TremorGuard/tremor-guard-backend/app/core/config.py)
- [tremor-guard-frontend/src/pages/login-page.tsx](/Users/peng/Documents/trae_projects/TremorGuard/tremor-guard-frontend/src/pages/login-page.tsx)

## 常用开发命令

前端：

```bash
cd /Users/peng/Documents/trae_projects/TremorGuard/tremor-guard-frontend
npm run dev
npm run build
npm run lint
npm run preview
```

后端：

```bash
cd /Users/peng/Documents/trae_projects/TremorGuard/tremor-guard-backend
./.venv/bin/python -m uvicorn app.main:app --reload
./.venv/bin/python -m pytest
./.venv/bin/python -m ruff check .
./.venv/bin/python -m app.scripts.export_openapi
```

## 主要接口与前端页面

后端当前已接入的主要 API 组包括：

- `/v1/auth`
- `/v1/me`
- `/v1/dashboard`
- `/v1/medications`
- `/v1/rehab-guidance`
- `/v1/reports`
- `/v1/medical-records`
- `/v1/devices`
- `/v1/ingest`
- `/v1/ai`

前端主要页面包括：

- `/login`
- `/register`
- `/overview`
- `/medication`
- `/rehab-guidance`
- `/records`
- `/reports`
- `/profile`
- `/ai-doctor`

路由定义见 [tremor-guard-frontend/src/router.tsx](/Users/peng/Documents/trae_projects/TremorGuard/tremor-guard-frontend/src/router.tsx)。

这些路由反映的是当前页面与实现入口，不等于患者侧主业务链本身。患者主业务与信息架构的上位说明见 [docs/patient_business_architecture.md](/Users/peng/Documents/trae_projects/TremorGuard/docs/patient_business_architecture.md)。

## 硬件目录说明

`I2C_Scanner/I2C_Scanner.ino` 是用于 ESP32 设备 bring-up 的辅助工具，不是正式固件。它主要用于：

- 检查 I2C 总线是否连通
- 确认传感器地址是否被识别
- 协助 MPU6050 等外设初期接线排障

该工具默认串口波特率为 `115200`。

## 文档入口

`docs/` 目录包含与产品和系统设计有关的材料：

- `patient_business_architecture.md`：患者侧一期业务架构、信息架构与 AI 服务边界
- `system_architecture.md`：分层架构与数据流说明
- `system_architecture.drawio`：架构图源文件
- `项目介绍.pdf`：项目介绍材料
- `震颤卫士PRD构建指南.md`：PRD 编写与拆解参考

## 验证建议

提交前建议至少执行：

```bash
cd /Users/peng/Documents/trae_projects/TremorGuard/tremor-guard-frontend
npm run lint
npm run build
```

```bash
cd /Users/peng/Documents/trae_projects/TremorGuard/tremor-guard-backend
./.venv/bin/python -m pytest
./.venv/bin/python -m ruff check .
```

如果只改文档，至少检查：

- 术语是否与架构文档一致
- 路径、命令、端口是否与仓库现状一致
- 是否把原型能力误写成已落地的正式医疗能力

## 当前状态与限制

- 前端和后端都已具备本地演示与接口联调能力
- 后端默认基于本地 SQLite 演示库即可运行
- AI 相关能力在未配置 `DASHSCOPE_API_KEY` 时会受到限制
- 硬件目录当前只包含 bring-up 工具，不包含完整设备固件
- 项目仍处于原型阶段，需避免对外表述为正式医疗产品
