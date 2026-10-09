'use client';

import { MessageSquare } from 'lucide-react';
import type { ReactNode } from 'react';

import { Drawer } from '@/components/ui/Drawer';
import { ResizablePanels } from '@/components/ui/ResizablePanels';
import { Tab, TabList, TabPanel, Tabs } from '@/components/ui/Tabs';
import { cx, focusRing } from '@/lib/design/styles';

import { ToolRail } from './ToolRail';
import { useElementSize } from './useElementSize';
import type { PhoneTab, WorkspaceLayout as LayoutState } from './useWorkspaceLayout';
import { conversationPx, MAIN_MIN, PANEL, pairBounds, PREVIEW_MIN, timelinePx } from './zoneSizes';
import { ZoneSurface } from './Zone';
import type { ConversationPlacement } from './zones/ConversationZone';
import type { PanelPlacement } from './zones/LeftPanelZone';
import type { PreviewPlacement } from './zones/PreviewZone';
import type { TimelinePlacement } from './zones/TimelineZone';

export interface WorkspaceLayoutProps {
  layout: LayoutState;
  /** Namespace for remembered sizes (`editor`, `clip`). */
  storageKey: string;
  topBar: ReactNode;
  /** Offline / reconnecting / viewing strips under the top bar. */
  strips?: ReactNode;
  renderPanel: (placement: PanelPlacement) => ReactNode;
  renderPreview: (placement: PreviewPlacement) => ReactNode;
  renderTimeline: (placement: TimelinePlacement) => ReactNode;
  /** Omit when there is no conversation zone (flag off, clip mode until EB-14). */
  renderConversation?: (placement: ConversationPlacement) => ReactNode;
  /** The phone's collapsed "Ask Clipnera" bar on the Timeline and Media tabs. */
  onAsk?: () => void;
}

/**
 * The editor's four zones at every width (07 §5.4, §5.7). Purely presentational: the zones come in
 * as render functions, so the editor and clip mode share it.
 */
export function WorkspaceLayout(props: WorkspaceLayoutProps) {
  const { layout, topBar, strips } = props;
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {topBar}
      {strips}
      {layout.arrangement === 'phone' ? <PhoneBody {...props} /> : <DesktopBody {...props} />}
    </div>
  );
}

/* ───────────── ≥ 768 ───────────── */

function DesktopBody(props: WorkspaceLayoutProps) {
  const { layout, storageKey, renderConversation } = props;
  const [ref, size] = useElementSize<HTMLDivElement>();
  const tablet = layout.arrangement === 'md';
  const side = !tablet && layout.conversationOpen && renderConversation;
  const main = <MainColumn {...props} />;
  const bounds = side && size.width > 0 ? pairBounds(size.width, conversationPx(layout.arrangement), MAIN_MIN) : null;
  const key = `${storageKey}:${layout.arrangement}:outer`;

  return (
    <div ref={ref} className="flex min-h-0 flex-1 p-0.5">
      {side ? (
        bounds && (
          <ResizablePanels
            key={key}
            storageKey={key}
            className="flex-1"
            panels={[
              { id: 'main', label: 'Editing area', ...bounds.partner, className: 'p-0.5', children: main },
              {
                id: 'conversation',
                label: 'Conversation',
                ...bounds.zone,
                className: 'p-0.5',
                children: <ZoneSurface label="Conversation">{renderConversation('side')}</ZoneSurface>,
              },
            ]}
          />
        )
      ) : (
        <div className="flex min-w-0 flex-1 p-0.5">{main}</div>
      )}
      {tablet && renderConversation && (
        <Drawer open={layout.conversationOpen} onOpenChange={layout.setConversationOpen} title="Conversation" side="right">
          {renderConversation('drawer')}
        </Drawer>
      )}
    </div>
  );
}

/** Rail (full height) beside the preview row over the timeline. */
function MainColumn(props: WorkspaceLayoutProps) {
  const { layout, storageKey, renderTimeline } = props;
  const [ref, size] = useElementSize<HTMLDivElement>();
  const bounds = size.height > 0 ? pairBounds(size.height, timelinePx(layout.arrangement, size.height), size.height / 2) : null;
  const key = `${storageKey}:${layout.arrangement}:timeline`;
  return (
    <div className="flex h-full min-h-0 min-w-0 flex-1">
      <ToolRail active={layout.panelOpen ? layout.tool : null} onToolClick={layout.toggleTool} />
      <div ref={ref} className="flex min-h-0 min-w-0 flex-1 flex-col">
        {bounds && (
          <ResizablePanels
            key={key}
            storageKey={key}
            direction="vertical"
            className="flex-1"
            panels={[
              { id: 'stage', label: 'Preview', ...bounds.partner, className: 'p-0.5', children: <PreviewRow {...props} /> },
              {
                id: 'timeline',
                label: 'Timeline',
                ...bounds.zone,
                className: 'p-0.5',
                children: <ZoneSurface label="Timeline">{renderTimeline(layout.arrangement === 'md' ? 'compact' : 'full')}</ZoneSurface>,
              },
            ]}
          />
        )}
      </div>
    </div>
  );
}

