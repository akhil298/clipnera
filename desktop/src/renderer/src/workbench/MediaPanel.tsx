import { runCommand } from '../commands'
import { MEDIA_COMMANDS } from '../../../shared/commands'
import type { MediaItem } from '../../../shared/media'
import { player } from '../player/player'
import { media } from '../state/media'
import { useStore } from '../state/store'
import { Icon } from './Icon'
import { Understanding } from './Understanding'

function duration(seconds: number): string {
  const s = Math.round(seconds)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const rest = String(s % 60).padStart(2, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${rest}` : `${m}:${rest}`
}

function details(item: MediaItem): string {
  const info = item.info
  if (!info) return ''
  const parts = [duration(info.durationSeconds)]
  if (info.width && info.height) parts.push(`${info.width}×${info.height}`)
  if (info.fps) parts.push(`${Math.round(info.fps * 100) / 100} fps`)
  if (!info.hasVideo) parts.push('audio')
  return parts.join(' · ')
}

function Status({ item }: { item: MediaItem }) {
  if (item.status === 'reading') return <span className="media-status">Reading…</span>
  if (item.status === 'failed') return <span className="media-status failed">{item.error}</span>
  if (item.status === 'preparing' && item.progress === 0) return <span className="media-status">Waiting to be prepared…</span>
  if (item.status === 'uploading')
    return (
      <span className="media-status">
        Adding to project {Math.round(item.progress * 100)}%
        <span className="progress"><span style={{ width: `${item.progress * 100}%` }} /></span>
      </span>
    )
  if (item.status === 'preparing')
    return (
      <span className="media-status">
        Preparing for editing {Math.round(item.progress * 100)}%
        <span className="progress"><span style={{ width: `${item.progress * 100}%` }} /></span>
      </span>
    )
  return null
}

function Row({ item, open }: { item: MediaItem; open: boolean }) {
  return (
    <li className={`media-item media-${item.status}${open ? ' media-open' : ''}`}>
      <button
        type="button"
        className="media-main"
        aria-label={`Open ${item.name}`}
        aria-current={open || undefined}
        disabled={item.status !== 'ready' && item.status !== 'uploading'}
        onClick={() => runCommand('player.open', { id: item.id })}
      >
        <div className="media-thumb">
          {item.thumbnail ? <img src={item.thumbnail} alt="" /> : <Icon name={item.kind === 'audio' ? 'music' : 'media'} size={18} />}
        </div>
        <div className="media-text">
          <span className="media-name" title={item.path}>{item.name}</span>
          <span className="muted">{details(item)}</span>
          <Status item={item} />
        </div>
      </button>
      <button type="button" className="media-add" aria-label={`Add ${item.name} to timeline`} title="Add to timeline" disabled={item.status !== 'ready'} onClick={() => runCommand('timeline.append', { mediaId: item.id })}>
        +
      </button>
      <button type="button" className="media-remove" aria-label={`Remove ${item.name}`} title="Remove from project" onClick={() => runCommand('media.remove', { id: item.id })}>
        ×
      </button>
      <Understanding item={item} />
    </li>
  )
}

export function MediaPanel() {
  const items = useStore(media, (s) => s.items)
  const openId = useStore(player.state, (s) => s.item?.id)
  return (
    <>
      <div className="panel-actions">
        <button type="button" className="secondary" onClick={() => runCommand(MEDIA_COMMANDS.import)}>Import… <kbd>⌘I</kbd></button>
      </div>
      {items.length === 0 ? (
        <p className="empty">Drop video or audio files anywhere on the window, or press ⌘I.</p>
      ) : (
        <ul className="media-list" aria-label="Media files">{items.map((item) => <Row key={item.id} item={item} open={item.id === openId} />)}</ul>
      )}
    </>
  )
}
