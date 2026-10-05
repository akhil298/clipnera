# 02 — Data layer, state and hooks (Wave 0 audit)

Scope: everything under `frontend/lib/` (22 files) and `frontend/hooks/` (8 files) — 30 files, 6,581 lines, each read top to bottom. Backend `route.py` / `schema.py` files, `main.py`, and the components that consume this slice were read only to verify contracts and callers.

Paths are relative to `frontend/` unless they start with `backend/`. "c/" in caller columns means `components/`.

Audit date: 2026-10-03, branch `clipnera` at `38f9bd5`. Nothing was run against a live server; every contract statement comes from reading source on both sides.

---

## 0. Summary

| Area | State today |
|---|---|
| HTTP client | Three hand-rolled `fetch` wrappers in one 2,593-line file (`lib/api.ts`). No library. |
| Server-state cache | None. No React Query / SWR / Zustand / Redux. Every component fetches in `useEffect` and keeps the result in `useState`. |
| Global state | One React context (`EntitlementsContext`). Two module-level promise caches (feature flags, hook transition catalogue). Everything else is prop-drilled from `DashboardApp.tsx`. |
| Auth | Bearer JWT (7-day lifetime) in `localStorage`. No refresh token, no server-side revocation, no route middleware. |
| Real time | SSE over `fetch` for pipeline progress and notifications; `setInterval`/`setTimeout` polling for everything else (9 separate polling loops, 500 ms – 30 s). |
| Envelope | Mixed. About half the endpoints return `{data,message,error}`, the rest return the bare object. The client hides this with two different wrappers. |
| Contracts | All 133 API methods (29 API objects) plus 2 standalone functions resolve to real backend routes. One call is broken on field names (audio), several are typed against untyped backend dicts. |
| Dead code | 18 API methods and 1 helper with no caller, 1 dead hook, 1 dead file, about 12 dead helper exports. |

Top ten findings (detail in section 8):

1. **Audio enhancement calls cannot work** — camelCase request against a snake_case schema, and an empty `audioUrl` (P0).
2. **422 validation errors are invisible** — FastAPI returns `{detail:[…]}`, the client only reads `message`, the user sees "Something went wrong" (P1).
3. **Token in `localStorage` for 7 days, logout is a server no-op** (P1 security).
4. **A 401 clears the token but does not redirect**; only one call site in the whole app handles it (P1).
5. **Up to four concurrent watchers on one pipeline run** (SSE + 2 s poll + 3 s poll + 5 s poll); the hook's 3 s poll never stops (P1).
6. **No request cancellation anywhere** except video upload parts and SSE (P2).
7. **No cache or dedupe**: `GET /me`, `/social/connections`, `/brand-kits/me`, `/creator-intro`, `/edits/limits` are refetched by several components independently (P2).
8. **Feature flags are global on/off only** — no per-user, per-workspace, per-plan, percentage, or client-side kill switch; flags fetched once per page load and never refreshed (P1 for the revamp).
9. **Project list is typed as full clips but the server sends 10-field summaries** (P2).
10. **`FREE_TIER_FALLBACK` has drifted from the server** (60 credits vs 20) (P3).

---

## 1. API call inventory

Conventions for the tables:

- **Wrapper**: `R` = `request()` (public POST, `api.ts:163`), `A` = `authedRequest()` (bearer, bare body, `api.ts:524`), `E` = `envelopeRequest()` (bearer, unwraps `.data`, `api.ts:1459`), `F` = raw `fetch`, `SSE` = `subscribeEvents()` (`api.ts:789`).
- **Auth**: `pub` = no token, `user` = bearer token, `admin` = bearer token plus server-side admin check.
- **Callers**: file:line of every call site outside `lib/api.ts`. **DEAD** = zero callers in `app/`, `components/`, `hooks/`, `lib/`.
- Line numbers in the first column are in `lib/api.ts`.

### 1.1 Auth — `authApi` (`api.ts:561`)

| Function | Method + path | Request | Response | Wrapper / auth | Callers |
|---|---|---|---|---|---|
| `login` :562 | POST `/auth/login` | `LoginPayload` | `TokenResponse` (then `setAuth`) | R / pub | **DEAD** (password UI replaced by Google) |
| `oauthLogin` :567 | POST `/auth/oauth/{provider}` | `OAuthLoginPayload` | `TokenResponse` (then `setAuth`) | R / pub | `app/login/google/page.tsx:39` |
| `register` :572 | POST `/auth/register` | `RegisterPayload` | untyped (`unknown`) | R / pub | **DEAD** |
| `forgotPassword` :573 | POST `/auth/forgot-password` | `ForgotPayload` | untyped | R / pub | **DEAD** |
| `resetPassword` :574 | POST `/auth/reset-password` | `ResetPayload` | untyped | R / pub | **DEAD** |
| `logout` :575 | POST `/auth/logout` | — | `void` (server sends `{message}`) | A / user | `c/dashboard/DashboardApp.tsx:692` |

### 1.2 User / account — `userApi` (`api.ts:578`)

| Function | Method + path | Request | Response | Wrapper / auth | Callers |
|---|---|---|---|---|---|
| `getMe` :579 | GET `/me` | — | `UserProfileResponse` | A / user | `c/admin/AdminGate.tsx:18`, `c/dashboard/DashboardApp.tsx:263`, `:711` |
| `dismissPlanNotice` :580 | POST `/me/plan-notice/dismiss` | — | `void` (204) | A / user | `c/dashboard/PlanBanner.tsx:28` |
| `setEmailPreferences` :581 | PUT `/me/email-preferences` | `EmailPreferencesRequest` | `UserProfileResponse` | E / user | `c/dashboard/AccountPrivacyPanel.tsx:28` |
| `unsubscribe` :584 | POST `/email/unsubscribe` | `UnsubscribeRequest` | `ApiEnvelope<null>` (not unwrapped) | R / pub | `app/unsubscribe/page.tsx:28` |
| `deleteAccount` :585 | POST `/me/delete` | `DeleteAccountRequest` | `null` | E / user | `c/dashboard/AccountPrivacyPanel.tsx:41` |

### 1.3 Workspaces — `workspaceApi` (`api.ts:589`)

| Function | Method + path | Request | Response | Wrapper / auth | Callers |
|---|---|---|---|---|---|
| `list` :590 | GET `/workspaces` | — | `WorkspaceResponse[]` | A / user | `c/dashboard/DashboardApp.tsx:264` |
| `create` :591 | POST `/workspaces` | `{name}` | `WorkspaceResponse` | A / user | **DEAD** |
| `get` :595 | GET `/workspaces/{id}` | — | `WorkspaceResponse` | A / user | **DEAD** |
| `listMembers` :596 | GET `/workspaces/{id}/members` | — | `WorkspaceMemberResponse[]` | A / user | `c/dashboard/SettingsView.tsx:82` |
| `inviteMember` :597 | POST `/workspaces/{id}/members` | `{email, role}` | `WorkspaceMemberResponse` | A / user (Pro) | **DEAD** |
| `createAndAddMember` :601 | POST `/workspaces/{id}/members/create` | `{email,password,full_name,role}` | `WorkspaceMemberResponse` | A / user (Pro) | `c/dashboard/SettingsView.tsx:120` |
| `updateMemberRole` :605 | PATCH `/workspaces/{id}/members/{mid}` | `{role}` | `WorkspaceMemberResponse` | A / user | **DEAD** |
| `removeMember` :609 | DELETE `/workspaces/{id}/members/{mid}` | — | `void` (server sends `{message}`) | A / user | **DEAD** |

Five of eight workspace methods are unused: the UI can list members and create one, but cannot invite, re-role, or remove.

### 1.4 Projects, clips, ingest — `clipApi` (`api.ts:614`)

| Function | Method + path | Request | Response | Wrapper / auth | Callers |
|---|---|---|---|---|---|
| `listProjects` :615 | GET `/clips/projects` | — | `{projects: BackendProject[], total}` | A / user | `c/dashboard/DashboardApp.tsx:265` |
| `fetchYoutubeMetadata` :616 | POST `/clips/youtube/metadata` | `{url}` | `YouTubeMetadataResponse` | A / user | `c/dashboard/UploadModal.tsx:118` |
| `fetchFormats` :620 | POST `/clips/formats` | `{url}` | `AvailableFormatsResponse` | A / user | **DEAD** |
| `saveEditorSettings` :625 | PUT `/clips/item/{clipId}/editor-settings` | `ClipEditorSettings` | `ClipEditorSettings` | E / user | `c/dashboard/VideoEditorStudio.tsx:375` |
| `downloadYoutube` :630 | POST `/clips/download` | `{url, format_id?}` | `Record<string, any>` | A / user | `c/dashboard/UploadModal.tsx:243` |
| `exportProject` :634 | POST `/pipeline/export/{projectId}` | built inline from `ExportProjectOptions` | `SocialExportResponse` | A / user | `c/dashboard/VideoEditorStudio.tsx:576`, `c/dashboard/ClipGeneratorView.tsx:111`, `lib/utils/clipExport.ts:29` |
| `subscribeDownloadProgress` :674 | GET `/clips/progress/{projectId}` every 500 ms | — | `DownloadProgress` | F / user | `c/dashboard/UploadModal.tsx:282`, internal `api.ts:944` |
| `listClips` :733 | GET `/clips/{projectId}` | — | `ClipListResponse` | A / user | `c/dashboard/DashboardApp.tsx:397` |
| `deleteProject` :734 | DELETE `/clips/projects/{projectId}` | — | `void` (204) | A / user | `c/dashboard/DashboardApp.tsx:580` |

Related non-API exports: `mapBackendClip` (`api.ts:428`, used by `DashboardApp.tsx`) converts `BackendClip` to the view model `ViralClip` and builds caption segments; `startPipelineWhenReady` (`api.ts:923`) is **DEAD** (UploadModal re-implements it inline at `UploadModal.tsx:280-300`).

### 1.5 Audio — `audioApi` (`api.ts:750`)

| Function | Method + path | Request | Response | Wrapper / auth | Callers |
|---|---|---|---|---|---|
| `process` :751 | POST `/audio/process` | `AudioProcessRequest` (camelCase) | `AudioProcessingResult` (camelCase) | A / user (daily limit) | `c/dashboard/AudioEnhancerPanel.tsx:66` |
| `preview` :756 | POST `/audio/preview` | `AudioPreviewRequest` (camelCase) | `AudioProcessingResult` | A / user | `c/dashboard/AudioEnhancerPanel.tsx:95` |
| `getPresets` :761 | GET `/audio/presets` | — | `{zones: AudioPresetZone[]}` | A / user | **DEAD** |

Both live calls are broken — see 2.2.

### 1.6 Pipeline — `pipelineApi` (`api.ts:850`)

| Function | Method + path | Request | Response | Wrapper / auth | Callers |
|---|---|---|---|---|---|
| `start` :851 | POST `/pipeline/start/{projectId}` | `{steps, audio_config, output_aspect_ratios?, clip_settings?}` | `{project_id,status,selected_steps,credits_deducted}` | A / user | `c/dashboard/UploadModal.tsx:347`, internal `api.ts:954` |
| `subscribeProgress` :867 | GET `/pipeline/progress/{projectId}` (SSE) | — | stream of `PipelineProgressEvent` | SSE / user | `hooks/usePipelineProgress.ts:89` |
| `getStatus` :880 | GET `/pipeline/status/{projectId}` | — | `PipelineStatus` | A / user | `c/dashboard/DashboardApp.tsx:469`, `:491`; `c/dashboard/UploadModal.tsx:358`; `hooks/usePipelineProgress.ts:57` |
| `getStatusBatch` :886 | POST `/pipeline/status/batch` | `{project_ids}` | `{statuses: Record<id, PipelineStatus>}` | A / user | `c/dashboard/DashboardApp.tsx:347` |
| `cancel` :891 | POST `/pipeline/cancel/{projectId}` | — | `{project_id,status}` | A / user | `c/dashboard/DashboardApp.tsx:500`, `:575` |
| `revertStep` :895 | POST `/pipeline/revert/{projectId}/{step}` | — | `{project_id,step,status}` | A / user | `c/dashboard/DashboardApp.tsx:490`, `:848` |
| `resume` :899 | POST `/pipeline/resume/{projectId}` | `{steps, audio_config, output_aspect_ratios?}` | same as `start` | A / user | `c/dashboard/DashboardApp.tsx:856` |

`DEFAULT_PIPELINE_STEPS` (`api.ts:765`) is exported but only used inside `api.ts`; `UploadModal.tsx:~325-340` keeps its own copy of the list.

### 1.7 Hook transitions and brand kit

