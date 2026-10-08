'use client';

import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { Badge, Button, InlineAlert, Skeleton, SkeletonGroup } from '@/components/ui';
import { isApiError } from '@/lib/api/errors';
import { getConnections, startConnect, type ConnectionsResponse, type SocialPlatform } from '@/lib/api/social';
import { socialKeys } from '@/lib/query/keys/social';

/** Only the platforms Clipnera claims (D3). */
const OFFERED: readonly SocialPlatform[] = ['youtube', 'instagram'];

interface Row {
  platform: SocialPlatform;
  label: string;
  /** Null when the Connect button is usable. */
  blocked: string | null;
  connectedAs: string | null;
}

function rowsFrom(data: ConnectionsResponse): Row[] {
  return OFFERED.flatMap((platform) => {
    const info = data.platforms.find((item) => item.platform === platform);
    if (!info) return [];
    const account = data.accounts.find((item) => item.platform === platform && item.status === 'active');
    const blocked = !info.available
      ? (info.pending_review_note ?? 'Not available yet')
      : !info.allowed_by_plan
        ? 'Not on your plan'
        : null;
    return [{ platform, label: info.label, blocked, connectedAs: account ? (account.handle ?? account.display_name ?? 'your account') : null }];
  });
}

/**
 * Connect a channel, optional. Connecting leaves for the platform and returns
 * to Settings; the welcome form is already saved by then, so nothing is lost.
 */
export function ConnectStep() {
  const connections = useQuery({ queryKey: socialKeys.connections(), queryFn: ({ signal }) => getConnections(signal), staleTime: 60_000 });
  const [opening, setOpening] = useState<SocialPlatform | null>(null);
  const [error, setError] = useState<string | null>(null);

  const connect = async (platform: SocialPlatform) => {
    setError(null);
    setOpening(platform);
    try {
      const { authorize_url } = await startConnect(platform);
      window.location.assign(authorize_url);
    } catch (err) {
      setOpening(null);
      setError(isApiError(err) && err.status === 429 ? 'That’s a lot of tries in an hour. Connect later from Settings.' : 'I couldn’t start the connection. Nothing was changed; you can connect later from Settings.');
    }
  };

  if (connections.isPending) {
    return (
      <SkeletonGroup label="Loading your channels" className="flex flex-col gap-2">
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-full" />
      </SkeletonGroup>
    );
  }

  if (connections.isError) {
    return (
      <InlineAlert
        tone="danger"
        action={
          <Button size="sm" variant="secondary" onClick={() => void connections.refetch()}>
            Try again
          </Button>
        }
      >
        I couldn’t load your channels. You can skip this and connect later in Settings.
      </InlineAlert>
    );
  }

  const rows = rowsFrom(connections.data);
  if (rows.length === 0) {
    return <p className="text-cn-body text-cn-fg-secondary">Publishing isn’t switched on yet. I’ll let you know when it is; nothing to do now.</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col divide-y divide-cn-border rounded-cn-lg border border-cn-border">
        {rows.map((row) => (
          <li key={row.platform} className="flex min-h-14 flex-wrap items-center gap-3 px-3 py-2">
            <div className="min-w-0 flex-1">
              <p className="text-cn-body font-medium text-cn-fg">{row.label}</p>
              {row.blocked && !row.connectedAs && <p className="text-cn-caption text-cn-fg-muted">{row.blocked}</p>}
            </div>
            {row.connectedAs ? (
              <Badge tone="success" dot>
                Connected as {row.connectedAs}
              </Badge>
            ) : (
              <Button
                size="sm"
                variant="secondary"
                disabled={row.blocked !== null || (opening !== null && opening !== row.platform)}
                loading={opening === row.platform}
                loadingLabel="Opening"
                aria-label={`Connect ${row.label}`}
                onClick={() => void connect(row.platform)}
              >
                Connect
              </Button>
            )}
          </li>
        ))}
      </ul>
      {error && (
        <p role="alert" className="text-cn-label text-cn-danger-text">
          {error}
        </p>
      )}
    </div>
  );
}
