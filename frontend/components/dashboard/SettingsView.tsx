"use client";
import React, { useState, useEffect } from 'react';
import {
  User,
  CreditCard,
  Share2,
  Users,
  ShieldCheck,
  Zap,
  Check,
  Plus,
  Trash2,
  ExternalLink,
  Smartphone,
  Layers,
  Settings,
  Bell,
  Crown
} from 'lucide-react';
import { UserProfile, Workspace } from '@/lib/types';
import { Avatar } from './Avatar';
import { workspaceApi } from '@/lib/api';
import { TableSkeleton } from '@/components/skeletons';
import { PlanSelectionModal, type SelectedPlan } from './PlanSelectionModal';
import { ProLockBadge } from './ProLockBadge';
import { useEntitlements, planLabel } from '@/hooks/useEntitlements';
import { FEATURE_LABELS, usePlan } from '@/hooks/usePlan';
import { formatDate } from '@/lib/utils/dates';
import { PaymentModal } from './PaymentModal';
import { MyPaymentsCard } from '@/components/payments/MyPaymentsCard';
import { ConnectedPlatformsPanel, useSocialTabVisible } from '@/components/social/ConnectedPlatformsPanel';

interface SettingsViewProps {
  user: UserProfile;
  workspaces: Workspace[];
  onUpdateUser: (user: UserProfile) => void;
  activeSettingsTab: 'account' | 'billing' | 'social' | 'team';
  onSettingsTabChange: (tab: 'account' | 'billing' | 'social' | 'team') => void;
}

interface TeamMember {
  id: string;
  name: string;
  email: string;
  role: string;
  status: string;
}

