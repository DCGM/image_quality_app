<template>
  <q-dialog v-model="open" maximized persistent transition-show="slide-up" transition-hide="slide-down">
    <q-card class="column full-height">
      <q-card-section class="row items-center bg-primary text-white">
        <div class="text-h6">Select tasks to annotate</div>
        <q-space />
        <q-btn flat round dense icon="close" @click="cancel" />
      </q-card-section>

      <q-card-section class="text-caption text-grey-7">
        Choose between 1 and 6 tasks. Click a task name to read its description.
      </q-card-section>

      <q-scroll-area class="col">
        <q-list separator class="q-pa-sm">
          <q-expansion-item
            v-for="task in tasks"
            :key="task.id"
            :label="task.name"
            :caption="task.multi_choice ? `Multi-choice (up to ${task.max_choices})` : 'Single choice'"
            expand-separator
            header-class="q-pa-sm"
          >
            <template #header>
              <q-item-section side>
                <q-checkbox
                  :model-value="selected.includes(task.id)"
                  :disable="!selected.includes(task.id) && selected.length >= 6"
                  @update:model-value="(val) => toggle(task.id, val)"
                  @click.stop
                />
              </q-item-section>
              <q-item-section>
                <q-item-label>{{ task.name }}</q-item-label>
                <q-item-label caption>
                  {{ task.multi_choice ? `Multi-choice (up to ${task.max_choices})` : 'Single choice' }}
                </q-item-label>
              </q-item-section>
              <q-item-section side class="row items-center q-gutter-xs no-wrap">
                <q-badge
                  v-if="task.current_multiplier && task.current_multiplier > 1.0"
                  color="orange"
                  :label="`×${task.current_multiplier.toFixed(1)} pts`"
                />
                <q-badge v-if="selected.includes(task.id)" color="positive" label="selected" />
              </q-item-section>
            </template>

            <q-card flat class="bg-grey-1 q-ma-sm">
              <q-card-section>
                <MarkdownView :content="task.description_md" />
              </q-card-section>
            </q-card>
          </q-expansion-item>
        </q-list>
      </q-scroll-area>

      <q-separator />

      <q-card-actions align="right" class="q-pa-md">
        <div class="text-caption text-grey-7 q-mr-auto">
          {{ selected.length }} / 6 tasks selected
        </div>
        <q-btn flat label="Cancel" @click="cancel" />
        <q-btn
          color="primary"
          label="Confirm selection"
          :disable="selected.length === 0"
          @click="confirm"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { TaskDefinition } from 'src/types/api';
import MarkdownView from 'components/MarkdownView.vue';

const props = defineProps<{
  modelValue: boolean;
  tasks: TaskDefinition[];
  initialSelection: string[];
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void;
  (e: 'confirmed', ids: string[]): void;
  (e: 'cancelled'): void;
}>();

const open = ref(props.modelValue);
const selected = ref<string[]>([...props.initialSelection]);

watch(() => props.modelValue, (val) => {
  open.value = val;
  if (val) selected.value = [...props.initialSelection];
});
watch(open, (val) => emit('update:modelValue', val));

const toggle = (id: string, checked: boolean) => {
  if (checked) {
    if (selected.value.length < 6) selected.value.push(id);
  } else {
    selected.value = selected.value.filter((s) => s !== id);
  }
};

const confirm = () => {
  emit('confirmed', [...selected.value]);
  open.value = false;
};

const cancel = () => {
  emit('cancelled');
  open.value = false;
};
</script>
