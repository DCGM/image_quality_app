import { api, resolvedApiUrl } from 'boot/axios';
import {
  BearerResponse, ComparisonSubmit, GlobalStats, ImageListResponse,
  ImageRankingResponse, LeaderboardEntry, LoginRequest, MyStats,
  NextImageResponse, NextPairResponse, PaginatedComparisons, PaginatedRatings,
  RatingSubmit, TaskCreate, TaskRead, TaskStatePatch, UserCreate, UserRead,
  UserReliabilityResponse,
} from 'src/types/api';

class ApiService {
  // Auth
  async login(credentials: LoginRequest): Promise<BearerResponse> {
    const formData = new URLSearchParams();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);
    return (await api.post<BearerResponse>('/auth/jwt/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })).data;
  }

  async getCurrentUser(): Promise<UserRead> {
    return (await api.get<UserRead>('/users/me')).data;
  }

  async register(userData: UserCreate): Promise<UserRead> {
    return (await api.post<UserRead>('/auth/register', userData)).data;
  }

  async logout(): Promise<void> {
    await api.post('/auth/jwt/logout').catch(() => undefined);
  }

  // Tasks (public)
  async getTasks(): Promise<TaskRead[]> {
    return (await api.get<TaskRead[]>('/api/tasks')).data;
  }

  async getTask(taskId: string): Promise<TaskRead> {
    return (await api.get<TaskRead>(`/api/tasks/${taskId}`)).data;
  }

  async getAlgorithmDescriptions(): Promise<Record<string, string>> {
    return (await api.get<Record<string, string>>('/api/algorithms')).data;
  }

  // Next item
  async getNextPair(taskId: string): Promise<NextPairResponse | null> {
    const res = await api.post<NextPairResponse | null>(`/api/tasks/${taskId}/next-pair`, {});
    return res.data;
  }

  async getNextImage(taskId: string): Promise<NextImageResponse | null> {
    const res = await api.post<NextImageResponse | null>(`/api/tasks/${taskId}/next-image`, {});
    return res.data;
  }

  // Submissions
  async submitComparison(payload: ComparisonSubmit): Promise<{ points: number }> {
    return (await api.post<{ points: number }>('/api/comparisons', payload)).data;
  }

  async submitRating(payload: RatingSubmit): Promise<{ points: number }> {
    return (await api.post<{ points: number }>('/api/ratings', payload)).data;
  }

  // Stats
  async getMyStats(): Promise<MyStats> {
    return (await api.get<MyStats>('/api/stats/me')).data;
  }

  async getGlobalStats(): Promise<GlobalStats> {
    return (await api.get<GlobalStats>('/api/stats/global')).data;
  }

  async getOverallLeaderboard(sinceDays?: number): Promise<LeaderboardEntry[]> {
    return (await api.get<LeaderboardEntry[]>('/api/stats/leaderboard', {
      params: sinceDays ? { since_days: sinceDays } : {},
    })).data;
  }

  async getTaskLeaderboard(taskId: string, sinceDays?: number): Promise<LeaderboardEntry[]> {
    return (await api.get<LeaderboardEntry[]>(`/api/stats/leaderboard/${taskId}`, {
      params: sinceDays ? { since_days: sinceDays } : {},
    })).data;
  }

  // Admin — Tasks
  async getAdminTasks(): Promise<TaskRead[]> {
    return (await api.get<TaskRead[]>('/api/admin/tasks')).data;
  }

  async createAdminTask(task: TaskCreate): Promise<TaskRead> {
    return (await api.post<TaskRead>('/api/admin/tasks', task)).data;
  }

  async updateAdminTask(taskId: string, task: Partial<TaskCreate>): Promise<TaskRead> {
    return (await api.put<TaskRead>(`/api/admin/tasks/${taskId}`, task)).data;
  }

  async patchAdminTask(taskId: string, patch: TaskStatePatch): Promise<void> {
    await api.patch(`/api/admin/tasks/${taskId}`, patch);
  }

  // Admin — Images
  async uploadImages(taskId: string, file: File): Promise<{ imported: number }> {
    const form = new FormData();
    form.append('file', file);
    return (await api.post<{ imported: number }>(`/api/admin/tasks/${taskId}/upload-images`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })).data;
  }

  async getAdminImages(taskId: string, page = 1, pageSize = 50, q?: string): Promise<ImageListResponse> {
    const params: Record<string, unknown> = { page, page_size: pageSize };
    if (q) params.q = q;
    return (await api.get<ImageListResponse>(`/api/admin/tasks/${taskId}/images`, { params })).data;
  }

  async patchAdminImage(imageId: string, suspended: boolean): Promise<void> {
    await api.patch(`/api/admin/images/${encodeURIComponent(imageId)}`, { suspended });
  }

  async getAdminRankings(taskId: string): Promise<ImageRankingResponse[]> {
    return (await api.get<ImageRankingResponse[]>(`/api/admin/tasks/${taskId}/rankings`)).data;
  }

  // Admin — Comparisons & Ratings
  async getAdminComparisons(taskId?: string, page = 1, pageSize = 50): Promise<PaginatedComparisons> {
    const params: Record<string, unknown> = { page, page_size: pageSize };
    if (taskId) params.task_id = taskId;
    return (await api.get<PaginatedComparisons>('/api/admin/comparisons', { params })).data;
  }

  async getAdminRatings(taskId?: string, page = 1, pageSize = 50): Promise<PaginatedRatings> {
    const params: Record<string, unknown> = { page, page_size: pageSize };
    if (taskId) params.task_id = taskId;
    return (await api.get<PaginatedRatings>('/api/admin/ratings', { params })).data;
  }

  // Admin — Reliability
  async getAdminReliability(): Promise<UserReliabilityResponse[]> {
    return (await api.get<UserReliabilityResponse[]>('/api/admin/reliability')).data;
  }

  async recomputeReliability(): Promise<void> {
    await api.post('/api/admin/reliability/recompute');
  }

  // Admin — Stats
  async getAdminStats(): Promise<GlobalStats> {
    return (await api.get<GlobalStats>('/api/admin/stats')).data;
  }

  imageUrl(path: string): string {
    return `${resolvedApiUrl}${path}`;
  }
}

export const apiService = new ApiService();
