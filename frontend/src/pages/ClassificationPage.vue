<template>
  <q-page class="q-pa-md">

    <!-- Task selection dialog -->
    <TaskSelectionDialog
      v-model="showTaskDialog"
      :tasks="allTasks"
      :initial-selection="selectedTaskIds"
      @confirmed="onTasksConfirmed"
    />

    <!-- Calibration feedback overlay -->
    <div v-if="calibFeedback.length" class="column items-center q-mt-xl">
      <div class="text-h6 q-mb-md"><q-icon name="quiz" color="primary" class="q-mr-sm" />Calibration result</div>
      <q-card
        v-for="fb in calibFeedback"
        :key="fb.task_id"
        class="q-mb-md"
        bordered
        style="min-width:320px;max-width:560px;width:100%"
      >
        <q-card-section>
          <div class="text-subtitle2 q-mb-sm">{{ fb.task_name }}</div>
          <div class="row q-col-gutter-md">
            <div class="col-6">
              <div class="text-caption text-grey-6">Your answer</div>
              <div class="text-body2">{{ fb.submitted.join(', ') || '—' }}</div>
            </div>
            <div class="col-6">
              <div class="text-caption text-grey-6">Correct answer</div>
              <div class="text-body2">{{ fb.gt.join(', ') || '—' }}</div>
            </div>
          </div>
        </q-card-section>
        <q-separator />
        <q-card-section class="row items-center">
          <q-icon
            :name="fb.match ? 'check_circle' : 'cancel'"
            :color="fb.match ? 'positive' : 'negative'"
            size="24px"
            class="q-mr-sm"
          />
          <span :class="fb.match ? 'text-positive' : 'text-negative'">
            {{ fb.match ? 'Correct!' : 'Incorrect' }}
          </span>
        </q-card-section>
      </q-card>
      <q-btn color="primary" label="Continue" icon-right="arrow_forward" @click="continueAfterCalib" />
    </div>

    <!-- No tasks selected yet -->
    <div v-else-if="selectedTaskIds.length === 0" class="column items-center q-mt-xl">
      <q-icon name="checklist" size="64px" color="grey-5" />
      <div class="text-h6 text-grey-6 q-mt-md">No tasks selected</div>
      <q-btn class="q-mt-lg" color="primary" icon="add_task" label="Choose tasks" @click="openTaskDialog" />
    </div>

    <!-- Loading -->
    <div v-else-if="loading" class="column items-center q-mt-xl">
      <q-spinner-dots size="48px" color="primary" />
    </div>

    <!-- No more texts -->
    <div v-else-if="!textItem" class="column items-center q-mt-xl">
      <q-icon name="check_circle" size="64px" color="positive" />
      <div class="text-h6 q-mt-md">All done for now!</div>
      <div class="text-caption text-grey-7 q-mt-sm">No more texts to annotate for your selected tasks.</div>
      <q-btn flat class="q-mt-lg" color="primary" label="Change tasks" @click="openTaskDialog" />
    </div>

    <!-- Annotation flow -->
    <div v-else>
      <!-- Header row -->
      <div class="row items-center q-mb-md">
        <div class="text-caption text-grey-6">
          Task {{ currentTaskIndex + 1 }} of {{ tasks.length }}
        </div>
        <q-space />
        <q-btn flat dense size="sm" icon="tune" label="Change tasks" @click="openTaskDialog" />
      </div>

      <!-- Progress bar -->
      <q-linear-progress
        :value="(currentTaskIndex) / tasks.length"
        color="primary"
        class="q-mb-md"
        rounded
        style="height: 6px"
      />

      <!-- Text card -->
      <q-card class="q-mb-lg" bordered>
        <q-card-section>
          <div class="row items-center q-mb-xs">
            <q-badge outline :label="textItem.language" class="q-mr-sm" />
            <div class="text-caption text-grey-6">{{ myTotal }} annotations submitted</div>
          </div>
          <div class="classified-text text-body1">{{ textItem.text }}</div>
        </q-card-section>
      </q-card>

      <!-- Current task card -->
      <q-card v-if="currentTask" bordered>
        <q-card-section>
          <div class="row items-center q-mb-xs">
            <div class="text-h6">{{ currentTask.name }}</div>
            <q-space />
            <q-btn flat round dense size="sm" :icon="showDescription ? 'expand_less' : 'info_outline'" @click="showDescription = !showDescription">
              <q-tooltip>{{ showDescription ? 'Hide' : 'Show' }} task description</q-tooltip>
            </q-btn>
          </div>

          <q-slide-transition>
            <div v-if="showDescription" class="q-mb-md">
              <q-separator class="q-mb-sm" />
              <MarkdownView :content="currentTask.description_md" />
              <q-separator class="q-mt-sm" />
            </div>
          </q-slide-transition>

          <div class="text-caption text-grey-7 q-mb-sm">
            {{ currentTask.multi_choice
              ? `Choose 1 to ${currentTask.max_choices} options.`
              : 'Choose exactly 1 option.' }}
          </div>

          <!-- Per-class radio / checkbox with info icons -->
          <div v-for="cls in currentTask.classes" :key="cls.id" class="row items-center no-wrap q-mb-xs">
            <q-radio
              v-if="!currentTask.multi_choice"
              v-model="(answers as Record<string, string>)[currentTask.id]"
              :val="cls.id"
              :label="cls.label_en"
              dense
            />
            <q-checkbox
              v-else
              v-model="(answers as Record<string, string[]>)[currentTask.id]"
              :val="cls.id"
              :label="cls.label_en"
              dense
              @update:model-value="limitMultiChoice(currentTask)"
            />
            <q-btn
              v-if="cls.description"
              flat round dense size="xs" icon="info_outline"
              class="q-ml-xs text-grey-6"
            >
              <q-tooltip anchor="center right" self="center left" max-width="360px" class="text-body2">
                {{ cls.description }}
              </q-tooltip>
            </q-btn>
          </div>
        </q-card-section>

        <q-separator />

        <q-card-actions align="right" class="q-pa-md">
          <q-btn v-if="currentTaskIndex > 0" flat label="Back" icon="arrow_back" @click="prevTask" />
          <q-space />
          <q-btn
            v-if="currentTaskIndex < tasks.length - 1"
            color="primary"
            label="Next task"
            icon-right="arrow_forward"
            :disable="!currentTaskAnswered"
            @click="nextTask"
          />
          <q-btn
            v-else
            color="positive"
            label="Submit"
            icon-right="send"
            :disable="!allAnswered"
            :loading="submitting"
            @click="submit"
          />
        </q-card-actions>
      </q-card>

      <!-- Answers summary (always visible when > 1 task) -->
      <q-card v-if="tasks.length > 1" flat bordered class="q-mt-md">
        <q-card-section>
          <div class="text-subtitle2 q-mb-sm">Summary</div>
          <q-list dense>
            <q-item
              v-for="(task, i) in tasks" :key="task.id"
              :clickable="i !== currentTaskIndex && i <= firstUnansweredIndex"
              :class="{ 'text-grey-5': i > firstUnansweredIndex }"
              @click="i !== currentTaskIndex && i <= firstUnansweredIndex && goToTask(i)"
            >
              <q-item-section side>
                <q-icon
                  :name="i === currentTaskIndex ? 'edit' : (selectedClasses(task).length > 0 ? 'check_circle' : 'radio_button_unchecked')"
                  :color="i === currentTaskIndex ? 'primary' : (selectedClasses(task).length > 0 ? 'positive' : 'grey-4')" />
              </q-item-section>
              <q-item-section>
                <q-item-label :class="i === currentTaskIndex ? 'text-primary text-weight-medium' : ''">{{ task.name }}</q-item-label>
                <q-item-label caption>{{ selectedClasses(task).join(', ') || (i < currentTaskIndex ? 'not answered' : (i === currentTaskIndex ? 'in progress…' : '')) }}</q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
        </q-card-section>
      </q-card>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { apiService } from 'src/services/api';
