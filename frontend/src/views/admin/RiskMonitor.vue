<template>
  <div class="page">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="cards">
      <el-col :span="4">
        <div class="stat-card">
          <div class="num">{{ overview.totalRequests ?? '-' }}</div>
          <div class="label">抢票请求总数</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat-card">
          <div class="num" style="color:#67c23a">{{ overview.successCount ?? '-' }}</div>
          <div class="label">成功次数</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat-card">
          <div class="num" style="color:#f56c6c">{{ overview.blockedCount ?? '-' }}</div>
          <div class="label">风控拦截次数</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat-card">
          <div class="num" style="color:#e6a23c">{{ overview.conflictCount ?? '-' }}</div>
          <div class="label">并发冲突</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat-card">
          <div class="num" style="color:#b03a2e">{{ overview.bannedCount ?? '-' }}</div>
          <div class="label">封禁中账号</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat-card">
          <div class="num" style="color:#409eff">{{ overview.successRate ?? '-' }}</div>
          <div class="label">成功率</div>
        </div>
      </el-col>
    </el-row>

    <!-- 嫌疑账号 -->
    <el-card class="block">
      <template #header>嫌疑账号排行（被拦截过 或 请求数&gt;50）—— 可直接发起分级处置</template>
      <el-table :data="overview.suspectAccounts || []" border stripe>
        <el-table-column prop="username" label="用户名" width="140" />
        <el-table-column prop="totalRequests" label="总请求" width="100" />
        <el-table-column prop="successCount" label="成功" width="100" />
        <el-table-column prop="blockedCount" label="被拦截" width="100" />
        <el-table-column label="状态" width="150">
          <template #default="{ row }">
            <el-tag v-if="row.banned" type="danger">封禁中{{ row.banExpireTime ? '' : '（永久）' }}</el-tag>
            <el-tag v-else-if="row.suspect" type="warning">嫌疑</el-tag>
            <el-tag v-else type="success">正常</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="处置" min-width="150">
          <template #default="{ row }">
            <el-dropdown v-if="!row.banned" @command="days => doBan(row, days)">
              <el-button size="small" type="danger" plain>封禁<el-icon><arrow-down /></el-icon></el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item :command="7">限时 7 天</el-dropdown-item>
                  <el-dropdown-item :command="30">限时 30 天</el-dropdown-item>
                  <el-dropdown-item :command="0" divided>永久封禁</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button v-else size="small" type="success" plain @click="doUnban(row)">解封</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="pager" background layout="total, prev, pager, next" :total="suspectTotal"
                     :current-page="suspectQuery.pageNum" :page-size="suspectQuery.pageSize"
                     @current-change="loadSuspectPage" />
    </el-card>

    <!-- 封禁名单 -->
    <el-card class="block">
      <template #header>
        <div class="toolbar">
          <span>封禁名单（分级处置：在线自动惩罚 30s → 限时封禁 → 永久封禁）</span>
          <div>
            <el-button type="warning" plain @click="openAnalysis">运行离线检测</el-button>
            <el-button type="primary" plain @click="importVisible = true">导入离线检测账号</el-button>
          </div>
        </div>
      </template>
      <el-table :data="bannedList" border stripe>
        <el-table-column prop="username" label="用户名" width="140" />
        <el-table-column prop="banReason" label="封禁原因" show-overflow-tooltip />
        <el-table-column label="解封时间" width="200">
          <template #default="{ row }">
            {{ row.banExpireTime ? formatTime(row.banExpireTime) : '永久（可申诉）' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" type="success" plain @click="doUnban(row)">解封</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 抢票日志 -->
    <el-card class="block">
      <template #header>
        <div class="toolbar">
          <span>抢票日志</span>
          <el-select v-model="query.result" placeholder="结果筛选" clearable style="width:140px" @change="loadRecords(1)">
            <el-option label="成功" value="SUCCESS" />
            <el-option label="风控拦截" value="RISK_BLOCKED" />
            <el-option label="封禁拦截" value="BANNED" />
            <el-option label="库存不足" value="STOCK_EMPTY" />
            <el-option label="并发冲突" value="VERSION_CONFLICT" />
          </el-select>
          <el-input v-model="query.username" placeholder="按用户名搜索" clearable style="width:160px"
                    @keyup.enter="loadRecords(1)" @clear="loadRecords(1)" />
          <el-button type="primary" @click="loadRecords(1)">查询</el-button>
        </div>
      </template>
      <el-table :data="records" border stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="createTime" label="时间" width="180">
          <template #default="{ row }">{{ formatTime(row.createTime) }}</template>
        </el-table-column>
        <el-table-column prop="username" label="用户" width="110" />
        <el-table-column prop="activityTitle" label="活动" width="120" show-overflow-tooltip />
        <el-table-column prop="ip" label="IP" width="130" />
        <el-table-column label="结果" width="140">
          <template #default="{ row }">
            <el-tag :type="resultType(row.result)">{{ resultText(row.result) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="userAgent" label="User-Agent" show-overflow-tooltip />
      </el-table>
      <el-pagination class="pager" background layout="total, prev, pager, next" :total="total"
                     :page-size="query.pageSize" :current-page="query.pageNum" @current-change="loadRecords" />
    </el-card>

    <!-- 批量导入离线检测异常账号 -->
    <el-dialog v-model="importVisible" title="导入离线检测异常账号" width="520px">
      <div class="import-tip">
        将 <b>risk-analysis/output/anomaly_report.csv</b> 中判为异常的账号粘贴到下方（每行一个，支持逗号分隔），
        由管理员研判后批量发起限时封禁，处置在下一场活动抢票前生效。
      </div>
      <el-input v-model="importForm.usernames" type="textarea" :rows="6"
                placeholder="student01&#10;student12" />
      <div class="import-row">
        <span class="import-label">封禁时长</span>
        <el-radio-group v-model="importForm.days">
          <el-radio-button :value="7">7 天</el-radio-button>
          <el-radio-button :value="30">30 天</el-radio-button>
          <el-radio-button :value="0">永久</el-radio-button>
        </el-radio-group>
      </div>
      <div class="import-row">
        <span class="import-label">封禁原因</span>
        <el-input v-model="importForm.reason" style="flex:1" />
      </div>
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="danger" @click="doBanBatch">批量封禁</el-button>
      </template>
    </el-dialog>
    <!-- 运行离线检测 -->
    <el-dialog v-model="analysisVisible" title="运行离线检测（孤立森林）" width="880px">
      <div class="import-tip">
        选择活动后自动串跑"日志导出 → 特征工程 → 孤立森林"三步脚本，需数秒。
        报告仅作研判证据，请结合"特征偏离度"人工确认后，再将异常账号填入批量封禁（限时封禁在下一场活动抢票前生效）。
      </div>
      <div class="import-row">
        <span class="import-label">分析活动</span>
        <el-select v-model="analysisForm.activityId" filterable style="flex:1"
                   placeholder="选择有抢票日志的活动">
          <el-option v-for="a in analysisActivities" :key="a.activityId"
                     :label="`${a.title}（${a.logCount} 条日志）`" :value="a.activityId" />
        </el-select>
        <el-button type="warning" :loading="analysisRunning" @click="runAnalysis">运行检测</el-button>
      </div>
      <template v-if="analysisResult">
        <el-alert style="margin-top:12px"
                  :title="`共分析 ${analysisResult.analyzedUsers} 个账号，孤立森林判为异常 ${analysisResult.anomalyCount} 个`"
                  :type="analysisResult.anomalyCount > 0 ? 'warning' : 'success'" :closable="false" />
        <el-table :data="analysisResult.rows" border stripe size="small" style="margin-top:12px" max-height="320">
          <el-table-column prop="username" label="用户名" width="110" />
          <el-table-column label="孤立森林" width="90">
            <template #default="{ row }">
              <el-tag :type="row.ifAnomaly ? 'danger' : 'success'" size="small">{{ row.ifAnomaly ? '异常' : '正常' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="3σ基线" width="90">
            <template #default="{ row }">
              <el-tag :type="row.sigAnomaly ? 'warning' : 'info'" size="small">{{ row.sigAnomaly ? '命中' : '未命中' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="ifScore" label="异常分" width="90" />
          <el-table-column prop="reqCount" label="请求数" width="80" />
          <el-table-column prop="intervalMean" label="间隔均值ms" width="105" />
          <el-table-column prop="conflictRate" label="冲突率" width="80" />
          <el-table-column prop="top3Features" label="特征偏离度（top3）" show-overflow-tooltip />
        </el-table>
        <el-collapse style="margin-top:10px">
          <el-collapse-item title="脚本控制台输出（审计）">
            <pre class="console-box">{{ analysisResult.console }}</pre>
          </el-collapse-item>
        </el-collapse>
      </template>
      <template #footer>
        <el-button @click="analysisVisible = false">关闭</el-button>
        <el-button type="danger" :disabled="!analysisResult || analysisResult.anomalyCount === 0"
                   @click="fillBanFromAnalysis">将异常账号填入批量封禁</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { ArrowDown } from '@element-plus/icons-vue';
import request from '@/utils/request';

const overview = ref({});
const records = ref([]);
const bannedList = ref([]);
const total = ref(0);
const suspectTotal = ref(0);
const suspectQuery = reactive({ pageNum: 1, pageSize: 10 });
const query = reactive({ pageNum: 1, pageSize: 10, username: '', result: '' });
const importVisible = ref(false);
const importForm = reactive({ usernames: '', days: 30, reason: '离线检测异常（孤立森林），经人工研判' });
const analysisVisible = ref(false);
const analysisRunning = ref(false);
const analysisActivities = ref([]);
const analysisForm = reactive({ activityId: null });
const analysisResult = ref(null);

const loadOverview = async (page) => {
  if (page) suspectQuery.pageNum = page;
  const res = await request.get('/risk/overview', { params: suspectQuery });
  overview.value = res.data;
  suspectTotal.value = res.data.suspectTotal || 0;
};

// 嫌疑账号排行翻页：统计卡片与当前页数据由同一接口返回，无需二次请求
const loadSuspectPage = (page) => loadOverview(page);

const loadRecords = async (page) => {
  if (page) query.pageNum = page;
  const res = await request.get('/risk/records', { params: query });
  records.value = res.data.records;
  total.value = res.data.total;
};

const loadBanned = async () => {
  const res = await request.get('/risk/banned');
  bannedList.value = res.data;
};

// 分级处置：days=0 → 永久；days>0 → 限时天数
const doBan = async (row, days) => {
  await request.post('/risk/ban', null, {
    params: { userId: row.userId, days: days || undefined, reason: '监控大盘人工研判封禁' }
  });
  ElMessage.success(days > 0 ? `已封禁 ${days} 天` : '已永久封禁');
  reloadAll();
};

const doUnban = async (row) => {
  // 两处入口的行结构不同：嫌疑账号表是 AccountRiskVO（userId），封禁名单表是 SysUser（id）
  const userId = row.userId ?? row.id;
  await request.post('/risk/unban', null, { params: { userId } });
  ElMessage.success('已解封');
  reloadAll();
};

const doBanBatch = async () => {
  const res = await request.post('/risk/ban-batch', null, {
    params: {
      usernames: importForm.usernames,
      days: importForm.days || undefined,
      reason: importForm.reason
    }
  });
  ElMessage.success(res.data || '批量封禁完成');
  importVisible.value = false;
  importForm.usernames = '';
  reloadAll();
};

// ===== 离线检测（选活动 → 跑脚本 → 研判 → 填入批量封禁） =====
const openAnalysis = async () => {
  analysisVisible.value = true;
  const res = await request.get('/risk/analysis-activities');
  analysisActivities.value = res.data;
  if (!analysisForm.activityId && analysisActivities.value.length) {
    analysisForm.activityId = analysisActivities.value[0].activityId;
  }
};

const runAnalysis = async () => {
  if (!analysisForm.activityId) {
    ElMessage.warning('请先选择活动');
    return;
  }
  analysisRunning.value = true;
  try {
    const res = await request.post('/risk/run-offline-analysis', null, {
      params: { activityId: analysisForm.activityId },
      timeout: 120000
    });
    analysisResult.value = res.data;
    ElMessage.success(`检测完成：${res.data.analyzedUsers} 个账号，异常 ${res.data.anomalyCount} 个`);
  } finally {
    analysisRunning.value = false;
  }
};

const fillBanFromAnalysis = () => {
  const names = (analysisResult.value?.rows || []).filter(r => r.ifAnomaly).map(r => r.username);
  if (!names.length) {
    ElMessage.warning('没有孤立森林判为异常的账号');
    return;
  }
  importForm.usernames = names.join('\n');
  importForm.reason = '离线检测异常（孤立森林），经人工研判';
  analysisVisible.value = false;
  importVisible.value = true;
};

const reloadAll = () => {
  loadOverview();
  loadBanned();
  loadRecords();
};

const resultMap = {
  SUCCESS: { text: '成功', type: 'success' },
  RISK_BLOCKED: { text: '风控拦截', type: 'danger' },
  BANNED: { text: '封禁拦截', type: 'danger' },
  STOCK_EMPTY: { text: '库存不足', type: 'warning' },
  VERSION_CONFLICT: { text: '并发冲突', type: 'warning' },
  TIME_WINDOW: { text: '非抢票时间', type: 'info' },
  ACTIVITY_ENDED: { text: '活动结束', type: 'info' },
  ERROR: { text: '系统异常', type: 'info' }
};
const resultText = r => (resultMap[r] || { text: r }).text;
const resultType = r => (resultMap[r] || { type: 'info' }).type;

const formatTime = t => (t ? String(t).replace('T', ' ').slice(0, 19) : '');

onMounted(() => {
  loadOverview();
  loadRecords(1);
  loadBanned();
});
</script>

<style scoped>
.page { padding: 20px; }
.cards { margin-bottom: 20px; }
.stat-card { background: #f7f8fa; border-radius: 8px; padding: 20px; text-align: center; }
.num { font-size: 26px; font-weight: bold; color: #303133; }
.label { margin-top: 8px; color: #909399; font-size: 13px; }
.block { margin-bottom: 20px; }
.toolbar { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.pager { margin-top: 16px; justify-content: flex-end; }
.import-tip { color: #606266; font-size: 13px; line-height: 1.6; margin-bottom: 12px; }
.import-row { display: flex; align-items: center; gap: 12px; margin-top: 12px; }
.import-label { font-size: 13px; color: #606266; width: 60px; }
.console-box {
  background: #1e1e1e; color: #d4d4d4; padding: 10px; border-radius: 6px;
  font-size: 12px; line-height: 1.5; max-height: 220px; overflow: auto;
  white-space: pre-wrap; margin: 0;
}
</style>
