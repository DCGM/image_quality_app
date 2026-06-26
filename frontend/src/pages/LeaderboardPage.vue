<template>
  <q-page class="q-pa-md">

    <!-- My stats -->
    <div class="text-h5 q-mb-sm">My contributions</div>
    <q-card class="q-mb-lg" bordered>
      <q-card-section>
        <div class="row q-col-gutter-md q-mb-sm">
          <div class="col-auto">
            <div class="text-caption text-grey-6">Comparisons</div>
            <div class="text-h6">{{ myStats.total_comparisons }}</div>
          </div>
          <div class="col-auto">
            <div class="text-caption text-grey-6">Ratings</div>
            <div class="text-h6">{{ myStats.total_ratings }}</div>
          </div>
          <div class="col-auto">
            <div class="text-caption text-grey-6">Score</div>
            <div class="text-h6 text-primary">{{ myStats.score.toFixed(1) }}</div>
          </div>
        </div>
      </q-card-section>
    </q-card>

    <!-- Overall leaderboard -->
    <div class="text-h5 q-mb-sm">Top annotators</div>
    <q-tabs v-model="overallTab" align="left" class="q-mb-sm">
      <q-tab name="week" label="This week" icon="date_range" />
      <q-tab name="all" label="All time" icon="all_inclusive" />
    </q-tabs>
    <q-card class="q-mb-lg" bordered>
      <q-tab-panels v-model="overallTab" animated>
        <q-tab-panel name="week">
          <q-table :rows="weeklyLb" :columns="lbCols" flat dense hide-bottom
            :rows-per-page-options="[0]" :loading="loadingOverall" no-data-label="No data yet" />
        </q-tab-panel>
        <q-tab-panel name="all">
          <q-table :rows="allTimeLb" :columns="lbCols" flat dense hide-bottom
            :rows-per-page-options="[0]" :loading="loadingOverall" no-data-label="No data yet" />
        </q-tab-panel>
      </q-tab-panels>
    </q-card>

    <!-- Global stats -->
    <div class="text-h5 q-mb-sm">Statistics per task</div>
    <q-card class="q-mb-lg" bordered>
      <q-card-section>
        <div class="row q-col-gutter-md q-mb-sm">
          <div class="col-auto">
            <div class="text-caption text-grey-6">Total comparisons</div>
            <div class="text-h6">{{ globalStats.total_comparisons }}</div>
          </div>
          <div class="col-auto">
            <div class="text-caption text-grey-6">Total ratings</div>
            <div class="text-h6">{{ globalStats.total_ratings }}</div>
          </div>
        </div>
        <q-table
          :rows="globalStats.per_task"
          :columns="taskStatsCols"
          flat dense hide-bottom :rows-per-page-options="[0]"
          :loading="loadingGlobal"
          no-data-label="No data yet"
        />
      </q-card-section>
    </q-card>

    <!-- Per-task leaderboards -->
    <div class="text-h5 q-mb-sm">Per-task leaderboards</div>
    <q-list bordered separator class="rounded-borders">
      <q-expansion-item
        v-for="task in tasks"
        :key="task.id"
        :label="task.name"
        icon="leaderboard"
        @before-show="loadTaskLb(task.id)"
      >
        <q-card flat>
          <q-card-section>
            <q-table
              :rows="taskLbs[task.id] ?? []"
              :columns="lbCols"
              flat dense hide-bottom :rows-per-page-options="[0]"
              no-data-label="No data yet"
            />
          </q-card-section>
        </q-card>
      </q-expansion-item>
    </q-list>

  </q-page>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { apiService } from 'src/services/api';
import { GlobalStats, LeaderboardEntry, MyStats, TaskRead } from 'src/types/api';

const myStats = ref<MyStats>({ total_comparisons: 0, total_ratings: 0, score: 0, per_task_comparisons: {}, per_task_ratings: {} });
const globalStats = ref<GlobalStats>({ total_comparisons: 0, total_ratings: 0, per_task: [] });
const tasks = ref<TaskRead[]>([]);
const weeklyLb = ref<LeaderboardEntry[]>([]);
const allTimeLb = ref<LeaderboardEntry[]>([]);
const taskLbs = reactive<Record<string, LeaderboardEntry[]>>({});
const overallTab = ref('week');
const loadingOverall = ref(false);
const loadingGlobal = ref(false);

const lbCols = [
  { name: 'rank', label: '#', field: (_: unknown, idx: number) => idx + 1, align: 'center' as const },
  { name: 'display_name', label: 'User', field: 'display_name', align: 'left' as const },
  { name: 'count', label: 'Annotations', field: 'count', sortable: true, align: 'right' as const },
  { name: 'score', label: 'Score', field: 'score', sortable: true, align: 'right' as const, format: (v: number) => v.toFixed(1) },
  { name: 'reliability', label: 'Reliability', field: 'reliability', align: 'right' as const, format: (v: number | null) => v != null ? (v * 100).toFixed(0) + '%' : '-' },
];

const taskStatsCols = [
  { name: 'task_name', label: 'Task', field: 'task_name', align: 'left' as const },
  { name: 'comparison_count', label: 'Comparisons', field: 'comparison_count', align: 'right' as const },
  { name: 'rating_count', label: 'Ratings', field: 'rating_count', align: 'right' as const },
];

onMounted(async () => {
  void apiService.getMyStats().then((s) => { myStats.value = s; });
  loadingGlobal.value = true;
  void apiService.getGlobalStats().then((s) => { globalStats.value = s; loadingGlobal.value = false; });
  void apiService.getTasks().then((t) => { tasks.value = t; });
  loadingOverall.value = true;
  const [weekly, allTime] = await Promise.all([
    apiService.getOverallLeaderboard(7),
    apiService.getOverallLeaderboard(),
  ]);
  weeklyLb.value = weekly;
  allTimeLb.value = allTime;
  loadingOverall.value = false;
});

async function loadTaskLb(taskId: string) {
  if (taskLbs[taskId]) return;
  taskLbs[taskId] = await apiService.getTaskLeaderboard(taskId);
}
</script>
