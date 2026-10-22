# 校园票务与智能分析系统（campus-ticket）

面向高校校园活动场景的票务管理系统，在常规的"发布活动—在线抢票—扫码核销"链路上，
叠加了两个智能模块：**抢票风控**（在线规则引擎 + 离线孤立森林检测）与
**活动评论情感分析**（TF-IDF + LinearSVC 四分类）。

系统源码、离线实验脚本与可复现的实验数据都在本仓库内：
实现细节见第六节，实验与压测的复现步骤见第七节。

---

## 一、技术栈

| 层次 | 技术选型 |
| --- | --- |
| 后端框架 | Spring Boot 3.2.5（JDK 17） |
| 持久层 | MyBatis-Plus 3.5.5 + MySQL 8.0 |
| 鉴权 | Hutool JWT（自定义 `AuthInterceptor` + `@RequireRole`）+ BCrypt 口令散列 |
| 前端 | Vue 3 + Vite 5 + Element Plus + Vue Router |
| 风控（在线） | 内存滑动窗口规则引擎（R0 黑名单 / R1 单用户限频 / R2 同 IP 多账号） |
| 风控（离线） | Python 3.12 + pandas + scikit-learn（IsolationForest，10 维行为特征） |
| 情感分析 | Python 3.12 + scikit-learn（TF-IDF 字符级 1-2 元 + LinearSVC 四分类） |
| 可视化 | matplotlib（混淆矩阵、异常检测图） |

---

## 二、目录结构

```
campus-ticket/
├── src/main/java/com/example/campusticket/
│   ├── common/          # 通用组件：Result、JWT、动态二维码、脚本路径解析、业务异常
│   ├── config/          # 拦截器、MyBatis-Plus、全局异常、情感分析定时任务
│   ├── controller/      # 7 个 REST 控制器
│   ├── entity/ mapper/ service/   # 实体、Mapper（含乐观锁条件 UPDATE）、业务服务
│   └── risk/            # 风控：规则引擎、RiskService、离线检测调度
├── src/main/resources/
│   └── application.yml  # 配置模板（密钥/口令走占位符，真实值放本地 application-local.yml）
├── application-local.example.yml  # 本机配置模板（复制为 application-local.yml 使用）
├── environment.yml    # Python 侧 conda 环境定义（风控/情感分析脚本与离线实验用）
├── frontend/            # Vue 3 前端源码
├── docs/
│   ├── sql/
│   │   ├── schema.sql   # 8 张核心表建表脚本
│   │   ├── seed.sql     # 演示账号与示例活动
│   │   └── add_ban_fields.sql  # 封禁字段增量脚本
│   ├── diagrams/        # 系统插图源码与产物（功能树 / E-R 图 / 流程图引擎）
│   ├── system-architecture.html  # 系统架构图（可交互）
│   └── 抢票风控功能详细方案.md
├── risk-analysis/       # 抢票风控离线检测（导出 → 特征 → 孤立森林）
├── sentiment/
│   ├── predict_new.py   # 线上情感回填（60 秒定时任务调用）
│   ├── model_metrics.py # 指标读取 / 实时评估
│   └── experiments/     # 情感分析对比实验：数据集构建、四模型对比、混淆矩阵
├── tools/               # 辅助脚本（按用途分三类）
│   ├── loadtest/        #   压测：load_test / run_load_matrix
│   ├── verify/          #   验证：P0 回归、库存一致性、级联删除、安全用例
│   └── maintenance/     #   运维：密码重置、历史数据修复、页面截图
├── 一键打包.bat          # 前端构建 + 后端打包
└── 启动系统.bat          # 启动打包后的 jar
```

> 仓库只收系统源码、实验脚本与可复现的数据：本机配置、导出的中间数据集
> 与报告类产物一律不入库（见 `.gitignore`）。

---

## 三、环境准备

| 依赖 | 版本要求 | 说明 |
| --- | --- | --- |
| JDK | 17 | 项目 `java.version=17` |
| Maven | 3.9+（或使用自带 `mvnw`） | |
| MySQL | 8.0 | 默认端口 3306 |
| Node.js | 18+（开发用 22） | 仅前端构建需要 |
| Python | 3.12（Anaconda/Miniconda） | 依赖见根目录 `environment.yml`（numpy/scipy/pandas/scikit-learn/matplotlib + snownlp/pymysql/bcrypt） |

