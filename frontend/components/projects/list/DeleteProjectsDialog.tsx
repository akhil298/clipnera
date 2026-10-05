'use client';

import { Button, Dialog } from '@/components/ui';

import { plural, type ProjectView } from './projectState';

function copy(targets: readonly ProjectView[]) {
  const clips = targets.reduce((sum, view) => sum + view.clipCount, 0);
  const running = targets.some((view) => view.kind === 'running');
  const what =
    targets.length === 1
      ? `${targets[0].project.title}${clips > 0 ? ` and its ${plural(clips, 'clip')}` : ''}`
      : `These ${targets.length} projects${clips > 0 ? ` and their ${plural(clips, 'clip')}` : ''}`;
  return {
    title: targets.length === 1 ? 'Delete this project?' : `Delete ${targets.length} projects?`,
    description: [
      running ? 'Work still running is stopped first.' : '',
      `${what} ${targets.length === 1 ? 'is' : 'are'} deleted for good.`,
      'Clips already posted to YouTube or Instagram stay posted.',
    ]
      .filter(Boolean)
      .join(' '),
  };
}

/** Confirmation for deleting one or more projects; Keep is focused (screens/01 §8). */
export function DeleteProjectsDialog({
  targets,
  deleting,
  onConfirm,
  onClose,
}: {
  targets: readonly ProjectView[];
  deleting: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const open = targets.length > 0;
  const { title, description } = open ? copy(targets) : { title: '', description: '' };
  const noun = targets.length === 1 ? 'project' : 'projects';
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => !next && !deleting && onClose()}
      role="alertdialog"
      size="sm"
      dismissible={!deleting}
      title={title}
      description={description}
      footer={
        <>
          <Button variant="secondary" data-autofocus disabled={deleting} onClick={onClose}>
            Keep {noun}
          </Button>
          <Button variant="danger" loading={deleting} loadingLabel="Deleting" onClick={onConfirm}>
            Delete {noun}
          </Button>
        </>
      }
    />
  );
}
