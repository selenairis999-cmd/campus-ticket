<template>
  <div class="page">
    <el-card>
      <div class="toolbar">
        <el-input v-model="keyword" placeholder="搜索活动标题" clearable style="width: 260px"
                  @keyup.enter="load(1)" />
        <el-button type="primary" @click="load(1)">搜索</el-button>
      </div>
      <el-table :data="records" v-loading="loading">
        <el-table-column prop="title" label="活动名称" />
        <el-table-column prop="location" label="地点" />
        <el-table-column label="抢票时间" width="280">
          <template #default="{ row }">
            {{ formatTime(row.signStartTime) }} ~ {{ formatTime(row.signEndTime) }}
          </template>
        </el-table-column>
        <el-table-column label="活动时间" width="280">
          <template #default="{ row }">
            {{ formatTime(row.startTime) }} ~ {{ formatTime(row.endTime) }}
          </template>
        </el-table-column>
        <el-table-column prop="remainStock" label="剩余" width="80" />
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <template v-if="userRole === 1">
              <el-button v-if="grabState(row) === 'open'" type="primary" size="small" @click="grab(row)">
                抢票
              </el-button>
              <el-tag v-else size="small" :type="grabState(row) === 'soldout' ? 'danger' : 'info'">
                {{ grabStateText(row) }}
              </el-tag>
            </template>
            <el-tag v-else type="info" size="small">仅学生可抢</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="评论" width="80" align="center">
          <template #default="{ row }">
            <el-button v-if="userRole === 1" type="success" size="small" plain @click="openComment(row)">评论</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="pageNum" :total="total" layout="prev, pager, next"
                     @current-change="load" style="margin-top: 15px" />
    </el-card>

    <!-- 评论弹窗：满意度饼图 + 评论列表 -->
    <el-dialog v-model="commentVisible" :title="'活动评论 - ' + (currentActivity?.title || '')"
               width="680px" @closed="disposeChart">

      <div v-if="userRole === 1" class="add-comment">
        <div v-if="quota" class="quota-tip">已到场核销 {{ quota.ticketCount }} 张票，还可评价 {{ quota.remain }} 次</div>
      <el-input v-model="newComment" type="textarea" :rows="2" maxlength="200" show-word-limit
                  placeholder="说说你对这个活动的感受…" />
        <el-button type="primary" style="margin-top: 8px" :loading="posting" @click="postComment">发表评论</el-button>
      </div>

      <div v-if="stats" class="stats-row">
        <div class="rate-box">
          <div class="rate-num">{{ stats.positiveRate }}%</div>
          <div class="rate-label">好评率（{{ stats.posCount }}/{{ stats.total }}）</div>
          <div class="rate-detail">好评 {{ stats.posCount }} · 中评 {{ stats.neuCount }} · 差评 {{ stats.negCount }}</div>
        </div>
        <div ref="chartRef" class="chart-box"></div>
      </div>
      <el-divider />
      <el-table :data="comments" v-loading="commentLoading" size="small">
        <el-table-column prop="username" label="用户" width="90" />
        <el-table-column label="评论内容" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.parentId > 0" class="follow-mark">追评：</span>{{ row.content }}
          </template>
        </el-table-column>
        <el-table-column label="情感" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="sentimentTag(row.sentiment)" size="small">{{ sentimentText(row.sentiment) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="150">
          <template #default="{ row }">{{ formatTime(row.createTime) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="60" align="center">
          <template #default="{ row }">
            <el-button v-if="row.parentId === 0" type="primary" link size="small" @click="followComment(row)">追评</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="commentPage" :total="commentTotal" layout="prev, pager, next"
                     page-size="10" @current-change="loadComments"
                     style="margin-top: 10px; justify-content: center" />
    </el-dialog>
    <!-- 抢票选票种弹窗（功能12） -->
    <el-dialog v-model="grabVisible" :title="'选择票种 - ' + (currentActivity?.title || '')" width="460px">
      <div class="ticket-options">
        <el-radio-group v-model="selectedTicketId">
          <el-radio v-for="t in tickets" :key="t.id" :value="t.id"
                    :disabled="t.remainStock <= 0" class="ticket-radio">
            {{ t.ticketName }}（剩余 {{ t.remainStock }}/{{ t.totalStock }}）
          </el-radio>
        </el-radio-group>
      </div>
      <template #footer>
        <el-button @click="grabVisible = false">取消</el-button>
        <el-button type="primary" :loading="grabbing" :disabled="!selectedTicketId" @click="doGrab">确认抢票</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import * as echarts from 'echarts';
import request from '@/utils/request';

const records = ref([]);
const total = ref(0);
const pageNum = ref(1);
const keyword = ref('');
const loading = ref(false);

// 当前登录用户角色（1=学生；评论仅学生可发，非学生隐藏评论入口）
let user = null;
try {
  const raw = localStorage.getItem('user');
  if (raw && raw !== 'undefined') user = JSON.parse(raw);
} catch (e) {}
const userRole = user ? user.role : null;


const formatTime = t => (t ? t.replace('T', ' ').slice(0, 16) : '');

// 抢票状态：open可抢 / notstart未开始 / ended已结束 / soldout已抢完
const grabState = row => {
  const now = Date.now();
  if (row.status === 2) return 'ended'; // 活动已结束
  if (row.remainStock <= 0) return 'soldout';
  const start = row.signStartTime ? new Date(row.signStartTime.replace('T', ' ')).getTime() : 0;
  const end = row.signEndTime ? new Date(row.signEndTime.replace('T', ' ')).getTime() : Infinity;
  if (now < start) return 'notstart';
  if (now > end) return 'ended';
  return 'open';
};
const grabStateText = row => {
  const s = grabState(row);
  if (s === 'notstart') return '抢票未开始';
  if (s === 'ended') return row.status === 2 ? '活动已结束' : '抢票已结束';
  if (s === 'soldout') return '已抢完';
  return '抢票';
};

const load = async () => {
  loading.value = true;
  try {
    const res = await request.get('/activity/page', {
      params: { pageNum: pageNum.value, pageSize: 10, keyword: keyword.value || undefined }
    });
    records.value = res.data.records;
    total.value = res.data.total;
  } finally {
    loading.value = false;
  }
};

const grab = async row => {
  // 查活动票种：单票种直接抢（与旧版行为一致），多票种弹窗选择
  const res = await request.get('/activity/ticketTypes', { params: { activityId: row.id } });
  const list = res.data || [];
  if (list.length <= 1) {
    try {
      await ElMessageBox.confirm(`确认抢购《${row.title}》的门票？`, '提示', { type: 'warning' });
    } catch (e) { return; }
    const r = await request.post('/activity/grab', null, { params: { activityId: row.id } });
    ElMessage.success(r.msg);
    load();
    return;
  }
  tickets.value = list;
  currentActivity.value = row;
  selectedTicketId.value = null;
  grabVisible.value = true;
};

// 多票种抢票（功能12）
const grabVisible = ref(false);
const grabbing = ref(false);
const tickets = ref([]);
const selectedTicketId = ref(null);

const doGrab = async () => {
  grabbing.value = true;
  try {
    const res = await request.post('/activity/grab', null, {
      params: { activityId: currentActivity.value.id, ticketId: selectedTicketId.value }
    });
    ElMessage.success(res.msg);
    grabVisible.value = false;
    load();
  } finally {
    grabbing.value = false;
  }
};


// ===== 评论弹窗 =====
const commentVisible = ref(false);
const currentActivity = ref(null);
const stats = ref(null);
const comments = ref([]);
const commentTotal = ref(0);
const commentPage = ref(1);
const commentLoading = ref(false);
const chartRef = ref(null);
let chart = null;

const sentimentText = s => (s === 2 ? '好评' : s === 1 ? '中评' : s === 0 ? '差评' : s === 9 ? '无意义' : '待分析');
const sentimentTag = s => (s === 2 ? 'success' : s === 1 ? 'warning' : s === 0 ? 'danger' : 'info');


const openComment = async row => {
  currentActivity.value = row;
  commentVisible.value = true;
  commentPage.value = 1;
  await loadComments();
  await loadStats();
  loadQuota();
  nextTick(renderChart);
};

// 评论额度（每张票可发1条主评，前端只展示，后端强校验）
const quota = ref(null);
const loadQuota = async () => {
  try {
    const res = await request.get('/comment/quota', { params: { activityId: currentActivity.value.id } });
    quota.value = res.data;
  } catch (e) { quota.value = null; }
};

// 追评（每条主评最多2次，后端强校验）
const followComment = async row => {
  try {
    const { value } = await ElMessageBox.prompt('输入追评内容（每条评价最多追评2次）', '追评', {
      inputPattern: /\S+/,
      inputErrorMessage: '追评内容不能为空',
      inputValidator: v => (v && v.trim().length > 0) || '追评内容不能为空'
    });
    await request.post('/comment/add', null, {
      params: { activityId: currentActivity.value.id, content: value.trim(), parentId: row.id }
    });
    ElMessage.success('追评成功，情感标签待离线分析后更新');
    commentPage.value = 1;
    await loadComments();
    await loadStats();
    nextTick(renderChart);
  } catch (e) { /* 用户取消或错误已由拦截器提示 */ }
};

const loadComments = async () => {
  commentLoading.value = true;
  try {
    const res = await request.get('/comment/list', {
      params: { activityId: currentActivity.value.id, pageNum: commentPage.value, pageSize: 10 }
    });
    comments.value = res.data.records;
    commentTotal.value = res.data.total;
  } finally {
    commentLoading.value = false;
  }
};

const loadStats = async () => {
  const res = await request.get('/comment/stats', { params: { activityId: currentActivity.value.id } });
  stats.value = res.data;
};

const renderChart = () => {
  if (!chartRef.value || !stats.value) return;
  if (chart) chart.dispose();
  chart = echarts.init(chartRef.value);
  chart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [{
      type: 'pie',
      radius: ['45%', '70%'],
      center: ['50%', '45%'],
      label: { formatter: '{b} {d}%' },
      data: [
        { value: stats.value.posCount, name: '好评', itemStyle: { color: '#67C23A' } },
        { value: stats.value.neuCount, name: '中评', itemStyle: { color: '#E6A23C' } },
        { value: stats.value.negCount, name: '差评', itemStyle: { color: '#F56C6C' } }
      ]
    }]
  });
};