export const SettingsView: React.FC<SettingsViewProps> = ({
  user,
  workspaces,
  onUpdateUser,
  activeSettingsTab,
  onSettingsTabChange,
}) => {
  const [isPlanModalOpen, setIsPlanModalOpen] = useState(false);
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<SelectedPlan | null>(null);
  const [paymentsRefreshKey, setPaymentsRefreshKey] = useState(0);
  const { entitlements, isLoading: loadingSub, refresh: refreshPlan } = useEntitlements();
  const { isPro, canUse, promptUpgrade } = usePlan();
  const canAddMembers = canUse('team_members');

  // Pick up payments approved or plans changed since the dashboard loaded.
  useEffect(() => {
    if (activeSettingsTab === 'billing') void refreshPlan();
  }, [activeSettingsTab, refreshPlan]);

  const showSocialTab = useSocialTabVisible();

  const activeWorkspaceId = user.activeWorkspaceId || workspaces[0]?.id;
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [loadingMembers, setLoadingMembers] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newMemberName, setNewMemberName] = useState('');
  const [newMemberEmail, setNewMemberEmail] = useState('');
  const [newMemberPassword, setNewMemberPassword] = useState('');
  const [newMemberRole, setNewMemberRole] = useState('member');
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviteSuccess, setInviteSuccess] = useState<string | null>(null);

  const fetchMembers = async (workspaceId: string) => {
    if (!workspaceId) return;
    setLoadingMembers(true);
    try {
      const members = await workspaceApi.listMembers(workspaceId);
      setTeamMembers(
        members.map((m) => ({
          id: m.id,
          name: m.name || m.email.split('@')[0],
          email: m.email,
          role: m.role,
          status: m.status,
        }))
      );
    } catch {
      setTeamMembers([]);
    } finally {
      setLoadingMembers(false);
    }
  };

  useEffect(() => {
    if (activeSettingsTab === 'team' && activeWorkspaceId) {
      fetchMembers(activeWorkspaceId);
    }
  }, [activeSettingsTab, activeWorkspaceId]);

  const resetForm = () => {
    setNewMemberName('');
    setNewMemberEmail('');
    setNewMemberPassword('');
    setNewMemberRole('member');
    setShowAddForm(false);
  };

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    setInviteError(null);
    setInviteSuccess(null);
    if (!newMemberName.trim() || !newMemberEmail.trim() || !newMemberPassword || !activeWorkspaceId) return;
    setInviting(true);
    try {
      console.log('Adding member to workspace:', activeWorkspaceId);
      const member = await workspaceApi.createAndAddMember(
        activeWorkspaceId,
        newMemberEmail.trim(),
        newMemberPassword,
        newMemberName.trim(),
        newMemberRole
      );
      console.log('Member added successfully:', member);
      setTeamMembers((prev) => [
        ...prev,
        {
          id: member.id,
          name: member.name || member.email.split('@')[0],
          email: member.email,
          role: member.role,
          status: member.status,
        },
      ]);
      setInviteSuccess(`${member.name || member.email} added successfully!`);
      resetForm();
    } catch (err) {
      console.error('Failed to add member:', err);
      setInviteError(err instanceof Error ? err.message : 'Failed to add member');
    } finally {
      setInviting(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Settings Header */}
      <div className="rounded-2xl bg-neutral-900/90 border border-neutral-800 p-5 lg:p-6 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xl">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-neutral-800 text-neutral-300 border border-neutral-700">
              Workspace & Account
            </span>
            <span className="text-xs text-neutral-400">Clipnera Pro Suite</span>
          </div>
          <h1 className="text-xl lg:text-2xl font-extrabold text-white tracking-tight font-['Syne',sans-serif]">
            Settings & Integrations
          </h1>
          <p className="text-xs text-neutral-400 mt-1">
            Manage your Clipnera profile, team seats, connected social platforms, and AI render billing.
          </p>
        </div>

        {/* Navigation Tabs Inside Settings */}
        <div className="flex flex-wrap items-center bg-neutral-950 p-1 rounded-xl border border-neutral-800">
          {[
            { id: 'account' as const, label: 'Profile', icon: User },
            { id: 'billing' as const, label: 'Plan & Billing', icon: CreditCard },
            ...(showSocialTab ? [{ id: 'social' as const, label: 'Social Accounts', icon: Share2 }] : []),
            { id: 'team' as const, label: 'Team & Workspace', icon: Users },
          ].map((tab) => {
            const Icon = tab.icon;
            const isSelected = activeSettingsTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => onSettingsTabChange(tab.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  isSelected
                    ? 'bg-neutral-800 text-white shadow-sm ring-1 ring-white/10'
                    : 'text-neutral-400 hover:text-neutral-200'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* SETTINGS TAB 1: PROFILE */}
      {activeSettingsTab === 'account' && (
        <div className="max-w-2xl p-6 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-6 shadow-xl">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">
            Personal Information
          </h3>

          <div className="flex items-center gap-4 pb-4 border-b border-neutral-800">
            <Avatar
              initials={user.avatarInitials}
              src={user.avatarUrl}
              alt={user.name}
              className="w-16 h-16"
            />
            <div>
              <h4 className="text-sm font-bold text-white">{user.name}</h4>
              <p className="text-xs text-neutral-400">{user.email}</p>
              <span className="inline-block mt-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-amber-500/10 text-amber-300 border border-amber-500/20">
                Clipnera {user.plan.toUpperCase()} Member
              </span>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-xs text-neutral-400 block mb-1">Full Name:</label>
              <input
                type="text"
                value={user.name}
                readOnly
                disabled
                className="w-full p-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-neutral-500 cursor-not-allowed"
              />
            </div>

            <div>
              <label className="text-xs text-neutral-400 block mb-1">Email Address:</label>
              <input
                type="email"
                value={user.email}
                readOnly
                disabled
                className="w-full p-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-neutral-500 cursor-not-allowed"
              />
            </div>
          </div>
        </div>
      )}

      {/* SETTINGS TAB 2: BILLING & AI CREDITS */}
      {activeSettingsTab === 'billing' && (
        <div className="grid lg:grid-cols-12 gap-6">
          <div className="lg:col-span-12 p-6 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-5 shadow-xl">
            <div className="flex items-center justify-between">
              <div>
                {loadingSub ? (
                  <div className="animate-pulse space-y-2">
                    <div className="h-5 bg-neutral-800 rounded w-32"></div>
                    <div className="h-4 bg-neutral-800 rounded w-48"></div>
                  </div>
                ) : (
                  <>
                    <span className="text-[10px] px-2 py-0.5 rounded font-bold uppercase bg-amber-500/10 text-amber-300 border border-amber-500/20">
                      {isPro ? 'Active Subscription' : entitlements.has_pending_payment ? 'Pending Verification' : 'Free Plan'}
                    </span>
                    <h3 className="text-lg font-bold text-white mt-1 flex items-center gap-1.5">
                      {isPro && <Crown className="w-4 h-4 text-amber-400" />}
                      {planLabel(entitlements.plan)} Plan
                    </h3>
                    <p className="text-xs text-neutral-400">
                      {entitlements.plan_expires_at
                        ? `Pro until ${formatDate(entitlements.plan_expires_at)}`
                        : 'Free forever. Upgrade any time.'}
                    </p>
                  </>
                )}
              </div>
              <div className="text-right">
                {!loadingSub && (
                  <>
                    <span className="text-xs text-neutral-400 block">Credits Remaining</span>
                    <span className="text-xs font-mono font-bold text-white">
                      {entitlements.credit_minutes_remaining} / {entitlements.credit_minutes_total} mins
                    </span>
                  </>
                )}
              </div>
            </div>

            {/* Quota Progress */}
            <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-neutral-300 font-bold flex items-center gap-1.5">
                  <Zap className="w-4 h-4 text-amber-400 fill-amber-400" />
                  <span>AI Rendering Quota</span>
                </span>
                <span className="font-mono text-amber-400 font-bold">
                  {entitlements.credit_minutes_remaining} of {entitlements.credit_minutes_total} mins
                </span>
              </div>
              <div className="h-2.5 w-full bg-neutral-900 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-amber-500 to-rose-500"
                  style={{ width: `${entitlements.credit_minutes_total > 0 ? Math.min(100, (entitlements.credit_minutes_remaining / entitlements.credit_minutes_total) * 100) : 0}%` }}
                />
              </div>
              <p className="text-[11px] text-neutral-500">
                {entitlements.next_credit_reset_at
                  ? `Resets to ${entitlements.credit_minutes} mins on ${formatDate(entitlements.next_credit_reset_at)}. Unused minutes don't roll over.`
                  : `Resets to ${entitlements.credit_minutes} mins every 30 days.`}
              </p>
            </div>

            {entitlements.has_pending_payment ? (
              <div className="w-full py-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 font-bold text-sm text-center">
                Pro activation pending verification
              </div>
            ) : (
              <button
                onClick={() => setIsPlanModalOpen(true)}
                className="w-full py-3 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-sm shadow-md shadow-amber-500/15 active:scale-95 transition-all"
              >
                {isPro ? 'Renew Pro' : 'Upgrade to Pro'}
              </button>
            )}
          </div>

          <div className="lg:col-span-12">
            <MyPaymentsCard refreshKey={paymentsRefreshKey} />
          </div>
        </div>
      )}

      {/* SETTINGS TAB 3: CONNECTED SOCIAL ACCOUNTS */}
      {activeSettingsTab === 'social' && <ConnectedPlatformsPanel />}

      {/* SETTINGS TAB 4: TEAM & WORKSPACE */}
      {activeSettingsTab === 'team' && (
        <div className="space-y-5">
          {/* Add Member Form */}
          <div className="p-6 rounded-2xl bg-neutral-900/90 border border-neutral-800 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Plus className="w-4 h-4 text-amber-400" />
                  <span>Add Team Member</span>
                </h3>
                <p className="text-xs text-neutral-400 mt-0.5">
                  Create a new account and add them to your workspace.
                </p>
              </div>
              <button
                onClick={() =>
                  canAddMembers ? setShowAddForm(!showAddForm) : promptUpgrade(FEATURE_LABELS.team_members)
                }
                className="px-3 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-300 text-xs font-semibold border border-neutral-700 transition-colors flex items-center gap-1.5"
              >
                {showAddForm ? 'Cancel' : '+ New Member'}
                {!canAddMembers && <ProLockBadge feature={FEATURE_LABELS.team_members} />}
              </button>
            </div>

            {showAddForm && canAddMembers && (
              <form onSubmit={handleAddMember} className="space-y-3 pt-3 border-t border-neutral-800">
                <div className="grid sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-neutral-400 block mb-1">Full Name</label>
                    <input
                      type="text"
                      placeholder="John Doe"
                      value={newMemberName}
                      onChange={(e) => setNewMemberName(e.target.value)}
                      className="w-full p-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-white placeholder-neutral-500 focus:outline-none focus:border-amber-400"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-xs text-neutral-400 block mb-1">Email Address</label>
                    <input
                      type="email"
                      placeholder="john@agency.com"
                      value={newMemberEmail}
                      onChange={(e) => setNewMemberEmail(e.target.value)}
                      className="w-full p-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-white placeholder-neutral-500 focus:outline-none focus:border-amber-400"
                      required
                    />
                  </div>
                </div>
                <div className="grid sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-neutral-400 block mb-1">Password</label>
                    <input
                      type="password"
                      placeholder="Min 8 characters"
                      value={newMemberPassword}
                      onChange={(e) => setNewMemberPassword(e.target.value)}
                      className="w-full p-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-white placeholder-neutral-500 focus:outline-none focus:border-amber-400"
                      minLength={8}
                      required
                    />
                  </div>
                  <div>
                    <label className="text-xs text-neutral-400 block mb-1">Role</label>
                    <select
                      value={newMemberRole}
                      onChange={(e) => setNewMemberRole(e.target.value)}
                      className="w-full p-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-white focus:outline-none focus:border-amber-400"
                    >
                      <option value="member">Member</option>
                      <option value="admin">Admin</option>
                      <option value="viewer">Viewer</option>
                    </select>
                  </div>
                </div>

                {inviteError && (
                  <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
                    {inviteError}
                  </div>
                )}
                {inviteSuccess && (
                  <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs">
                    {inviteSuccess}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={inviting || !newMemberName.trim() || !newMemberEmail.trim() || !newMemberPassword}
                  className="w-full py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-xs disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {inviting ? 'Creating Account...' : 'Create & Add to Team'}
                </button>
              </form>
            )}
          </div>

          {/* Team Members List */}
          <div className="p-6 rounded-2xl bg-neutral-900/90 border border-neutral-800 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Users className="w-4 h-4 text-amber-400" />
                <span>Team Roster ({teamMembers.length})</span>
              </h3>
            </div>

             {!activeWorkspaceId ? (
               <div className="py-8 text-center">
                 <p className="text-xs text-neutral-400">Create a workspace first to manage team members.</p>
               </div>
             ) : (
              <div className="divide-y divide-neutral-800">
                {loadingMembers ? (
                  <TableSkeleton rows={4} />
                ) : teamMembers.length === 0 ? (
                  <div className="py-8 text-center">
                    <Users className="w-8 h-8 text-neutral-600 mx-auto mb-2" />
                    <p className="text-xs text-neutral-400">No team members yet.</p>
                    <p className="text-[11px] text-neutral-500 mt-1">Add someone above to get started.</p>
                  </div>
                ) : (
                  teamMembers.map((m) => (
                    <div key={m.id} className="py-3 flex items-center justify-between text-xs">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-amber-500 to-rose-500 flex items-center justify-center text-[11px] font-bold text-white">
                          {m.name.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <span className="font-bold text-white block">{m.name}</span>
                          <span className="text-neutral-400 text-[11px]">{m.email}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="px-2 py-0.5 rounded bg-neutral-800 text-neutral-300 font-semibold text-[10px] capitalize">
                          {m.role}
                        </span>
                        <span
                          className={`text-[10px] font-semibold capitalize ${
                            m.status === 'active' ? 'text-emerald-400' : 'text-amber-400'
                          }`}
                        >
                          {m.status}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </div>
      )}

      <PlanSelectionModal
        isOpen={isPlanModalOpen}
        onClose={() => setIsPlanModalOpen(false)}
        onPlanSelected={(plan) => {
          setIsPlanModalOpen(false);
          setSelectedPlan(plan);
          setIsPaymentModalOpen(true);
        }}
      />
      <PaymentModal
        isOpen={isPaymentModalOpen}
        onClose={() => {
          setIsPaymentModalOpen(false);
          setSelectedPlan(null);
        }}
        plan={selectedPlan}
        onPaymentComplete={() => {
          setIsPaymentModalOpen(false);
          setSelectedPlan(null);
          void refreshPlan();
          setPaymentsRefreshKey((k) => k + 1);
        }}
      />
    </div>
  );
};
