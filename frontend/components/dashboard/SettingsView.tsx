"use client";
import React, { useState, useEffect } from 'react';
import { User, CreditCard, Share2, Users, Zap, Plus, Crown } from 'lucide-react';
import { UserProfile, Workspace } from '@/lib/types';
import { Avatar } from './Avatar';
import { AccountPrivacyPanel } from './AccountPrivacyPanel';
import { workspaceApi, type AssignableWorkspaceRole, type CreditPackResponse } from '@/lib/api';
import { TableSkeleton } from '@/components/skeletons';
import { PlanSelectionModal, type SelectedPlan } from './PlanSelectionModal';
import { ProLockBadge } from './ProLockBadge';
import { useEntitlements, planLabel, videoMinutesFor } from '@/hooks/useEntitlements';
import { FEATURE_LABELS, usePlan } from '@/hooks/usePlan';
import { formatDate } from '@/lib/utils/dates';
import { PaymentModal } from './PaymentModal';
import { MyPaymentsCard } from '@/components/payments/MyPaymentsCard';
import { CreditPacksCard } from '@/components/payments/CreditPacksCard';
import { ConnectedPlatformsPanel, useSocialTabVisible } from '@/components/social/ConnectedPlatformsPanel';
import { Select, SelectOption } from '@/components/ui/Select';
import { PageHeader } from '@/components/ui/PageHeader';
import { StatusPill } from '@/components/ui/StatusPill';