| Function | Method + path | Request | Response | Wrapper / auth | Callers |
|---|---|---|---|---|---|
| `hookTransitionApi.getCatalog` :980 | GET `/hook-transitions/catalog` | — | `HookTransitionCatalog` | A / user | `hooks/useHookTransitionCatalog.ts:13` |
| `hookTransitionApi.resolveForClip` :982 | POST `/hook-transitions/clips/{clipId}/resolve` | `HookTransitionConfig` | `HookTransitionResolveResponse` | A / user | `c/dashboard/HookTransitionPanel.tsx:75` |
| `brandKitApi.getMe` :990 | GET `/brand-kits/me` | — | `BrandKit` | A / user | `c/dashboard/DashboardHomeView.tsx:115`, `c/dashboard/BrandKitView.tsx:82` |
| `brandKitApi.list` :991 | GET `/brand-kits` | — | `BrandKit[]` | A / user | `c/dashboard/VideoEditorStudio.tsx:207` |
| `brandKitApi.create` :992 | POST `/brand-kits` | `CreateBrandKitPayload` | `BrandKit` | A / user (Pro) | `c/dashboard/BrandKitView.tsx:107` |
| `brandKitApi.delete` :997 | DELETE `/brand-kits/{id}` | — | `void` (204) | A / user | **DEAD** |

### 1.8 Billing — `subscriptionApi` (`api.ts:1146`), `paymentsApi` (`api.ts:1221`)

| Function | Method + path | Request | Response | Wrapper / auth | Callers |
|---|---|---|---|---|---|
| `subscriptionApi.getPlans` :1147 | GET `/subscription/plans` | — | `PlansResponse` | A / user | `c/payments/CreditPacksCard.tsx:20`, `c/dashboard/PlanSelectionModal.tsx:46` |
| `subscriptionApi.getPublicPlans` :1149 | GET `/subscription/plans` | — | `PlansResponse` | F / pub | `c/landing/PricingSection.tsx:20` |
| `subscriptionApi.getEntitlements` :1156 | GET `/subscription/entitlements` | — | `EntitlementsResponse` | A / user | `c/dashboard/EntitlementsProvider.tsx:45` |
| `subscriptionApi.getMyTransactions` :1157 | GET `/subscription/transactions` | — | `PaymentTransactionResponse[]` | A / user | **DEAD** |
| `subscriptionApi.getCreditLedger` :1158 | GET `/subscription/ledger?limit=` | — | `CreditLedgerResponse[]` | A / user | **DEAD** |
| `paymentsApi.getCheckout` :1222 | GET `/payments/qr?plan_slug&plan_type` | query | `UpiCheckoutResponse` | A / user | `c/dashboard/PaymentModal.tsx:57` |
| `paymentsApi.getCreditPackCheckout` :1224 | GET `/payments/credit-packs/{slug}/qr` | — | `UpiCheckoutResponse` | A / user | `c/dashboard/PaymentModal.tsx:57` |
| `paymentsApi.submitCreditPack` :1226 | POST `/payments/credit-packs` | multipart: `credit_pack, utr_number, screenshot` | `PaymentResponse` | A / user | `c/dashboard/PaymentModal.tsx:89` |
| `paymentsApi.submit` :1233 | POST `/payments` | multipart: `plan_slug, plan_type, utr_number, screenshot` | `PaymentResponse` | A / user | `c/dashboard/PaymentModal.tsx:91` |
| `paymentsApi.getMine` :1241 | GET `/payments/my` | — | `PaymentResponse[]` | A / user | `c/payments/MyPaymentsCard.tsx:16` |

`getPlans` and `getPublicPlans` hit the same public route; the authed variant only adds a token the server ignores.

### 1.9 Analytics and usage

| Function | Method + path | Response | Wrapper / auth | Callers |
|---|---|---|---|---|
| `analyticsApi.getDashboardStats` :1447 | GET `/analytics/dashboard` | `DashboardStatsResponse` | A / user | `c/dashboard/DashboardHomeView.tsx:107` |
| `usageApi.getProjectUsage` :1531 | GET `/usage/projects/{projectId}` | `ProjectUsage` | E / user | **DEAD** |

### 1.10 Social publishing — `socialApi` (`api.ts:1663`)

| Function | Method + path | Request | Response | Wrapper / auth | Callers |
|---|---|---|---|---|---|
| `getConnections` :1664 | GET `/social/connections` | — | `SocialConnectionsResponse` | E / user | `c/dashboard/DashboardHomeView.tsx:139`, `c/social/PublishComposer.tsx:85`, `c/social/ConnectedPlatformsPanel.tsx:34`, `:275` |
| `startConnect` :1665 | POST `/social/oauth/{platform}/start` | — | `ConnectStartResponse` | E / user | `c/social/ConnectedPlatformsPanel.tsx:49` |
| `completeConnect` :1667 | POST `/social/oauth/{platform}/callback` | `ConnectCallbackRequest` | `ConnectedAccountResponse` | E / user | `app/dashboard/connect/[platform]/page.tsx:39` |
| `disconnectPreview` :1672 | GET `/social/accounts/{id}/disconnect-preview` | — | `DisconnectPreviewResponse` | E / user | `c/social/ConnectedPlatformsPanel.tsx:60` |
| `disconnect` :1674 | DELETE `/social/accounts/{id}` | — | `DisconnectPreviewResponse` | E / user | `c/social/ConnectedPlatformsPanel.tsx:73` |
| `getTikTokCreatorInfo` :1676 | GET `/social/accounts/{id}/tiktok-creator-info` | — | `TikTokCreatorInfoResponse` | E / user | `c/social/PublishComposer.tsx:107` |
| `createPosts` :1678 | POST `/social/posts` | `CreateSocialPostsRequest` | `SocialPostListResponse` | E / user | `c/social/PublishComposer.tsx:127` |
| `listPosts` :1680 | GET `/social/posts?limit&status=…` | query | `SocialPostListResponse` | E / user | `c/dashboard/SocialSchedulerView.tsx:156`, `c/dashboard/DashboardHomeView.tsx:127` |
| `cancelPost` :1685 | POST `/social/posts/{id}/cancel` | — | `SocialPostResponse` | E / user | `c/social/ScheduledPostsQueue.tsx:33` |
| `getDataDeletionStatus` :1698 | GET `/social/webhooks/data-deletion/{code}` | — | `DataDeletionStatusResponse` | F / pub | `app/data-deletion/page.tsx` |

### 1.11 Notifications and feature flags

| Function | Method + path | Response | Wrapper / auth | Callers |
|---|---|---|---|---|
| `notificationsApi.list` :1759 | GET `/notifications?limit=30` | `InAppNotificationListResponse` | E / user | `hooks/useNotificationInbox.ts:72` |
| `notificationsApi.markAllRead` :1760 | POST `/notifications/read-all` | `InAppNotificationListResponse` | E / user | `hooks/useNotificationInbox.ts:114` |
| `notificationsApi.clear` :1761 | DELETE `/notifications` | `InAppNotificationListResponse` | E / user | `hooks/useNotificationInbox.ts:125` |
| `notificationsApi.subscribe` :1763 | GET `/notifications/stream` (SSE) | stream of `InAppNotificationResponse` | SSE / user | `hooks/useNotificationInbox.ts:82` |
| `featuresApi.get` :1768 | GET `/features` | `FeatureFlagsResponse` | E / user | `hooks/useFeatureFlags.ts:29` |

### 1.12 Upload — `uploadApi` (`api.ts:1917`)

| Function | Method + path | Request | Response | Wrapper / auth | Callers |
|---|---|---|---|---|---|
| `initVideo` :1918 | POST `/uploads/video/init` | `VideoUploadInitRequest` | `VideoUploadInitResponse` | E / user | internal only (`api.ts:1934`) |
| `completeVideo` :1920 | POST `/uploads/video/{projectId}/complete` | `VideoUploadCompleteRequest` | `VideoUploadCompleteResponse` | E / user | internal only (`api.ts:1965`) |
| `abortVideo` :1925 | POST `/uploads/video/{projectId}/abort` | `VideoUploadAbortRequest` | `null` | E / user | internal only (`api.ts:1967`) |
| `uploadVideo` :1932 | orchestrates init, S3 part PUTs, complete | `File`, `VideoUploadOptions` | project id | — | `c/dashboard/UploadModal.tsx:196` |

### 1.13 B-roll — `brollApi` (`api.ts:2068`)

| Function | Method + path | Request | Response | Wrapper / auth | Callers |
|---|---|---|---|---|---|
| `getClip` :2069 | GET `/broll/clips/{clipId}` | — | `ClipBrollResponse` | E / user | `c/dashboard/ClipBrollPanel.tsx:96`, `:104` |
| `updatePlacement` :2070 | POST `/broll/clips/{clipId}/placements/{index}` | `BrollPlacementUpdate` | `ClipBrollResponse` | E / user | `c/dashboard/ClipBrollPanel.tsx:122` |
| `search` :2075 | GET `/broll/search?q&min_duration` | query | `BrollPreview[]` | E / user | `c/dashboard/ClipBrollPanel.tsx:40` |
| `generatePlacement` :2078 | POST `/broll/clips/{clipId}/placements/{index}/generate` | `{shot}` | `ClipBrollResponse` | E / user (Pro) | `c/dashboard/ClipBrollPanel.tsx:112` |

### 1.14 Reels from images — `reelsApi` (`api.ts:2179`)

| Function | Method + path | Request | Response | Wrapper / auth | Callers |
|---|---|---|---|---|---|
| `create` :2180 | POST `/reels` | `ReelCreateRequest` | `ReelResponse` | E / user | `c/dashboard/ReelsView.tsx:76` |
| `list` :2181 | GET `/reels` | — | `ReelSummary[]` | E / user | `c/dashboard/ReelsView.tsx:420` |
| `get` :2182 | GET `/reels/{id}` | — | `ReelResponse` | E / user | `c/dashboard/ReelsView.tsx:284` |
| `initAssets` :2183 | POST `/reels/{id}/assets/init` | `{files}` | `{uploads}` | E / user | internal only |
| `completeAssets` :2185 | POST `/reels/{id}/assets/complete` | `{keys}` | `ReelResponse` | E / user | internal only |
| `plan` :2187 | POST `/reels/{id}/plan` | `{}` | `ReelResponse` | E / user | `c/dashboard/ReelsView.tsx:85`, `:346` |
| `updateScene` :2188 | POST `/reels/{id}/scenes/{index}` | `ReelSceneUpdate` | `ReelResponse` | E / user | `c/dashboard/ReelsView.tsx:388` |
| `render` :2190 | POST `/reels/{id}/render` | `{}` | `ReelResponse` | E / user | `c/dashboard/ReelsView.tsx:339` |
| `generateScene` :2191 | POST `/reels/{id}/scenes/{index}/generate` | `{shot}` | `ReelResponse` | E / user (Pro) | `c/dashboard/ReelsView.tsx:389` |
| `uploadAssets` :2195 | init, direct S3 PUT per file, complete | `File[]` | `ReelResponse` | — | `c/dashboard/ReelsView.tsx:84` |

### 1.15 Channel intro — `creatorIntroApi` (`api.ts:2262`)

| Function | Method + path | Request | Response | Wrapper / auth | Callers |
|---|---|---|---|---|---|
| `get` :2264 | GET `/creator-intro` | — | `CreatorIntro \| null` | E / user | `c/dashboard/VideoEditorStudio.tsx:521`, `c/dashboard/ChannelIntroNudge.tsx:31`, `c/dashboard/ChannelIntroPanel.tsx:91` |
| `save` :2265 | PUT `/creator-intro` | `CreatorIntroSaveRequest` | `CreatorIntro` | E / user (Pro) | `c/dashboard/ChannelIntroPanel.tsx:152`, `:167` |
| `render` :2267 | POST `/creator-intro/render` | `{}` | `CreatorIntro` | E / user (Pro) | `c/dashboard/ChannelIntroPanel.tsx:154` |
| `uploadAvatar` :2270 | POST `/creator-intro/avatar`, then S3 PUT | `{content_type,size_bytes}` | key string | E / user (Pro) | `c/dashboard/ChannelIntroPanel.tsx:151` |

### 1.16 Reels from raw footage — `editsApi` (`api.ts:2497`)