import { NextTextResponse, TaskDefinition } from 'src/types/api';
import TaskSelectionDialog from 'components/TaskSelectionDialog.vue';
import MarkdownView from 'components/MarkdownView.vue';

interface CalibItem {
  task_id: string;
  task_name: string;
  submitted: string[];
  gt: string[];
  match: boolean;
}

const allTasks = ref<TaskDefinition[]>([]);
const tasks = ref<TaskDefinition[]>([]);
const textItem = ref<NextTextResponse | null>(null);
const answers = ref<Record<string, string[] | string>>({});
const myTotal = ref(0);
const loading = ref(false);
const submitting = ref(false);
const showTaskDialog = ref(false);
const showDescription = ref(false);
const currentTaskIndex = ref(0);
const taskStartTimes = ref<Record<string, string>>({});
const calibFeedback = ref<CalibItem[]>([]);

const selectedTaskIds = ref<string[]>(JSON.parse(localStorage.getItem('selected_tasks') ?? '[]'));
const currentTask = computed(() => tasks.value[currentTaskIndex.value] ?? null);

const selectedClasses = (task: TaskDefinition): string[] => {
  const value = answers.value[task.id];
  if (Array.isArray(value)) return value;
  return value ? [value] : [];
};

const currentTaskAnswered = computed(() => {
  if (!currentTask.value) return false;
  return selectedClasses(currentTask.value).length > 0;
});

