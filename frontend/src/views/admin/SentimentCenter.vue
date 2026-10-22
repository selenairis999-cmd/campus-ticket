<template>
  <div class="page">
    <!-- 顶部操作栏 -->
    <el-card class="block">
      <div class="toolbar">
        <span class="pending">待分析评论：<b>{{ info.pendingCount ?? '-' }}</b> 条</span>
        <el-button type="primary" :loading="analyzing" @click="runAnalyze">立即分析</el-button>
        <el-button :loading="refreshing" @click="refreshAll">刷新</el-button>
      </div>
    </el-card>

    <!-- 模型指标卡片 -->
    <el-row :gutter="20" class="cards">
      <el-col :span="6">
        <div class="stat-card">
          <div class="num" style="color:#67c23a">{{ info.svmAccuracy ?? '-' }}</div>
          <div class="label">SVM 测试集准确率</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="num" style="color:#409eff">{{ info.lrAccuracy ?? '-' }}</div>
          <div class="label">逻辑回归测试集准确率</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="num" style="color:#e6a23c">{{ info.nbAccuracy ?? '-' }}</div>
          <div class="label">朴素贝叶斯测试集准确率</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="num" style="color:#909399">{{ info.svmRealHitRate ?? '-' }}</div>
          <div class="label">SVM 手工评论命中率</div>
        </div>
      </el-col>
    </el-row>

    <!-- 情感分布饼图 -->
    <el-card class="block">
      <template #header>
        <div class="pie-header">
          <span>活动情感分布</span>
          <el-select v-model="pieActivityId" placeholder="请选择活动" style="width: 260px" @change="loadPieStats">
            <el-option v-for="a in rankings" :key="a.activityId" :label="a.title" :value="a.activityId" />
          </el-select>
        </div>
      </template>
      <div v-if="pieStats" class="pie-wrap">
        <div class="pie-num">
          <div class="rate-num">{{ pieStats.positiveRate }}%</div>
          <div class="rate-label">好评率（{{ pieStats.posCount }}/{{ pieStats.total }}）</div>
          <div class="rate-detail">好评 {{ pieStats.posCount }} · 中评 {{ pieStats.neuCount }} · 差评 {{ pieStats.negCount }}</div>
        </div>
        <div ref="pieChartRef" class="pie-chart"></div>
      </div>
      <el-empty v-else description="暂无评论数据，请先选择有评论的活动" />
    </el-card>

    <!-- 满意度排行图 -->
    <el-card class="block">
      <template #header>各活动满意度排行 TOP 10（按好评率）</template>
      <div ref="chartRef" class="chart"></div>
    </el-card>

    <!-- 明细表 -->
    <el-card class="block">
      <template #header>活动评论情感分布明细</template>
      <el-table :data="rankings" border stripe>
        <el-table-column prop="title" label="活动" min-width="180" />
        <el-table-column prop="total" label="评论数" width="90" />
        <el-table-column label="好评" width="90">
          <template #default="{ row }"><span style="color:#67c23a">{{ row.posCount }}</span></template>
        </el-table-column>
        <el-table-column label="中评" width="90">
          <template #default="{ row }"><span style="color:#e6a23c">{{ row.neuCount }}</span></template>
        </el-table-column>
        <el-table-column label="差评" width="90">
          <template #default="{ row }"><span style="color:#f56c6c">{{ row.negCount }}</span></template>
        </el-table-column>
        <el-table-column label="好评率" width="110">
          <template #default="{ row }">
            <el-progress :percentage="Number(row.positiveRate.replace('%',''))" :stroke-width="14"
                         :color="rateColor(row.positiveRate)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button type="primary" size="small" plain @click="openDetail(row)">查看评论</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 评论详情弹窗（管理员查看具体评论内容，调 /comment/list） -->
    <el-dialog v-model="detailVisible" :title="'评论详情 - ' + (detailTitle || '')" width="640px">
      <el-table :data="detailRows" border stripe v-loading="detailLoading" max-height="420">
        <el-table-column prop="username" label="用户" width="110" />
        <el-table-column label="评论内容" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.parentId > 0" style="color:#909399;font-size:12px">追评：</span>{{ row.content }}
          </template>
        </el-table-column>
        <el-table-column label="情感" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.sentiment === 2" type="success" size="small">好评</el-tag>
            <el-tag v-else-if="row.sentiment === 1" type="warning" size="small">中评</el-tag>
            <el-tag v-else-if="row.sentiment === 0" type="danger" size="small">差评</el-tag>
            <el-tag v-else-if="row.sentiment === 9" type="info" size="small">无意义</el-tag>
            <el-tag v-else type="info" size="small">待分析</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="160">
          <template #default="{ row }">{{ (row.createTime || '').replace('T', ' ').slice(0, 16) }}</template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="detailPage" :total="detailTotal" layout="prev, pager, next"
                     @current-change="loadDetail" style="margin-top: 12px; justify-content: flex-end" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue';
import { ElMessage } from 'element-plus';
import * as echarts from 'echarts';
import request from '@/utils/request';

const info = ref({});
const rankings = ref([]);
const analyzing = ref(false);
const refreshing = ref(false);
const chartRef = ref(null);
let chart = null;

// —— 情感分布饼图 ——
const pieActivityId = ref(null);
const pieStats = ref(null);
const pieChartRef = ref(null);
let pieChart = null;

const loadInfo = async () => {
  const res = await request.get('/comment/model-info');
  info.value = res.data;
};