| Function | Method + path | Request | Response | Wrapper / auth | Callers |
|---|---|---|---|---|---|
| `limits` :2498 | GET `/edits/limits` | — | `EditLimitsResponse` | E / user | `c/dashboard/FootageReelBoard.tsx:109`, `c/dashboard/FootageReelForm.tsx:74` |
| `create` :2499 | POST `/edits` | `EditCreateRequest` | `EditResponse` | E / user | `c/dashboard/FootageReelForm.tsx:103` |
| `list` :2500 | GET `/edits` | — | `EditSummary[]` | E / user | `c/dashboard/ReelsView.tsx:421`, `c/dashboard/editor/EditorView.tsx:46` |
| `get` :2501 | GET `/edits/{id}` | — | `EditResponse` | E / user | `c/dashboard/FootageReelBoard.tsx:96` |
| `initSources` :2502 | POST `/edits/{id}/sources/init` | `{files}` | `{uploads}` | E / user | internal only |
| `completeSources` :2504 | POST `/edits/{id}/sources/complete` | `{keys}` | `EditResponse` | E / user | internal only |
| `analyze` :2506 | POST `/edits/{id}/analyze` | `{}` | `EditResponse` | E / user | `c/dashboard/FootageReelBoard.tsx:175`, `c/dashboard/FootageReelForm.tsx:116` |
| `replan` :2507 | POST `/edits/{id}/plan` | `{}` | `EditResponse` | E / user | `c/dashboard/FootageReelBoard.tsx:325` |
| `change` :2508 | POST `/edits/{id}/changes` | `{changes}` | `EditResponse` | E / user | `c/dashboard/FootageReelBoard.tsx:125` |
| `chat` :2510 | POST `/edits/{id}/chat` | `{message}` | `EditResponse` | E / user | `c/dashboard/FootageReelBoard.tsx:307` |
| `render` :2511 | POST `/edits/{id}/render` | `{}` | `EditResponse` | E / user | `c/dashboard/FootageReelBoard.tsx:168` |
| `uploadSources` :2514 | init, XHR PUT per file, complete | files + durations | `EditResponse` | — | `c/dashboard/FootageReelForm.tsx:115` |

### 1.17 Editor (Timeline v1) — `editorApi` (`api.ts:2585`)

| Function | Method + path | Request | Response | Wrapper / auth | Callers |
|---|---|---|---|---|---|
| `create` :2586 | POST `/editor/projects` | `EditorProjectCreate` | `EditorProjectResponse` | E / user | `c/dashboard/editor/EditorView.tsx:69` |
| `openReel` :2588 | POST `/editor/projects/from-reel/{editId}` | `{}` | `EditorProjectResponse` | E / user | `c/dashboard/editor/EditorView.tsx:114` |
| `list` :2589 | GET `/editor/projects` | — | `EditorProjectSummary[]` | E / user | `c/dashboard/editor/EditorView.tsx:44` |
| `get` :2590 | GET `/editor/projects/{id}` | — | `EditorProjectResponse` | E / user | `c/dashboard/editor/EditorView.tsx:158` |
| `applyOps` :2591 | POST `/editor/projects/{id}/ops` | `EditorOpsRequest` | `EditorOpsResponse` | E / user | `c/dashboard/editor/EditorView.tsx:182` |

### 1.18 Admin

| Function | Method + path | Request | Response | Wrapper | Callers |
|---|---|---|---|---|---|
| `adminPaymentsApi.list` :1252 | GET `/admin/payments?status&q&limit&offset` | query | `AdminPaymentResponse[]` | A | `c/payments/AdminPaymentsView.tsx:42` |
| `adminPaymentsApi.get` :1254 | GET `/admin/payments/{id}` | — | `AdminPaymentResponse` | A | `c/payments/AdminPaymentsView.tsx:103` |
| `adminPaymentsApi.approve` :1255 | PATCH `/admin/payments/{id}/approve` | — | `AdminPaymentResponse` | A | `c/payments/AdminPaymentsView.tsx:97` |
| `adminPaymentsApi.reject` :1257 | PATCH `/admin/payments/{id}/reject` | `{reason}` | `AdminPaymentResponse` | A | `c/payments/AdminPaymentsView.tsx:245` |
| `adminCreditsApi.topup` :1286 | POST `/subscription/topup` | `CreditTopupRequest` | `AdminCreditTopupResponse` | A | `c/admin/AdminCreditsView.tsx:67` |
| `adminCreditsApi.list` :1291 | GET `/subscription/topups?q&limit&offset` | query | `AdminCreditTopupResponse[]` | A | `c/admin/AdminCreditsView.tsx:38` |
| `adminUsersApi.list` :1428 | GET `/admin/users?q&limit&offset&sort` | query | `AdminUserResponse[]` | A | `c/admin/AdminUsersView.tsx:66` |
| `adminUsersApi.getDetail` :1429 | GET `/admin/users/{id}/detail` | — | `AdminUserDetailResponse` | E | `c/admin/AdminUserDetailView.tsx:98` |
| `adminUsersApi.setPlan` :1430 | PATCH `/admin/users/{id}/plan` | `AdminUserPlanRequest` | `AdminUserResponse` | A | `c/admin/AdminUsersView.tsx:92` |
| `adminUsersApi.getOverview` :1435 | GET `/admin/overview` | — | `AdminOverviewResponse` | A | `c/admin/AdminOverviewView.tsx:92` |
| `adminUsersApi.getGrowth` :1436 | GET `/admin/growth?days` | query | `AdminGrowthResponse` | E | `c/admin/AdminOverviewView.tsx:101` |
| `adminUsageApi.getSummary` :1535 | GET `/admin/usage?days` | query | `AdminUsageSummary` | E | `c/admin/AdminUsageView.tsx:25` |
| `adminUsageApi.getClipQuality` :1536 | GET `/admin/clip-quality?days` | query | `ClipQualityReport` | E | `c/admin/AdminUsageView.tsx:30` |
| `adminFeaturesApi.list` :1772 | GET `/admin/features` | — | `AdminFeatureFlagListResponse` | E | `c/admin/FeatureSwitches.tsx:12` |
| `adminFeaturesApi.set` :1773 | PATCH `/admin/features/{key}` | `{enabled}` | `AdminFeatureFlagListResponse` | E | `c/admin/FeatureSwitches.tsx:18` |
| `adminSocialApi.getOverview` :1823 | GET `/admin/social/overview?days` | query | `AdminSocialOverviewResponse` | E | `c/admin/AdminSocialView.tsx:33` |
| `adminSocialApi.listAccounts` :1824 | GET `/admin/social/accounts?q&limit&offset` | query | `AdminSocialAccountListResponse` | E | `c/admin/AdminSocialView.tsx:28` |
| `adminSocialApi.forceDisconnect` :1826 | POST `/admin/social/accounts/{id}/disconnect` | — | `DisconnectPreviewResponse` | E | `c/admin/AdminSocialView.tsx:42` |
| `adminBrollApi.listAssets` :2024 | GET `/admin/broll/assets?q&status&limit&offset` | query | `BrollAssetListResponse` | E | `c/admin/AdminBrollView.tsx:80` |
| `adminBrollApi.setStatus` :2026 | POST `/admin/broll/assets/{id}/status` | `BrollStatusRequest` | `BrollAssetResponse` | E | `c/admin/AdminBrollView.tsx:98` |
| `adminBrollApi.ingest` :2031 | POST `/admin/broll/ingest` | `BrollIngestRequest` | `BrollIngestResponse` | E | `c/admin/AdminBrollView.tsx:109` |
| `adminMusicApi.list` :2544 | GET `/admin/music` | — | `MusicTrackResponse[]` | E | **DEAD** |
| `adminMusicApi.add` :2546 | POST `/admin/music` | multipart `FormData` | `MusicTrackResponse` | E | **DEAD** |
| `adminMusicApi.setStatus` :2547 | POST `/admin/music/{id}/status` | `{status}` | `MusicTrackResponse` | E | **DEAD** |

All admin calls are auth = admin (router-level `get_current_admin`, 403 otherwise). The music library has a complete client and backend but no admin page (`app/admin/` has no `music` route).

### 1.19 Network calls outside `lib/api.ts`

| Location | Call | Notes |
|---|---|---|
| `hooks/useDownloadProgress.ts:28` | GET `/clips/progress/{projectId}` via raw `fetch`, every 500 ms | Duplicates `clipApi.subscribeDownloadProgress`. The hook has zero callers. |
| `lib/googleAuth.ts:33` | `window.location.assign` to `accounts.google.com/o/oauth2/v2/auth` | Browser redirect, not a fetch. |
| `lib/api.ts:1887`, `:2202`, `:2275`, `:2530` | PUT to presigned S3 URLs | Three different implementations (see 3.7). |

No component under `app/` or `components/` calls `fetch` directly; all backend traffic goes through `lib/api.ts`.

### 1.20 Dead API surface (zero callers)

`authApi.login`, `authApi.register`, `authApi.forgotPassword`, `authApi.resetPassword`, `workspaceApi.create`, `workspaceApi.get`, `workspaceApi.inviteMember`, `workspaceApi.updateMemberRole`, `workspaceApi.removeMember`, `clipApi.fetchFormats`, `audioApi.getPresets`, `brandKitApi.delete`, `subscriptionApi.getMyTransactions`, `subscriptionApi.getCreditLedger`, `usageApi.getProjectUsage`, `adminMusicApi.list`, `adminMusicApi.add`, `adminMusicApi.setStatus`, `startPipelineWhenReady`, plus the payload types that only they use (`LoginPayload`, `RegisterPayload`, `ForgotPayload`, `ResetPayload`, `FormatInfo`, `AvailableFormatsResponse`, `PaymentTransactionResponse`, `PlanResponse`, `CreditLedgerResponse`, `StepUsage`, `ProjectUsage`, `MusicTrackResponse`).

---

## 2. Contract check

### 2.1 Route existence

Every one of the 133 API methods in the 29 `*Api` objects, plus `getDataDeletionStatus` and the dead hook's raw fetch, maps to a registered backend route with the same method and path (routers enumerated from `backend/main.py:78-112` and every `backend/**/route.py`). There are **no frontend calls to a missing route** and no method mismatches.

### 2.2 Mismatches (field names, types, shapes)

