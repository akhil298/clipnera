export interface ServerEvent {
  event: string
  data: unknown
}

/**
 * Splits a text/event-stream into events as chunks arrive. Each event is lines of
 * "event: name" and "data: json", ended by a blank line (core/responses.py sse()).
 */
export class SseParser {
  private buffer = ''

  push(chunk: string): ServerEvent[] {
    this.buffer += chunk.replace(/\r\n/g, '\n')
    const events: ServerEvent[] = []
    let end: number
    while ((end = this.buffer.indexOf('\n\n')) >= 0) {
      const block = this.buffer.slice(0, end)
      this.buffer = this.buffer.slice(end + 2)
      const event = parseBlock(block)
      if (event) events.push(event)
    }
    return events
  }
}

function parseBlock(block: string): ServerEvent | null {
  let event = 'message'
  const data: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith(':')) continue
    const colon = line.indexOf(':')
    const field = colon < 0 ? line : line.slice(0, colon)
    const value = colon < 0 ? '' : line.slice(colon + 1).replace(/^ /, '')
    if (field === 'event') event = value
    else if (field === 'data') data.push(value)
  }
  if (!data.length) return null
  try {
    return { event, data: JSON.parse(data.join('\n')) }
  } catch {
    return { event, data: data.join('\n') }
  }
}

/** Reads a streamed response body, calling `onEvent` for each event in order. */
export async function readEvents(body: ReadableStream<Uint8Array>, onEvent: (event: ServerEvent) => void): Promise<void> {
  const parser = new SseParser()
  const decoder = new TextDecoder()
  const reader = body.getReader()
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    for (const event of parser.push(decoder.decode(value, { stream: true }))) onEvent(event)
  }
  for (const event of parser.push(`${decoder.decode()}\n\n`)) onEvent(event)
}
