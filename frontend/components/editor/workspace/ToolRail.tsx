'use client';

import { ToolRailItem } from '@/components/ui/ToolRailItem';
import { cx } from '@/lib/design/styles';

import { EDITOR_TOOLS, type EditorToolId } from './tools';

export interface ToolRailProps {
  /** The open tool, or null when the panel is closed. */
  active: EditorToolId | null;
  onToolClick: (tool: EditorToolId) => void;
  /** `rail`: the 48 px left column. `tab`: a sideways-scrolling row (phone Media tab). */
  layout?: 'rail' | 'tab';
}

export function ToolRail({ active, onToolClick, layout = 'rail' }: ToolRailProps) {
  return (
    <nav aria-label="Tools" className={cx('flex shrink-0 gap-1', layout === 'rail' ? 'w-12 flex-col items-center py-1' : 'overflow-x-auto px-2 py-1')}>
      {EDITOR_TOOLS.map((tool) => (
        <ToolRailItem
          key={tool.id}
          label={tool.label}
          icon={tool.icon}
          shortcut={tool.shortcut}
          layout={layout}
          active={active === tool.id}
          onClick={() => onToolClick(tool.id)}
        />
      ))}
    </nav>
  );
}
