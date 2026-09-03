'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Eye, EyeOff, Mail, Lock, User, ArrowRight, Check, AlertCircle } from 'lucide-react';

type AuthMode = 'login' | 'register' | 'forgot' | 'reset';

interface AuthFormProps {
  onAuthenticated: () => void;
  initialMode?: AuthMode;
}

export function AuthForm({ onAuthenticated, initialMode }: AuthFormProps) {
  const [mode, setMode] = useState<AuthMode>(initialMode ?? 'login');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const [form, setForm] = useState({
    email: '',
    password: '',
    username: '',
    fullName: '',
    token: '',
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setError(null);
  };

  const resetInfo = () => setInfo(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setInfo(null);

    try {
      if (mode === 'login') {
        const data = await (await import('@/lib/api')).authApi.login({
          email: form.email,
          password: form.password,
        });
        localStorage.setItem('token', data.access_token);
        onAuthenticated();
      } else if (mode === 'register') {
        await (await import('@/lib/api')).authApi.register({
          email: form.email,
          password: form.password,
          ...(form.username ? { username: form.username } : {}),
          ...(form.fullName ? { full_name: form.fullName } : {}),
        });
        setMode('login');
        setInfo('Registration successful! Please sign in.');
        setForm((prev) => ({ ...prev, password: '', username: '', fullName: '' }));
      } else if (mode === 'forgot') {
        await (await import('@/lib/api')).authApi.forgotPassword({ email: form.email });
        setInfo('If the account exists, a reset link has been sent to your email.');
        setMode('reset');
      } else if (mode === 'reset') {
        await (await import('@/lib/api')).authApi.resetPassword({
          token: form.token,
          new_password: form.password,
        });
        setMode('login');
        setInfo('Password reset successful! You can now sign in.');
        setForm((prev) => ({ ...prev, password: '', token: '' }));
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const passwordRequirements = [
    { label: '8+ chars', met: form.password.length >= 8 },
    { label: 'Number', met: /\d/.test(form.password) },
  ];

  return (
    <div className="w-full rounded-2xl bg-neutral-900/90 border border-neutral-800 p-6 shadow-xl">
      <div className="text-center mb-6">
        <h2 className="text-xl font-bold mb-1.5 font-['Syne',sans-serif] text-white">
          {mode === 'login'
            ? 'Welcome back'
            : mode === 'register'
            ? 'Create account'
            : mode === 'forgot'
            ? 'Reset password'
            : 'Set new password'}
        </h2>
        <p className="text-neutral-400 text-xs">
          {mode === 'login'
            ? 'Sign in to continue to Clipnera'
            : mode === 'register'
            ? 'Start creating viral clips with AI'
            : mode === 'forgot'
            ? 'We will email you a reset link'
            : 'Enter the code from your email'}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        {mode === 'reset' && (
          <div className="relative">
            <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-500" />
            <input
              type="text"
              name="token"
              placeholder="Reset code"
              value={form.token}
              onChange={handleChange}
              required
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-700/80 text-white placeholder-neutral-500 focus:outline-none focus:border-amber-400 transition-colors text-xs shadow-inner"
            />
          </div>
        )}

        <div className="relative">
          <Mail size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-500" />
          <input
            type="email"
            name="email"
            placeholder="you@example.com"
            value={form.email}
            onChange={handleChange}
            required
            disabled={mode === 'reset'}
            className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-700/80 text-white placeholder-neutral-500 focus:outline-none focus:border-amber-400 transition-colors text-xs shadow-inner disabled:opacity-50"
          />
        </div>

        {mode === 'register' && (
          <div className="relative">
            <User size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-500" />
            <input
              type="text"
              name="username"
              placeholder="Username"
              value={form.username}
              onChange={handleChange}
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-700/80 text-white placeholder-neutral-500 focus:outline-none focus:border-amber-400 transition-colors text-xs shadow-inner"
            />
          </div>
        )}

        {mode === 'register' && (
          <div className="relative">
            <User size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-500" />
            <input
              type="text"
              name="fullName"
              placeholder="Full name"
              value={form.fullName}
              onChange={handleChange}
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-700/80 text-white placeholder-neutral-500 focus:outline-none focus:border-amber-400 transition-colors text-xs shadow-inner"
            />
          </div>
        )}

        {mode !== 'forgot' && (
          <div>
            <div className="relative">
              <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-500" />
              <input
                type={showPassword ? 'text' : 'password'}
                name="password"
                placeholder="••••••••"
                value={form.password}
                onChange={handleChange}
                required
                className="w-full pl-10 pr-10 py-2.5 rounded-xl bg-neutral-950 border border-neutral-700/80 text-white placeholder-neutral-500 focus:outline-none focus:border-amber-400 transition-colors text-xs shadow-inner"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-neutral-500 hover:text-white"
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {mode === 'register' && form.password && (
              <div className="flex gap-3 mt-2">
                {passwordRequirements.map((req) => (
                  <div key={req.label} className="flex items-center gap-1.5 text-xs">
                    <Check size={10} className={req.met ? 'text-emerald-400' : 'text-neutral-600'} />
                    <span className={req.met ? 'text-emerald-400' : 'text-neutral-500'}>{req.label}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-center gap-2"
            >
              <AlertCircle size={14} />
              {error}
            </motion.div>
          )}
          {info && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs"
            >
              {info}
            </motion.div>
          )}
        </AnimatePresence>

        <button
          type="submit"
          disabled={loading}
          className="w-full py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold transition-all active:scale-95 disabled:opacity-50 flex items-center justify-center gap-2 text-xs shadow-md shadow-amber-500/15"
        >
          {loading ? (
            <div className="w-4 h-4 border-2 border-neutral-950/30 border-t-neutral-950 rounded-full animate-spin" />
          ) : (
            <>
              {mode === 'login'
                ? 'Sign In'
                : mode === 'register'
                ? 'Create Account'
                : mode === 'forgot'
                ? 'Send Reset Link'
                : 'Reset Password'}
              <ArrowRight size={14} />
            </>
          )}
        </button>
      </form>

      <div className="mt-5 text-center text-xs text-neutral-400 space-y-2">
        {mode === 'login' ? (
          <>
            <p>
              No account?{' '}
              <button
                onClick={() => {
                  resetInfo();
                  setMode('register');
                }}
                className="text-amber-400 hover:text-amber-300 font-medium"
              >
                Sign up
              </button>
            </p>
            <p>
              <button
                onClick={() => {
                  resetInfo();
                  setMode('forgot');
                }}
                className="text-neutral-500 hover:text-neutral-300 font-medium"
              >
                Forgot password?
              </button>
            </p>
          </>
        ) : (
          <p>
            <button
              onClick={() => {
                resetInfo();
                setMode('login');
              }}
              className="text-amber-400 hover:text-amber-300 font-medium"
            >
              Back to sign in
            </button>
          </p>
        )}
      </div>
    </div>
  );
}