const MEMBER_ROLE_OPTIONS: SelectOption<AssignableWorkspaceRole>[] = [
  { value: 'member', label: 'Member' },
  { value: 'viewer', label: 'Viewer' },
];

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
  const [selectedPack, setSelectedPack] = useState<CreditPackResponse | null>(null);
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
  const [newMemberRole, setNewMemberRole] = useState<AssignableWorkspaceRole>('member');
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

  // Keeps the form open so the success message (rendered inside it) stays visible.
  const resetForm = () => {
    setNewMemberName('');
    setNewMemberEmail('');
    setNewMemberPassword('');
    setNewMemberRole('member');
  };

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    setInviteError(null);
    setInviteSuccess(null);
    if (!newMemberName.trim() || !newMemberEmail.trim() || !newMemberPassword || !activeWorkspaceId) return;
    setInviting(true);
    try {
      const member = await workspaceApi.createAndAddMember(
        activeWorkspaceId,
        newMemberEmail.trim(),
        newMemberPassword,
        newMemberName.trim(),
        newMemberRole
      );
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
      setInviteError(err instanceof Error ? err.message : 'Failed to add member');
    } finally {
      setInviting(false);
    }
  };

  const tabs = [
    { id: 'account' as const, label: 'Profile', icon: User },
    { id: 'billing' as const, label: 'Plan & billing', icon: CreditCard },
    ...(showSocialTab ? [{ id: 'social' as const, label: 'Social accounts', icon: Share2 }] : []),
    { id: 'team' as const, label: 'Team & workspace', icon: Users },
  ];

  const total = Math.max(entitlements.credit_minutes_total, entitlements.credit_minutes_remaining, 1);
  const bought = Math.min(entitlements.purchased_credits_remaining, entitlements.credit_minutes_remaining);
  const planCredits = Math.max(0, entitlements.credit_minutes_remaining - bought);
  const usageRows = (
    [
      ['exports', 'Exports'],
      ['audio_enhancements', 'Audio clean-ups'],
      ['reel_renders', 'Reel renders'],
      ['ai_shots', 'AI shots'],
      ['auto_edits', 'Footage edits'],
    ] as const
  ).map(([key, label]) => ({
    key,
    label,
    used: entitlements.usage_today[key] ?? 0,
    limit: entitlements.daily_limits[key],
  }));
  const inputClass =
    'w-full h-10 px-3 rounded-xl bg-neutral-950 border border-neutral-800 text-[13px] text-white placeholder:text-neutral-600 focus:outline-none focus:border-amber-400';

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <PageHeader title="Settings" description="Your profile, plan, connected accounts and team." />

      <div className="grid grid-cols-1 lg:grid-cols-[220px_minmax(0,1fr)] gap-6 items-start">
        {/* Section navigation: a side list on desktop, scrolling tabs on smaller screens */}
        <nav aria-label="Settings sections" className="lg:sticky lg:top-20">
          <div className="flex lg:flex-col gap-1 p-1 rounded-2xl bg-neutral-900/80 border border-neutral-800 overflow-x-auto [scrollbar-width:none]">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isSelected = activeSettingsTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => onSettingsTabChange(tab.id)}
                  aria-current={isSelected ? 'page' : undefined}
                  className={`flex items-center gap-2.5 h-9 px-3 rounded-xl text-[13px] font-semibold whitespace-nowrap transition-colors ${
                    isSelected ? 'bg-neutral-800 text-white' : 'text-neutral-400 hover:text-white hover:bg-neutral-800/50'
                  }`}
                >
                  <Icon className={`w-4 h-4 shrink-0 ${isSelected ? 'text-amber-400' : ''}`} />
                  {tab.label}
                </button>
              );
            })}
          </div>
        </nav>

        <div className="min-w-0 space-y-6">
          {/* PROFILE */}
          {activeSettingsTab === 'account' && (
            <>
              <section className="p-4 sm:p-6 rounded-2xl bg-neutral-900/80 border border-neutral-800 space-y-5" aria-labelledby="profile-title">
                <h2 id="profile-title" className="text-sm font-bold text-white">Profile</h2>
                <div className="flex items-center gap-4">
                  <Avatar initials={user.avatarInitials} src={user.avatarUrl} alt={user.name} className="w-14 h-14 text-lg" />
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-white truncate">{user.name}</p>
                    <p className="text-xs text-neutral-400 truncate">{user.email}</p>
                    <span className="inline-flex items-center gap-1 mt-1.5 h-5 px-1.5 rounded-md text-[10.5px] font-bold bg-amber-500/10 text-amber-300">
                      {isPro && <Crown className="w-3 h-3" />}
                      {planLabel(entitlements.plan)} plan
                    </span>
                  </div>
                </div>
                <div className="grid sm:grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="profile-name" className="text-xs font-semibold text-neutral-300 block mb-1.5">Full name</label>
                    <input id="profile-name" type="text" value={user.name} readOnly disabled className={`${inputClass} text-neutral-400 cursor-not-allowed`} />
                  </div>
                  <div>
                    <label htmlFor="profile-email" className="text-xs font-semibold text-neutral-300 block mb-1.5">Email</label>
                    <input id="profile-email" type="email" value={user.email} readOnly disabled className={`${inputClass} text-neutral-400 cursor-not-allowed`} />
                  </div>
                </div>
                <p className="text-[11.5px] text-neutral-500">Your name and email come from your Google account.</p>
              </section>
              <AccountPrivacyPanel user={user} onUpdateUser={onUpdateUser} />
            </>
          )}

          {/* PLAN & BILLING */}
          {activeSettingsTab === 'billing' && (
            <>
              <div className="grid md:grid-cols-2 gap-4">
                <section className="p-4 sm:p-5 rounded-2xl bg-neutral-900/80 border border-neutral-800 space-y-4" aria-labelledby="plan-title">
                  {loadingSub ? (
                    <div className="animate-pulse space-y-2">
                      <div className="h-5 bg-neutral-800 rounded w-32" />
                      <div className="h-4 bg-neutral-800 rounded w-48" />
                    </div>
                  ) : (
                    <>
                      <div className="flex items-center gap-2">
                        {isPro ? (
                          <StatusPill tone="ready">Active</StatusPill>
                        ) : entitlements.has_pending_payment ? (
                          <StatusPill tone="processing">Pending verification</StatusPill>
                        ) : (
                          <StatusPill tone="neutral">Free plan</StatusPill>
                        )}
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-300 via-amber-500 to-amber-600 text-neutral-950 flex items-center justify-center shrink-0">
                          <Crown className="w-5 h-5" />
                        </span>
                        <div>
                          <h2 id="plan-title" className="text-lg font-bold text-white">{planLabel(entitlements.plan)}</h2>
                          <p className="text-xs text-neutral-400">
                            {entitlements.plan_expires_at
                              ? `Paid until ${formatDate(entitlements.plan_expires_at)}`
                              : 'Free forever. Upgrade any time.'}
                          </p>
                        </div>
                      </div>
                      {entitlements.has_pending_payment ? (
                        <p className="rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-200 text-xs font-semibold px-3 py-2.5">
                          Pro activation pending verification. We’ll switch your plan as soon as the payment is approved.
                        </p>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setIsPlanModalOpen(true)}
                          className="h-10 px-4 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-[13px] shadow-md shadow-amber-500/20 transition-colors"
                        >
                          {isPro ? 'Renew or change plan' : 'Upgrade to Pro'}
                        </button>
                      )}
                    </>
                  )}
                </section>

                <section className="p-4 sm:p-5 rounded-2xl bg-neutral-900/80 border border-neutral-800 space-y-3" aria-labelledby="credits-title">
                  <div className="flex items-baseline justify-between">
                    <h2 id="credits-title" className="text-sm font-bold text-white flex items-center gap-1.5">
                      <Zap className="w-4 h-4 text-amber-400 fill-amber-400" /> Credits
                    </h2>
                    {!loadingSub && (
                      <span className="text-sm font-bold text-white tabular-nums">
                        {entitlements.credit_minutes_remaining}
                        <span className="text-neutral-500 font-medium"> / {entitlements.credit_minutes_total}</span>
                      </span>
                    )}
                  </div>
                  <div className="h-2.5 w-full bg-neutral-800 rounded-full overflow-hidden flex" role="img"
                    aria-label={`${entitlements.credit_minutes_remaining} of ${entitlements.credit_minutes_total} credits left`}>
                    <div className="h-full bg-amber-500" style={{ width: `${(planCredits / total) * 100}%` }} />
                    <div className="h-full bg-violet-400" style={{ width: `${(bought / total) * 100}%` }} />
                  </div>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11.5px] text-neutral-400">
                    <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-sm bg-amber-500" />{planCredits} plan credits</span>
                    {bought > 0 && (
                      <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-sm bg-violet-400" />{bought} bought, never expire</span>
                    )}
                  </div>
                  <p className="text-[11.5px] text-neutral-500">
                    ≈ {videoMinutesFor(entitlements, entitlements.credit_minutes_remaining)} min of video at {entitlements.credits_per_video_minute} credit{entitlements.credits_per_video_minute === 1 ? '' : 's'} a minute.{' '}
                    {entitlements.next_credit_reset_at
                      ? `Plan credits reset to ${entitlements.credit_minutes} on ${formatDate(entitlements.next_credit_reset_at)}; unused ones don't roll over.`
                      : `Plan credits reset to ${entitlements.credit_minutes} every 30 days.`}
                  </p>
                </section>
              </div>

              <section className="p-4 sm:p-5 rounded-2xl bg-neutral-900/80 border border-neutral-800 space-y-4" aria-labelledby="usage-title">
                <div className="flex items-baseline justify-between gap-2">
                  <h2 id="usage-title" className="text-sm font-bold text-white">Used today</h2>
                  <span className="text-[11.5px] text-neutral-500">Resets at midnight UTC</span>
                </div>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  {usageRows.map((row) => (
                    <div key={row.key}>
                      <div className="flex items-baseline justify-between text-xs mb-1.5">
                        <span className="font-semibold text-neutral-300">{row.label}</span>
                        <span className="text-neutral-400 tabular-nums">
                          {row.used}
                          {row.limit !== null ? ` / ${row.limit}` : ' · no limit'}
                        </span>
                      </div>
                      <div className="h-1.5 w-full bg-neutral-800 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${row.limit !== null && row.used >= row.limit ? 'bg-rose-400' : 'bg-amber-500'}`}
                          style={{ width: `${row.limit ? Math.min(100, (row.used / row.limit) * 100) : row.used > 0 ? 100 : 0}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              <CreditPacksCard
                onSelect={(pack) => {
                  setSelectedPack(pack);
                  setIsPaymentModalOpen(true);
                }}
              />

              <MyPaymentsCard refreshKey={paymentsRefreshKey} />
            </>
          )}

          {/* SOCIAL ACCOUNTS */}
          {activeSettingsTab === 'social' && <ConnectedPlatformsPanel />}

          {/* TEAM & WORKSPACE */}
          {activeSettingsTab === 'team' && (
            <>
              <section className="p-4 sm:p-6 rounded-2xl bg-neutral-900/80 border border-neutral-800" aria-labelledby="add-member-title">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 id="add-member-title" className="text-sm font-bold text-white">Add a team member</h2>
                    <p className="text-xs text-neutral-400 mt-0.5">Creates their account and adds them to this workspace.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => (canAddMembers ? setShowAddForm(!showAddForm) : promptUpgrade(FEATURE_LABELS.team_members))}
                    aria-expanded={showAddForm}
                    className="h-9 px-3 rounded-xl border border-neutral-700 bg-neutral-800/60 hover:bg-neutral-800 text-white text-xs font-semibold transition-colors flex items-center gap-1.5"
                  >
                    {showAddForm ? 'Cancel' : <><Plus className="w-3.5 h-3.5" /> New member</>}
                    {!canAddMembers && <ProLockBadge feature={FEATURE_LABELS.team_members} />}
                  </button>
                </div>

                {showAddForm && canAddMembers && (
                  <form onSubmit={handleAddMember} className="space-y-4 mt-4 pt-4 border-t border-neutral-800">
                    <div className="grid sm:grid-cols-2 gap-4">
                      <div>
                        <label htmlFor="member-name" className="text-xs font-semibold text-neutral-300 block mb-1.5">Full name</label>
                        <input id="member-name" type="text" placeholder="John Doe" value={newMemberName}
                          onChange={(e) => setNewMemberName(e.target.value)} className={inputClass} required />
                      </div>
                      <div>
                        <label htmlFor="member-email" className="text-xs font-semibold text-neutral-300 block mb-1.5">Email</label>
                        <input id="member-email" type="email" placeholder="john@agency.com" value={newMemberEmail}
                          onChange={(e) => setNewMemberEmail(e.target.value)} className={inputClass} required />
                      </div>
                      <div>
                        <label htmlFor="member-password" className="text-xs font-semibold text-neutral-300 block mb-1.5">Password</label>
                        <input id="member-password" type="password" placeholder="At least 8 characters" value={newMemberPassword}
                          onChange={(e) => setNewMemberPassword(e.target.value)} className={inputClass} minLength={8} required autoComplete="new-password" />
                      </div>
                      <div>
                        <span className="text-xs font-semibold text-neutral-300 block mb-1.5">Role</span>
                        <Select value={newMemberRole} onChange={setNewMemberRole} options={MEMBER_ROLE_OPTIONS} aria-label="Role" className={inputClass} />
                      </div>
                    </div>

                    {inviteError && (
                      <p role="alert" className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-200 text-xs">{inviteError}</p>
                    )}
                    {inviteSuccess && (
                      <p role="status" className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-200 text-xs">{inviteSuccess}</p>
                    )}

                    <button
                      type="submit"
                      disabled={inviting || !newMemberName.trim() || !newMemberEmail.trim() || !newMemberPassword}
                      className="h-10 px-4 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-[13px] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      {inviting ? 'Creating account…' : 'Create and add to team'}
                    </button>
                  </form>
                )}
              </section>

              <section className="p-4 sm:p-6 rounded-2xl bg-neutral-900/80 border border-neutral-800" aria-labelledby="roster-title">
                <h2 id="roster-title" className="text-sm font-bold text-white flex items-center gap-2 mb-3">
                  <Users className="w-4 h-4 text-amber-400" />
                  Team <span className="text-neutral-500 font-medium tabular-nums">{teamMembers.length}</span>
                </h2>

                {!activeWorkspaceId ? (
                  <p className="py-8 text-center text-xs text-neutral-400">Create a workspace first to manage team members.</p>
                ) : loadingMembers ? (
                  <TableSkeleton rows={4} />
                ) : teamMembers.length === 0 ? (
                  <div className="py-8 text-center">
                    <Users className="w-8 h-8 text-neutral-600 mx-auto mb-2" />
                    <p className="text-sm font-semibold text-neutral-200">No team members yet</p>
                    <p className="text-xs text-neutral-500 mt-1">Add someone above to get started.</p>
                  </div>
                ) : (
                  <ul className="divide-y divide-neutral-800">
                    {teamMembers.map((m) => (
                      <li key={m.id} className="py-3 flex items-center gap-3">
                        <Avatar initials={m.name.charAt(0).toUpperCase()} alt={m.name} className="w-9 h-9 text-xs shrink-0" />
                        <div className="min-w-0 flex-1">
                          <p className="text-[13px] font-semibold text-white truncate">{m.name}</p>
                          <p className="text-[11.5px] text-neutral-500 truncate">{m.email}</p>
                        </div>
                        <span className="h-6 px-2 rounded-md bg-neutral-800 text-neutral-300 font-semibold text-[11px] capitalize flex items-center">{m.role}</span>
                        <StatusPill tone={m.status === 'active' ? 'ready' : 'processing'} className="capitalize">{m.status}</StatusPill>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </>
          )}
        </div>
      </div>

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
          setSelectedPack(null);
        }}
        plan={selectedPlan}
        creditPack={selectedPack}
        onPaymentComplete={() => {
          setIsPaymentModalOpen(false);
          setSelectedPlan(null);
          setSelectedPack(null);
          void refreshPlan();
          setPaymentsRefreshKey((k) => k + 1);
        }}
      />
    </div>
  );
};