const disposeChart = () => {
  if (chart) { chart.dispose(); chart = null; }
};

const newComment = ref('');
const posting = ref(false);

const postComment = async () => {
  if (!newComment.value.trim()) {
    ElMessage.warning('请输入评论内容');
    return;
  }
  posting.value = true;
  try {
    await request.post('/comment/add', null, {
      params: { activityId: currentActivity.value.id, content: newComment.value.trim() }
    });
    ElMessage.success('评论成功，情感标签待离线分析后更新');
    newComment.value = '';
    commentPage.value = 1;
    await loadComments();
    await loadStats();
    loadQuota();
    nextTick(renderChart);
  } finally {
    posting.value = false;
  }
};


onMounted(() => load());
</script>

<style scoped>
.page { padding: 20px; }
.toolbar { margin-bottom: 15px; display: flex; gap: 10px; }
.stats-row { display: flex; align-items: center; gap: 20px; }
.rate-box { flex: 0 0 200px; text-align: center; }
.rate-num { font-size: 36px; font-weight: bold; color: #409EFF; }
.rate-label { margin-top: 6px; color: #666; font-size: 14px; }
.rate-detail { margin-top: 4px; color: #999; font-size: 13px; }
.chart-box { flex: 1; height: 260px; }
.add-comment { margin-bottom: 15px; }
.quota-tip { font-size: 13px; color: #909399; margin-bottom: 8px; }
.follow-mark { color: #909399; font-size: 12px; }
.ticket-options { padding: 10px 0; }
.ticket-radio { display: flex; height: auto; margin: 0 0 12px; white-space: normal; }
</style>