const allAnswered = computed(() => tasks.value.every((t) => selectedClasses(t).length > 0));

const load = async () => {
  loading.value = true;
  try {
    const ids = selectedTaskIds.value;
    if (ids.length === 0) { loading.value = false; return; }
    const all = await apiService.getTasks();
    tasks.value = all.filter((t) => ids.includes(t.id));
    textItem.value = await apiService.getNextText(ids);
    answers.value = {};
    taskStartTimes.value = {};
    currentTaskIndex.value = 0;
    showDescription.value = false;
    for (const task of tasks.value) {
      answers.value[task.id] = task.multi_choice ? [] : '';
    }
    if (tasks.value[0]) {
      taskStartTimes.value[tasks.value[0].id] = new Date().toISOString();
    }
    const stats = await apiService.getMyStats();
    myTotal.value = stats.total;
  } finally {
    loading.value = false;
  }
};

onMounted(async () => {
  allTasks.value = await apiService.getTasks();
  if (selectedTaskIds.value.length === 0) {
    showTaskDialog.value = true;
  } else {
    await load();
  }
});

const openTaskDialog = () => { showTaskDialog.value = true; };

const onTasksConfirmed = async (ids: string[]) => {
  selectedTaskIds.value = ids;
  localStorage.setItem('selected_tasks', JSON.stringify(ids));
  await load();
};

const limitMultiChoice = (task: TaskDefinition) => {
  if (!task.multi_choice) return;
  const selected = selectedClasses(task);
  if (selected.length > task.max_choices) {
    answers.value[task.id] = selected.slice(0, task.max_choices);
  }
};

const goToTask = (index: number) => {
  currentTaskIndex.value = index;
  showDescription.value = false;
  const task = tasks.value[index];
  if (task && !taskStartTimes.value[task.id]) {
    taskStartTimes.value[task.id] = new Date().toISOString();
  }
};

const nextTask = () => {
  if (currentTaskIndex.value < tasks.value.length - 1) goToTask(currentTaskIndex.value + 1);
};

const prevTask = () => {
  if (currentTaskIndex.value > 0) goToTask(currentTaskIndex.value - 1);
};

const submit = async () => {
  if (!textItem.value || !allAnswered.value) return;
  submitting.value = true;
  const endTime = new Date().toISOString();
  const submittedTextItem = textItem.value;
  const submittedAnswers = { ...answers.value };
  try {
    await apiService.submitAnnotations({
      text_id: submittedTextItem.id,
      annotations: tasks.value.map((t) => ({
        task_id: t.id,
        selected_classes: selectedClasses(t),
        start_time: taskStartTimes.value[t.id] || endTime,
        end_time: endTime,
      })),
    });
    // Show calibration feedback if needed
    const calibIds = submittedTextItem.calibration_task_ids ?? [];
    if (calibIds.length > 0) {
      const gtMap = await apiService.getGroundTruth(submittedTextItem.id, calibIds);
      calibFeedback.value = calibIds
        .filter((tid) => tid in gtMap)
        .map((tid) => {
          const task = tasks.value.find((t) => t.id === tid);
          const submitted = (Array.isArray(submittedAnswers[tid]) ? submittedAnswers[tid] : submittedAnswers[tid] ? [submittedAnswers[tid]] : []) as string[];
          const gt = gtMap[tid] ?? [];
          const match = submitted.length === gt.length && submitted.every((c) => gt.includes(c));
          return { task_id: tid, task_name: task?.name ?? tid, submitted, gt, match };
        });
      if (calibFeedback.value.length > 0) return; // wait for user to click Continue
    }
    await load();
  } finally {
    submitting.value = false;
  }
};

const continueAfterCalib = async () => {
  calibFeedback.value = [];
  await load();
};

// Reload when tasks list is available
watch(allTasks, (val) => {
  if (val.length > 0 && selectedTaskIds.value.length > 0 && tasks.value.length === 0) {
    void load();
  }
});
</script>

<style scoped>
.classified-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.6;
}
</style>
