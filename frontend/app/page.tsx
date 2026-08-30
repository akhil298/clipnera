"use client";

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Sparkles, Film } from 'lucide-react';
import { AuthForm } from '@/components/auth/AuthForm';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    if (localStorage.getItem('token')) {
      router.replace('/dashboard');
    }
  }, [router]);

  return (
    <div className="min-h-screen flex flex-col relative overflow-hidden bg-neutral-950 text-neutral-100 font-['Plus_Jakarta_Sans',sans-serif]">
      {/* Background glow */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-[-20%] left-[-10%] w-[600px] h-[600px] rounded-full bg-amber-500/10 blur-[120px]" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[500px] h-[500px] rounded-full bg-rose-500/10 blur-[100px]" />
      </div>

      {/* Header */}
      <header className="relative z-10 flex items-center justify-between px-6 md:px-12 py-6">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-amber-500 flex items-center justify-center">
            <Film size={18} className="text-neutral-950" />
          </div>
          <span className="text-xl font-bold tracking-tight">
            Clip<span className="text-amber-400">nera</span>
          </span>
        </div>
      </header>

      {/* Hero + Auth */}
      <main className="relative z-10 flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-5xl mx-auto grid lg:grid-cols-2 gap-16 items-center">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300 mb-6">
              <Sparkles size={12} />
              AI-Powered Video Platform
            </div>
            <h1 className="text-4xl md:text-5xl font-bold leading-tight mb-6">
              Create Viral Clips with{' '}
              <span className="text-amber-400">AI Magic</span>
            </h1>
            <p className="text-lg text-neutral-400">
              Turn long-form videos into stunning shorts and social-ready content — auto-reframed,
              captioned, and optimized for virality.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <AuthForm onAuthenticated={() => router.replace('/dashboard')} />
          </motion.div>
        </div>
      </main>
    </div>
  );
}
