import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { reviewApi } from '../api/client';
import { ReviewData } from '../types';
import { formatTimecode } from '../lib/utils';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import {
  Play, Pause, Mic, Square, Send, Clock,
  CheckCircle2, Circle, Film, ArrowLeft, X, Trash2
} from 'lucide-react';

export default function ReviewPlayer() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();

  const [data, setData] = useState<ReviewData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');

  const videoRef = useRef<HTMLVideoElement>(null);
  const timelineRef = useRef<HTMLDivElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isScrubbing, setIsScrubbing] = useState(false);

  const [authorName, setAuthorName] = useState(() => sessionStorage.getItem('cutnote_author') || '');
  const [commentText, setCommentText] = useState('');
  const [isSending, setIsSending] = useState(false);

  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordingIntervalRef = useRef<number | null>(null);
  const cancelRecordingRef = useRef(false);

  useEffect(() => {
    if (token) {
      loadReviewData();
    }
  }, [token]);

  const loadReviewData = async () => {
    try {
      const result = await reviewApi.get(token!);
      setData(result);
      if (result.duration_seconds > 0) {
        setDuration(result.duration_seconds);
      }
      setIsLoading(false);
    } catch (err: any) {
      setError(err.message || 'Failed to load review');
      setIsLoading(false);
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current && !isScrubbing) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current && videoRef.current.duration && !isNaN(videoRef.current.duration)) {
      setDuration(videoRef.current.duration);
    }
  };

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (videoRef.current.paused) {
      videoRef.current.play();
      setIsPlaying(true);
    } else {
      videoRef.current.pause();
      setIsPlaying(false);
    }
  };

  const seekTo = (time: number, autoPlay = false) => {
    if (!videoRef.current) return;
    const total = duration || data?.duration_seconds || 0;
    const clamped = Math.max(0, Math.min(time, total));
    videoRef.current.currentTime = clamped;
    setCurrentTime(clamped);
    if (autoPlay && videoRef.current.paused) {
      videoRef.current.play();
      setIsPlaying(true);
    }
  };

  const scrubFromClientX = (clientX: number) => {
    if (!timelineRef.current) return;
    const total = duration || data?.duration_seconds || 0;
    if (total <= 0) return;
    const rect = timelineRef.current.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    seekTo(ratio * total, false);
  };

  useEffect(() => {
    if (!isScrubbing) return;
    const handleMouseMove = (e: MouseEvent) => scrubFromClientX(e.clientX);
    const handleMouseUp = () => setIsScrubbing(false);
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isScrubbing, duration, data?.duration_seconds]);

  const handleSendComment = async () => {
    if (!token || !commentText.trim() || isSending) return;
    setActionError('');
    setIsSending(true);

    const finalAuthor = authorName.trim() || 'Client';
    sessionStorage.setItem('cutnote_author', finalAuthor);

    try {
      await reviewApi.addComment(token, {
        author_name: finalAuthor,
        timestamp_seconds: currentTime,
        body_text: commentText.trim(),
      });
      setCommentText('');
      await loadReviewData();
    } catch (err: any) {
      console.error('Failed to send comment:', err);
      setActionError(err.message || 'Failed to send comment');
    } finally {
      setIsSending(false);
    }
  };

  const startRecording = async () => {
    setActionError('');
    const finalAuthor = authorName.trim() || 'Client';
    sessionStorage.setItem('cutnote_author', finalAuthor);
    cancelRecordingRef.current = false;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      const recordedAt = currentTime;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        if (cancelRecordingRef.current) return;

        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        const formData = new FormData();
        formData.append('author_name', finalAuthor);
        formData.append('timestamp_seconds', recordedAt.toString());
        formData.append('audio', audioBlob, 'voice-note.webm');

        setIsSending(true);
        try {
          await reviewApi.addVoiceComment(token!, formData);
          await loadReviewData();
        } catch (err: any) {
          console.error('Failed to upload voice comment:', err);
          setActionError(err.message || 'Failed to upload voice note');
        } finally {
          setIsSending(false);
        }
      };

      mediaRecorder.start();
      setIsRecording(true);
      setRecordingTime(0);

      recordingIntervalRef.current = window.setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);

      if (videoRef.current && !videoRef.current.paused) {
        videoRef.current.pause();
        setIsPlaying(false);
      }
    } catch (err) {
      console.error('Failed to start recording:', err);
      setActionError('Microphone access denied or not available');
    }
  };

  const stopRecording = (cancel = false) => {
    cancelRecordingRef.current = cancel;
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (recordingIntervalRef.current) {
        clearInterval(recordingIntervalRef.current);
      }
    }
  };

  const handleToggleResolve = async (e: React.MouseEvent, commentId: string) => {
    e.stopPropagation();
    if (!token) return;
    try {
      await reviewApi.toggleResolveComment(token, commentId);
      await loadReviewData();
    } catch (err) {
      console.error('Failed to toggle resolve:', err);
    }
  };

  const handleDeleteComment = async (e: React.MouseEvent, commentId: string) => {
    e.stopPropagation();
    if (!token) return;
    try {
      await reviewApi.deleteComment(token, commentId);
      await loadReviewData();
    } catch (err) {
      console.error('Failed to delete comment:', err);
    }
  };

  const totalDuration = duration || data?.duration_seconds || 0;
  const progressPercent = totalDuration > 0 ? (currentTime / totalDuration) * 100 : 0;
  const sortedComments = [...(data?.comments || [])].sort(
    (a, b) => a.timestamp_seconds - b.timestamp_seconds
  );

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas">
        <div className="text-muted">Loading review...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-canvas p-4">
        <h1 className="mb-4 text-xl font-semibold text-primary">Review Not Found</h1>
        <p className="mb-6 text-muted">{error || 'This review link may have expired or is invalid.'}</p>
        <Button onClick={() => navigate('/login')}>
          <ArrowLeft className="mr-2 h-4 w-4" strokeWidth={1.5} />
          Return to Login
        </Button>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-canvas">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-hairline bg-panel px-4">
        <div className="flex items-center gap-3">
          <Film className="h-5 w-5 text-primary" strokeWidth={1.5} />
          <span className="font-semibold tracking-tight text-primary">CutNote</span>
          <span className="mx-2 h-4 w-px bg-hairline" />
          <span className="text-sm text-muted truncate max-w-[240px] sm:max-w-md">{data.title}</span>
        </div>
        <Button variant="ghost" size="sm" onClick={() => navigate('/login')}>
          <ArrowLeft className="mr-2 h-4 w-4" strokeWidth={1.5} />
          Back to Dashboard
        </Button>
      </header>

      <div className="flex flex-1 min-h-0 overflow-hidden lg:flex-row flex-col">
        <div className="flex flex-1 min-h-0 flex-col bg-black lg:w-[70%] w-full">
          <div
            className="relative flex flex-1 min-h-0 items-center justify-center bg-canvas cursor-pointer"
            onClick={togglePlay}
          >
            <video
              ref={videoRef}
              src={`/api/v1/review/${token}/video`}
              className="max-h-full max-w-full"
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
            />

            {!isPlaying && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/20 pointer-events-none">
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10 backdrop-blur-sm">
                  <Play className="h-8 w-8 text-primary fill-primary" strokeWidth={1.5} />
                </div>
              </div>
            )}
          </div>

          <div className="shrink-0 border-t border-hairline bg-panel p-4">
            <div className="mb-4 flex items-center gap-4">
              <Button variant="ghost" size="sm" onClick={togglePlay} className="h-8 w-8 p-0">
                {isPlaying ? (
                  <Pause className="h-4 w-4" strokeWidth={1.5} />
                ) : (
                  <Play className="h-4 w-4" strokeWidth={1.5} />
                )}
              </Button>

              <div
                ref={timelineRef}
                className="relative flex-1 py-3 cursor-pointer select-none"
                onMouseDown={(e) => {
                  setIsScrubbing(true);
                  scrubFromClientX(e.clientX);
                }}
              >
                <div className="relative h-1.5 w-full rounded-full bg-input">
                  <div
                    className="absolute h-full rounded-full bg-cobalt"
                    style={{ width: `${progressPercent}%` }}
                  />
                  <div
                    className="absolute top-1/2 h-3.5 w-3.5 -translate-y-1/2 -translate-x-1/2 rounded-full bg-primary shadow ring-2 ring-cobalt pointer-events-none"
                    style={{ left: `${progressPercent}%` }}
                  />
                  {totalDuration > 0 &&
                    sortedComments.map((comment) => (
                      <button
                        key={comment.id}
                        className="absolute top-1/2 h-3 w-3 -translate-y-1/2 -translate-x-1/2 rounded-full bg-amber-400 ring-2 ring-canvas hover:scale-125 transition-transform z-10"
                        style={{ left: `${(comment.timestamp_seconds / totalDuration) * 100}%` }}
                        onMouseDown={(e) => e.stopPropagation()}
                        onClick={(e) => {
                          e.stopPropagation();
                          seekTo(comment.timestamp_seconds, false);
                        }}
                        title={`${comment.author_name} at ${formatTimecode(comment.timestamp_seconds)}`}
                      />
                    ))}
                </div>
              </div>

              <div className="font-mono tabular-nums text-xs text-muted">
                {formatTimecode(currentTime)} / {formatTimecode(totalDuration)}
              </div>
            </div>

            <div className="space-y-2">
              <Input
                placeholder="Your name (optional)"
                value={authorName}
                onChange={(e) => setAuthorName(e.target.value)}
                className="h-8 text-xs"
              />

              <div className="flex gap-2">
                <Input
                  id="comment-input"
                  placeholder={`Add a comment at ${formatTimecode(currentTime)}...`}
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  onFocus={() => {
                    if (videoRef.current && !videoRef.current.paused) {
                      videoRef.current.pause();
                      setIsPlaying(false);
                    }
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendComment();
                    }
                  }}
                  disabled={isRecording}
                />

                {!isRecording ? (
                  <div className="flex gap-1.5">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={startRecording}
                      disabled={isSending}
                      title="Record Voice Note"
                    >
                      <Mic className="h-4 w-4" strokeWidth={1.5} />
                    </Button>
                    <Button
                      size="sm"
                      onClick={handleSendComment}
                      disabled={!commentText.trim() || isSending}
                      title="Send Comment"
                    >
                      <Send className="h-4 w-4" strokeWidth={1.5} />
                    </Button>
                  </div>
                ) : (
                  <div className="flex gap-1.5">
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => stopRecording(false)}
                      title="Stop & Send Voice Note"
                    >
                      <Square className="mr-1.5 h-3.5 w-3.5 fill-current" />
                      Send
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => stopRecording(true)}
                      title="Cancel Recording"
                    >
                      <X className="h-4 w-4" strokeWidth={1.5} />
                    </Button>
                  </div>
                )}
              </div>

              {isRecording && (
                <div className="flex items-center gap-2 text-xs text-red-400">
                  <div className="h-2 w-2 animate-pulse rounded-full bg-red-400" />
                  Recording voice note at {formatTimecode(currentTime)} — {formatTimecode(recordingTime)}
                </div>
              )}

              {actionError && (
                <div className="text-xs text-red-400">{actionError}</div>
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-col border-l border-hairline bg-panel lg:w-[30%] w-full h-[35vh] lg:h-auto min-h-0">
          <div className="flex shrink-0 items-center justify-between border-b border-hairline p-4">
            <h3 className="text-sm font-semibold text-primary">Feedback ({sortedComments.length})</h3>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3 hide-scrollbar">
            {sortedComments.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-muted text-sm">
                <Clock className="h-8 w-8 mb-2 opacity-50" strokeWidth={1.5} />
                <p>No comments yet</p>
                <p className="text-xs mt-1">Pause anywhere and type or record</p>
              </div>
            ) : (
              sortedComments.map((comment) => {
                const isVoiceNote = !comment.body_text;
                const cleanTranscript =
                  comment.voice_transcript &&
                  !comment.voice_transcript.includes('configure Whisper') &&
                  !comment.voice_transcript.includes('GROQ_API_KEY')
                    ? comment.voice_transcript
                    : '';

                return (
                  <div
                    key={comment.id}
                    className={`group rounded-md border p-3 transition-colors cursor-pointer ${
                      comment.is_resolved
                        ? 'border-green-500/30 bg-input/50 opacity-75'
                        : 'border-hairline bg-input hover:border-cobalt/50'
                    }`}
                    onClick={() => seekTo(comment.timestamp_seconds, false)}
                  >
                    <div className="mb-2 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-mono tabular-nums text-xs font-medium text-cobalt">
                          {formatTimecode(comment.timestamp_seconds)}
                        </span>
                        <span className="text-xs font-medium text-primary">{comment.author_name}</span>
                        {comment.is_resolved && (
                          <span className="rounded bg-green-500/15 px-1.5 py-0.5 text-[10px] font-medium text-green-400">
                            Done
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          onClick={(e) => handleToggleResolve(e, comment.id)}
                          title={comment.is_resolved ? 'Mark as Pending' : 'Mark as Done'}
                          className="text-muted hover:text-green-400 transition-colors"
                        >
                          {comment.is_resolved ? (
                            <CheckCircle2 className="h-4 w-4 text-green-400" strokeWidth={1.5} />
                          ) : (
                            <Circle className="h-4 w-4" strokeWidth={1.5} />
                          )}
                        </button>
                        <button
                          onClick={(e) => handleDeleteComment(e, comment.id)}
                          title="Delete Feedback"
                          className="text-muted hover:text-red-400 transition-colors"
                        >
                          <Trash2 className="h-3.5 w-3.5" strokeWidth={1.5} />
                        </button>
                      </div>
                    </div>

                    {comment.body_text && (
                      <p
                        className={`text-sm whitespace-pre-wrap ${
                          comment.is_resolved ? 'line-through text-muted' : 'text-primary'
                        }`}
                      >
                        {comment.body_text}
                      </p>
                    )}

                    {isVoiceNote && (
                      <div
                        className="mt-2 space-y-2 rounded border border-hairline bg-canvas p-2"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <audio
                          controls
                          preload="none"
                          src={`/api/v1/review/${token}/comments/${comment.id}/audio`}
                          className="h-8 w-full"
                        />
                        {cleanTranscript && (
                          <p className="text-xs text-primary/90 leading-relaxed">
                            {cleanTranscript}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
}