| # | Sev | Call | Frontend | Backend | Effect |
|---|---|---|---|---|---|
| C1 | **P0** | `audioApi.process` | sends `{audioUrl, config}` (`api.ts:152`, `:751`); caller passes `audioUrl: ''` (`c/dashboard/AudioEnhancerPanel.tsx:67`) | `AudioEnhanceRequest.audio_url` is required (`backend/audio/enhancement/schema.py:6`) | Always 422. Because 422 bodies have no `message` (see C3) the panel shows "Something went wrong". The route's `check_limit("audio_enhancements")` dependency (`backend/audio/enhancement/route.py:14`) is resolved in the same pass as the body, so a failed call may still use up one of the Free plan's 3 daily enhancements — not verified at runtime. |
| C2 | **P0** | `audioApi.preview` and both responses | sends `{frequencyHz, durationSeconds}`; reads `processedUrl`, `processingTimeSeconds`, `sampleRate`, `durationSeconds`, `appliedSettings` (`api.ts:136-161`) | `frequency_hz`, `duration_seconds`; responds `processed_url`, `processing_time_seconds`, `sample_rate`, `duration_seconds`, `applied_settings` (`schema.py:16-35`) | Request fields are ignored (defaults 440 Hz / 3 s are used), and every response field the UI reads is `undefined`. The preview never plays. |
| C3 | **P1** | every call | error text comes from `body.message` (`api.ts:172`, `:547`) | Only `CustomException`, `TimeoutError` and unhandled `Exception` have handlers (`backend/main.py:115-139`). Pydantic `RequestValidationError` (422) and Starlette `HTTPException` use FastAPI's default `{"detail": …}` | Any validation failure surfaces as the literal string "Something went wrong". |
| C4 | P2 | `clipApi.listProjects` | typed `BackendProject.clips: BackendClip[]` (40 fields) (`api.ts:262-271`) | each clip is a 10-key summary: `id,title,score,duration_seconds,start_time,end_time,content_category,status,poster_url,created_at` (`backend/clip/service.py:98-111`) | `mapBackendClip` runs on rows with no `scores`, `transcript`, `project_id`, URLs. It survives only because every access is optional-chained. `DashboardApp.tsx:354-358` has a workaround comment for exactly this. |
| C5 | P2 | `clipApi.listClips`, `listProjects`, `pipelineApi.*` (except export), `/clips/progress`, `/analytics/dashboard`, `/audio/presets` | hand-written TS types | routes have no `response_model`; `pipeline/start`, `resume`, `status/batch` take `body: dict` (`backend/pipeline/route.py:17`, `:33`, `:49`) | No schema on either side to check against. `BackendClip.captions`, `edit_spans`, `editor_settings`, `created_at` are not in `GeneratedClipResponse` (`backend/clip_generation/schema.py:127-158`) at all. Breaks the project rule "define request/response schemas in schema.py — always". |
| C6 | P2 | `clipApi.downloadYoutube` | returns `Record<string, any>`; caller types the result `any` (`UploadModal.tsx:243`) | `VideoMetadataResponse` (`backend/clip/schema.py:30`) | A typed response exists and is thrown away. |
| C7 | P2 | `clipApi.exportProject` `custom_config` (`api.ts:652-671`) | forwards 18 `CaptionConfig` fields | the burner also reads `stroke_width`, `stroke_color`, `italic`, `upcoming_color`, `hide_upcoming`, `rows`, `second_line_color`, `second_line_scale`, `active_scale`, `glow` (`backend/subtitle_styling/ass_generator.py:576-642`) | Those ten `CaptionConfig` fields are never sent, so the export always uses the preset's values for them even if the editor's config differs. Needs a product check: does the editor let users change any of them? |
| C8 | P2 | `clipApi.exportProject` | hardcodes `platforms: ['tiktok']` (`api.ts:640`) | default `["tiktok","instagram_reels"]` | Every export is a "tiktok" render regardless of where it will be posted. |
| C9 | P3 | `ClipEditorSettings.caption_config` | camelCase `CaptionConfig` (`types.ts:200`) | `Optional[dict[str, Any]]`, "stored as sent" (`backend/clip_generation/schema.py:296`) | A camelCase blob inside a snake_case API; untyped server side. |
| C10 | P3 | `PipelineStatus` (`types.ts:426`) | `current_step`, `is_completed`, `error` required | `_not_started()` returns only `{project_id,status,steps}` (`backend/pipeline/service.py:1590`) | Required fields are `undefined` for projects with no run. |
| C11 | P3 | `BrandKit` (`types.ts:369`) | no `userId` | `BrandKitResponse.userId` (`backend/brand_kit/schema.py:26`) | Extra field ignored. This is the only camelCase response in the API. |
| C12 | P3 | `Workspace.role` (`types.ts:365`) | `'owner' \| 'editor' \| 'viewer'` | assignable roles are `'member' \| 'viewer'` (`backend/workspace/schema.py:10`) | `DashboardApp.tsx:274` casts with `as`; `'editor'` never occurs, `'member'` is not in the type. |
| C13 | P3 | `UserProfile.plan` (`types.ts:353`) | `'free' \| 'pro' \| 'pro_plus'` | `str` | Narrower than the wire type. |
| C14 | P3 | `ReelResponse.status`, `EditSummary.status`, `BrollAssetResponse.status` | string-literal unions | plain `str` | Frontend is stricter than the schema guarantees. |
| C15 | P3 | `FeatureFlagsResponse.flags` | `Record<FeatureFlagKey, boolean>` (13 literal keys, `api.ts:1705`) | `Dict[str, bool]` from the registry (`backend/feature_flags/registry.py`) | In sync today (13 = 13), but the union is hand-maintained in two frontend places (`api.ts:1705`, `hooks/useFeatureFlags.ts:8`). |
| C16 | P3 | `authApi.logout`, `workspaceApi.removeMember` | typed `void` | return `{message}` | Harmless. |
| C17 | P3 | `backend/edit_engine/schema.py:3` | — | docstring says the types are mirrored in `frontend/lib/types.ts` | They are in `lib/api.ts`. Documentation drift. |

### 2.3 Envelope consistency

The project rule is "API response format must always be `{data, message, error}`". Reality:

| Returns bare object (uses `authedRequest`) | Returns envelope (uses `envelopeRequest`) |
|---|---|
| `/auth/*`, `GET /me`, `/workspaces/*`, `/clips/*` (except editor-settings), `/pipeline/*`, `/audio/*`, `/hook-transitions/*`, `/brand-kits/*`, `/subscription/*`, `/payments/*`, `/admin/payments/*`, `/admin/users` (list, plan), `/admin/overview`, `/analytics/dashboard` | `/me/email-preferences`, `/me/delete`, `/email/unsubscribe`, `/clips/item/{id}/editor-settings`, `/features`, `/admin/features`, `/notifications`, `/social/*`, `/admin/social/*`, `/uploads/*`, `/broll/*`, `/admin/broll/*`, `/reels/*`, `/creator-intro/*`, `/edits/*`, `/admin/music/*`, `/editor/*`, `/usage/*`, `/admin/usage`, `/admin/clip-quality`, `/admin/users/{id}/detail`, `/admin/growth` |

Error bodies are never enveloped: `CustomException.to_dict()` returns `{error, message, …extra}` with no `data` key (`backend/core/exceptions.py:14`). The split even runs through single routers (`/admin/users` list is bare, `/admin/users/{id}/detail` is enveloped; `GET /me` is bare, `PUT /me/email-preferences` is enveloped).

### 2.4 Backend routes with no frontend caller

| Route | Notes |
|---|---|
| `POST /clips/youtube` | Creates a project from metadata only; superseded by `/clips/download`. |
| `GET /clips/item/{clip_id}` | Single clip fetch — the client always loads the whole project's clips. |
| `POST /clips/item/{clip_id}/burn` | Single-clip burn; exports go through `/pipeline/export`. |
| `GET /pipeline/social-platforms` | Unauthenticated platform list. |
| `GET /subscription/me`, `POST /subscription/activate-free` | Credits summary and free activation; the client uses `/subscription/entitlements` instead. |
| `GET/POST /subtitle-styles/*` (4 routes) | Whole router unused; styles come from the generated TS file. |
| `/depth-captions/*` (6 routes) | Whole feature has no client code at all, although `depth_captions` is a plan feature shown in pricing. |
| `/transcription/*` (2), `/audio/extraction/*` (2) | Standalone tools, no client. |
| `POST /social/webhooks/meta/*`, `/social/webhooks/tiktok` | Platform callbacks, correctly not called by the app. |
| Routes whose client method exists but is dead | see 1.20 (`/clips/formats`, `/audio/presets`, `/subscription/transactions`, `/subscription/ledger`, `/usage/projects/{id}`, `/admin/music/*`, five workspace routes, `DELETE /brand-kits/{id}`, password auth routes). |

---

## 3. The fetch client

### 3.1 Base URL

