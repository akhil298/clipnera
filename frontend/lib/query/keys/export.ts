/** Query keys for exports. One file per domain in lib/query/keys/; see docs/revamp/wave6/01-platform-api.md. */
export const exportKeys = {
  all: ['export'] as const,
  /** NEEDS-BACKEND: EB-24 `GET /jobs/{id}`; polled while the job works. */
  job: (jobId: string) => [...exportKeys.all, 'job', jobId] as const,
};
