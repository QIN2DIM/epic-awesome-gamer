<div align="center">
    <h1> EPIC 免费人</h1>
    <p>🍷 Gracefully claim weekly free games from Epic Store.</p>
    <img src="https://img.shields.io/static/v1?message=reference&color=blue&style=for-the-badge&logo=micropython&label=python">
    <img src="https://img.shields.io/github/license/QIN2DIM/epic-awesome-gamer?style=for-the-badge">
    <a href="https://hub.docker.com/r/ech0sec/awesome-epic"><img src="https://img.shields.io/docker/pulls/ech0sec/awesome-epic?color=green&style=for-the-badge"></a>
	<a href=""><img src="https://img.shields.io/github/actions/workflow/status/QIN2DIM/epic-awesome-gamer/ci_docker_fish.yaml?style=for-the-badge"></a>
	<br>
    	<a href="https://discord.gg/KA66wZBQ"><img alt="Discord" src="https://img.shields.io/discord/978108215499816980?style=social&logo=discord&label=echosec"></a>
	<a href="https://t.me/+Wdtxnn1yxU5jMmY5"><img src="https://img.shields.io/static/v1?style=social&logo=telegram&label=chat&message=studio" ></a>
	<br>
	<br>
</div>


![scaffold-get-demo-output-small](https://github.com/QIN2DIM/img_pool/blob/main/img/scaffold-get-demo-output-small.gif)

## Introduction 👋

[Epic 免费人](https://github.com/QIN2DIM/epic-awesome-gamer) 帮助玩家优雅地领取免费游戏。内置 [hcaptcha-challenger](https://github.com/QIN2DIM/hcaptcha-challenger) AI 模块，直面人机挑战。

## Features

| Component | Support |
| :------------------- | :------ |
| hCaptcha Solver      | ✅       |
| Docker Compose | ✅       |
| Persistent context @multi-user |   ✅      |
| Epicgames DLC | 🚧 |
| 2FA OTP support | 🚧 |

## Documentation

### 🚀 快速开始

我们推荐使用 Docker Compose 进行一键部署，这是最简单、最稳定的运行方式。

#### 1. 克隆代码仓库

首先，将本仓库克隆至你的本地环境，并进入 `docker` 工作目录：

```bash
git clone https://github.com/QIN2DIM/epic-awesome-gamer.git
cd epic-awesome-gamer/docker
```

#### 2. 配置环境变量

接下来，配置你的专属环境变量。我们提供了一份 `.env.example` 模板，请以它为蓝本创建 `.env` 文件：

```bash
cp .env.example .env
```

随后，使用你偏爱的编辑器（如 `vim` 或 `nano`）调整 `.env` 文件中的配置项。各项配置的详细说明，请参考下文的 [**⚙️ 环境变量**](#️-环境变量) 部分。

#### 3. 启动服务

一切就绪，启动容器！我们提供了一个便捷的启动脚本：

```bash
# 赋予脚本执行权限
chmod +x ./start.sh

# 启动服务
./start.sh
```

当然，你也可以直接使用 `docker compose` 命令进行部署，这能让你更好地控制服务生命周期。项目的编排文件位于 [docker-compose.yaml](https://github.com/QIN2DIM/epic-awesome-gamer/blob/main/docker/docker-compose.yaml)。

```bash
# 后台启动服务
docker compose up -d
```

### ☁️ 其他部署方式（CI/CD）

如果你希望将 `epic-awesome-gamer` 集成到 `GitHub Actions` 或 `GitLab CI` 等自动化工作流中，完全没问题！

本项目核心逻辑清晰，稍作调整即可轻松适配各类云端定时任务。欢迎动手能力强的朋友们探索与分享！

### ⚙️ 环境变量

以下是项目运行所必需的环境变量，请确保每一项都已正确配置，否则程序将无法启动。

| 环境变量         | required | 说明                                                         |
| ---------------- | -------- | ------------------------------------------------------------ |
| `EPIC_EMAIL`     | **YES**  | 你的 Epic 游戏账号。<br>⚠️ **注意**：请预先禁用该账户的二步验证（2FA）。 |
| `EPIC_PASSWORD`  | **YES**  | 你的 Epic 游戏密码。<br>⚠️ **注意**：同上，请确保已禁用二步验证。 |
| `GEMINI_API_KEY` | **YES**  | 用于接入 Google Gemini Pro Vision 多模态大模型，以应对登录过程中可能出现的**人机验证（hCaptcha）**。<br>你可以从 [Google AI Studio](https://aistudio.google.com/apikey) 免费获取，其提供的免费额度足以支撑日常使用。 |

> [!TIP]
> 其他环境变量主要用于微调 hCaptcha Challenger 的内部行为，通常情况下，你无需关心或修改它们，保持默认即可。

### 🖼️ 项目展示 (Gallery)

这里展示了一些项目在早期开发阶段的运行截图，记录了它曾经的“全盛时期”。

由于目前维护重心已转向核心逻辑的稳定与优化，此处的展示内容可能略显陈旧。我们热烈欢迎社区伙伴通过 **Pull Request** 提交更棒的截图或 GIF 动图，共同完善这一部分！

👉 [**点击查看项目演示 (Notion)**](https://www.google.com/url?sa=E&q=https%3A%2F%2Fechosec.notion.site%2FDemonstration-008fc2ff5324488caff65cadef3defca)