`const API_BASE = process.env.NEXT_PUBLIC_API_URL` (`api.ts:21`), concatenated as `${API_BASE}/api/v1${path}`. No fallback and no check: if the variable is unset, requests go to the literal path `undefined/api/v1/...` on the Next origin. `hooks/useDownloadProgress.ts:27` reads the env var a second time rather than importing the constant. `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (`lib/googleAuth.ts:18`) is required for sign-in but is missing from `env.local.example`.

### 3.2 Three wrappers

| Wrapper | Line | Method | Auth | Unwraps envelope | Fires upgrade event | Clears token on 401 |
|---|---|---|---|---|---|---|
| `request<T>(path, body)` | `api.ts:163` | always POST | none | no | no | no |
| `authedRequest<T>(path, options)` | `api.ts:524` | any | bearer | no | yes | yes |
| `envelopeRequest<T>(path, options)` | `api.ts:1459` | any | bearer | yes (`body.data as T`) | yes | yes |

Plus `subscribeEvents` (SSE), `clipApi.subscribeDownloadProgress` (its own fetch loop), `subscriptionApi.getPublicPlans` and `getDataDeletionStatus` (bare `fetch`), and three S3 uploaders. There are effectively **eight** places that build a request by hand.

`envelopeRequest` is declared at line 1459 but used from line 582; this only works because function declarations hoist. The file has no internal ordering.

### 3.3 Auth token storage and refresh

`lib/auth.ts` (53 lines):

- Keys: `localStorage['token']` (the JWT) and `localStorage['token_expires_at']` (epoch ms, computed client-side from `expires_in`).
- `getToken()` (`auth.ts:45`) returns null and clears storage once the client-side expiry passes or is NaN.
- `setAuth` is called from `authApi.login` / `oauthLogin` (`api.ts:564`, `:569`).
- **No refresh**: there is no refresh token, no refresh endpoint, no silent renewal. The JWT lives `ACCESS_TOKEN_EXPIRE_MINUTES = 60*24*7` (7 days, `backend/core/config.py:34`), then the user is signed out mid-session.
- **No revocation**: `AuthService.logout` only writes a log line (`backend/auth/service.py:185`). A copied token stays valid for the rest of its 7 days.
- **Logout bypasses the helper**: `DashboardApp.tsx:696` does `localStorage.removeItem('token')` directly and leaves `token_expires_at` behind, instead of calling `clearAuth()`.
- `isTokenExpired()` (`auth.ts:35`) and `getAuth()` (outside `auth.ts`) have no callers.
- No `middleware.ts`, no cookies, no server components reading auth. Route protection is client-side only: `DashboardApp.tsx:119` (`isAuthenticated()`), `AdminGate.tsx:14`, `LandingPageView.tsx:49`, `EditorLanding.tsx:64`. Protected pages therefore render a shell, then redirect.
- No cross-tab sync: nothing listens to the `storage` event, so signing out in one tab leaves the others running until their next request fails.

### 3.4 Error handling

`authedRequest` (`api.ts:524-559`):

1. No token: `clearAuth()` and throw `Error('Unauthorized: Your session has expired.')`.
2. `fetch` — a network failure throws the browser's raw `TypeError: Failed to fetch`, uncaught and unmapped.
3. Status 401: `clearAuth()`, throw `Error('Unauthorized: ' + message)`.
4. Body parsed with `res.json().catch(() => ({}))` — a non-JSON body (HTML error page, 204, proxy 502) silently becomes `{}`.
5. Not OK: if `body.error` is one of six plan codes, dispatch `window` event `clipnera:upgrade-required` with `{error, feature, message}`; then throw `Error(message ?? 'Something went wrong')`.

Consequences:

- Errors are plain `Error` objects carrying only a string. **Status code and error code are discarded.** Callers that need to branch do string matching: `err.message.startsWith('Unauthorized:')` (`DashboardApp.tsx:371`), `err.message.includes('No active pipeline')` (`DashboardApp.tsx:504`), `err.message === 'Session expired'` (`hooks/useNotificationInbox.ts:90`). The editor's `409 STALE_VERSION` and the pipeline's `409 VIDEO_NOT_READY` cannot be detected by code.
- `handleUnauthorized()` (`api.ts:23`) only clears storage. It does not redirect or notify. Exactly one call site in the app reacts to a 401 (`DashboardApp.tsx:371`); every other component shows an error string or nothing and the user stays on a dead page.
- 429 responses carry a `Retry-After` header (`backend/core/rate_limit.py:262`) that the client never reads. `LIMIT_REACHED` (daily quota, also 429) opens the upgrade modal; a rate-limit 429 shows only its message.
- `FEATURE_DISABLED` (403 when a flag is off) is not treated specially; the user sees the server's sentence.
- Successful `envelopeRequest` drops `body.message`, so server success messages ("Saved", "Account connected") are never shown.
- `request()` (public) never dispatches upgrade events and never touches the token.

### 3.5 Retries, timeouts, cancellation

| Concern | State |
|---|---|
| Retry | None in the wrappers. Only S3 part uploads retry (3 attempts, 1 s / 2 s backoff, `api.ts:1905-1915`) and `DashboardApp.tsx:383-405` retries clip loading 3 times. |
| Timeout | None. No `AbortSignal.timeout`, no per-request deadline. A hung request hangs its spinner forever. |
| Cancellation | `authedRequest` accepts `RequestInit` so a `signal` could be passed, but **no caller ever passes one**. Only `subscribeEvents` (own `AbortController`) and `uploadApi.uploadVideo` (`options.signal`) can be aborted. Components guard against stale results with `let cancelled = false` flags; the requests themselves still complete. |
| Dedupe | None, except the two module-level promise caches (flags, hook transition catalogue). |
| Idempotency | Only `socialApi.createPosts` (`idempotency_key`, `api.ts:1636`). Payments, pipeline start, renders and AI shots can be double-submitted by a double click unless the component disables the button. |

### 3.6 Streaming

`subscribeEvents<T>(path, onEvent, onError)` (`api.ts:789-836`) implements SSE over `fetch` + `ReadableStream`, because `EventSource` cannot send an `Authorization` header.

- Splits the buffer on `\n\n` only (a proxy that rewrites to `\r\n\r\n` would break it), takes the **first** `data:` line of each block, ignores `event:`, `id:` and `retry:`, and silently drops unparsable JSON.
- `onEvent` returning `false` aborts the stream.
- Stream end is reported as `Error('Stream closed')` through `onError`; reconnection is the caller's job.
- No `Last-Event-ID`, so nothing is replayed after a reconnect.
- The token is read once at connect; a token that expires mid-stream is only noticed on reconnect.

Used by: `pipelineApi.subscribeProgress` (server emits one snapshot per second until a terminal status, `backend/pipeline/service.py:1789-1798`) and `notificationsApi.subscribe` (server pushes `event: notification` blocks plus `: keepalive` comments, `backend/notifications/service.py:53-61`).

No WebSocket anywhere.

### 3.7 Uploads

| Flow | Function | Mechanism | Chunked | Progress | Retry | Abort | Resumable |
|---|---|---|---|---|---|---|---|
| Source video | `uploadApi.uploadVideo` (`api.ts:1932`) | S3 multipart: API signs all part URLs up front, browser PUTs parts with XHR, 4 in parallel, then `complete`; on failure calls `abort` | yes (`part_size` from server) | yes, byte-accurate, capped at 99% until `complete` returns | 3 attempts per part | yes (`AbortSignal`) | **no** — part URLs and ETags live in memory only; a reload or tab close loses the upload |
| Reel images / voiceover | `reelsApi.uploadAssets` (`api.ts:2195`) | single presigned PUT per file via `fetch`, all in parallel | no | none | none | no | no |
| Footage reel sources (up to 2 GB each, 40 files) | `editsApi.uploadSources` + `putWithProgress` (`api.ts:2514-2541`) | single presigned PUT per file via XHR, **all files in parallel, unbounded** | no | per-file fraction | none | no | no |
| Channel intro avatar | `creatorIntroApi.uploadAvatar` (`api.ts:2270`) | single presigned PUT via `fetch` | no | none | none | no | no |
| UPI screenshot, admin music | `FormData` through the API | multipart form to FastAPI | no | none | none | no | no |

Three separate "PUT a blob to S3" implementations. The footage-reel path sends multi-gigabyte files in one PUT with no retry — the worst fit for the largest files. `uploadVideo` also trusts `file.type` (cast with `as VideoContentType`), which is empty for some `.mkv`/`.mov` files on some platforms.

### 3.8 Polling inside the client

`clipApi.subscribeDownloadProgress` (`api.ts:674-732`) is a `while` loop with a 500 ms sleep: 2 requests per second per ingest, for as long as a YouTube download or upload post-processing takes. Any non-OK response or thrown error ends the loop permanently (one transient network blip stops progress tracking). It builds its own headers instead of using `authedRequest`.

---

## 4. State management and data fetching

### 4.1 Approach

There is no data-fetching or state library (`package.json` dependencies: next, react, react-dom, framer-motion, lucide-react, recharts, canvas-confetti, fontsource packages). The pattern everywhere is:

```
useEffect(() => { let cancelled = false; api.x().then(r => !cancelled && setState(r)); return () => { cancelled = true } }, [])
```

- **Server state lives in component `useState`.** `components/dashboard/DashboardApp.tsx` (1,021 lines) owns the user profile, workspaces, the full project list with clips, the active project, the selected clip, pipeline steps, notifications and every modal flag, and passes them down as props.
- **No cache**: navigating away and back refetches. Two components that need the same resource each fetch it (see 8, P2-4).
- **No invalidation model**: after a mutation each component decides by hand what to refetch — `refreshAccount()` bumps a `refreshKey` and refetches `/me` (`DashboardApp.tsx:708-716`); `AudioEnhancerPanel` calls `refreshPlan()`; most mutations rely on the mutation's own response.
- **No optimistic-update helper**: `useNotificationInbox.markAllRead` updates locally first and never rolls back on failure (`hooks/useNotificationInbox.ts:110-119`).
- **No loading/error convention**: each component invents its own `isLoading` / `error` state; many `catch {}` blocks swallow errors.
- **No SSR data**: every page is a client component fetching after mount, so first paint is always a spinner or an empty shell.

### 4.2 React context

| Context | Defined | Provider | Value | Consumers |
|---|---|---|---|---|
| `EntitlementsContext` | `hooks/useEntitlements.ts:94` | `c/dashboard/EntitlementsProvider.tsx` (mounted by the dashboard shell) | `{entitlements, isLoading, promptUpgrade, refresh}` | 20 components directly via `useEntitlements`, 10 via `usePlan` |

That is the only context in the app. There is no auth/user context, no project context, no flags context, no toast context.

### 4.3 Module-level caches

| Cache | Location | Holds | Lifetime | Invalidated by |
|---|---|---|---|---|
| Feature flags | `hooks/useFeatureFlags.ts:25` (`cached` promise) | `Record<FeatureFlagKey, boolean>` | until full page reload | `refresh()` from one hook instance; not cleared on logout |
| Hook transition catalogue | `hooks/useHookTransitionCatalog.ts:8-9` (`cached`, `inflight`) | `HookTransitionCatalog` | until full page reload | never |

Both survive sign-out and sign-in as a different user within the same tab, because client-side navigation does not reload the module.

### 4.4 Browser storage keys

| Storage | Key | Written by | Holds | Notes |
|---|---|---|---|---|
| localStorage | `token` | `lib/auth.ts:25` | JWT access token | Readable by any script on the origin. Also removed directly at `DashboardApp.tsx:696`. |
| localStorage | `token_expires_at` | `lib/auth.ts:26` | epoch ms | Left behind by the sign-out path. |
| localStorage | `clipnera.setupChecklistDismissed` | `c/dashboard/DashboardHomeView.tsx:57`, `:180` | `'1'` | Per browser, not per user. |
| localStorage | `clipnera.channelIntroNudge.dismissed` | `c/dashboard/ChannelIntroNudge.tsx:7`, `:42` | `'1'` | Per browser, not per user. |
| localStorage | `clipnera.projectsView` | `c/dashboard/ProjectFoldersView.tsx:70`, `:137` | grid/list view mode | |
| localStorage | `cookie_notice_dismissed` | `c/legal/LegalPage.tsx:21`, `c/legal/CookieNotice.tsx:27` | `'1'` | |
| sessionStorage | `google_oauth_state` | `lib/googleAuth.ts:22` | OAuth `state` nonce, single use | |
| sessionStorage | `google_accept_terms` | `lib/googleAuth.ts:23` | `'1'`/`'0'`, single use | |

Key naming is inconsistent (`token`, `cookie_notice_dismissed`, `clipnera.*`). No cookies are set by the frontend. No IndexedDB. UI-dismissal keys are not namespaced by user id, so a second account on the same browser inherits the first one's dismissals.

### 4.5 Polling and timers

| What | Where | Interval | Stops when |
|---|---|---|---|
| Download / upload-processing progress | `lib/api.ts:716` | 500 ms | status `done`/`error`, or any failure |
| Download progress (dead hook) | `hooks/useDownloadProgress.ts:74` | 500 ms | status `done`/`error` |
| Pipeline status (hook) | `hooks/usePipelineProgress.ts:125` | 3 s | **only on unmount** |
| Pipeline status (upload modal) | `c/dashboard/UploadModal.tsx:356` | 2 s | completed / error / exception |
| Pipeline status (active project) | `c/dashboard/DashboardApp.tsx:465-476` | 5 s (`setTimeout` chain) | run settles |
| Image reel status | `c/dashboard/ReelsView.tsx:292` | 2 s | (component-owned) |
| Footage reel status | `c/dashboard/FootageReelBoard.tsx:102` | 2.5 s | (component-owned) |
| Clip B-roll generation | `c/dashboard/ClipBrollPanel.tsx:103` | (component-owned) | (component-owned) |
| Channel intro render | `c/dashboard/ChannelIntroPanel.tsx:114` | (component-owned) | (component-owned) |
| Scheduled posts | `c/dashboard/SocialSchedulerView.tsx:167` | 15 s | unmount |
| Entitlements while a payment is pending | `c/dashboard/EntitlementsProvider.tsx:77` | 30 s | `has_pending_payment` false |

None of these pause when the tab is hidden. Only `EntitlementsProvider` listens to `visibilitychange` (to refetch on return).

### 4.6 How real-time progress works today

**YouTube download / upload processing**

1. `UploadModal` calls `clipApi.downloadYoutube` or `uploadApi.uploadVideo`, gets a project id.
2. It calls `clipApi.subscribeDownloadProgress` (500 ms polling of `/clips/progress/{id}`) until `done`.
3. Only then may `POST /pipeline/start/{id}` be called (the server rejects earlier calls with 409 `VIDEO_NOT_READY`). The handoff logic exists twice: dead in `startPipelineWhenReady` (`api.ts:923`) and live, inline, in `UploadModal.tsx:280-347`.

**Pipeline run** — up to four watchers on one run:

1. SSE `GET /pipeline/progress/{id}` via `usePipelineProgress` (server re-reads state and emits once a second).
2. `usePipelineProgress` also polls `GET /pipeline/status/{id}` every 3 s "as a fallback".
3. `UploadModal` polls the same endpoint every 2 s to append log lines.
4. `DashboardApp` polls it every 5 s for the active project.

All four update different pieces of component state; nothing reconciles them. On dashboard load, `POST /pipeline/status/batch` fetches every project's status in one request (a fix for a previous N-request waterfall, noted in comments at `api.ts:882-885`).

**Notifications**

`useNotificationInbox` opens the SSE stream and, on every (re)connect, loads `GET /notifications?limit=30` as the source of truth. Reconnect backoff doubles from 2 s to 60 s. New unread items fire `onArrive` once (deduped by id in a ref) for the snackbar. This is the best-built real-time path in the app and the only one with reconnection.

**Reels, footage reels, B-roll shots, channel intro**

Plain interval polling of the resource's `GET` until its `status` changes. No SSE, no shared polling helper — each component re-implements the loop.

**Plan changes**

`EntitlementsProvider` refetches on tab focus, on the `clipnera:upgrade-required` window event, when `refreshKey` changes, and every 30 s while a UPI payment awaits admin approval.

---

## 5. Hooks inventory

| Hook | Lines | Purpose | Inputs / outputs | Side effects | Callers | Problems | Decision |
|---|---|---|---|---|---|---|---|
| `usePrefersReducedMotion` | 20 | Tracks the OS reduced-motion setting. | none / `boolean` | `matchMedia` listener | `c/landing/LandingVideo.tsx` | Returns `false` on first render even when the user prefers reduced motion, so one frame of motion can start. Only the landing page uses it; the dashboard's framer-motion animations ignore the preference. | **KEEP** — make it the single motion gate for the whole app (or switch to framer-motion's `useReducedMotion`). |
| `useHookTransitionCatalog` | 43 | Loads the static transition catalogue once and shares it. | none / `{catalog, error}` | `GET /hook-transitions/catalog`, module-level cache | `c/dashboard/HookTransitionPanel.tsx` | Hand-rolled cache; never invalidated; survives user switch (harmless: static data). No `isLoading`. | **REBUILD** as a cached query with `staleTime: Infinity`. Logic is correct, mechanism should be the shared one. |
| `useFeatureFlags` | 56 | Admin on/off switches for dark-launched features. | none / `{flags, isLoading, refresh}` | `GET /features`, module-level promise cache | 11 components: `MobileTabBar`, `VideoEditorStudio`, `DashboardHomeView`, `CommandPalette`, `PlanSelectionModal`, `Sidebar`, `ReelsView`, `DashboardApp`, `ClipBrollPanel`, `UploadModal`, `ConnectedPlatformsPanel` | See section 7. Cache not cleared on logout; `refresh()` updates only the calling instance; a failed load returns all-off and silently hides features; flag list duplicated from `api.ts`. | **REBUILD** — keep the "all off until loaded" default, replace the rest. |
| `useEntitlements` (file also exports helpers) | 159 | Context accessor for the plan's capabilities, plus pure helpers (`canUseCaptionStyle`, `canUseAspectRatio`, `estimateVideoCredits`, `videoMinutesFor`, `isPaidPlan`, `isPaidPlanSlug`, `canUseFeature`, `planLabel`, `creditResetLabel`, `daysUntil`). | none / `{entitlements, isLoading, promptUpgrade, refresh}` | none (provider does the fetching) | 20 components + `usePlan` | `FREE_TIER_FALLBACK` is a hand copy of server rules and has drifted (`credit_minutes: 60` vs server 20, `hooks/useEntitlements.ts:29` vs `backend/subscription/entitlements.py:207`). The file mixes a context, a fallback constant and ten utilities. `estimateVideoCredits` re-implements server pricing. | **KEEP the model, REBUILD the plumbing** — server-driven capabilities are the right design. Move helpers to `lib/`, back the context with a cached query, generate or fetch the fallback. |
| `usePlan` | 77 | Friendlier facade over entitlements: `isPro`, `canUse(feature)`, `remainingToday(key)`, expiry, `promptUpgrade`. Also exports `FEATURE_LABELS`, `upgradeReasonFor`. | none / object | none | 10 components (plus `EntitlementsProvider`, which imports only `upgradeReasonFor`) | Overlaps `useEntitlements`; components import one, the other, or both (`VideoEditorStudio`, `DashboardHomeView`, `SettingsView`, `PlanBanner` use both). `RENEWAL_REMINDER_DAYS` exported, unused elsewhere. Returns new closures whenever entitlements change. | **REBUILD** — merge with `useEntitlements` into one access hook. |
| `useDownloadProgress` | 105 | Polls download progress every 500 ms. | none / `{progress, isPolling, start, stop, reset}` | raw `fetch`, `setInterval` | **none** | Dead. Duplicates `clipApi.subscribeDownloadProgress`. `start()` twice leaks the first interval; `setInterval` with an async body lets requests overlap; no `'use client'`; bypasses the API client (no 401 handling). | **DELETE**. |
| `useNotificationInbox` | 137 | Server notifications (SSE + list) merged with local session-only ones. | `(enabled, onArrive)` / `{notifications, pushLocal, markAllRead, clearAll}` | SSE stream, list fetch, timers | `c/dashboard/DashboardApp.tsx` | `timestamp` is a relative string computed once at mapping time and never refreshed ("Just now" stays forever). Own `timeAgo` duplicates `lib/utils/dates.formatRelativeTime`. `markAllRead` / `clearAll` are optimistic with no rollback. Server `kind` (7 values) is squashed into a 5-value legacy `type` (`social_expiring` becomes `scheduled_post`). Limit hardcoded at 30, no pagination. Stops reconnecting on "Session expired" but tells nobody. | **KEEP the design, REBUILD the edges** — reconnect and list-as-truth logic is sound; fix time handling, typing and error surfacing. |
| `usePipelineProgress` | 155 | Live pipeline progress for one project. | `(projectId, selectedSteps, initialCreditsDeducted)` / `{steps, progress, currentStep, creditsDeducted, isProcessing, error, refetchStatus}` | SSE + 3 s poll | `c/dashboard/PipelineProgressTracker.tsx` | (1) The poll never stops after completion or error. (2) No SSE reconnect — an error is only `console.error`'d. (3) Effect depends on the `selectedSteps` array identity; a caller passing a fresh array each render would tear down and reopen the stream every render (today's caller passes state, so it holds). (4) `selectedStepsKey` computed and unused (`:77`). (5) `refetchStatus` replaces `steps` with the server's list, which is `[]` before the run registers, wiping the placeholder steps. (6) An `idle` SSE event sets `isProcessing = true`. (7) No `'use client'`. (8) `sseUnsubRef` written, never read. | **REBUILD** — one subscription per run shared by every watcher. |

Hooks that do not exist and are re-implemented inline in components: current user/session, projects list, a generic "poll until status" helper, debounced autosave (`VideoEditorStudio.tsx:375-380`), upload with progress.

---

## 6. Types

### 6.1 Where types live

The project rule says frontend types go in `frontend/lib/types.ts` "or near the consuming code". In practice:

| File | Lines | Contents |
|---|---|---|
| `lib/types.ts` | 441 | **View-model** types (camelCase: `ViralClip`, `VideoProject`, `CaptionConfig`, `UserProfile`, `Workspace`, `BrandKit`, `AppNotification`) mixed with a few wire types (snake_case: `ClipEditorSettings`, `TranscriptEdits`, `HookTransition*`, `PipelineStep`, `PipelineStatus`, `PipelineProgressEvent`). |
| `lib/api.ts` | 2,593 | **174 exported interfaces/types** — nearly every wire type — interleaved with the functions that use them. |
| `lib/editor/timeline.ts` | 492 | Timeline v1 document and operation types (deliberately import-free so Node can test it). |
| `lib/utils/captionStyles.generated.ts` | 887 | `CaptionPreset`, `CaptionAnimation`, `CaptionStyle` (generated from the backend). |
| `lib/data/emojiCatalog.generated.ts` | 187 | `EmojiCatalogEntry`, `EmojiCategory` (generated). |

So `types.ts` is not the type home it is documented to be, and there is no separation between "what the server sends" and "what the UI renders".

### 6.2 `lib/types.ts` inventory

| Group | Types | Notes |
|---|---|---|
| Editor view model | `AspectRatio`, `LayoutMode`, `WordTimestamp`, `TranscriptSegment`, `CaptionConfig`, `AutoZoomConfig`, `AutoReframeConfig`, `SocialOptimization`, `ViralClip`, `BRollOverlay`, `SoundEffect` | `ViralClip` has 35 fields. `mapBackendClip` fills 12 of them with constants because the backend has no such data: `suggestedAspectRatio`, `suggestedLayout`, `layoutMode`, `keywords`, `emojiHighlights`, `autoBrollKeywords`, `bRollOverlays`, `soundEffects`, `autoZoom`, `autoReframe`, `socialOptimization`, `thumbnailTime` (`api.ts:458-485`). These are leftovers from a mock-data prototype. |
| Project view model | `VideoProject` | Carries prototype fields with no server source: `folderName`, `folderCategory`, `folderColor`, `genre`, `tags`, `syncStatus`, `offlineAvailable`, `audioOriginalUrl`, `audioProcessedUrl`, `audioReverted`, `transcript`. `DashboardApp.tsx:303-318` invents values for them. |
| Audio | `AudioEnhancementConfig`, `AudioProcessingResult`, `AudioPresetZone` | Last two are duplicated in `api.ts`. |
| Wire types | `TranscriptEdits`, `ClipEditorSettings`, `HookTransitionMode/Config/Applied/Part/Phrase/Preset/Catalog/ResolveResponse`, `DownloadProgress`, `PipelineStep`, `PipelineStatus`, `PipelineProgressEvent` | snake_case, mirror backend schemas. |
| Account | `UserProfile`, `Workspace`, `BrandKit`, `AppNotification` | camelCase view models; `UserProfile` drops `features`, `daily_limits`, `usage_today`, `plan_expires_at` from the wire type. |
| Navigation | `TabType` | Union of 10 tab ids. |
| Unused | `AnalyticsMetric`, `RetentionPoint` | No references anywhere. `RetentionPoint` has a field named `opusAiRetention` ("legacy alias"). |

### 6.3 Duplication

| Duplicate | Locations |
|---|---|
| `DownloadProgress` | `api.ts:127` and `types.ts:407` (identical; the hook imports one, the API the other) |
| `AudioProcessingResult` | `api.ts:136` and `types.ts:14` |
| `AudioPresetZone` | `api.ts:146` and `types.ts:24` |
| `AudioProcessRequest`, `AudioPreviewRequest` | declared **twice in the same file**: `api.ts:152-161` and `api.ts:739-748` (legal only because interfaces merge) |
| Aspect ratio union | `AspectRatio` (`types.ts:1`), `EditorAspect` (`api.ts:2553`), plain `string` in `ExportProjectOptions`, `PlanCapabilities.aspect_ratios` |
| Upload descriptor `{key,url,content_type}` | `ReelAssetUpload` (`api.ts:2117`), `CreatorIntroAvatarUpload` (`api.ts:2235`), `EditUpload` (`api.ts:2316`) |
| Image MIME lists | `REEL_IMAGE_TYPES`, `INTRO_AVATAR_TYPES`, `EDIT_IMAGE_TYPES` (`api.ts:2174`, `:2260`, `:2487`), `SCREENSHOT_TYPES` (`lib/utils/payments.ts:30`) |
| Audio MIME lists | `REEL_AUDIO_TYPES`, `EDIT_AUDIO_TYPES` |
| Pipeline step list | `DEFAULT_PIPELINE_STEPS` (`api.ts:765`) and an inline copy in `UploadModal.tsx` |
| Feature-flag key list | `FeatureFlagKey` (`api.ts:1705`) and `ALL_OFF` (`hooks/useFeatureFlags.ts:8`) |
| Relative-time formatter | `timeAgo` (`hooks/useNotificationInbox.ts:11`) and `formatRelativeTime` (`lib/utils/dates.ts:17`) |
| Duration formatter | `formatDuration` (`lib/utils/videoFile.ts:14`) and `formatSeconds` (`lib/utils/footageReels.ts:75`) |
| Media duration probe | `readVideoDuration` (`lib/utils/videoFile.ts:30`) and `mediaDuration` (`lib/utils/footageReels.ts:57`) |
| Date-time formatter | `formatDateTime` in `lib/utils/payments.ts:19` (a date helper living in the payments file) next to `lib/utils/dates.ts` |
| Server constants copied by hand | `AI_SHOT_CREDITS = 120` (`api.ts:2091`), `EDIT_BASE_CREDITS` / `EDIT_OUTPUT_SECONDS_PER_CREDIT` / `EDIT_OPUS_CREDIT_MULTIPLIER` (`lib/utils/footageReels.ts:5-7`), `EDIT_LOOKS`, `EDIT_MOODS` (`api.ts:2490-2495`), `FREE_TIER_FALLBACK` (`hooks/useEntitlements.ts:20`) — each will silently drift when the backend setting changes |

### 6.4 `any` usage in the slice

| Location | Use |
|---|---|
| `api.ts:142`, `types.ts:20` | `appliedSettings: Record<string, any>` |
| `api.ts:154`, `:160`, `:741`, `:747` | `config: Record<string, any>` (audio requests) |
| `api.ts:630` | `downloadYoutube` returns `Record<string, any>` |
| `api.ts:854`, `:902`, `:927` | `audioConfig: Record<string, any>` (pipeline start/resume) |
| `lib/utils/audioSynth.ts:8` | `(window as any).webkitAudioContext` |

Eleven occurrences, all in the audio and ingest area. Unsafe casts that matter more than the `any`s: `body.data as T` in `envelopeRequest` (a null `data` becomes a non-null `T`, `api.ts:1460`), `data as T` in both wrappers, `file.type as VideoContentType` / `ReelAssetType` / `EditSourceType` / `IntroAvatarType` (`api.ts:1936`, `:2198`, `:2273`, `:2522`), and the non-null assertions throughout `normaliseItem` (`lib/editor/timeline.ts:250-262`).

### 6.5 Good patterns worth keeping

- `captionStyles.generated.ts` and `emojiCatalog.generated.ts` are generated from the backend (`python -m subtitle_styling.export_styles`, `export_emoji_catalog`) — the only place the frontend/backend contract is machine-checked. The 21 caption styles, 13 animations and 28 legacy aliases all come from here.
- `lib/editor/timeline.ts` + `timeline.test.mts` run the backend's own fixture file (`backend/editor/fixtures/timeline_ops.json`) through the browser applier (`npm test`). This is the model for how every shared contract should work.
- `lib/utils/captionStyles.ts` mirrors named backend functions and says so in comments (`_active_colour`, `_row_split`).

### 6.6 Other `lib/` files

| File | Purpose | Notes |
|---|---|---|
| `lib/auth.ts` | Token storage. | See 3.3. |
| `lib/googleAuth.ts` | Starts Google OAuth, verifies `state`. | Sound: random state, single-use, sessionStorage. Throws if the client id env var is missing. |
| `lib/landingMedia.ts` + `.json` | Landing page stock clips (7 Pexels videos). | Posters hot-link the Pexels CDN. |
| `lib/data/mockProjects.ts` | Exports an empty `LANDING_SAMPLE_PROJECTS` and re-exports `CAPTION_PRESETS`. | **Dead file** — nothing imports it. |
| `lib/data/captionPresets.ts` | Derives picker rows from the generated styles. | Fine. |
| `lib/data/emojiCollections.ts` | 18 hand-written emoji "collections". | Unrelated to the generated catalogue the backend actually uses; `getAllEmojiCollectionIds` unused. Verify whether `emoji_collection` does anything server-side. |
| `lib/utils/captionStyles.ts` | Style lookup, legacy-id resolution, CSS for the caption preview. | `applyStyleToTranscript`, `getWordsForTimeRange`, `getActiveWordsAtTime`, `getCaptionPresetIds` have no callers. |
| `lib/utils/clipExport.ts` | Download helper and "export all as ZIP". | Applies the first clip's style to every clip. |
| `lib/utils/urlParser.ts` | YouTube id extraction (mirrors backend) plus `analyzeVideoSource`. | `inferSourceMeta` (`:65-174`) is prototype residue: it matches keywords like "hormozi", "huberman", "naval", "ai" and returns **hardcoded fake titles, channels, durations and Unsplash posters**. The substring test `lower.includes('ai')` matches any title containing those two letters ("training", "explained"). Its output is used for the optimistic project card in `UploadModal.tsx:207-230`. |
| `lib/utils/audioSynth.ts` | Web Audio sound effects for the editor preview. | Fine; self-contained. |
| `lib/utils/dates.ts`, `timezones.ts` | API date parsing and zone conversion. | `parseApiDate` exists because most endpoints send naive UTC timestamps while `/social/*` sends `Z`-suffixed ones (`backend/social/schema.py:15-21`). `DEFAULT_TIMEZONE = 'Asia/Kolkata'`. |
| `lib/utils/payments.ts` | INR formatting, UTR validation, plan comparison rows. | `comparisonRows` builds marketing copy from server capabilities (good). |
| `lib/utils/footageReels.ts` | Labels, credit estimate, media duration for footage reels. | Imports a type from `components/ui/StatusPill` — a `lib -> components` dependency, the wrong direction. |
| `lib/utils/videoFile.ts` | Byte/duration formatting, file duration probe. | Duplicated by `footageReels.ts`. |

---

## 7. Feature flags and entitlements

Two separate systems gate the UI. They do not know about each other.

### 7.1 Feature flags (admin switches)

**Backend** (`backend/feature_flags/`):

- Flags are declared in code in `registry.py` as `FlagDefinition(key, label, description, parent)`. An undeclared key raises, so typos fail loudly.
- One table, `feature_flags(key PK, enabled, updated_by, updated_at)` (`model.py`). No row means off.
- Evaluation (`service.py:18-26`): `effective = stored[key] AND stored[parent]`. Only the **direct** parent is checked: `broll_studio.reels.footage.opus_director` requires `…reels.footage` to be stored-on, but not `broll_studio` itself, so turning the top switch off does not turn grandchildren off.
- `GET /features` (any signed-in user) returns `{flags: {key: bool}}`. The `CurrentUserDep` is unused (`_`) — the answer is identical for every user.
- `GET /admin/features`, `PATCH /admin/features/{key}` for admins; every change records `updated_by`.
- Enforcement: `require_flag(key)` router dependency returns 403 `FEATURE_DISABLED` with `{feature}`. Applied to `/uploads`, `/reels`, `/broll`, `/edits`, `/editor`, and inside social connect/publish, AI shots and the pipeline's B-roll step. Each check is a fresh DB query; there is no server cache.

**Flags that exist (13):**

| Key | Parent | Gates |
|---|---|---|
| `social_publishing` | — | Connect and publish to social platforms |
| `social_publishing.youtube` / `.tiktok` / `.instagram` / `.x` | `social_publishing` | Per-platform connect and publish |
| `video_upload` | — | Uploading a file instead of a YouTube link |
| `broll_studio` | — | Master switch for B-roll features |
| `broll_studio.cutaways` | `broll_studio` | AI cutaways on clips |
| `broll_studio.reels` | `broll_studio` | Reels from images |
| `broll_studio.ai_shots` | `broll_studio` | Veo-generated shots (Pro) |
| `broll_studio.reels.footage` | `broll_studio.reels` | Reels from raw footage |
| `broll_studio.reels.footage.opus_director` | `broll_studio.reels.footage` | Opus planner for Pro footage reels |
| `agent_editor` | — | The multi-track editor |

**Frontend** (`hooks/useFeatureFlags.ts`):

1. First hook instance calls `featuresApi.get()` and stores the promise in a module variable.
2. Result is merged over an `ALL_OFF` constant; a failed request resolves to `ALL_OFF` and clears the cache so a later mount retries.
3. Every instance returns `{flags, isLoading, refresh}`; until loaded, everything reads as off (features never flash in).
4. Components read `flags['broll_studio.reels']` etc. and hide navigation or controls.

**What is missing for the revamp's requirements:**

| Requirement | Today |
|---|---|
| Per-user targeting | No. The user is ignored when evaluating. |
| Per-workspace targeting | No. No workspace concept in flags. |
| Per-plan targeting | No. Plan gating is a separate system (7.2). A feature that is both dark-launched and Pro-only needs two checks in two places, written by hand in each component. |
| Percentage rollout | No. Flags are boolean; no bucketing, no stable hash. |
| Kill switch | Server side, yes (an admin toggle takes effect on the next API call). **Client side, no**: flags are fetched once per page load, never polled, not pushed over the notification SSE. An open tab keeps showing a killed feature until reload and gets 403 `FEATURE_DISABLED` errors with no special handling. |
| Allow-list / beta cohort / staff-only | No. To test in production, an admin must turn the feature on for everyone. |
| Variants / remote config | No. Booleans only — numeric settings (credit prices, limits) live in server env or are copied into frontend constants. |
| Anonymous / pre-login flags | No. `/features` requires a token, so the landing page, pricing and sign-in cannot be flagged. |
| Default value | Always off; cannot ship default-on with a kill switch. |
| Environment scoping | None — one table per database. |
| Scheduled enable / expiry / stale-flag cleanup | None. |
| Exposure logging / audit history | Only last `updated_by`/`updated_at`; no history, no exposure events. |
| Type safety | Keys hand-copied in three places (`registry.py`, `api.ts:1705`, `useFeatureFlags.ts:8`). |
| Server cache | None; each guarded request queries the table. |
| Refresh after change | `refresh()` updates only the hook instance that called it; other mounted consumers keep the old state until they remount. |
| Reset on sign-out | Module cache persists across users in the same tab. |
| Loading vs off | `isLoading` is exposed but most consumers treat "loading" as "off", so flagged navigation items pop in after the request completes (layout shift in the sidebar and tab bar). |
| Failure visibility | A failed `/features` request is indistinguishable from "everything off". |

### 7.2 Entitlements (plan capabilities)

**Backend** (`backend/subscription/`):

- Plan rules are a frozen dataclass per plan slug in `entitlements.py:197-250`: `free`, `pro`, and a legacy `pro_plus` (no longer sold). Fields cover allowed aspect ratios, caption styles, max clips per video, watermark, upload length, monthly credits, daily limits per usage key, social limits and ten boolean features.
- `GET /subscription/entitlements` returns the caller's `EntitlementsResponse`: the plan's capabilities plus credit balance, purchased credits, period end, `plan_expires_at`, `usage_today`, `has_pending_payment`, `show_plan_notice`, and pricing constants (`credits_per_video_minute`, `extra_aspect_ratio_credit_share`).
- `GET /subscription/plans` (public) returns the same capability objects for every plan plus prices and credit packs, so pricing pages are data-driven.
- Enforcement: `require_feature(name)` gives 403 `PRO_REQUIRED`; `check_limit(key)` counts one use and gives 429 `LIMIT_REACHED`; other services raise `ASPECT_RATIO_NOT_ENTITLED`, `CAPTION_STYLE_NOT_ENTITLED`, `DURATION_NOT_ENTITLED`, `INSUFFICIENT_CREDITS`. Error bodies carry `feature`.
- `GET /me` repeats `plan`, `features`, `daily_limits`, `usage_today` and the credit balance — the same facts from a second endpoint.

**Frontend flow:**

1. `EntitlementsProvider` (`c/dashboard/EntitlementsProvider.tsx`) fetches entitlements when `isAuthed`; until then, and on any error, it serves `FREE_TIER_FALLBACK` (fail closed).
2. Refetch triggers: `refreshKey` prop change, tab becoming visible, every 30 s while `has_pending_payment`, and the `clipnera:upgrade-required` window event.
3. `authedRequest` dispatches that event whenever any response carries one of six plan error codes (`api.ts:496-503`, `:551-555`). The provider turns it into `onPromptUpgrade(reason)` using `upgradeReasonFor` (`hooks/usePlan.ts:34`) — so a refused request anywhere in the app opens the upsell modal with the right wording. This is a genuinely good mechanism.
4. Components read through `useEntitlements()` (raw object + helpers) or `usePlan()` (facade: `isPro`, `canUse`, `remainingToday`, `isExpiringSoon`, `promptUpgrade`).

**Plan features (10):** `remove_watermark`, `pro_ai`, `all_hook_transitions`, `brand_kit_edit`, `depth_captions`, `batch_processing`, `team_members`, `social_scheduling`, `custom_aspect_ratios`, `creator_intro`.
**Usage keys (6):** `exports`, `audio_enhancements`, `reel_renders`, `ai_shots`, `auto_edits`, `intro_renders`.

**Gaps:**

| Gap | Detail |
|---|---|
| Per-user, not per-workspace | Entitlements belong to the user. Workspaces exist (`/workspaces`, members with roles) but members do not inherit the owner's plan, and nothing in the client sends a workspace id with any request. `UserProfileResponse.active_workspace_id` is fetched and then unused; `DashboardApp.tsx:267` just takes `wsList[0]`. |
| No per-user overrides | An admin can grant Pro for N days (`PATCH /admin/users/{id}/plan`) or top up credits, but cannot grant a single capability or raise one limit. |
| Rules in code | Changing a limit requires a deploy; no admin UI for plan definitions. |
| Fallback drift | `FREE_TIER_FALLBACK.credit_minutes` is 60, the server says 20. The whole 48-line object must be edited by hand whenever the server's Free plan changes. |
| Loading is indistinguishable from Free | `isLoading` exists, but a Pro user sees locked controls and a watermark toggle forced on for the first request's duration. |
| Two hooks, two styles | `canUseFeature(entitlements, 'x')` vs `usePlan().canUse('x')` vs reading `entitlements.brand_kit_edit` directly; all three appear in the codebase. Features are exposed both as top-level booleans and inside `features{}`. |
| Flags and plans are not composed | No single "can this user see/use X, and if not, why" answer. Each component combines `flags[...]`, `canUse(...)`, `remainingToday(...)` and credit balance by hand. |
| Stale usage counters | `usage_today` only updates on the refetch triggers above; after an export the remaining-today number is stale unless the component remembers to call `refresh()` (only `AudioEnhancerPanel` does so explicitly). |
| Client-side price estimates | `estimateVideoCredits`, `estimateEditCredits`, `AI_SHOT_CREDITS` duplicate server pricing; the footage-reel constants are not in the entitlements payload at all. |
| Plan slug comparisons | `isPaidPlanSlug(plan) => plan !== 'free'` and `planLabel` special-case slugs; any future tier (team, enterprise, trial) needs code changes. |
| Admin role | `role: 'user' \| 'admin'` from `/me` is a third, separate gate (`AdminGate.tsx`), with no finer permissions. |

### 7.3 What a replacement must provide

One evaluated "access" answer per capability, computed on the server for a context of (user, workspace, plan, role), returning `{enabled, reason, limit, remaining, variant}`, cached on the client with a known TTL, pushed or re-polled on change, with deterministic percentage bucketing, allow/deny lists, a default value and a kill switch that overrides everything else. Today's two good ideas to preserve: fail-closed defaults, and the global "plan error opens the upsell" event.

---

## 8. Problems

Severity: **P0** broken for users now · **P1** serious risk or will block the revamp · **P2** should fix during the revamp · **P3** cleanup.

### 8.1 Bugs

| ID | Sev | Problem | Where |
|---|---|---|---|
| B1 | P0 | Audio enhance request uses camelCase against a snake_case schema and sends an empty URL; always 422. Possibly burns a daily quota unit per attempt (unverified). | `lib/api.ts:152-155`, `:751-755`; `c/dashboard/AudioEnhancerPanel.tsx:66-75`; `backend/audio/enhancement/schema.py:5-13` |
| B2 | P0 | Audio preview: request fields ignored, response fields all read as `undefined`. | `lib/api.ts:136-161`, `:756-760`; `AudioEnhancerPanel.tsx:95-110`; `backend/audio/enhancement/schema.py:16-35` |
| B3 | P1 | 422 and other non-`CustomException` errors lose their message ("Something went wrong"). | `lib/api.ts:172`, `:547`; `backend/main.py:115-139` |
| B4 | P1 | 401 clears the token but nothing redirects; only the initial dashboard load handles it. | `lib/api.ts:23-25`, `:541-550`; `DashboardApp.tsx:371` |
| B5 | P1 | Pipeline status poll in `usePipelineProgress` runs every 3 s until unmount, even after completion or failure. | `hooks/usePipelineProgress.ts:125-128` |
| B6 | P2 | Sign-out removes `token` directly and leaves `token_expires_at`; bypasses `clearAuth()`. | `DashboardApp.tsx:696` |
| B7 | P2 | `analyzeVideoSource` returns fabricated metadata (fake titles, channels, durations, stock posters) for keyword matches, including any title containing "ai". | `lib/utils/urlParser.ts:65-142` |
| B8 | P2 | Project list clips are typed as full `BackendClip` but are 10-field summaries. | `lib/api.ts:262-271`, `:615`; `backend/clip/service.py:98-111` |
| B9 | P2 | Download-progress loop stops for good on a single failed poll; the caller treats it as a failed ingest. | `lib/api.ts:704-720` |
| B10 | P2 | Notification timestamps are frozen relative strings. | `hooks/useNotificationInbox.ts:11-19`, `:37` |
| B11 | P2 | `refetchStatus` overwrites placeholder steps with `[]` when the run is not registered yet; an `idle` SSE event marks the run as processing. | `hooks/usePipelineProgress.ts:58`, `:114-116` |
| B12 | P2 | `envelopeRequest` returns `null` typed as `T` when `data` is absent. | `lib/api.ts:1459-1461` |
| B13 | P3 | `FREE_TIER_FALLBACK.credit_minutes` is 60; server Free plan is 20. | `hooks/useEntitlements.ts:29`; `backend/subscription/entitlements.py:207` |
| B14 | P3 | Flag parent check is one level deep; turning `broll_studio` off leaves `…reels.footage` effective if its direct parent row is on. | `backend/feature_flags/service.py:18-26` |
| B15 | P3 | `usePrefersReducedMotion` reports `false` on first render. | `hooks/usePrefersReducedMotion.ts:9` |
| B16 | P3 | `uploadVideo` progress can run backwards: a retried part resets its byte count to 0. | `lib/api.ts:1910`, `:1941` |
| B17 | P3 | `Workspace.role` type does not include `'member'`, the role the server actually assigns. | `lib/types.ts:365`; `DashboardApp.tsx:274` |

### 8.2 Races

| ID | Sev | Problem | Where |
|---|---|---|---|
| R1 | P1 | Up to four independent watchers of one pipeline run write overlapping state (SSE, 2 s, 3 s, 5 s polls). | `hooks/usePipelineProgress.ts:89`, `:125`; `UploadModal.tsx:356`; `DashboardApp.tsx:465` |
| R2 | P2 | `usePipelineProgress` effect depends on the `selectedSteps` array identity and on `initialCreditsDeducted`; a change in either tears down and reopens the SSE stream and resets all step state. | `hooks/usePipelineProgress.ts:140` |
| R3 | P2 | No request cancellation: responses to superseded requests are guarded only by per-component `cancelled` flags, and many handlers (search, autosave, polling ticks) have none. Last response wins. | `lib/api.ts:524` (no caller passes `signal`) |
| R4 | P2 | Feature-flag and catalogue caches survive a user switch in the same tab. | `hooks/useFeatureFlags.ts:25`; `hooks/useHookTransitionCatalog.ts:8` |
| R5 | P2 | `useFeatureFlags().refresh()` updates one instance; other consumers stay stale. | `hooks/useFeatureFlags.ts:53` |
| R6 | P2 | Optimistic notification mark-read / clear with no rollback on failure. | `hooks/useNotificationInbox.ts:110-129` |
| R7 | P3 | `setInterval` with async bodies allows overlapping requests when a response takes longer than the interval. | `hooks/useDownloadProgress.ts:74`; `UploadModal.tsx:356` |
| R8 | P3 | `EntitlementsProvider`'s `cancelled` flag does nothing (checked after `load()` has already set state). | `c/dashboard/EntitlementsProvider.tsx:56-65` |
| R9 | P3 | No cross-tab auth sync (`storage` event unused). | `lib/auth.ts` |

### 8.3 Missing error handling

| ID | Sev | Problem | Where |
|---|---|---|---|
| E1 | P1 | Errors are stringly typed: no status, no code, no `feature`, no `Retry-After`. Callers match on message text. | `lib/api.ts:546-557`; `DashboardApp.tsx:371`, `:504`; `hooks/useNotificationInbox.ts:90` |
| E2 | P1 | No timeout on any request. | `lib/api.ts:164`, `:531` |
| E3 | P2 | Network failures surface as the browser's "Failed to fetch". No offline handling. | `lib/api.ts:531` |
| E4 | P2 | Non-JSON bodies are swallowed into `{}`. | `lib/api.ts:170`, `:545` |
| E5 | P2 | Pipeline SSE errors are only logged; there is no reconnect and no user feedback. | `hooks/usePipelineProgress.ts:118-120` |
| E6 | P2 | `FEATURE_DISABLED` (flag turned off under an open tab) has no client handling. | `lib/api.ts:496-503` |
| E7 | P2 | Presigned-URL expiry mid-upload is not handled; all part URLs are signed once at init. | `lib/api.ts:1934-1961` |
| E8 | P2 | Editor `409 STALE_VERSION` cannot be detected by code. | `lib/api.ts:2575`, `:2591` |
| E9 | P3 | Many callers `catch {}` silently (entitlements, flags, profile refresh). | `EntitlementsProvider.tsx:47`; `hooks/useFeatureFlags.ts:32`; `DashboardApp.tsx:713` |
| E10 | P3 | `API_BASE` undefined is not detected. | `lib/api.ts:21` |

### 8.4 Waterfalls, over-fetching, duplicate requests

| ID | Sev | Problem | Where |
|---|---|---|---|
| W1 | P1 | 2 requests/second per ingest for download progress, for minutes. | `lib/api.ts:716` |
| W2 | P1 | Pipeline: 1 SSE stream (server polls its store each second) plus roughly 1 status request per second from the three client polls combined. | see R1 |
| W3 | P2 | Dashboard load waterfall: `getMe` + `workspaces` + `listProjects` in parallel, then `status/batch`, then `listClips` for the active project, then `status` polling; separately `/features`, `/subscription/entitlements`, `/notifications`, SSE connect, and on the home view `/analytics/dashboard`, `/brand-kits/me`, `/social/posts`, `/social/connections`. About 12 requests before the page settles, none cached. | `DashboardApp.tsx:256-400`; `DashboardHomeView.tsx:94-139` |
| W4 | P2 | Same resource fetched independently by several components: `GET /me` (3 sites, and `/me` overlaps `/subscription/entitlements`), `/social/connections` (4), `/creator-intro` (3), `/brand-kits/me` (2) plus `/brand-kits` (1), `/edits/limits` (2), `/edits` (2), `/subscription/plans` (3), `/social/posts` (2). | section 1 caller columns |
| W5 | P2 | `listProjects` returns every project with every clip summary, unpaginated; `listClips` returns full clips with transcripts and word-level captions, unpaginated. `mapBackendClip` rebuilds every transcript segment for every clip on every fetch. | `lib/api.ts:428-487`, `:615`, `:733` |
| W6 | P2 | Polling does not pause in hidden tabs. | section 4.5 |
| W7 | P3 | `notificationsApi.list` runs on every SSE reconnect (by design), including the first connect where the stream itself has nothing to replay. | `hooks/useNotificationInbox.ts:95` |
| W8 | P3 | Feature-flag guards hit the database on every guarded request. | `backend/feature_flags/service.py:33-38` |

### 8.5 Security

| ID | Sev | Problem | Where |
|---|---|---|---|
| S1 | P1 | 7-day bearer JWT in `localStorage`: any XSS on the origin can read and exfiltrate it. No httpOnly cookie, no refresh rotation. | `lib/auth.ts:25`; `backend/core/config.py:34` |
| S2 | P1 | Logout does not revoke the token server-side. | `backend/auth/service.py:185-186` |
| S3 | P2 | Route protection is client-only (no `middleware.ts`); admin page bundles are served to anyone, with the gate applied after mount. Data is still protected by the API. | `c/admin/AdminGate.tsx`; `DashboardApp.tsx:119` |
| S4 | P2 | `workspaceApi.createAndAddMember` sends a plaintext password chosen by the workspace owner for another person's account. | `lib/api.ts:601-604`; `c/dashboard/SettingsView.tsx:120` |
| S5 | P3 | Client-side expiry (`token_expires_at`) is derived from the local clock; a wrong clock signs the user out early or keeps a dead token. | `lib/auth.ts:24`, `:48` |
| S6 | P3 | Landing posters hot-link `images.pexels.com`, and fabricated posters hot-link `images.unsplash.com`; both leak visitor IPs to third parties and need CSP entries. | `lib/landingMedia.ts:21`; `lib/utils/urlParser.ts:80` |
| S7 | P3 | No idempotency keys on payment submission, pipeline start, renders or AI shots. | `lib/api.ts:1226-1240`, `:858`, `:2190`, `:2078` |

Positive notes: OAuth `state` is random, single-use and verified (`lib/googleAuth.ts:21-41`); OAuth callback URLs are stripped from history and served with `Referrer-Policy: no-referrer` (`next.config.mjs`); the bearer token is never put in a URL (SSE uses `fetch` headers rather than a query-string token); presigned S3 URLs keep large uploads off the API.

### 8.6 Structure and maintainability

| ID | Sev | Problem | Where |
|---|---|---|---|
| M1 | P1 | `lib/api.ts` is a 2,593-line file holding the client, 174 exported types, 29 API objects, view-model mapping (`mapBackendClip`, `buildTranscriptSegments`), an SSE implementation, three uploaders and business constants. | `lib/api.ts` |
| M2 | P1 | Two response conventions (bare and envelope) and two wrappers; the author of each call must know which one the route uses. | section 2.3 |
| M3 | P2 | Wire types are hand-mirrored from Pydantic ("Mirrors backend/…" comments in about 25 places); nothing checks them. Only caption styles, the emoji catalogue and timeline ops are verified. | `lib/api.ts` throughout |
| M4 | P2 | View model carries prototype fields the backend never fills (section 6.2), so components render placeholders as if they were data. | `lib/types.ts:144-187`, `:296-324`; `lib/api.ts:458-485` |
| M5 | P2 | Naming: project rule says "camel_case hooks/utilities"; files are camelCase (`useFeatureFlags.ts`, `captionStyles.ts`). The rule as written is self-contradictory and should be restated. Wire fields are snake_case, view models camelCase, one endpoint (`/brand-kits`) responds in camelCase. | repo-wide |
| M6 | P2 | Dead code: 18 API methods and `startPipelineWhenReady` (1.20), `hooks/useDownloadProgress.ts`, `lib/data/mockProjects.ts`, `isTokenExpired`, `getAllEmojiCollectionIds`, `emojiForSlug`, `emojiByCategory`, `EMOJI_CATEGORIES` (external use), `applyStyleToTranscript`, `getWordsForTimeRange`, `getActiveWordsAtTime`, `getCaptionPresetIds`, `AnalyticsMetric`, `RetentionPoint`, `RENEWAL_REMINDER_DAYS` (external use), `DEFAULT_PIPELINE_STEPS` (external use). | as listed |
| M7 | P3 | `lib` imports from `components` (`StatusTone`). | `lib/utils/footageReels.ts:2` |
| M8 | P3 | `'use client'` missing on `usePipelineProgress.ts` and `useDownloadProgress.ts` (works only because their importers are client components). | hooks |
| M9 | P3 | Leftover competitor naming in types (`opusAiRetention`). | `lib/types.ts:403` |
| M10 | P3 | No tests for the client, hooks or mappers; `npm test` covers only `lib/editor/timeline.ts`. | `package.json` scripts |

---

## 9. Implications for the revamp (data-layer view)

These are observations for the architecture wave, not decisions.

1. **One client.** A single request function that knows the base URL, token, envelope, typed errors (`status`, `code`, `feature`, `retryAfter`), timeouts and `AbortSignal`, with one place that reacts to 401 (redirect) and plan errors (upsell). The backend needs to finish moving to the envelope and add a 422 handler so the client can drop the dual wrappers.
2. **A server-state cache.** Almost every problem in 8.2 and 8.4 (duplicate fetches, no cancellation, manual invalidation, stale counters, per-component polling loops) is what a query cache with keys, dedupe, `staleTime`, refetch-on-focus and `refetchInterval` solves. A prompt-first UI where a chat turn mutates a project and several panels must update makes this a prerequisite, not a nicety.
3. **One live channel per job.** Pipeline, reel, footage-edit, intro and AI-shot progress should share one subscription primitive (SSE with reconnect, falling back to polling) that writes into the cache, instead of nine hand-written loops. `useNotificationInbox`'s reconnect-then-resync pattern is the one to generalise.
4. **Generated contracts.** The app already generates caption styles and the emoji catalogue and shares timeline fixtures. Extending that to an OpenAPI-derived types file would remove M3 and would have caught B1, B2, B8 and C7 at build time. It requires `response_model` on the untyped routes (2.2 C5) first.
5. **Wire types vs view models.** Split them, and cut `ViralClip` / `VideoProject` down to fields that have a source.
6. **Auth.** Decide between httpOnly cookie sessions (enables server components, middleware route protection, removes S1) and the current bearer model with refresh and revocation added. This is a backend change either way.
7. **Access control as one system.** Merge flags, plan capabilities, limits and role into a single evaluated-access payload (7.3) with a workspace dimension, and one hook. Keep fail-closed defaults and the global upgrade-required event.
8. **Uploads.** One uploader: multipart with bounded concurrency, retry, abort and (ideally) resume for every large-file path, especially footage reels.
9. **Delete before redesigning.** Removing the dead surface in M6 and the prototype residue in B7 / M4 shrinks what the new design has to account for.