Python 依赖安装（**推荐用仓库自带的 `environment.yml`**）：

```bash
conda env create -f environment.yml
conda activate campus-ticket
```

> 为什么不用 `pip install` 一把梭：numpy/scipy/pandas/scikit-learn/matplotlib
> 都是带 C 扩展的包，必须来自**同一频道、同一批构建**。用 pip 单独升级其中一个
> （例如 `pip install opencv-python` 会顺手把 numpy 顶到 2.x），
> 其余按 numpy 1.x 编译的包会立刻 `ImportError: numpy.core.multiarray failed to import`。
> `environment.yml` 已把数值栈钉死在与离线实验一致的版本。

若坚持用 pip，注意 `snownlp / pymysql / bcrypt` 走 pypi，数值栈走 conda，不要混装：

```bash
conda install numpy=1.26.4 scipy=1.13.1 pandas=2.2.2 scikit-learn=1.4.2 matplotlib=3.8.4 pillow
pip install snownlp pymysql bcrypt
```

> Python 解释器路径在 `application-local.yml` 中配置（本机文件，不入库）：
> `risk.python-path` 与 `sentiment.python-path` 默认 `python`（走 PATH）；
> 若用 conda 专用环境，请填该环境 `python.exe` 的绝对路径，例如
> `D:/Anaconda/envs/campus-ticket/python.exe`（Windows 下用正斜杠即可）。

---

## 四、数据库初始化

```bash
# 1. 建库
mysql -uroot -p -e "CREATE DATABASE campus_ticket DEFAULT CHARACTER SET utf8mb4;"

# 2. 建表（8 张核心表）
mysql -uroot -p campus_ticket < docs/sql/schema.sql

# 3. 演示数据（5 个账号 + 1 个示例活动）
mysql -uroot -p campus_ticket < docs/sql/seed.sql
```

随后配置本机参数。仓库里的 `application.yml` 是模板（密钥为占位符），真实值放在**不入库**的 `application-local.yml`：

```bash
# Windows
copy application-local.example.yml application-local.yml
# Linux/macOS
cp application-local.example.yml application-local.yml
```

打开 `application-local.yml` 填三项：

```yaml
spring:
  datasource:
    username: root
    password: "你的 MySQL 口令"

jwt:
  secret: "随机长串"      # python -c "import secrets;print(secrets.token_urlsafe(32))"

qrcode:
  secret: "另一个随机长串"
```

`application.yml` 用 `${JWT_SECRET:...}` 这类占位符读取，环境变量与 `application-local.yml` 都可以覆盖；`application-local.yml` 已在 `.gitignore` 里。

### 演示账号（初始口令均为 `123456`）

| 用户名 | 角色 | 说明 |
| --- | --- | --- |
| `admin` | 管理员 | 风控监控、情感分析中心、封禁解封 |
| `organizer01` | 组织者 | 发布/编辑活动与票种、查看出勤统计 |
| `student01` | 学生 | 抢票、我的票券、出示动态二维码、评论 |
| `checker01` | 核销员 | 扫码核销、核销记录查询 |
| `zhangsan` | 组织者 | 备用组织者账号 |

---

## 五、启动方式

### 开发模式（前后端分离）

```bash
# 后端（8080）
./mvnw spring-boot:run

# 前端（Vite 开发服务器，已配置 /api 代理）
cd frontend
npm install
npm run dev
```

### 生产模式（单 jar 运行）

```bash
# 一键：构建前端 → 拷贝到 static → Maven 打包
一键打包.bat

# 启动
启动系统.bat
# 或
java -jar target/campus-ticket-0.1.0.jar
```

访问 <http://localhost:8080>。

---

## 六、核心业务说明

### 6.1 抢票（乐观锁防超卖）

抢票流程在**同一事务**内依次执行：

