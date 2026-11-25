import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/client';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Film, Eye, EyeOff } from 'lucide-react';

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
    setIsLoading(true);

    try {
      if (isLogin) {
        await authApi.login({ email, password });
      } else {
        await authApi.register({ email, password, full_name: fullName });
      }
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas p-4">
      <div className="w-full max-w-md space-y-8">
        <div className="flex flex-col items-center space-y-2">
          <div className="flex h-12 w-12 items-center justify-center rounded-md border border-hairline bg-panel">
            <Film className="h-6 w-6 text-primary" strokeWidth={1.5} />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-primary">CutNote</h1>
          <p className="text-sm text-muted">Frame-accurate video review for editors.</p>
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

          <form onSubmit={handleSubmit} className="space-y-4">
            {!isLogin && (
              <div className="space-y-2">
                <label className="text-xs font-medium text-muted">Full Name</label>
                <Input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required={!isLogin}
                  placeholder="Name"
                />
              </div>
            )}

            <div className="space-y-2">
              <label className="text-xs font-medium text-muted">Email</label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="Email"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-muted">Password</label>
              <div className="relative">
                <Input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="Password"
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
  );
}