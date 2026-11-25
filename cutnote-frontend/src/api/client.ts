import type { Project, ReviewLink, ReviewData } from '../types';
const BASE_URL = '/api/v1';

export async function api<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const isFormData = options.body instanceof FormData;

  const headers: HeadersInit = {
    ...(!isFormData ? { 'Content-Type': 'application/json' } : {}),
    ...options.headers,
  };

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const errorData = await response.json();
      if (typeof errorData.detail === 'string') {
        message = errorData.detail;
      } else if (Array.isArray(errorData.detail) && errorData.detail[0]?.msg) {
        message = errorData.detail[0].msg;
      }
    } catch {
      const errorText = await response.text().catch(() => '');
      if (errorText) message = errorText;
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

export const authApi = {
  register: (data: { email: string; password: string; full_name: string }) =>
    api('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  login: (data: { email: string; password: string }) =>
    api('/auth/login', { method: 'POST', body: JSON.stringify(data) }),
  logout: () => api('/auth/logout', { method: 'POST' }),
  me: () => api<{ email: string; full_name: string }>('/auth/me'),
};

export const projectApi = {
  list: () => api<Project[]>('/projects'),
  delete: (id: string) => api(`/projects/${id}`, { method: 'DELETE' }),
  initUpload: (data: { title: string; filename: string; expected_size_bytes: number }) =>
    api<{ session_id: string; project_id: string; max_chunk_size_bytes: number }>('/projects/uploads/init', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  uploadChunk: (sessionId: string, chunk: Blob) => {
    const formData = new FormData();
    formData.append('chunk', chunk);
    return api(`/projects/uploads/${sessionId}/chunk`, {
      method: 'POST',
      body: formData,
    });
  },
  completeUpload: (sessionId: string) =>
    api<Project>(`/projects/uploads/${sessionId}/complete`, { method: 'POST' }),
  createReviewLink: (projectId: string, expires_in_hours = 72) =>
    api<ReviewLink>(`/projects/${projectId}/review-links`, {
      method: 'POST',
      body: JSON.stringify({ expires_in_hours }),
    }),
  exportPremiereCsv: (projectId: string) =>
    `${BASE_URL}/projects/${projectId}/export/premiere-csv`,
  exportResolveEdl: (projectId: string) =>
    `${BASE_URL}/projects/${projectId}/export/resolve-edl`,
};

export const reviewApi = {
  get: (token: string) => api<ReviewData>(`/review/${token}`),
  addComment: (token: string, data: { author_name: string; timestamp_seconds: number; body_text: string }) =>
    api(`/review/${token}/comments`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  addVoiceComment: (token: string, formData: FormData) =>
    api(`/review/${token}/voice-comments`, {
      method: 'POST',
      body: formData,
    }),
  toggleResolveComment: (token: string, commentId: string) =>
    api(`/review/${token}/comments/${commentId}/resolve`, {
      method: 'PATCH',
    }),
  deleteComment: (token: string, commentId: string) =>
    api(`/review/${token}/comments/${commentId}`, {
      method: 'DELETE',
    }),
};