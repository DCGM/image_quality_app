import { api } from 'boot/axios';
import {
  AnnotationSubmit, BearerResponse, GlobalStats, LeaderboardEntry, LoginRequest,
  MyStats, NextTextResponse, TaskDefinition, TextAnnotationEntry, TextListResponse,
  UserCreate, UserRead, UserReliabilityResponse,
} from 'src/types/api';

class ApiService {
  async login(credentials: LoginRequest): Promise<BearerResponse> {
    const formData = new URLSearchParams();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);
    const response = await api.post<BearerResponse>('/auth/jwt/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    return response.data;
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

  async getTasks(): Promise<TaskDefinition[]> {
    return (await api.get<TaskDefinition[]>('/api/tasks')).data;
  }

  async getAdminTasks(): Promise<TaskDefinition[]> {
    return (await api.get<TaskDefinition[]>('/api/admin/tasks')).data;
  }

  async saveAdminTask(task: TaskDefinition): Promise<void> {
    await api.put(`/api/admin/tasks/${task.id}`, task);
  }

  async createAdminTask(task: TaskDefinition): Promise<void> {
    await api.post('/api/admin/tasks', task);
  }

  async patchAdminTask(taskId: string, patch: { enabled?: boolean; deleted?: boolean }): Promise<void> {
    await api.patch(`/api/admin/tasks/${taskId}`, patch);
  }

  async importPromptTasks(): Promise<{ imported: number }> {
    return (await api.post<{ imported: number }>('/api/admin/tasks/import-prompts')).data;
  }

  async uploadTextsJsonl(jsonl: string): Promise<{ imported: number }> {
    return (await api.post<{ imported: number }>('/api/admin/texts', jsonl, { headers: { 'Content-Type': 'text/plain' } })).data;
  }

  async getAdminTexts(page = 0, q = '', pageSize = 50, taskId?: string): Promise<TextListResponse> {
    const params: Record<string, unknown> = { page, q, page_size: pageSize };
    if (taskId) params.task_id = taskId;
    return (await api.get<TextListResponse>('/api/admin/texts', { params })).data;
  }

  async patchAdminText(textId: string, suspended: boolean): Promise<void> {
    await api.patch(`/api/admin/texts/${textId}`, { suspended });
  }

  async getTextAnnotations(textId: string, taskId?: string): Promise<TextAnnotationEntry[]> {
    const params: Record<string, unknown> = {};
    if (taskId) params.task_id = taskId;
    return (await api.get<TextAnnotationEntry[]>(`/api/admin/texts/${textId}/annotations`, { params })).data;
  }

  async getNextText(taskIds: string[]): Promise<NextTextResponse | null> {
    const response = await api.post<NextTextResponse>('/api/texts/next', { task_ids: taskIds }, { validateStatus: (s) => s === 200 || s === 204 });
    return response.status === 204 ? null : response.data;
  }

  async submitAnnotations(payload: AnnotationSubmit): Promise<{ points: Record<string, number> }> {
    return (await api.post<{ points: Record<string, number> }>('/api/annotations', payload)).data;
  }

  async getGroundTruth(textId: string, taskIds: string[]): Promise<Record<string, string[]>> {
    return (await api.get<Record<string, string[]>>(`/api/texts/${textId}/ground-truth`, { params: { task_ids: taskIds } })).data;
  }

  async getMyStats(): Promise<MyStats> {
    return (await api.get<MyStats>('/api/stats/me')).data;
  }

  async getGlobalStats(): Promise<GlobalStats> {
    return (await api.get<GlobalStats>('/api/stats/global')).data;
  }

  async getLeaderboard(taskId: string, sinceDays?: number): Promise<LeaderboardEntry[]> {
    return (await api.get<LeaderboardEntry[]>(`/api/stats/leaderboard/${taskId}`, { params: sinceDays ? { since_days: sinceDays } : {} })).data;
  }

  async getOverallLeaderboard(sinceDays?: number): Promise<LeaderboardEntry[]> {
    return (await api.get<LeaderboardEntry[]>('/api/stats/leaderboard', { params: sinceDays ? { since_days: sinceDays } : {} })).data;
  }

  async uploadGroundTruth(jsonl: string): Promise<{ imported: number }> {
    return (await api.post<{ imported: number }>('/api/admin/ground-truth', jsonl, { headers: { 'Content-Type': 'text/plain' } })).data;
  }

  async uploadLlmAnnotations(jsonl: string): Promise<{ imported: number }> {
    return (await api.post<{ imported: number }>('/api/admin/llm-annotations', jsonl, { headers: { 'Content-Type': 'text/plain' } })).data;
  }

  async getAdminIrr(): Promise<UserReliabilityResponse[]> {
    return (await api.get<UserReliabilityResponse[]>('/api/admin/irr')).data;
  }

  async recomputeIrr(): Promise<void> {
    await api.post('/api/admin/irr/recompute');
  }
}

export const apiService = new ApiService();
