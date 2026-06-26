// Types mirroring backend image_rater/base_objects.py

export interface UserRead {
  id: string;
  email: string;
  display_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
}

export interface UserCreate {
  email: string;
  password: string;
  display_name?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface BearerResponse {
  access_token: string;
  token_type: string;
}

// Tasks
export interface TaskRead {
  id: string;
  name: string;
  description_md: string;
  instructions_md: string;
  task_type: 'two_forced_choice' | 'single_rating';
  enabled: boolean;
  pair_algorithm: string | null;
  rating_options: string[] | null;
  rating_hotkeys: string[] | null;
  bonus_multiplier: number;
  calib_ratio: number;
}

export interface TaskCreate {
  id: string;
  name: string;
  description_md: string;
  instructions_md: string;
  task_type: 'two_forced_choice' | 'single_rating';
  pair_algorithm?: string | null;
  rating_options?: string[] | null;
  rating_hotkeys?: string[] | null;
  bonus_multiplier?: number;
  calib_ratio?: number;
}

export interface TaskStatePatch {
  enabled?: boolean;
  deleted?: boolean;
  bonus_multiplier?: number;
}

// Images
export interface ImageItemResponse {
  id: string;
  task_id: string;
  filename: string;
  group_id: string;
  url: string;
  suspended: boolean;
  width: number | null;
  height: number | null;
}

export interface ImageListResponse {
  total: number;
  items: ImageItemResponse[];
}

// Next item to annotate
export interface NextPairResponse {
  task_id: string;
  image_a_id: string;
  image_b_id: string;
  image_a_url: string;
  image_b_url: string;
  group_id: string;
  is_reliability_check: boolean;
}

export interface NextImageResponse {
  task_id: string;
  image_id: string;
  image_url: string;
  group_id: string;
  is_reliability_check: boolean;
}

// Submissions
export interface ComparisonSubmit {
  task_id: string;
  image_a_id: string;
  image_b_id: string;
  winner_id: string;
  start_time: string;
  end_time: string;
}

export interface RatingSubmit {
  task_id: string;
  image_id: string;
  selected_option: string;
  start_time: string;
  end_time: string;
}

// Rankings
export interface ImageRankingResponse {
  image_id: string;
  filename: string;
  url: string;
  score: number;
  comparisons: number;
  wins: number;
}

// Admin lists
export interface ComparisonRecord {
  id: string;
  user_id: string;
  display_name: string | null;
  task_id: string;
  group_id: string;
  image_a_id: string;
  image_b_id: string;
  winner_id: string | null;
  is_reliability_check: boolean;
  points_earned: number | null;
  created_at: string;
}

export interface RatingRecord {
  id: string;
  user_id: string;
  display_name: string | null;
  task_id: string;
  image_id: string;
  selected_option: string | null;
  is_reliability_check: boolean;
  points_earned: number | null;
  created_at: string;
}

export interface PaginatedComparisons {
  total: number;
  items: ComparisonRecord[];
}

export interface PaginatedRatings {
  total: number;
  items: RatingRecord[];
}

// Stats & Leaderboard
export interface LeaderboardEntry {
  user_id: string;
  display_name: string | null;
  count: number;
  score: number;
  reliability: number | null;
}

export interface TaskStats {
  task_id: string;
  task_name: string;
  comparison_count: number;
  rating_count: number;
}

export interface GlobalStats {
  total_comparisons: number;
  total_ratings: number;
  per_task: TaskStats[];
}

export interface MyStats {
  total_comparisons: number;
  total_ratings: number;
  score: number;
  per_task_comparisons: Record<string, number>;
  per_task_ratings: Record<string, number>;
}

// Reliability
export interface UserReliabilityResponse {
  user_id: string;
  display_name: string | null;
  task_id: string;
  annotation_count: number;
  consistency_score: number | null;
  inter_rater_agreement: number | null;
  computed_at: string | null;
}
