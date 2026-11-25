import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { authApi } from '../api/client';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { InstallAppButton } from '../components/InstallAppButton';
import { Eye, EyeOff } from 'lucide-react';

const BLOCKED_DOMAINS = new Set([
  'example.com',
  'test.com',
  'fake.com',
  'invalid.com',
  'mailinator.com',
  'tempmail.com',
  '10minutemail.com',
  'guerrillamail.com',
  'sharklasers.com',
  'yopmail.com',
]);

function validateRealEmailInput(raw: string): string | null {
  const cleaned = raw.trim().toLowerCase();
  if (!cleaned) return null;
  const parts = cleaned.split('@');
  if (parts.length !== 2 || !parts[1].includes('.')) {
    throw new Error('Please enter a valid email address.');
  }
  const [localPart, domain] = parts;
  if (
    localPart.length < 2 ||
    ['test', 'fake', 'asdf', 'abc', 'user', 'admin', 'none', 'null'].includes(localPart)
  ) {
    throw new Error('Please enter your real email address, not a placeholder.');
  }
  if (
    BLOCKED_DOMAINS.has(domain) ||
    domain.endsWith('.test') ||
    domain.endsWith('.invalid') ||
    domain.endsWith('.local')
  ) {
    throw new Error('Please enter a real email address. Fake or disposable emails are not allowed.');
  }
  return cleaned;
}

