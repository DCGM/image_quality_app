import { defineStore } from 'pinia';
import { apiService } from 'src/services/api';
import { TaskRead } from 'src/types/api';

interface TaskState {
  tasks: TaskRead[];
  selectedTaskId: string | null;
  loading: boolean;
}

export const useTaskStore = defineStore('tasks', {
  state: (): TaskState => ({
    tasks: [],
    selectedTaskId: null,
    loading: false,
  }),

  getters: {
    selectedTask: (state): TaskRead | null =>
      state.tasks.find((t) => t.id === state.selectedTaskId) ?? null,
  },

  actions: {
    async fetchTasks() {
      this.loading = true;
      try {
        this.tasks = await apiService.getTasks();
      } finally {
        this.loading = false;
      }
    },

    selectTask(taskId: string) {
      this.selectedTaskId = taskId;
    },

    clearSelection() {
      this.selectedTaskId = null;
    },
  },
});