1. 风控在线校验（R0 黑名单 → R1 单用户限频 → R2 同 IP 多账号）
2. 活动状态与抢票时间窗校验
3. 一人一票校验（订单表 `user_id + activity_id` 计数）
4. 票种库存预检 → 票种级条件 UPDATE 扣减
5. 活动总库存预检 → 活动级条件 UPDATE 扣减
6. 生成订单与电子票（票号 + 静态 `qr_content`）

两处库存扣减均为**条件更新**，由数据库行锁保证原子性：

```sql
UPDATE ticket   SET remain_stock = remain_stock - 1, version = version + 1
 WHERE id = #{id} AND version = #{version} AND remain_stock > 0;

UPDATE activity SET remain_stock = remain_stock - 1, version = version + 1
 WHERE id = #{activityId} AND version = #{version} AND remain_stock > 0;
```

两次扣减之间存在**写后写**依赖：若活动级扣减失败，服务层抛出
`BusinessException` 触发事务回滚（`return Result.error(...)` 不会回滚），
避免出现"票种库存已扣、订单与电子票未生成"的脏数据。

**控制层有限次重试（防"假售罄"）**：单次条件更新未命中时会抛
`BusinessException("抢票失败，请重试", "VERSION_CONFLICT")`，由
`ActivityController#grabTicket` 捕获并重试，最多 40 次，每次退避
`min(2 + attempt × 2, 25)` 毫秒再加 0~5 毫秒随机抖动。

之所以必须重试：并发线程都在同一时刻读到了相同的 `version`，只有第一个
条件更新会命中，其余全部失败；若不重试，即使库存尚未售罄，用户也会收到
"抢票失败，请重试"——即**假售罄**。实测 8 次重试在库存与并发数接近时仍有
约 1/3 的请求误报失败，20 次在 100/200 并发下仍有 5~17 张票卖不出去，
40 次可在 50/100/200 并发下把库存全部卖出且不超卖。

风控在线校验放在**重试循环之外**只判定一次，避免重试被重复计入 R1 滑动窗口。

### 6.1.1 活动删除的级联清理

删除活动时在**同一事务**内级联清理该活动的票种、订单、电子票、核销记录与
评论，避免遗留孤儿数据（学生的"我的票券"、组织者的核销记录、评论排行中
都不应再出现已删除活动的数据）。`grab_log` 作为风控审计日志**保留不删**。

### 6.2 动态二维码核销

- 学生端每 3 秒请求一次 `/ticket/qrcode`，服务端生成 `票号.时间戳.签名`，
  签名 = `SHA256(票号 & 时间戳 & 密钥)`
- 核销端扫码后调用 `/checkin/verify`，服务端校验签名与时间窗
  （`|now - ts| ≤ 3s + 2s 时钟容差`），再以
  `UPDATE eticket SET status=1 WHERE id=? AND status=0` 的受影响行数
  保证**一票一核**（并发重复核销只会有一次成功）
- 验票时间窗为活动开始前 1 小时至活动结束

### 6.3 风控：在线 + 离线双引擎

**在线层**（`RiskRuleEngine`，内存滑动窗口）：

| 规则 | 判定 | 处置 |
| --- | --- | --- |
| R0 黑名单 | `sys_user.status=0` 且未过 `ban_expire_time` | 登录与抢票入口直接拒绝（不受总开关约束） |
| R1 单用户限频 | 10 秒内抢票请求 > 5 次 | 拒绝并进入 30 秒惩罚名单 |
| R2 同 IP 多账号 | 同一活动下同 IP 账号数 > 3 | 拒绝（默认关闭，防 NAT 误伤） |

**离线层**（`risk-analysis/`）：导出抢票日志 → 构造 10 维行为特征 →
IsolationForest 异常检测，与 3σ 统计基线对照，输出嫌疑账号排行供管理员研判。

**分级处置**：30 秒自动惩罚 → 限时封禁（7/30 天）→ 永久封禁，封禁记录留痕
（`ban_expire_time`、`ban_reason`），到期自动解封。

### 6.4 评论情感分析

用户发表评论后 `sentiment` 留空，后端定时任务每 60 秒调用
`sentiment/predict_new.py`：以全量带真实标签的样本训练 TF-IDF + LinearSVC 模型，
对 `sentiment IS NULL` 的评论批量预测并回填；纯标点、纯符号等无信息量文本
不进入模型，直接标记为「无意义(9)」。

