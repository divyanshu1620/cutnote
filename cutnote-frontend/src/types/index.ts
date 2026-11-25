export interface Project {
  id: string;
  title: string;
  original_filename: string;
  mime_type: string;
  file_size_bytes: number;
  duration_seconds: number;
  fps: number;
  status: 'processing' | 'ready' | 'error';
  created_at: string;
}

export interface ReviewLink {
  id: string;
  project_id: string;
  review_token: string;
  expires_at: string;
}

export interface Comment {
  id: string;
  author_name: string;
  timestamp_seconds: number;
  body_text: string;
  voice_transcript: string | null;
  ai_checklist_item: string | null;
  is_resolved: boolean;
  created_at: string;
}

export interface ReviewData {
  project_id: string;
  title: string;
  duration_seconds: number;
  fps: number;
  comments: Comment[];
}