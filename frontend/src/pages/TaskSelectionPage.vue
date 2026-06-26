<template>
  <q-page class="q-pa-md">
    <div class="text-h4 q-mb-md">Select a Task</div>
    <div class="text-body1 text-grey-7 q-mb-lg">
      Choose an image-rating task to start annotating.
    </div>

    <div v-if="taskStore.loading" class="flex flex-center q-pa-xl">
      <q-spinner-dots size="3em" color="primary" />
    </div>

    <div v-else-if="taskStore.tasks.length === 0" class="text-grey-6 text-center q-pa-xl">
      No tasks available right now. Check back later.
    </div>

    <div v-else class="row q-col-gutter-md">
      <div
        v-for="task in taskStore.tasks"
        :key="task.id"
        class="col-12 col-sm-6 col-md-4"
      >
        <q-card
          class="task-card cursor-pointer full-height"
          bordered
          @click="selectTask(task)"
        >
          <q-card-section>
            <div class="row items-center q-mb-sm">
              <q-badge
                :color="task.task_type === 'two_forced_choice' ? 'deep-purple' : 'teal'"
                :label="task.task_type === 'two_forced_choice' ? '2-Choice' : 'Rating'"
                class="q-mr-sm"
              />
              <q-badge
                v-if="task.bonus_multiplier > 1"
                color="orange"
                :label="`×${task.bonus_multiplier.toFixed(1)} bonus`"
              />
            </div>
            <div class="text-h6">{{ task.name }}</div>
            <div class="text-body2 text-grey-7 q-mt-sm ellipsis-3-lines">
              {{ stripMd(task.description_md) }}
            </div>
          </q-card-section>
          <q-card-actions align="right">
            <q-btn flat color="primary" label="Start" icon-right="arrow_forward" @click.stop="selectTask(task)" />
          </q-card-actions>
        </q-card>
      </div>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useTaskStore } from 'src/stores/task-store';
import { TaskRead } from 'src/types/api';

const router = useRouter();
const taskStore = useTaskStore();

onMounted(async () => {
  await taskStore.fetchTasks();
});

function stripMd(md: string): string {
  return md.replace(/[#*_`>\[\]]/g, '').substring(0, 200);
}

function selectTask(task: TaskRead) {
  taskStore.selectTask(task.id);
  if (task.task_type === 'two_forced_choice') {
    void router.push(`/compare/${task.id}`);
  } else {
    void router.push(`/rate/${task.id}`);
  }
}
</script>

<style scoped>
.task-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transition: box-shadow 0.2s;
}
.ellipsis-3-lines {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
