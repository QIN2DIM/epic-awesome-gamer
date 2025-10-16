# Epic Awesome Gamer - GitHub Actions 工作流

> ⚡ **快速开始**：按照下方教程，从创建仓库到首次运行只需10分钟！

## 前置要求

在开始之前，请确保您已准备：

✅ GitHub 账号（免费即可）  
✅ Epic Games 账号（需关闭二步验证）  
✅ Google 账号（用于获取免费的 Gemini API）  

⚠️ **重要提醒**：Epic Games 账号必须关闭二步验证（2FA），否则自动化流程无法正常工作。

## 功能特性

✅ **定时执行**：默认每天15:55 (UTC)自动运行一次  
✅ **手动触发**：支持通过 Actions 界面手动执行  
✅ **私有仓库检测**：仅在私有仓库中运行，保护账号安全  
✅ **数据持久化**：使用独立分支存储用户数据，实现跨运行的状态保持  
✅ **超时保护**：15分钟自动超时，防止无限运行  
✅ **完整日志**：自动保存运行日志和截图

## 完整设置教程

### 步骤1：创建私有仓库

⚠️ **重要**：出于安全考虑，此工作流只能在私有仓库中运行！

1. 访问 [GitHub](https://github.com) 并登录您的账号
2. 点击右上角的 "+" 按钮，选择 "New repository"
3. **Repository name**: 输入 `gamer-nx892`（或您喜欢的名称，请不要出现 `epic` 和 `爬虫` 等敏感词）
4. ⚠️ **重要**：勾选 "Private" 选项（私有仓库）
5. 勾选 "Add a README file"
6. 点击 "Create repository"

### 步骤2：上传工作流文件

1. **创建目录结构**：
   - 在您的仓库主页点击 "Add file" → "Create new file"
   - 在文件名输入框中输入：`.github/workflows/epic-gamer.yml`
   - GitHub 会自动创建目录结构

2. **粘贴工作流内容**：
   - 将下方的完整 YAML 内容复制并粘贴到编辑器中
   - 点击页面底部的 "Commit new file"

<details>
<summary>📄 点击展开完整的工作流文件内容（epic-gamer.yml）</summary>

```yaml
name: Epic Awesome Gamer

on:
  # Manual trigger
  workflow_dispatch:

  # Scheduled trigger - run once daily at 15:55 (UTC)
#  schedule:
#    - cron: '55 15 * * *'

jobs:
  epic-gamer:
    runs-on: ubuntu-latest
    timeout-minutes: 20

    steps:
      # Check if repository is private
      - name: Check repository visibility
        run: |
          if [[ "${{ github.event.repository.private }}" != "true" ]]; then
            echo "⚠️ This workflow must be run in a private repository for security reasons."
            echo "Please fork this repository and make it private before running this workflow."
            exit 0
          fi
          echo "✅ Running in private repository"

      # Checkout repository
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 1
          token: ${{ secrets.GITHUB_TOKEN }}

      # Switch to data-persistence branch
      - name: Switch to data-persistence branch
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          
          git fetch origin --prune
          
          if git ls-remote --exit-code --heads origin data-persistence >/dev/null 2>&1; then
            echo "Switching to existing data-persistence branch..."
            git checkout -B data-persistence origin/data-persistence
          else
            echo "Creating new data-persistence branch..."
            git checkout -b data-persistence
            git push -u origin data-persistence
          fi

      # Clone epic-awesome-gamer source code
      - name: Clone epic-awesome-gamer repository
        run: |
          echo "Cloning epic-awesome-gamer source code..."
          git clone https://github.com/QIN2DIM/epic-awesome-gamer.git epic-gamer-src
          echo "✅ Source code cloned successfully"

      - name: Install uv
        uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
          version: '0.8.0'

      - name: "Set up Python"
        uses: actions/setup-python@v5
        with:
          python-version-file: "./epic-gamer-src/pyproject.toml"

      # Install dependencies
      - name: Install dependencies
        working-directory: ./epic-gamer-src
        run: uv sync

      # Install system dependencies for browser automation
      - name: Install system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y xvfb

      # Install Playwright browsers with retry logic
      - name: Install Playwright browsers
        working-directory: ./epic-gamer-src
        run: |
          for i in {1..3}; do
            if uv run camoufox fetch; then
              echo "✅ Camoufox fetch successful (attempt $i)"
              break
            else
              echo "❌ Camoufox fetch attempt $i failed"
              if [[ $i -lt 3 ]]; then
                echo "⏳ Waiting 5 seconds before retry..."
                sleep 5
              else
                echo "⚠️ All camoufox fetch attempts failed"
                exit 1
              fi
            fi
          done

      # Run Epic Awesome Gamer
      - name: Run Epic Awesome Gamer
        working-directory: ./epic-gamer-src
        env:
          EPIC_EMAIL: ${{ secrets.EPIC_EMAIL }}
          EPIC_PASSWORD: ${{ secrets.EPIC_PASSWORD }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          ENABLE_APSCHEDULER: false
        run: |
          echo "Starting Epic Awesome Gamer..."
          xvfb-run --auto-servernum --server-num=1 --server-args='-screen 0, 1920x1080x24' uv run app/deploy.py
          echo "Execution completed"

      # Copy generated volumes to current repository
      - name: Copy generated volumes to current repository
        if: always()
        run: |
          echo "Copying generated volumes from source to current repository..."
          mkdir -p app/volumes
          if [ -d "epic-gamer-src/app/volumes" ]; then
            cp -r epic-gamer-src/app/volumes/* app/volumes/ 2>/dev/null || echo "No volumes content to copy"
            echo "✅ Volumes copied successfully"
          else
            echo "⚠️ No volumes directory found in source"
          fi

      # Check generated files
      - name: Check generated files
        if: always()
        run: |
          echo "Checking app volumes content after execution:"
          find app/volumes -type f -name "*" -exec ls -la {} \; 2>/dev/null || echo "No files found in app/volumes"

      # Commit and push app/volumes data
      - name: Commit and push app volumes data
        if: always()
        run: |
          git checkout data-persistence
          
          echo "Current git status:"
          git status
          
          echo "Files in app/volumes:"
          find app/volumes -type f -name "*" 2>/dev/null || echo "No files in app/volumes"
          
          git add app/volumes/ || true
          
          if git diff --staged --quiet; then
            echo "✅ No changes to commit - volumes may be empty or unchanged"
          else
            TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
            CHANGED_FILES=$(git diff --staged --name-only | wc -l)
          
            echo "📝 Committing $CHANGED_FILES changed files..."
          
            git commit -m "🔄 Update persistence data - $TIMESTAMP" \
              -m "📊 Workflow run: ${{ github.run_id }}" \
              -m "🚀 Triggered by: ${{ github.event_name }}" \
              -m "📁 Files changed: $CHANGED_FILES" || {
              echo "⚠️ Commit failed, but continuing..."
            }
          
            echo "📤 Pushing changes to remote..."
            for i in {1..3}; do
              if git push origin data-persistence; then
                echo "✅ Successfully pushed changes (attempt $i)"
                break
              else
                echo "❌ Push attempt $i failed, retrying in 5 seconds..."
                sleep 5
                if [[ $i -eq 3 ]]; then
                  echo "⚠️ All push attempts failed"
                fi
              fi
            done
          fi
```

</details>

### 步骤3：获取 Gemini API 密钥

在配置 Secrets 之前，您需要获取 Google Gemini API 密钥：

1. 访问 [Google AI Studio](https://aistudio.google.com/apikey)
2. 使用您的 Google 账号登录
3. 点击 "Create API Key"
4. 选择一个 Google Cloud 项目（或创建新项目）
5. 复制生成的 API 密钥并妥善保存

### 步骤4：配置 Secrets

在仓库设置中添加以下敏感信息：

| Secret 名称 | 说明 |
|------------|------|
| `EPIC_EMAIL` | 您的 Epic Games 账号邮箱<br>⚠️ 需要关闭二步验证 |
| `EPIC_PASSWORD` | 您的 Epic Games 账号密码<br>⚠️ 需要关闭二步验证 |
| `GEMINI_API_KEY` | Google Gemini API 密钥<br>从步骤3获取 |

**详细添加步骤**：
1. 在您的仓库页面，点击顶部的 "Settings" 标签
2. 在左侧菜单中找到 "Secrets and variables" → 点击 "Actions"
3. 点击 "New repository secret" 按钮
4. 输入 Secret 名称（如 `EPIC_EMAIL`）
5. 输入对应的值
6. 点击 "Add secret"
7. 重复步骤3-6，添加所有3个 Secret

### 步骤5：设置工作流权限

为了让工作流能够创建和管理 `data-persistence` 分支：

1. 在仓库 Settings 页面
2. 点击左侧菜单的 "Actions" → "General"
3. 滚动到 "Workflow permissions" 部分
4. 选择 "Read and write permissions"
5. 勾选 "Allow GitHub Actions to create and approve pull requests"
6. 点击 "Save" 保存设置

### 步骤6：启用 Actions

如果这是您的第一个工作流：

1. 点击仓库顶部的 "Actions" 标签
2. 如果看到提示页面，点击 "I understand my workflows, go ahead and enable them"
3. 您应该能看到 "Epic Awesome Gamer" 工作流

### 步骤7：首次手动运行

完成所有配置后，立即测试工作流：

1. **进入 Actions 页面**：
   - 点击仓库顶部的 "Actions" 标签

2. **选择工作流**：
   - 在左侧工作流列表中，点击 "Epic Awesome Gamer"

3. **手动触发**：
   - 点击右侧的 "Run workflow" 按钮
   - 确认分支选择为 "main"（或您的默认分支）
   - 点击绿色的 "Run workflow" 按钮

4. **监控执行**：
   - 页面会刷新，显示新的运行记录
   - 点击运行记录查看详细执行过程
   - 整个过程大约需要3-10分钟

5. **检查结果**：
   - 如果成功，工作流状态会显示绿色的 ✅
   - 如果失败，会显示红色的 ❌，点击查看错误日志

## 使用方法

### 手动运行

完成初始设置后，您可以随时手动运行：

1. 进入 Actions 标签页
2. 选择 "Epic Awesome Gamer" 工作流
3. 点击 "Run workflow"
4. 选择分支（通常是 main）
5. 点击绿色的 "Run workflow" 按钮

### 查看运行结果

1. 点击正在运行或已完成的工作流
2. 查看各步骤的执行日志
3. 在 "Artifacts" 部分下载日志和截图

### 数据持久化

- 用户数据自动保存在 `data-persistence` 分支
- 包括登录状态、缓存等信息
- 每次运行都会自动加载和更新这些数据

## 注意事项

1. **安全提醒**：
   - 必须在私有仓库运行
   - 妥善保管您的账号密码
   - 定期检查 Secrets 是否泄露

2. **运行限制**：
   - GitHub Actions 每月有免费额度限制（私有仓库 2000 分钟）
   - 请合理安排运行频率

3. **故障排查**：
   - 如果任务失败，检查 Actions 日志
   - 常见问题：网络超时、验证码识别失败、账号状态异常
   - 可以通过 Artifacts 下载截图查看具体情况

## 定时任务配置

### 启用定时运行

默认情况下，工作流仅支持手动触发。如需启用定时自动运行，请按以下步骤操作：

1. 编辑 `.github/workflows/epic-gamer.yml` 文件
2. 找到被注释的 schedule 部分：
   ```yaml
   # schedule:
   #   - cron: '55 15 * * *'
   ```
3. 去掉注释符号，改为：
   ```yaml
   schedule:
     - cron: '55 15 * * *'
   ```

### 定时表达式说明

`55 15 * * *` 表示：
- 每天的15:55 (UTC时间)运行一次
- 对应北京时间 23:55（UTC+8）
- 对应纽约时间 10:55/11:55（根据夏令时而定）

您可以使用 [crontab.guru](https://crontab.guru/) 来测试和生成自定义的定时表达式。

**时区转换参考**：
- UTC 15:55 = 北京时间 23:55
- UTC 15:55 = 东京时间 00:55+1天
- UTC 15:55 = 伦敦时间 15:55/16:55（根据夏令时）
- UTC 15:55 = 纽约时间 10:55/11:55（根据夏令时）

**建议**：首次使用时建议先手动运行几次，确保工作流稳定后再启用定时任务。

## 常见问题

**Q: 为什么必须在私有仓库运行？**  
A: 工作流需要访问您的 Epic Games 账号信息，在公开仓库运行可能导致信息泄露。

**Q: 首次运行出现 "Checkout repository" 错误怎么办？**  
A: 这是正常现象！首次运行时 `data-persistence` 分支不存在，工作流会自动创建。如果看到此错误：
- 等待工作流自动重试（通常会在几秒后成功）
- 或者手动重新运行工作流
- 第二次运行时就不会再出现此问题

**Q: 如何查看领取了哪些游戏？**  
A: 查看 Actions 运行日志，或下载 Artifacts 中的日志文件。

**Q: 运行失败怎么办？**  
A: 检查错误日志，常见原因包括：
- **Git 分支问题**：首次运行时正常，重新运行即可
- **账号密码错误**：检查 Secrets 配置
- **开启了二步验证**：必须关闭 Epic Games 账号的2FA
- **网络连接问题**：GitHub Actions 网络不稳定，重试即可
- **API 密钥无效**：检查 Gemini API 密钥是否正确

**Q: 数据存储在哪里？**  
A: 持久化数据存储在 `data-persistence` 分支，包括：
- `/volumes/user_data/` - 用户数据和登录状态
- `/volumes/logs/` - 运行日志
- `/volumes/runtime/` - 运行时数据和截图 