export default function Auth() {
  const [searchParams] = useSearchParams();
  const [mode, setMode] = useState<'login' | 'register' | 'forgot'>('login');
  const [username, setUsername] = useState('');
  const [recoveryEmail, setRecoveryEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [fullName, setFullName] = useState('');

  const [identifier, setIdentifier] = useState('');
  const [resetCode, setResetCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [resetSent, setResetSent] = useState(false);
  const [infoMessage, setInfoMessage] = useState('');

  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const tokenFromUrl = searchParams.get('reset_token');
    if (tokenFromUrl) {
      setMode('forgot');
      setResetCode(tokenFromUrl);
      setResetSent(true);
    }
  }, [searchParams]);

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setInfoMessage('');

    const trimmedName = fullName.trim();
    const trimmedUsername = username.trim().toLowerCase();

    if (mode === 'register' && trimmedName.length < 2) {
      setError('Please enter your full name (at least 2 characters).');
      return;
    }

    if (!trimmedUsername || trimmedUsername.length < 3) {
      setError('Please enter a username with at least 3 characters.');
      return;
    }

    let validEmail: string | null = null;
    if (mode === 'register' && recoveryEmail.trim()) {
      try {
        validEmail = validateRealEmailInput(recoveryEmail);
      } catch (validationErr: any) {
        setError(validationErr.message);
        return;
      }
    }

    if (password.length < 6) {
      setError('Please enter a password with at least 6 characters.');
      return;
    }

    setIsLoading(true);

    try {
      if (mode === 'login') {
        await authApi.login({ username: trimmedUsername, password });
      } else {
        await authApi.register({
          username: trimmedUsername,
          password,
          full_name: trimmedName,
          recovery_email: validEmail || undefined,
        });
      }
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Could not complete your request. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendResetCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setInfoMessage('');

    const cleanId = identifier.trim();
    if (cleanId.length < 3) {
      setError('Enter your registered username or recovery email.');
      return;
    }

    setIsLoading(true);
    try {
      const res = await authApi.forgotPassword({ identifier: cleanId });
      setResetSent(true);
      setInfoMessage(res.message);
    } catch (err: any) {
      setError(err.message || 'Could not send reset code.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setInfoMessage('');

    if (!resetCode.trim()) {
      setError('Enter the OTP or reset token from your email.');
      return;
    }
    if (newPassword.length < 6) {
      setError('New password must be at least 6 characters.');
      return;
    }

    setIsLoading(true);
    try {
      await authApi.resetPassword({
        token_or_otp: resetCode.trim(),
        new_password: newPassword,
      });
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Could not reset password.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-canvas p-4">
      <div className="flex justify-end">
        <InstallAppButton />
      </div>

      <div className="flex flex-1 items-center justify-center">
        <div className="w-full max-w-md space-y-8">
          <div className="flex flex-col items-center space-y-2">
            <div className="flex h-12 w-12 items-center justify-center rounded-md border border-hairline bg-panel">
              <img src="/cutnote-icon.svg" alt="CutNote" className="h-7 w-7" />
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-primary">CutNote</h1>
            <p className="text-sm text-muted">Timestamped video review, voice notes, and marker export.</p>
          </div>

          <div className="rounded-md border border-hairline bg-panel p-8">
            {mode !== 'forgot' ? (
              <>
                <div className="mb-6 flex rounded-md border border-hairline bg-input p-1">
                  <button
                    type="button"
                    onClick={() => {
                      setMode('login');
                      setError('');
                      setInfoMessage('');
                    }}
                    className={`flex-1 rounded-sm py-1.5 text-sm font-medium transition-colors ${
                      mode === 'login' ? 'bg-canvas text-primary shadow-sm' : 'text-muted hover:text-primary'
                    }`}
                  >
                    Log In
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setMode('register');
                      setError('');
                      setInfoMessage('');
                    }}
                    className={`flex-1 rounded-sm py-1.5 text-sm font-medium transition-colors ${
                      mode === 'register' ? 'bg-canvas text-primary shadow-sm' : 'text-muted hover:text-primary'
                    }`}
                  >
                    Register
                  </button>
                </div>

                <form onSubmit={handleAuthSubmit} className="space-y-4" noValidate>
                  {mode === 'register' && (
                    <div className="space-y-2">
                      <label className="text-xs font-medium text-muted">Full Name</label>
                      <Input
                        type="text"
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        placeholder="Enter your full name"
                      />
                    </div>
                  )}

                  <div className="space-y-2">
                    <label className="text-xs font-medium text-muted">Username</label>
                    <Input
                      type="text"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="Enter unique username"
                    />
                  </div>

                  {mode === 'register' && (
                    <div className="space-y-2">
                      <label className="text-xs font-medium text-muted">
                        Recovery Email (Optional — real email only for password reset)
                      </label>
                      <Input
                        type="email"
                        value={recoveryEmail}
                        onChange={(e) => setRecoveryEmail(e.target.value)}
                        placeholder="name@gmail.com"
                      />
                    </div>
                  )}

                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-medium text-muted">Password</label>
                      {mode === 'login' && (
                        <button
                          type="button"
                          onClick={() => {
                            setMode('forgot');
                            setError('');
                            setInfoMessage('');
                            setIdentifier(username);
                          }}
                          className="text-xs text-muted hover:text-primary underline-offset-2 hover:underline"
                        >
                          Forgot password?
                        </button>
                      )}
                    </div>
                    <div className="relative">
                      <Input
                        type={showPassword ? 'text' : 'password'}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="Enter password"
                        className="pr-10"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword((prev) => !prev)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-primary transition-colors"
                        aria-label={showPassword ? 'Hide password' : 'Show password'}
                      >
                        {showPassword ? (
                          <EyeOff className="h-4 w-4" strokeWidth={1.5} />
                        ) : (
                          <Eye className="h-4 w-4" strokeWidth={1.5} />
                        )}
                      </button>
                    </div>
                  </div>

                  {error && (
                    <div className="rounded-md border border-red-900/50 bg-red-900/20 p-3 text-sm text-red-400">
                      {error}
                    </div>
                  )}

                  <Button type="submit" className="w-full" disabled={isLoading}>
                    {isLoading ? 'Processing...' : mode === 'login' ? 'Log In' : 'Create Account'}
                  </Button>
                </form>
              </>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-medium text-primary">Reset Password via Recovery Email</h2>
                  <button
                    type="button"
                    onClick={() => {
                      setMode('login');
                      setError('');
                      setInfoMessage('');
                    }}
                    className="text-xs text-muted hover:text-primary"
                  >
                    Back to Log In
                  </button>
                </div>

                <form onSubmit={handleSendResetCode} className="space-y-3" noValidate>
                  <div className="space-y-2">
                    <label className="text-xs font-medium text-muted">Username or Recovery Email</label>
                    <Input
                      type="text"
                      value={identifier}
                      onChange={(e) => setIdentifier(e.target.value)}
                      placeholder="your_username or name@gmail.com"
                    />
                  </div>
                  <Button type="submit" className="w-full" disabled={isLoading}>
                    {isLoading ? 'Sending...' : 'Send Reset Link & OTP'}
                  </Button>
                </form>

                {resetSent && (
                  <form onSubmit={handleResetPassword} className="space-y-3 border-t border-hairline pt-4" noValidate>
                    <div className="space-y-2">
                      <label className="text-xs font-medium text-muted">Email OTP or Reset Token</label>
                      <Input
                        type="text"
                        value={resetCode}
                        onChange={(e) => setResetCode(e.target.value)}
                        placeholder="Enter 6-digit OTP or token"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-xs font-medium text-muted">New Password</label>
                      <Input
                        type="password"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        placeholder="At least 6 characters"
                      />
                    </div>
                    <Button type="submit" className="w-full" disabled={isLoading}>
                      {isLoading ? 'Updating Password...' : 'Set New Password & Log In'}
                    </Button>
                  </form>
                )}

                {infoMessage && (
                  <div className="rounded-md border border-hairline bg-input p-3 text-xs text-primary">
                    {infoMessage}
                  </div>
                )}

                {error && (
                  <div className="rounded-md border border-red-900/50 bg-red-900/20 p-3 text-sm text-red-400">
                    {error}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
