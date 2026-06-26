import { defineStore } from 'pinia';
import { apiService } from 'src/services/api';
import { NextImageResponse, NextPairResponse } from 'src/types/api';

interface AnnotationState {
  currentPair: NextPairResponse | null;
  currentImage: NextImageResponse | null;
  startTime: string | null;
  lastPoints: number | null;
  loading: boolean;
  done: boolean;
}

export const useAnnotationStore = defineStore('annotations', {
  state: (): AnnotationState => ({
    currentPair: null,
    currentImage: null,
    startTime: null,
    lastPoints: null,
    loading: false,
    done: false,
  }),

  actions: {
    async fetchNextPair(taskId: string) {
      this.loading = true;
      this.currentPair = null;
      this.done = false;
      try {
        const pair = await apiService.getNextPair(taskId);
        if (pair === null) {
          this.done = true;
        } else {
          this.currentPair = pair;
          this.startTime = new Date().toISOString();
        }
      } finally {
        this.loading = false;
      }
    },

    async fetchNextImage(taskId: string) {
      this.loading = true;
      this.currentImage = null;
      this.done = false;
      try {
        const img = await apiService.getNextImage(taskId);
        if (img === null) {
          this.done = true;
        } else {
          this.currentImage = img;
          this.startTime = new Date().toISOString();
        }
      } finally {
        this.loading = false;
      }
    },

    async submitComparison(taskId: string, imageAId: string, imageBId: string, winnerId: string) {
      if (!this.startTime) return;
      const result = await apiService.submitComparison({
        task_id: taskId,
        image_a_id: imageAId,
        image_b_id: imageBId,
        winner_id: winnerId,
        start_time: this.startTime,
        end_time: new Date().toISOString(),
      });
      this.lastPoints = result.points;
    },

    async submitRating(taskId: string, imageId: string, selectedOption: string) {
      if (!this.startTime) return;
      const result = await apiService.submitRating({
        task_id: taskId,
        image_id: imageId,
        selected_option: selectedOption,
        start_time: this.startTime,
        end_time: new Date().toISOString(),
      });
      this.lastPoints = result.points;
    },

    reset() {
      this.currentPair = null;
      this.currentImage = null;
      this.startTime = null;
      this.lastPoints = null;
      this.done = false;
    },
  },
});