const loadRanking = async () => {
  const res = await request.get('/comment/activity-ranking');
  rankings.value = res.data;
  // 默认选中第一个有评论的活动并渲染饼图
  if (rankings.value.length && !pieActivityId.value) {
    pieActivityId.value = rankings.value[0].activityId;
    loadPieStats();
  } else if (pieActivityId.value) {
    loadPieStats();
  }
  nextTick(renderChart);
};

const loadPieStats = async () => {
  if (!pieActivityId.value) return;
  const res = await request.get('/comment/stats', { params: { activityId: pieActivityId.value } });
  pieStats.value = res.data;
  nextTick(renderPieChart);
};

const renderPieChart = () => {
  if (!pieChartRef.value || !pieStats.value) return;
  if (pieChart) pieChart.dispose();
  pieChart = echarts.init(pieChartRef.value);
  pieChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [{
      type: 'pie',
      radius: ['45%', '70%'],
      center: ['50%', '45%'],
      label: {
        formatter: '{b} {d}%',
        overflow: 'break',
        width: 90
      },
      labelLayout: { hideOverlap: true },
      data: [
        { value: pieStats.value.posCount, name: '好评', itemStyle: { color: '#67C23A' } },
        { value: pieStats.value.neuCount, name: '中评', itemStyle: { color: '#E6A23C' } },
        { value: pieStats.value.negCount, name: '差评', itemStyle: { color: '#F56C6C' } }
      ]
    }]
  });
};

const runAnalyze = async () => {
  analyzing.value = true;
  try {
    const res = await request.post('/comment/analyze');
    ElMessage.success(res.msg || '分析完成');
    await loadInfo();
    await loadRanking();
  } finally {
    analyzing.value = false;
  }
};

const loadAll = () => {
  loadInfo();
  loadRanking();
};

const refreshAll = async () => {
  refreshing.value = true;
  try {
    // 「刷新」只刷新随数据变化的内容（满意度排行、情感分布饼图、明细）。
    // 顶部的模型指标卡固定展示论文定稿实验口径（表 14），不在此处重算，
    // 避免页面上同时出现两套互不相同的准确率。
    await loadRanking();
    await loadInfo();      // 同步待分析评论数
    ElMessage.success('已刷新');
  } catch (e) {
    ElMessage.error('刷新失败：' + (e?.message || '未知错误'));
  } finally {
    refreshing.value = false;
  }
};

const detailVisible = ref(false);
const detailRows = ref([]);
const detailTotal = ref(0);
const detailPage = ref(1);
const detailTitle = ref('');
const detailActivityId = ref(null);
const detailLoading = ref(false);

const openDetail = row => {
  detailTitle.value = row.title;
  detailActivityId.value = row.activityId;
  detailPage.value = 1;
  detailVisible.value = true;
  loadDetail(1);
};

const loadDetail = async page => {
  detailPage.value = page;
  detailLoading.value = true;
  try {
    const res = await request.get('/comment/list', {
      params: { activityId: detailActivityId.value, pageNum: page, pageSize: 10 }
    });
    detailRows.value = res.data.records;
    detailTotal.value = res.data.total;
  } finally {
    detailLoading.value = false;
  }
};

const rateColor = rate => {
  const n = Number(rate.replace('%', ''));
  return n >= 60 ? '#67c23a' : n >= 45 ? '#e6a23c' : '#f56c6c';
};

const renderChart = () => {
  if (!chartRef.value || !rankings.value.length) return;
  // 只取好评率前 10，避免活动多了挤成细条
  const data = rankings.value
      .slice()
      .sort((a, b) => Number(b.positiveRate.replace('%', '')) - Number(a.positiveRate.replace('%', '')))
      .slice(0, 10);
  // 图表高度按条数自适应（每条 36px），最多 10 条不会再膨胀
  chartRef.value.style.height = Math.max(200, data.length * 36 + 30) + 'px';
  if (chart) chart.dispose();
  chart = echarts.init(chartRef.value);
  chart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 40, right: 60, top: 20, bottom: 30 },
    xAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
    yAxis: {
      type: 'category',
      data: data.map(d => d.title),
      axisLabel: { width: 120, overflow: 'truncate' }
    },
    series: [{
      type: 'bar',
      data: data.map(d => ({
        value: Number(d.positiveRate.replace('%', '')),
        itemStyle: { color: rateColor(d.positiveRate) }
      })),
      label: { show: true, position: 'right', formatter: '{c}%' },
      barWidth: 18
    }]
  });
};

onMounted(() => loadAll());
</script>

<style scoped>
.page { padding: 20px; }
.block { margin-bottom: 20px; }
.cards { margin-bottom: 20px; }
.stat-card { background: #f7f8fa; border-radius: 8px; padding: 20px; text-align: center; }
.num { font-size: 28px; font-weight: bold; color: #303133; }
.label { margin-top: 8px; color: #909399; font-size: 13px; }
.toolbar { display: flex; align-items: center; gap: 15px; flex-wrap: wrap; }
.pending { font-size: 15px; }
.chart { height: 320px; }
.pie-header { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.pie-wrap { display: flex; align-items: center; gap: 30px; flex-wrap: wrap; }
.pie-chart { width: 420px; height: 260px; flex-shrink: 0; }
.pie-num { flex: 1; min-width: 220px; }
.rate-num { font-size: 40px; font-weight: bold; color: #303133; }
.rate-label { margin-top: 8px; color: #909399; font-size: 14px; }
.rate-detail { margin-top: 12px; color: #606266; font-size: 14px; line-height: 1.6; }
</style>