---

## 七、实验复现

### 7.1 情感分析对比实验（SVM / LR / NB / SnowNLP）

```bash
cd sentiment/experiments

# 1. 生成实验数据集（1828 条：好评 832 / 差评 522 / 中评 335 / 无意义 139，固定种子可复现）
python build_dataset.py

# 2. 运行四模型对比实验（SVM / 逻辑回归 / 朴素贝叶斯 / SnowNLP）
#    输出 metrics.json 与 confusion_matrix.png
python run_experiment.py

# 3.（可选）将数据集导入数据库，使线上样本量与实验口径一致
python load_dataset.py

# 4.（可选）用线上模型回填 sentiment 字段
python ../predict_new.py
```

`run_experiment.py` 使用固定设置：8:2 分层划分（`random_state=42`）、
字符级 1-2 元 TF-IDF（`max_features=10000`），并额外在 25 条手工真实评论上
评测各模型的泛化命中率。

线上页面显示的指标由 `sentiment/model_metrics.py` 读取 `metrics.json` 得到
（`python model_metrics.py`），不再手工填写；`--live` 参数则基于当前数据库
全量样本重新训练评估。

### 7.2 抢票风控离线检测（孤立森林 vs 3σ 基线）

```bash
cd risk-analysis

python export_grab_log.py          # 导出抢票日志 → output/grab_log.csv
python feature_engineering.py      # 10 维行为特征 → output/features.csv
python isolation_forest.py         # 孤立森林 + 3σ 基线对照 → output/anomaly_report.csv
python plot_fig21_compare.py       # 可视化对比 → output/anomaly_plot_compare.png
```

**复现 341 条基准数据集**（关键，否则结果对不上）：

基准数据集来自活动 **「风控实验-混合流量」（activity_id=11）**，
共 341 条：student01=141、student12=100、其余 10 个正常账号各 10 条。复现方式：

```bash
python export_grab_log.py 11       # 按活动导出，得到 341 条
python feature_engineering.py
python isolation_forest.py         # 期望：孤立森林 P=R=1.00，3σ 标记 1 漏检 1
```

> **注意**：不带参数导出的是**全库**日志（含后续新增的抢票记录），
> 条数会随时间增长而大于 341，此时孤立森林的 P/R 不再等于 1.00——
> 这是数据集口径变了，不是算法变了。要复核基准数值请务必带上活动参数 `11`。
>
> 管理端「运行离线检测」按钮支持按活动分析，此时导出结果会额外留档为
> `output/grab_log_act<id>.csv`，避免覆盖全量数据集。


### 7.3 抢票并发压测

```bash
# 单场景
python tools/loadtest/load_test.py --threads 200 --stock 99

# 完整矩阵（预热 2 轮 + 每场景 3 轮取中位数）
python tools/loadtest/run_load_matrix.py
```

`load_test.py` 会临时创建一个测试活动，以 N 个并发线程同时抢票，统计成功数、
各失败原因分布、响应时间分位数，并校验 `成功数 + 剩余库存 = 初始库存`
（无超卖），最后清理测试数据。`run_load_matrix.py` 在其之上做预热与多轮取中位数，
原始数据写入 `压测结果.csv`。

> **压测前请将 `application.yml` 中 `risk.enabled` 置为 `false`**，
> 否则 R1 限频规则会拦截压测流量，且 `checkBan` 会给每个请求增加一次数据库查询，
> 使响应时间偏高（实测约 +15%）。压测完成后记得改回 `true`。
>
> 响应时间对 JIT 与连接池预热敏感：冷启动首轮明显偏高，因此必须先预热再测量，
> 且取多轮中位数而非单次结果。

---

## 八、主要接口