/** Panel + preview. The panel pushes the preview at ≥ 1280 and floats over it below that. */
function PreviewRow({ layout, storageKey, renderPanel, renderPreview, renderConversation }: WorkspaceLayoutProps) {
  const [ref, size] = useElementSize<HTMLDivElement>();
  const docked = layout.arrangement === 'wide' || layout.arrangement === 'xl';
  const panel = (placement: PanelPlacement) => <ZoneSurface label="Tool panel">{renderPanel(placement)}</ZoneSurface>;
  const preview = (
    <div className="flex h-full min-h-0 flex-col gap-1">
      <ZoneSurface label="Preview" tone="stage" className="flex-1">
        {renderPreview('stage')}
      </ZoneSurface>
      {layout.arrangement === 'md' && renderConversation && (
        <div className="shrink-0 rounded-cn-xl border border-cn-border bg-cn-surface-raised">{renderConversation('dock')}</div>
      )}
    </div>
  );
  const bounds = docked && layout.panelOpen && size.width > 0 ? pairBounds(size.width, PANEL, PREVIEW_MIN) : null;
  const key = `${storageKey}:${layout.arrangement}:panel`;

  return (
    <div ref={ref} className="relative flex h-full min-h-0 min-w-0">
      {docked && layout.panelOpen ? (
        bounds && (
          <ResizablePanels
            key={key}
            storageKey={key}
            className="flex-1"
            panels={[
              { id: 'panel', label: 'Tool panel', ...bounds.zone, className: 'pr-0.5', children: panel('docked') },
              { id: 'preview', label: 'Preview', ...bounds.partner, className: 'pl-0.5', children: preview },
            ]}
          />
        )
      ) : (
        <div className="min-w-0 flex-1">{preview}</div>
      )}
      {!docked && layout.panelOpen && <div className="absolute inset-y-0 left-0 z-cn-raised w-72 max-w-full rounded-cn-lg shadow-cn-2">{panel('overlay')}</div>}
    </div>
  );
}

/* ───────────── < 768 ───────────── */

function PhoneBody({ layout, renderPanel, renderPreview, renderTimeline, renderConversation, onAsk }: WorkspaceLayoutProps) {
  const tab: PhoneTab = !renderConversation && layout.phoneTab === 'chat' ? 'timeline' : layout.phoneTab;
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-1 p-1">
      <ZoneSurface label="Preview" tone="stage" className="aspect-video h-auto w-full shrink-0">
        {renderPreview('phone')}
      </ZoneSurface>
      <Tabs value={tab} defaultValue={tab} onValueChange={(value) => layout.setPhoneTab(value as PhoneTab)} className="flex min-h-0 flex-1 flex-col">
        <TabList label="Editor views" className="shrink-0 justify-around px-2">
          {renderConversation && <Tab value="chat">Chat</Tab>}
          <Tab value="timeline">Timeline</Tab>
          <Tab value="media">Media</Tab>
        </TabList>
        {renderConversation && (
          <TabPanel value="chat" className="flex min-h-0 flex-1 flex-col">
            {renderConversation('phone')}
          </TabPanel>
        )}
        <TabPanel value="timeline" className="flex min-h-0 flex-1 flex-col">
          {renderTimeline('strip')}
        </TabPanel>
        <TabPanel value="media" className="flex min-h-0 flex-1 flex-col">
          <ToolRail layout="tab" active={layout.tool} onToolClick={layout.openTool} />
          {renderPanel('tab')}
        </TabPanel>
      </Tabs>
      {renderConversation && tab !== 'chat' && onAsk && (
        <button
          type="button"
          onClick={onAsk}
          className={cx(
            'flex h-11 shrink-0 items-center gap-2 rounded-cn-xl border border-cn-border bg-cn-surface-raised px-3 text-left text-cn-body text-cn-fg-muted hover:bg-cn-surface-hover',
            focusRing,
          )}
        >
          <MessageSquare aria-hidden className="size-4" />
          Ask Clipnera
        </button>
      )}
    </div>
  );
}
