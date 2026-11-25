import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { projectApi, authApi } from '../api/client';
import { Project, ReviewLink } from '../types';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Modal } from '../components/ui/Modal';
import { InstallAppButton } from '../components/InstallAppButton';
import { formatTimecode, formatBytes } from '../lib/utils';
import { 
  Upload, LogOut, Plus, Share2, FileText, FileCode, 
  Trash2, X, Check, Copy, Film, Loader2, MessageSquare 
} from 'lucide-react';

const SEEN_STORAGE_KEY = 'cutnote_seen_comments';
const MAX_VIDEO_BYTES = 10 * 1024 * 1024 * 1024; // 10 GB

function loadSeenCounts(): Record<string, number> {
  try {
    const raw = localStorage.getItem(SEEN_STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [user, setUser] = useState<{ full_name: string } | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [seenCounts, setSeenCounts] = useState<Record<string, number>>(loadSeenCounts);

  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [shareModalProject, setShareModalProject] = useState<Project | null>(null);
  const [reviewLink, setReviewLink] = useState<ReviewLink | null>(null);
  const [copied, setCopied] = useState(false);
  const [openingProjectId, setOpeningProjectId] = useState<string | null>(null);
  
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const navigate = useNavigate();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [userData, projectData] = await Promise.all([
        authApi.me(),
        projectApi.list()
      ]);
      setUser(userData);
      setProjects(projectData);
      setIsLoading(false);
    } catch (err) {
      navigate('/login');
    }
  };

  const markProjectAsRead = (project: Project) => {
    const updated = { ...seenCounts, [project.id]: project.total_comments };
    setSeenCounts(updated);
    try {
      localStorage.setItem(SEEN_STORAGE_KEY, JSON.stringify(updated));
    } catch {
      // ignore storage quota errors
    }
  };

  const handleLogout = async () => {
    await authApi.logout();
    navigate('/login');
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    setUploadError('');
    if (!file) return;

    if (file.size > MAX_VIDEO_BYTES) {
      setUploadError('Video file exceeds the 10 GB maximum limit.');
      return;
    }

    setUploadFile(file);
    setUploadTitle(file.name.replace(/\.[^/.]+$/, ""));
  };

  const handleUpload = async () => {
    if (!uploadFile) return;
    if (uploadTitle.trim().length < 2) {
      setUploadError('Please enter a valid project title (at least 2 characters).');
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);
    setUploadError('');

    try {
      const initRes = await projectApi.initUpload({
        title: uploadTitle.trim(),
        filename: uploadFile.name,
        expected_size_bytes: uploadFile.size,
      });

      const chunkSize = Math.min(initRes.max_chunk_size_bytes || 10 * 1024 * 1024, 10 * 1024 * 1024);
      const totalChunks = Math.ceil(uploadFile.size / chunkSize);
      let uploadedChunks = 0;

      for (let start = 0; start < uploadFile.size; start += chunkSize) {
        const end = Math.min(start + chunkSize, uploadFile.size);
        const chunk = uploadFile.slice(start, end);
        
        await projectApi.uploadChunk(initRes.session_id, chunk);
        uploadedChunks++;
        setUploadProgress(Math.round((uploadedChunks / totalChunks) * 100));
      }

      await projectApi.completeUpload(initRes.session_id);
      
      setUploadFile(null);
      setUploadTitle('');
      setUploadProgress(0);
      setIsUploadModalOpen(false);
      await loadData();
    } catch (err: any) {
      console.error('Upload failed:', err);
      setUploadError(err.message || 'Upload failed. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this project permanently?')) return;
    await projectApi.delete(id);
    await loadData();
  };

  const handleShare = async (project: Project) => {
    setCopied(false);
    setShareModalProject(project);
    try {
      const link = await projectApi.createReviewLink(project.id, 72);
      setReviewLink(link);
    } catch (err) {
      console.error('Failed to create review link:', err);
    }
  };

  const handleOpenReview = async (project: Project) => {
    markProjectAsRead(project);
    setOpeningProjectId(project.id);
    try {
      const link = await projectApi.createReviewLink(project.id, 72);
      navigate(`/review/${link.review_token}`);
    } catch (err) {
      console.error('Failed to open review:', err);
    } finally {
      setOpeningProjectId(null);
    }
  };

  const copyToClipboard = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleExport = (url: string, _filename: string) => {
    window.open(url, '_blank');
  };

  const renderStatusBadge = (project: Project) => {
    if (project.status === 'ready') {
      const total = project.total_comments || 0;
      const done = project.resolved_comments || 0;

      if (total > 0 && done < total) {
        return (
          <span className="inline-flex items-center rounded-full border border-amber-800/60 bg-amber-900/20 px-2.5 py-1 text-xs font-medium text-amber-400">
            {done}/{total} Done
          </span>
        );
      }

      return (
        <span className="inline-flex items-center rounded-full border border-green-900/50 bg-green-900/20 px-2.5 py-1 text-xs font-medium text-green-400">
          Ready
        </span>
      );
    }

    if (project.status === 'processing' || project.status === 'uploading') {
      return (
        <span className="inline-flex items-center rounded-full border border-yellow-900/50 bg-yellow-900/20 px-2.5 py-1 text-xs font-medium text-yellow-400">
          {project.status.charAt(0).toUpperCase() + project.status.slice(1)}
        </span>
      );
    }

    return (
      <span className="inline-flex items-center rounded-full border border-red-900/50 bg-red-900/20 px-2.5 py-1 text-xs font-medium text-red-400">
        {project.status.charAt(0).toUpperCase() + project.status.slice(1)}
      </span>
    );
  };

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas">
        <Loader2 className="h-6 w-6 animate-spin text-muted" strokeWidth={1.5} />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <header className="flex h-16 items-center justify-between border-b border-hairline bg-panel px-6">
        <div className="flex items-center gap-3">
          <img src="/cutnote-icon.svg" alt="CutNote" className="h-6 w-6" />
          <span className="text-lg font-semibold tracking-tight text-primary">CutNote</span>
        </div>
        <div className="flex items-center gap-3">
          <InstallAppButton />
          <Button
            onClick={() => {
              setUploadError('');
              setIsUploadModalOpen(true);
            }}
            size="sm"
          >
            <Plus className="mr-2 h-4 w-4" strokeWidth={1.5} />
            Upload Cut
          </Button>
          <div className="h-6 w-px bg-hairline" />
          <span className="text-sm text-muted">{user?.full_name}</span>
          <Button variant="ghost" size="sm" onClick={handleLogout} title="Sign Out">
            <LogOut className="h-4 w-4" strokeWidth={1.5} />
          </Button>
        </div>
      </header>

      <main className="flex-1 p-6">
        <div className="mx-auto max-w-6xl">
          <div className="mb-6 flex items-center justify-between">
            <h2 className="text-xl font-semibold tracking-tight text-primary">Projects</h2>
            <span className="text-xs text-muted">Supports MP4, MOV, WEBM · Up to 10 GB</span>
          </div>

          <div className="overflow-hidden rounded-md border border-hairline bg-panel">
            <table className="w-full text-left text-sm">
              <thead className="bg-input text-muted">
                <tr>
                  <th className="px-6 py-3 font-medium">Title</th>
                  <th className="px-6 py-3 font-medium">Duration</th>
                  <th className="px-6 py-3 font-medium">FPS</th>
                  <th className="px-6 py-3 font-medium">Status</th>
                  <th className="px-6 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline">
                {projects.map((project) => {
                  const seen = seenCounts[project.id] ?? 0;
                  const unreadCount = Math.max(0, (project.total_comments || 0) - seen);

                  return (
                    <tr key={project.id} className="hover:bg-input/50 transition-colors">
                      <td className="px-6 py-4 font-medium text-primary">
                        <button
                          type="button"
                          onClick={() => handleOpenReview(project)}
                          className="text-left hover:underline focus:outline-none"
                        >
                          {project.title}
                        </button>
                      </td>
                      <td className="px-6 py-4 font-mono tabular-nums text-muted">
                        {formatTimecode(project.duration_seconds)}
                      </td>
                      <td className="px-6 py-4 font-mono tabular-nums text-muted">{project.fps}</td>
                      <td className="px-6 py-4">
                        {renderStatusBadge(project)}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleOpenReview(project)}
                            disabled={openingProjectId === project.id}
                            title={unreadCount > 0 ? `${unreadCount} new feedback` : 'View Feedback'}
                            className="relative"
                          >
                            {openingProjectId === project.id ? (
                              <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.5} />
                            ) : (
                              <MessageSquare className="h-4 w-4" strokeWidth={1.5} />
                            )}
                            {unreadCount > 0 && (
                              <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-semibold leading-none text-white">
                                {unreadCount > 9 ? '9+' : unreadCount}
                              </span>
                            )}
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleShare(project)} title="Share Review Link">
                            <Share2 className="h-4 w-4" strokeWidth={1.5} />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleExport(projectApi.exportPremiereCsv(project.id), 'markers.csv')} title="Export Premiere CSV">
                            <FileText className="h-4 w-4" strokeWidth={1.5} />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleExport(projectApi.exportResolveEdl(project.id), 'markers.edl')} title="Export Resolve EDL">
                            <FileCode className="h-4 w-4" strokeWidth={1.5} />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleDelete(project.id)} className="text-red-400 hover:text-red-300" title="Delete Project">
                            <Trash2 className="h-4 w-4" strokeWidth={1.5} />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {projects.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center text-muted">
                      No projects yet. Upload your first cut to get started.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>

      <Modal
        isOpen={isUploadModalOpen}
        onClose={() => {
          if (!isUploading) {
            setIsUploadModalOpen(false);
            setUploadError('');
          }
        }}
        title="Upload Cut"
      >
        <div className="space-y-4">
          {uploadError && (
            <div className="rounded-md border border-red-900/50 bg-red-950/40 px-3 py-2 text-xs text-red-300">
              {uploadError}
            </div>
          )}

          {!uploadFile ? (
            <div 
              className="flex cursor-pointer flex-col items-center justify-center rounded-md border border-dashed border-hairline bg-input p-12 transition-colors hover:border-cobalt/50"
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload className="mb-4 h-8 w-8 text-muted" strokeWidth={1.5} />
              <p className="mb-2 text-sm font-medium text-primary">Click to select a video file</p>
              <p className="text-xs text-muted">MP4, MOV, or WEBM (Max 10 GB · Up to 2 hours)</p>
              <input 
                ref={fileInputRef}
                type="file" 
                accept=".mp4,.mov,.webm" 
                className="hidden" 
                onChange={handleFileSelect}
              />
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between rounded-md border border-hairline bg-input p-3">
                <div className="flex items-center gap-3">
                  <Film className="h-5 w-5 text-muted" strokeWidth={1.5} />
                  <div>
                    <p className="text-sm font-medium text-primary">{uploadFile.name}</p>
                    <p className="text-xs text-muted">{formatBytes(uploadFile.size)}</p>
                  </div>
                </div>
                {!isUploading && (
                  <Button variant="ghost" size="sm" onClick={() => setUploadFile(null)}>
                    <X className="h-4 w-4" strokeWidth={1.5} />
                  </Button>
                )}
              </div>

              <div className="space-y-2">
                <label className="text-xs font-medium text-muted">Project Title</label>
                <Input 
                  value={uploadTitle} 
                  onChange={(e) => setUploadTitle(e.target.value)} 
                  placeholder="e.g., Brand Reel v2"
                  disabled={isUploading}
                />
              </div>

              {isUploading && (
                <div className="space-y-2">
                  <div className="flex justify-between text-xs text-muted">
                    <span>Uploading video chunks...</span>
                    <span className="font-mono tabular-nums">{uploadProgress}%</span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-input">
                    <div 
                      className="h-full bg-cobalt transition-all duration-300" 
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-3 pt-2">
                <Button variant="secondary" onClick={() => setUploadFile(null)} disabled={isUploading}>
                  Cancel
                </Button>
                <Button onClick={handleUpload} disabled={isUploading || !uploadTitle.trim()}>
                  {isUploading ? (
                    <><Loader2 className="mr-2 h-4 w-4 animate-spin" strokeWidth={1.5} /> Uploading</>
                  ) : (
                    'Start Upload'
                  )}
                </Button>
              </div>
            </div>
          )}
        </div>
      </Modal>

      <Modal
        isOpen={!!shareModalProject}
        onClose={() => {
          setShareModalProject(null);
          setCopied(false);
        }}
        title="Share Review Link"
      >
        {reviewLink && shareModalProject && (
          <div className="space-y-4">
            <p className="text-sm text-muted">
              This link expires in 72 hours. Anyone with the link can watch the cut and leave timestamped feedback.
            </p>
            <div className="flex gap-2">
              <Input 
                readOnly 
                value={`${window.location.origin}/review/${reviewLink.review_token}`} 
                className="font-mono text-xs"
              />
              <Button
                onClick={() => copyToClipboard(`${window.location.origin}/review/${reviewLink.review_token}`)}
                title={copied ? 'Copied' : 'Copy link'}
              >
                {copied ? (
                  <Check className="h-4 w-4" strokeWidth={1.5} />
                ) : (
                  <Copy className="h-4 w-4" strokeWidth={1.5} />
                )}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
