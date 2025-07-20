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
  # 手动触发
  workflow_dispatch:
  
  # 定时触发 - 每天15:55 (UTC)运行一次
  schedule:
    - cron: '55 15 * * *'

jobs:
  epic-gamer:
    runs-on: ubuntu-latest
    timeout-minutes: 15  # 15分钟超时限制
    
    steps:
      # 检查是否为私有仓库
      - name: Check repository visibility
        run: |
          if [[ "${{ github.event.repository.private }}" != "true" ]]; then
            echo "⚠️ This workflow must be run in a private repository for security reasons."
            echo "Please fork this repository and make it private before running this workflow."
            exit 0
          fi
          echo "✅ Running in private repository"
      
      # 检出代码
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # 获取完整历史，便于分支操作
          
      # 创建或切换到 data-persistence 分支
      - name: Setup data-persistence branch
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          
          # 检查远程分支是否存在
          if git ls-remote --heads origin data-persistence | grep -q data-persistence; then
            echo "data-persistence branch exists, checking out..."
            git checkout data-persistence
          else
            echo "Creating new data-persistence branch..."
            git checkout -b data-persistence
            
            # 创建必要的目录结构
            mkdir -p volumes/user_data
            mkdir -p volumes/logs
            mkdir -p volumes/runtime
            
            # 创建 .gitkeep 文件以保持目录结构
            touch volumes/user_data/.gitkeep
            touch volumes/logs/.gitkeep
            touch volumes/runtime/.gitkeep
            
            # 提交初始结构
            git add volumes/
            git commit -m "Initialize persistence directories" || echo "No changes to commit"
            git push -u origin data-persistence
          fi
      
      # 准备持久化目录
      - name: Prepare volumes
        run: |
          # 确保目录存在且有正确的权限
          mkdir -p ${{ github.workspace }}/volumes/user_data
          mkdir -p ${{ github.workspace }}/volumes/logs
          mkdir -p ${{ github.workspace }}/volumes/runtime
          chmod -R 777 ${{ github.workspace }}/volumes
          
      # 运行容器
      - name: Run Epic Awesome Gamer
        run: |
          docker run \
            --rm \
            --name epic-awesome-gamer \
            --memory="4g" \
            --memory-swap="4g" \
            --shm-size="2gb" \
            -e EPIC_EMAIL="${{ secrets.EPIC_EMAIL }}" \
            -e EPIC_PASSWORD="${{ secrets.EPIC_PASSWORD }}" \
            -e GEMINI_API_KEY="${{ secrets.GEMINI_API_KEY }}" \
            -v "${{ github.workspace }}/volumes/user_data:/app/app/user_data" \
            -v "${{ github.workspace }}/volumes/logs:/app/app/logs" \
            -v "${{ github.workspace }}/volumes/runtime:/app/app/runtime" \
            --entrypoint "/usr/bin/tini" \
            ghcr.io/qin2dim/epic-awesome-gamer:latest \
            -- xvfb-run --auto-servernum --server-num=1 --server-args='-screen 0, 1920x1080x24' uv run app/deploy.py
      
      # 提交持久化数据更新
      - name: Commit and push persistence data
        if: always()  # 即使任务失败也要保存数据
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          
          # 添加所有更改（包括日志）
          git add volumes/ || true
          
          # 检查是否有更改
          if git diff --staged --quiet; then
            echo "No changes to commit"
          else
            # 生成提交信息
            TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
            git commit -m "Update persistence data - $TIMESTAMP" \
              -m "Workflow run: ${{ github.run_id }}" \
              -m "Triggered by: ${{ github.event_name }}"
            
            # 推送更改
            git push origin data-persistence
          fi
          
      # 上传日志作为 Artifacts（备份用途）
      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: epic-gamer-logs-${{ github.run_id }}
          path: volumes/logs/
          retention-days: 7
          
      # 上传运行时数据作为 Artifacts（备份用途）
      - name: Upload runtime data
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: epic-gamer-runtime-${{ github.run_id }}
          path: volumes/runtime/
          retention-days: 7
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