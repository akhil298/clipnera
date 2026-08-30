"use client";
import React from 'react';

interface AvatarProps {
  initials: string;
  src?: string;
  alt: string;
  className?: string;
}

const AVATAR_COLORS = [
  'from-amber-500 to-rose-500',
  'from-emerald-500 to-teal-600',
  'from-blue-500 to-indigo-600',
  'from-purple-500 to-pink-600',
  'from-orange-500 to-red-600',
  'from-cyan-500 to-blue-600',
  'from-rose-500 to-pink-600',
  'from-lime-500 to-green-600',
];

function getColorFromString(str: string) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

export const Avatar: React.FC<AvatarProps> = ({ initials, src, alt, className = '' }) => {
  const gradient = getColorFromString(alt + initials);

  if (src) {
    return (
      <img
        src={src}
        alt={alt}
        className={`rounded-xl object-cover border border-amber-500/30 ${className}`}
      />
    );
  }

  return (
    <div
      className={`rounded-xl bg-gradient-to-br ${gradient} flex items-center justify-center text-neutral-950 font-black border border-white/10 ${className}`}
    >
      <span className="select-none leading-none">{initials}</span>
    </div>
  );
};
