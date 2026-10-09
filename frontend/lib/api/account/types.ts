/**
 * Account and privacy contracts for Settings → Account. The profile itself is
 * `UserProfile` in `lib/api/me.ts` (shared with the app shell); import it from there.
 *
 * Not built yet (the dependent UI is hidden until they exist):
 * - NEEDS-BACKEND: `UserProfileResponse.created_at`, `.terms_accepted_at` (L-API-5: "Member since", "Age confirmed")
 * - NEEDS-BACKEND: GET /auth/sessions, DELETE /auth/sessions/{id}, POST /auth/sessions/revoke-others (L-API-6: "Where you're signed in")
 * - NEEDS-BACKEND: PATCH /me/preferences {use_uploads_in_ai} (L-API-7: the Privacy switch)
 * - NEEDS-BACKEND: language and region on the profile (no field exists, so none is shown)
 */

/** backend/user/schema.py DeleteAccountRequest (`POST /me/delete`). */
export interface DeleteAccountRequest {
  /** The account's email, typed by the user. The server compares it trimmed and case-insensitively. */
  confirm_email: string;
}
