import { api } from 'boot/axios';
import { AnnotationSubmit, BearerResponse, LoginRequest, NextTextResponse, TaskDefinition, UserCreate, UserRead } from 'src/types/api';

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

  async getTasks(): Promise<TaskDefinition[]> {
    return (await api.get<TaskDefinition[]>('/api/tasks')).data;
  }

  async getNextText(taskIds: string[]): Promise<NextTextResponse | null> {
    const response = await api.post<NextTextResponse>('/api/texts/next', { task_ids: taskIds }, { validateStatus: (s) => s === 200 || s === 204 });
    return response.status === 204 ? null : response.data;
  }

  async submitAnnotations(payload: AnnotationSubmit): Promise<void> {
    await api.post('/api/annotations', payload);
  }

  async getMyStats(): Promise<{ total: number; per_task: Record<string, number> }> {
    return (await api.get('/api/stats/me')).data;
  }

  async getLeaderboard(taskId: string): Promise<Array<{ user_id: string; count: number }>> {
    return (await api.get(`/api/stats/leaderboard/${taskId}`)).data;
  }
}

export const apiService = new ApiService();
