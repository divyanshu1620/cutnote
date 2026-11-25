import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { projectApi, authApi } from '../api/client';
import { Project, ReviewLink } from '../types';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Modal } from '../components/ui/Modal';
import { formatTimecode, formatBytes } from '../lib/utils';
import { 
  Upload, LogOut, Plus, Share2, FileText, FileCode, 
  Trash2, X, Check, Copy, Film, Loader2 
} from 'lucide-react';

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [user, setUser] = useState<{ full_name: string } | null>(null);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [shareModalProject, setShareModalProject] = useState<Project | null>(null);
  const [reviewLink, setReviewLink] = useState<ReviewLink | null>(null);
  const [copied, setCopied] = useState(false);
  
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadProgress, setUploadProgress] = useState(0);
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
    } catch (err) {
      navigate('/login');
    }
  };

  const handleLogout = async () => {
    await authApi.logout();
    navigate('/login');
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadFile(file);
      setUploadTitle(file.name.replace(/\.[^/.]+$/, ""));
    }
  };

  const handleUpload = async () => {
    if (!uploadFile) return;
    setIsUploading(true);
    setUploadProgress(0);

    try {
      const initRes = await projectApi.initUpload({
        title: uploadTitle,
        filename: uploadFile.name,
        expected_size_bytes: uploadFile.size,
      });

      const chunkSize = 5 * 1024 * 1024; // 5MB
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
      alert('Upload failed: ' + err.message);
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

  const copyToClipboard = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleExport = (url: string, _filename: string) => {
    window.open(url, '_blank');
  };

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <header className="flex h-16 items-center justify-between border-b border-hairline bg-panel px-6">
        <div className="flex items-center gap-3">
          <Film className="h-5 w-5 text-primary" strokeWidth={1.5} />
          <span className="text-lg font-semibold tracking-tight text-primary">CutNote</span>
        </div>
        <div className="flex items-center gap-4">
          <Button onClick={() => setIsUploadModalOpen(true)} size="sm">
            <Plus className="mr-2 h-4 w-4" strokeWidth={1.5} />
            Upload Cut
          </Button>
          <div className="h-6 w-px bg-hairline" />
          <span className="text-sm text-muted">{user?.full_name}</span>
          <Button variant="ghost" size="sm" onClick={handleLogout}>
            <LogOut className="h-4 w-4" strokeWidth={1.5} />
          </Button>
        </div>
      </header>

      <main className="flex-1 p-6">
        <div className="mx-auto max-w-6xl">
          <div className="mb-6 flex items-center justify-between">
            <h2 className="text-xl font-semibold tracking-tight text-primary">Projects</h2>
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
                {projects.map((project) => (
                  <tr key={project.id} className="hover:bg-input/50 transition-colors">
                    <td className="px-6 py-4 font-medium text-primary">{project.title}</td>
                    <td className="px-6 py-4 font-mono tabular-nums text-muted">
                      {formatTimecode(project.duration_seconds)}
                    </td>
                    <td className="px-6 py-4 font-mono tabular-nums text-muted">{project.fps}</td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                        project.status === 'ready' ? 'bg-green-900/20 text-green-400 border border-green-900/50' :
                        project.status === 'processing' ? 'bg-yellow-900/20 text-yellow-400 border border-yellow-900/50' :
                        'bg-red-900/20 text-red-400 border border-red-900/50'
                      }`}>
                        {project.status.charAt(0).toUpperCase() + project.status.slice(1)}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button variant="ghost" size="sm" onClick={() => handleShare(project)} title="Share Link">
                          <Share2 className="h-4 w-4" strokeWidth={1.5} />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleExport(projectApi.exportPremiereCsv(project.id), 'markers.csv')} title="Premiere CSV">
                          <FileText className="h-4 w-4" strokeWidth={1.5} />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleExport(projectApi.exportResolveEdl(project.id), 'markers.edl')} title="Resolve EDL">
                          <FileCode className="h-4 w-4" strokeWidth={1.5} />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleDelete(project.id)} className="text-red-400 hover:text-red-300" title="Delete">
                          <Trash2 className="h-4 w-4" strokeWidth={1.5} />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
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

      <Modal isOpen={isUploadModalOpen} onClose={() => !isUploading && setIsUploadModalOpen(false)} title="Upload Cut">
        <div className="space-y-4">
          {!uploadFile ? (
            <div 
              className="flex flex-col items-center justify-center rounded-md border border-dashed border-hairline bg-input p-12 transition-colors hover:border-cobalt/50"
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload className="mb-4 h-8 w-8 text-muted" strokeWidth={1.5} />
              <p className="mb-2 text-sm font-medium text-primary">Click to upload or drag and drop</p>
              <p className="text-xs text-muted">MP4, MOV, or WEBM (Max 5GB)</p>
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
                  disabled={isUploading}
                />
              </div>

              {isUploading && (
                <div className="space-y-2">
                  <div className="flex justify-between text-xs text-muted">
                    <span>Uploading...</span>
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
                <Button onClick={handleUpload} disabled={isUploading || !uploadTitle}>
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
              This link will expire in 72 hours. Anyone with the link can view and comment.
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