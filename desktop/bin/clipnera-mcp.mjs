#!/usr/bin/env node
// A stdio bridge to Clipnera Studio's MCP server, for agents that start a command (Codex,
// Claude Code without HTTP): each JSON-RPC line on stdin is sent to the app on 127.0.0.1,
// and its answer comes back on stdout. The port and token are read from the app's settings.
import { readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { createInterface } from 'node:readline'

const config = process.env.CLIPNERA_MCP_CONFIG ?? join(homedir(), 'Library', 'Application Support', 'Clipnera Studio', 'mcp.json')

function settings() {
  try {
    return JSON.parse(readFileSync(config, 'utf8'))
  } catch {
    return null
  }
}

let session = null
const fail = (id, message) => process.stdout.write(`${JSON.stringify({ jsonrpc: '2.0', id: id ?? null, error: { code: -32000, message } })}\n`)

async function forward(line) {
  let message
  try {
    message = JSON.parse(line)
  } catch {
    return fail(null, 'Not JSON')
  }
  const current = settings()
  if (!current?.token) return fail(message.id, 'Clipnera Studio is not set up for agents. Open it and turn on Agents (status bar → Agents).')
  const url = process.env.CLIPNERA_MCP_URL ?? `http://127.0.0.1:${current.port}/mcp`
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${current.token}`, ...(session ? { 'Mcp-Session-Id': session } : {}) },
      body: JSON.stringify(message)
    })
    session = res.headers.get('mcp-session-id') ?? session
    if (res.status === 202) return
    if (!res.ok) return fail(message.id, `Clipnera Studio said ${res.status}: ${await res.text()}`)
    process.stdout.write(`${await res.text()}\n`)
  } catch {
    fail(message.id, 'Clipnera Studio is not running, or Agents is off in it.')
  }
}

// One at a time, so answers come back in the order they were asked.
let queue = Promise.resolve()
createInterface({ input: process.stdin }).on('line', (line) => {
  if (line.trim()) queue = queue.then(() => forward(line))
})
