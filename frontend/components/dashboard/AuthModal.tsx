"use client";

import React from 'react';
import { X, Briefcase, Check, LogOut } from 'lucide-react';
import { UserProfile, Workspace } from '@/lib/types';
import { Avatar } from './Avatar';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentUser: UserProfile;
  workspaces: Workspace[];
  onSelectWorkspace: (workspaceId: string) => void;
  onSignOut: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({
  isOpen,
  onClose,
  currentUser,
  workspaces,
  onSelectWorkspace,
  onSignOut,
}) => {
  if (!isOpen) return null;

  const handleSignOut = () => {
    onSignOut();
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in">
      <div className="relative w-full max-w-md rounded-2xl bg-neutral-900/90 border border-neutral-800 p-6 shadow-xl space-y-6">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 p-1.5 rounded-full text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Modal Header */}
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-2xl bg-amber-500 flex items-center justify-center text-neutral-950 font-black text-xl shadow-md shadow-amber-500/15 mx-auto">
            C
          </div>
          <h2 className="text-xl font-bold text-white">
            Account & Workspace
          </h2>
          <p className="text-xs text-neutral-400">
            Manage your active workspace and session
          </p>
        </div>

        {/* Active User Card */}
        <div className="p-3.5 rounded-2xl bg-neutral-950 border border-neutral-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Avatar
              initials={currentUser.avatarInitials}
              src={currentUser.avatarUrl}
              alt={currentUser.name}
              className="w-10 h-10"
            />
            <div>
              <h4 className="text-xs font-bold text-white">{currentUser.name}</h4>
              <p className="text-[11px] text-neutral-400 font-mono">{currentUser.email}</p>
            </div>
          </div>
          <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-amber-500/10 text-amber-300 border border-amber-500/20">
            {currentUser.plan}
          </span>
        </div>

        {/* Workspaces Switcher */}
        <div>
          <label className="text-xs font-bold text-neutral-300 block mb-2">
            Select Active Workspace:
          </label>
          <div className="space-y-2">
            {workspaces.map((ws) => {
              const isSelected = ws.id === currentUser.activeWorkspaceId;
              return (
                <button
                  key={ws.id}
                  onClick={() => {
                    onSelectWorkspace(ws.id);
                    onClose();
                  }}
                  className={`w-full p-3 rounded-xl border text-left transition-all flex items-center justify-between ${
                    isSelected
                      ? 'bg-neutral-800 border-amber-400 text-white ring-1 ring-amber-400/30'
                      : 'bg-neutral-950 border-neutral-800 text-neutral-400 hover:border-neutral-700 hover:text-neutral-200'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Briefcase className="w-4 h-4 text-amber-400" />
                    <div>
                      <span className="text-xs font-bold block text-white">{ws.name}</span>
                      <span className="text-[10px] text-neutral-400 capitalize">
                        Role: {ws.role} • {ws.membersCount} members
                      </span>
                    </div>
                  </div>
                  {isSelected && <Check className="w-4 h-4 text-amber-400" />}
                </button>
              );
            })}
          </div>
        </div>

        {/* Sign Out */}
        <button
          onClick={handleSignOut}
          className="w-full py-3 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-amber-400 hover:text-amber-300 font-bold text-xs transition-all flex items-center justify-center gap-2 active:scale-95"
        >
          <LogOut className="w-4 h-4" />
          <span>Sign Out</span>
        </button>
      </div>
    </div>
  );
};