| 模块 | 接口 | 方法 | 权限 |
| --- | --- | --- | --- |
| 认证 | `/auth/login`、`/auth/register`、`/auth/forgot`、`/auth/refresh` | POST | 公开 |
| 活动 | `/activity/page`、`/list`、`/detail`、`/ticketTypes` | GET | 已登录 |
| 活动 | `/activity/grab` | POST | 学生 |
| 活动 | `/activity/create`、`/update`、`/changeStatus`、`/delete` | POST | 组织者 |
| 活动 | `/activity/ticketType/create`、`/update`、`/delete` | POST | 组织者 |
| 票券 | `/ticket/myList`、`/detail`、`/qrcode` | GET | 学生 |
| 票券 | `/ticket/delete` | POST | 学生 |
| 核销 | `/checkin/verify` | POST | 核销员 |
| 核销 | `/checkin/records` | GET | 核销员 / 组织者 |
| 统计 | `/stats/activity` | GET | 组织者 / 管理员 |
| 统计 | `/stats/certificate` | GET | 学生 |
| 评论 | `/comment/list`、`/comment/stats` | GET | 学生 / 管理员 |
| 评论 | `/comment/add`、`/comment/quota` | POST/GET | 学生 |
| 评论 | `/comment/analyze`、`/model-info`、`/activity-ranking` | POST/GET | 管理员 |
| 风控 | `/risk/overview`、`/banned`、`/records`、`/analysis-activities` | GET | 管理员 |
| 风控 | `/risk/ban`、`/unban`、`/ban-batch`、`/run-offline-analysis` | POST | 管理员 |

除 `/auth/*` 外，所有接口均需在请求头携带 `token`（JWT，有效期 2 小时）；
被禁用账号即使持有未过期的旧令牌也会被拦截器拒绝。

---

## 九、常见问题

**Q：控制台日志出现中文乱码或卡死？**
`application.yml` 中已注明**不要**开启 MyBatis-Plus 的 `log-impl: StdOutImpl`。
Windows 控制台的快速编辑模式会冻结输出管道，导致所有请求线程阻塞在日志锁上。

**Q：情感分析/离线检测没有结果？**
确认 Python 可用（`python --version`）且依赖齐全；两个模块的脚本路径均为
**相对项目根目录**的相对路径，请确保以项目根目录为工作目录启动应用
（`启动系统.bat` 已自动切换）。

**Q：抢票返回"操作过于频繁"？**
在线风控 R1 规则触发（10 秒内超过 5 次）。可等待 30 秒惩罚期结束，
或在 `application.yml` 中临时关闭 `risk.enabled`。

---

## 十、单元测试

```bash
mvnw.cmd test          # Windows
./mvnw test            # Linux / macOS
```

共 **65** 个测试用例，全部为离线运行（纯 Mockito，不依赖数据库）：

| 测试类 | 用例数 | 覆盖点 |
| --- | --- | --- |
| `QrCodeUtilTest` | 10 | 动态二维码签名、格式校验、双向时间窗（含未来时间戳拒绝） |
| `AuthInterceptorTest` | 13 | 登录态、角色校验、封禁账号持旧令牌被拒、解封后放行 |
| `RiskRuleEngineTest` | 10 | R1 滑动窗口与惩罚名单、R2 同 IP 多账号、并发计数不丢失 |
| `ActivityServiceImplTest` | 17 | 抢票成功/各失败分支、事务回滚、活动删除级联清理 |
| `CheckinServiceImplTest` | 10 | 核销成功/重复核销/时间窗/票状态各分支 |
| `ActivityStockSyncerTest` | 4 | 活动总库存与票种库存之和的同步（一致/不一致/版本冲突重试/空票种） |
| `CampusTicketApplicationTests` | 1 | Spring 上下文加载 |

关键回归点：

- **事务回滚**：活动级库存条件更新失败时必须抛 `BusinessException` 触发回滚，
  而不是 `return Result.error`——后者不回滚，会造成"票种库存已扣但无订单"的泄漏。
- **封禁令牌**：`status=0` 且未到期的账号，即使持有未过期的旧 JWT，
  访问任意业务接口也返回 401。
- **二维码时间窗**：`|当前时间 − 时间戳| > 3 秒 + 2 秒容差` 一律拒绝，
  未来时间戳同样拒绝（防止持有密钥者伪造"永不过期"的二维码）。
- **级联清理**：删除活动时票种/订单/电子票/核销记录/评论一并清理，
  `grab_log` 保留。

