import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/client';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { InstallAppButton } from '../components/InstallAppButton';
import { Eye, EyeOff } from 'lucide-react';

export default function Auth() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const trimmedName = fullName.trim();
    const trimmedEmail = email.trim();

    if (!isLogin && trimmedName.length < 2) {
      setError('Please enter your full name (at least 2 characters).');
      return;
    }

    if (!trimmedEmail || !trimmedEmail.includes('@')) {
      setError('Please enter a valid email address.');
      return;
    }

    if (password.length < 6) {
      setError('Please enter a password with at least 6 characters.');
      return;
    }

    setIsLoading(true);

    try {
      if (isLogin) {
        await authApi.login({ email: trimmedEmail, password });
      } else {
        await authApi.register({
          email: trimmedEmail,
          password,
          full_name: trimmedName,
        });
      }
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Could not complete your request. Please try again.');
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
            <div className="mb-6 flex rounded-md border border-hairline bg-input p-1">
              <button
                type="button"
                onClick={() => {
                  setIsLogin(true);
                  setError('');
                }}
                className={`flex-1 rounded-sm py-1.5 text-sm font-medium transition-colors ${
                  isLogin ? 'bg-canvas text-primary shadow-sm' : 'text-muted hover:text-primary'
                }`}
              >
                Log In
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsLogin(false);
                  setError('');
                }}
                className={`flex-1 rounded-sm py-1.5 text-sm font-medium transition-colors ${
                  !isLogin ? 'bg-canvas text-primary shadow-sm' : 'text-muted hover:text-primary'
                }`}
              >
                Register
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
              {!isLogin && (
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
                <label className="text-xs font-medium text-muted">Email</label>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                />
              </div>

              <div className="space-y-2">
                <label className="text-xs font-medium text-muted">Password</label>
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
                {isLoading ? 'Processing...' : isLogin ? 'Log In' : 'Create Account'}
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
