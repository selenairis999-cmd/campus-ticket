<template>
  <div class="page">
    <el-card>
      <div class="toolbar">
        <span>选择活动：</span>
        <el-select v-model="activityId" placeholder="请选择活动" style="width: 300px" @change="loadStats">
          <el-option v-for="a in activities" :key="a.id" :label="a.title" :value="a.id" />
        </el-select>
      </div>

      <div v-if="stats" class="stats">
        <h3>{{ stats.activityTitle }}</h3>
        <el-row :gutter="20">
          <el-col :span="6">
            <div class="stat-card">
              <div class="num">{{ stats.totalStock }}</div>
              <div class="label">总票数</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="num">{{ stats.soldCount }}</div>
              <div class="label">已售出</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="num">{{ stats.checkedCount }}</div>
              <div class="label">已入场</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="num highlight">{{ stats.attendanceRate }}</div>
              <div class="label">出勤率</div>
            </div>
          </el-col>
        </el-row>
        <div class="progress-wrap">
          <span class="plabel">出勤率</span>
          <el-progress :percentage="rateNum" :stroke-width="18" striped striped-flow style="flex: 1" />
        </div>
      </div>

      <el-empty v-else description="请选择活动查看出勤统计" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import request from '@/utils/request';

const activities = ref([]);
const activityId = ref(null);
const stats = ref(null);

const rateNum = computed(() => {
  if (!stats.value || !stats.value.attendanceRate) return 0;
  return parseFloat(stats.value.attendanceRate) || 0;
});

const loadActivities = async () => {
  const res = await request.get('/activity/list');
  activities.value = res.data;
};

const loadStats = async () => {
  if (!activityId.value) return;
  const res = await request.get('/stats/activity', { params: { activityId: activityId.value } });
  stats.value = res.data;
};

onMounted(() => loadActivities());
</script>

<style scoped>
.page { padding: 20px; }
.toolbar { margin-bottom: 20px; display: flex; align-items: center; gap: 10px; }
.stat-card {
  background: #f7f8fa; border-radius: 8px; padding: 20px; text-align: center;
}
.num { font-size: 28px; font-weight: bold; color: #303133; }
.num.highlight { color: #409eff; }
.label { margin-top: 8px; color: #909399; font-size: 13px; }
.progress-wrap { margin-top: 30px; display: flex; align-items: center; gap: 15px; }
.plabel { color: #606266; white-space: nowrap; }
</style>
