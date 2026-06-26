<template>
  <q-page class="q-pa-md rating-page">
    <!-- Task header -->
    <div class="row items-center q-mb-md">
      <q-btn flat round dense icon="arrow_back" @click="goBack" class="q-mr-sm" />
      <div class="text-h5">{{ task?.name }}</div>
      <q-space />
      <q-badge color="teal" label="Rating" />
    </div>

    <!-- Instructions (collapsible) -->
    <q-expansion-item
      v-if="task?.instructions_md"
      icon="info_outline"
      label="Instructions"
      class="q-mb-md"
      dense
    >
      <q-card flat>
        <q-card-section>
          <MarkdownView :content="task.instructions_md" />
        </q-card-section>
      </q-card>
    </q-expansion-item>

    <!-- Loading -->
    <div v-if="annoStore.loading" class="flex flex-center q-pa-xl">
      <q-spinner-dots size="3em" color="primary" />
    </div>

    <!-- Done -->
    <div v-else-if="annoStore.done" class="flex flex-center column q-pa-xl text-center">
      <q-icon name="check_circle" color="positive" size="4em" class="q-mb-md" />
      <div class="text-h6">All images have been rated!</div>
      <div class="text-grey-6 q-mt-sm">Come back later for more images.</div>
      <q-btn class="q-mt-lg" color="primary" label="Back to tasks" @click="goBack" />
    </div>

    <!-- Rating interface -->
    <div v-else-if="annoStore.currentImage" class="rating-container">
      <div class="text-body2 text-grey-6 text-center q-mb-sm">
        Rate this image
        <q-badge v-if="annoStore.currentImage.is_reliability_check" color="amber" label="Consistency check" class="q-ml-sm" />
      </div>

      <!-- Image -->
      <div class="image-wrapper q-mb-md">
        <img
          :src="imageUrl(annoStore.currentImage.image_url)"
          class="rating-image"
          alt="Image to rate"
        />
      </div>

      <!-- Options -->
      <div class="row justify-center q-gutter-sm">
        <q-btn
          v-for="(option, idx) in task?.rating_options ?? []"
          :key="option"
          :label="hotkeyLabel(option, idx)"
          color="primary"
          :outline="selectedOption !== option"
          :disable="!!selectedOption"
          size="lg"
          @click="choose(option)"
        />
      </div>

      <!-- Points feedback -->
      <transition name="fade">
        <div v-if="showPoints" class="text-center q-mt-md text-positive text-h6">
          +{{ annoStore.lastPoints?.toFixed(2) }} pts
        </div>
      </transition>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAnnotationStore } from 'src/stores/annotation-store';
import { useTaskStore } from 'src/stores/task-store';
import { apiService } from 'src/services/api';
import { TaskRead } from 'src/types/api';
import MarkdownView from 'src/components/MarkdownView.vue';

const route = useRoute();
const router = useRouter();
const annoStore = useAnnotationStore();
const taskStore = useTaskStore();

const taskId = route.params.taskId as string;
const task = ref<TaskRead | null>(null);
const selectedOption = ref<string | null>(null);
const showPoints = ref(false);

onMounted(async () => {
  task.value = taskStore.tasks.find((t) => t.id === taskId) ?? await apiService.getTask(taskId);
  await annoStore.fetchNextImage(taskId);
  window.addEventListener('keydown', onKeyDown);
});

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown);
  annoStore.reset();
});

function hotkeyLabel(option: string, idx: number): string {
  const hotkeys = task.value?.rating_hotkeys;
  if (hotkeys && hotkeys[idx]) return `${option} [${hotkeys[idx]}]`;
  return `${option} [${idx + 1}]`;
}

function onKeyDown(e: KeyboardEvent) {
  if (!annoStore.currentImage || selectedOption.value) return;
  const options = task.value?.rating_options ?? [];
  const hotkeys = task.value?.rating_hotkeys;
  if (hotkeys) {
    const hIdx = hotkeys.indexOf(e.key);
    if (hIdx >= 0 && hIdx < options.length) { choose(options[hIdx]); return; }
  }
  const numKey = parseInt(e.key, 10);
  if (!isNaN(numKey) && numKey >= 1 && numKey <= options.length) {
    choose(options[numKey - 1]);
  }
}

async function choose(option: string) {
  if (!annoStore.currentImage || selectedOption.value) return;
  const img = annoStore.currentImage;
  selectedOption.value = option;

  try {
    await annoStore.submitRating(taskId, img.image_id, option);
    showPoints.value = true;
    setTimeout(() => { showPoints.value = false; }, 1500);
  } catch {
    /* ignore */
  }

  setTimeout(async () => {
    selectedOption.value = null;
    await annoStore.fetchNextImage(taskId);
  }, 600);
}

function imageUrl(path: string): string {
  return apiService.imageUrl(path);
}

function goBack() {
  void router.push('/tasks');
}
</script>

<style scoped>
.rating-page { max-width: 960px; margin: 0 auto; }
.image-wrapper { display: flex; justify-content: center; }
.rating-image { max-width: 100%; max-height: 65vh; object-fit: contain; border-radius: 8px; }
.fade-enter-active, .fade-leave-active { transition: opacity 0.5s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
