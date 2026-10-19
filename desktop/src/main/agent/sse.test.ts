import { describe, expect, it } from 'vitest'
import { readEvents, SseParser } from './sse'

describe('SseParser', () => {
  it('reads events split across chunks', () => {
    const parser = new SseParser()
    expect(parser.push('event: text\ndata: {"te')).toEqual([])
    expect(parser.push('xt": "Hi"}\n\nevent: done\ndata: {"reason": "answered"}\n\n')).toEqual([
      { event: 'text', data: { text: 'Hi' } },
      { event: 'done', data: { reason: 'answered' } }
    ])
  })

  it('handles CRLF, comments and multi-line data', () => {
    const parser = new SseParser()
    expect(parser.push(': keep-alive\r\n\r\nevent: x\r\ndata: [1,\r\ndata: 2]\r\n\r\n')).toEqual([{ event: 'x', data: [1, 2] }])
  })

  it('reads a whole streamed body, including a last event without a blank line', async () => {
    const chunks = ['event: a\ndata: 1\n\n', 'event: b\ndata: 2']
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const c of chunks) controller.enqueue(new TextEncoder().encode(c))
        controller.close()
      }
    })
    const seen: unknown[] = []
    await readEvents(body, (e) => seen.push(e))
    expect(seen).toEqual([{ event: 'a', data: 1 }, { event: 'b', data: 2 }])
  })
})
