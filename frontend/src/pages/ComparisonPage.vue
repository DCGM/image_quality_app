<template>
  <q-page class="q-pa-md comparison-page">
    <!-- Task header -->
    <div class="row items-center q-mb-md">
      <q-btn flat round dense icon="arrow_back" @click="goBack" class="q-mr-sm" />
      <div class="text-h5">{{ task?.name }}</div>
      <q-space />
      <q-badge color="deep-purple" label="2-Choice" />
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
      <div class="text-h6">All images have been compared!</div>
      <div class="text-grey-6 q-mt-sm">Come back later for more comparisons.</div>
      <q-btn class="q-mt-lg" color="primary" label="Back to tasks" @click="goBack" />
    </div>

    <!-- Pair comparison -->
    <div v-else-if="annoStore.currentPair" class="comparison-container">
      <div class="text-body2 text-grey-6 text-center q-mb-sm">
        Click the <strong>better</strong> image, or use ← → arrow keys
        <q-badge v-if="annoStore.currentPair.is_reliability_check" color="amber" label="Consistency check" class="q-ml-sm" />
      </div>

      <div class="row q-col-gutter-md justify-center">
        <!-- Image A -->
        <div class="col-12 col-sm-6">
          <q-card
            class="image-card cursor-pointer"
            :class="{ selected: selectedId === annoStore.currentPair.image_a_id, 'flash-green': flashWinner === 'a' }"
            bordered
            @click="choose(annoStore.currentPair.image_a_id)"
          >
            <img
              :src="imageUrl(annoStore.currentPair.image_a_url)"
              class="comparison-image"
              alt="Image A"
            />
            <q-card-section class="text-center q-pa-xs">
              <q-icon name="keyboard_arrow_left" /> Press ← or click
            </q-card-section>
          </q-card>
        </div>

        <!-- Image B -->
        <div class="col-12 col-sm-6">
          <q-card
            class="image-card cursor-pointer"
            :class="{ selected: selectedId === annoStore.currentPair.image_b_id, 'flash-green': flashWinner === 'b' }"
            bordered
            @click="choose(annoStore.currentPair.image_b_id)"
          >
            <img
              :src="imageUrl(annoStore.currentPair.image_b_url)"
              class="comparison-image"
              alt="Image B"
            />
            <q-card-section class="text-center q-pa-xs">
              Press → or click <q-icon name="keyboard_arrow_right" />
            </q-card-section>
          </q-card>
        </div>
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
import { onMounted, onUnmounted, ref, watch } from 'vue';
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
const selectedId = ref<string | null>(null);
const flashWinner = ref<'a' | 'b' | null>(null);
const showPoints = ref(false);

onMounted(async () => {
  task.value = taskStore.tasks.find((t) => t.id === taskId) ?? await apiService.getTask(taskId);
  await annoStore.fetchNextPair(taskId);
  window.addEventListener('keydown', onKeyDown);
});

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown);
  annoStore.reset();
});

function onKeyDown(e: KeyboardEvent) {
  if (!annoStore.currentPair) return;
  if (e.key === 'ArrowLeft') choose(annoStore.currentPair.image_a_id);
  else if (e.key === 'ArrowRight') choose(annoStore.currentPair.image_b_id);
}

async function choose(winnerId: string) {
  if (!annoStore.currentPair || selectedId.value) return;
  const pair = annoStore.currentPair;
  selectedId.value = winnerId;
  flashWinner.value = winnerId === pair.image_a_id ? 'a' : 'b';

  try {
    await annoStore.submitComparison(taskId, pair.image_a_id, pair.image_b_id, winnerId);
    showPoints.value = true;
    setTimeout(() => { showPoints.value = false; }, 1500);
  } catch {
    /* ignore */
  }

  setTimeout(async () => {
    selectedId.value = null;
    flashWinner.value = null;
    await annoStore.fetchNextPair(taskId);
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
.comparison-page { max-width: 1200px; margin: 0 auto; }
.comparison-image { width: 100%; height: auto; object-fit: contain; max-height: 60vh; display: block; }
.image-card { transition: box-shadow 0.15s, border-color 0.15s; }
.image-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.2); }
.image-card.selected { border: 3px solid var(--q-primary); }
.flash-green { border: 3px solid #21ba45 !important; }
.fade-enter-active, .fade-leave-active { transition: opacity 0.5s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
