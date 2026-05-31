<template>
  <q-page class="q-pa-md">

    <!-- My contributions -->
    <div class="text-h5 q-mb-sm">My contributions</div>
    <q-card class="q-mb-lg" bordered>
      <q-card-section>
        <div class="row q-col-gutter-md q-mb-sm">
          <div class="col-auto">
            <div class="text-caption text-grey-6">Annotations</div>
            <div class="text-h6">{{ myStats.total }}</div>
          </div>
          <div class="col-auto">
            <div class="text-caption text-grey-6">Score</div>
            <div class="text-h6 text-primary">{{ myStats.score?.toFixed(1) ?? '0.0' }}</div>
          </div>
        </div>
        <q-table
          v-if="myPerTaskRows.length"
          :rows="myPerTaskRows"
          :columns="myStatsCols"
          flat
          dense
          hide-bottom
          :rows-per-page-options="[0]"
        />
        <div v-else class="text-caption text-grey-6">No annotations yet.</div>
      </q-card-section>
    </q-card>

    <!-- Overall top annotators -->
    <div class="text-h5 q-mb-sm">Top annotators</div>
    <q-tabs v-model="overallTab" align="left" class="q-mb-sm">
      <q-tab name="week" icon="date_range" label="This week" />
      <q-tab name="all" icon="all_inclusive" label="All time" />
    </q-tabs>
    <q-card class="q-mb-lg" bordered>
      <q-tab-panels v-model="overallTab" animated>
        <q-tab-panel name="week">
          <q-table :rows="weeklyLb" :columns="lbCols" flat dense hide-bottom :rows-per-page-options="[0]"
            :loading="loadingOverall" no-data-label="No data for this week" />
        </q-tab-panel>
        <q-tab-panel name="all">
          <q-table :rows="allTimeLb" :columns="lbCols" flat dense hide-bottom :rows-per-page-options="[0]"
            :loading="loadingOverall" no-data-label="No annotations yet" />
        </q-tab-panel>
      </q-tab-panels>
    </q-card>

    <!-- Global stats per task -->
    <div class="text-h5 q-mb-sm">Statistics per task</div>
    <q-card class="q-mb-lg" bordered>
      <q-card-section>
        <div class="text-caption text-grey-6 q-mb-sm">Total across all tasks: {{ globalStats.total_annotations }}</div>
        <q-table
          :rows="globalStats.per_task"
          :columns="taskStatsCols"
          flat dense hide-bottom :rows-per-page-options="[0]"
          :loading="loadingGlobal"
          no-data-label="No annotations yet"
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
        @before-show="loadTaskLeaderboard(task.id)"
      >
        <q-card flat>
          <q-card-section>
            <q-table
              :rows="taskLbs[task.id] || []"
              :columns="lbCols"
              flat dense hide-bottom :rows-per-page-options="[0]"
              :loading="loadingTask[task.id]"
              no-data-label="No annotations yet"
            />
          </q-card-section>
        </q-card>
      </q-expansion-item>
    </q-list>

  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { QTableColumn } from 'quasar';
import { apiService } from 'src/services/api';
import { GlobalStats, LeaderboardEntry, MyStats, TaskDefinition } from 'src/types/api';

const myStats = ref<MyStats>({ total: 0, per_task: {} });
const tasks = ref<TaskDefinition[]>([]);
const weeklyLb = ref<LeaderboardEntry[]>([]);
const allTimeLb = ref<LeaderboardEntry[]>([]);
const globalStats = ref<GlobalStats>({ total_annotations: 0, per_task: [] });
const taskLbs = ref<Record<string, LeaderboardEntry[]>>({});
const loadingOverall = ref(false);
const loadingGlobal = ref(false);
const loadingTask = ref<Record<string, boolean>>({});
const overallTab = ref('week');

const myPerTaskRows = ref<{ task_id: string; task_name: string; count: number }[]>([]);

const myStatsCols: QTableColumn[] = [
  { name: 'task_name', label: 'Task', field: 'task_name', align: 'left' },
  { name: 'count', label: 'Annotations', field: 'count', align: 'right' },
  { name: 'score', label: 'Score', field: 'score', align: 'right', format: (v: number) => v?.toFixed(1) ?? '—' },
];
const lbCols: QTableColumn[] = [
  { name: 'rank', label: '#', field: (_: LeaderboardEntry, ri: number) => ri + 1, align: 'right', style: 'width:40px' },
  { name: 'display_name', label: 'Annotator', field: 'display_name', align: 'left' },
  { name: 'count', label: 'Annotations', field: 'count', align: 'right' },
  { name: 'score', label: 'Score', field: 'score', align: 'right', format: (v: number) => v?.toFixed(1) ?? '—' },
  { name: 'reliability', label: 'Reliability', field: 'reliability', align: 'right', format: (v: number | null) => v != null ? `${(v * 100).toFixed(0)}%` : '—' },
];
const taskStatsCols: QTableColumn[] = [
  { name: 'task_name', label: 'Task', field: 'task_name', align: 'left' },
  { name: 'count', label: 'Total annotations', field: 'count', align: 'right' },
];

const loadTaskLeaderboard = async (taskId: string) => {
  if (taskLbs.value[taskId]) return;
  loadingTask.value[taskId] = true;
  taskLbs.value[taskId] = await apiService.getLeaderboard(taskId);
  loadingTask.value[taskId] = false;
};

onMounted(async () => {
  [tasks.value, myStats.value] = await Promise.all([
    apiService.getTasks(),
    apiService.getMyStats(),
  ]);

  // Build per-task rows for my stats, enriched with task names
  const taskNameMap: Record<string, string> = Object.fromEntries(tasks.value.map((t) => [t.id, t.name]));
  myPerTaskRows.value = Object.entries(myStats.value.per_task).map(([id, count]) => ({
    task_id: id, task_name: taskNameMap[id] || id, count,
    score: myStats.value.per_task_score?.[id] ?? 0,
  })).sort((a, b) => b.score - a.score);

  loadingOverall.value = true;
  loadingGlobal.value = true;
  [weeklyLb.value, allTimeLb.value, globalStats.value] = await Promise.all([
    apiService.getOverallLeaderboard(7),
    apiService.getOverallLeaderboard(),
    apiService.getGlobalStats(),
  ]);
  loadingOverall.value = false;
  loadingGlobal.value = false;
});
</script>
