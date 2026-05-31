export interface TaskClass {
  id: string;
  label_en: string;
  label_cs: string;
  description?: string;
}

export interface TaskDefinition {
  id: string;
  name: string;
  description_md: string;
  multi_choice: boolean;
  max_choices: number;
  enabled: boolean;
  classes: TaskClass[];
}

export interface NextTextResponse {
  id: string;
  text: string;
  language: string;
}

export interface TaskAnnotation {
  task_id: string;
  selected_classes: string[];
  start_time: string;
  end_time: string;
}

export interface AnnotationSubmit {
  text_id: string;
  annotations: TaskAnnotation[];
}

export interface UserRead {
  id: string;
  email: string;
  display_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface UserCreate {
  email: string;
  password: string;
  display_name?: string;
}

export interface BearerResponse {
  access_token: string;
  token_type: string;
}

export interface LeaderboardEntry {
  user_id: string;
  display_name: string;
  count: number;
}

export interface TextItemResponse {
  id: string;
  text_preview: string;
  language: string;
  suspended: boolean;
}

export interface TextListResponse {
  total: number;
  items: TextItemResponse[];
}

export interface TaskStats {
  task_id: string;
  task_name: string;
  count: number;
}

export interface GlobalStats {
  total_annotations: number;
  per_task: TaskStats[];
}

export interface MyStats {
  total: number;
  per_task: Record<string, number>;
}
