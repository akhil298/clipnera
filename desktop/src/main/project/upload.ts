import { createReadStream } from 'node:fs'
import { request as httpRequest } from 'node:http'
import { request as httpsRequest } from 'node:https'

/**
 * PUTs a file to a presigned URL with an exact Content-Length (S3 refuses chunked uploads),
 * reporting progress as bytes leave the Mac.
 */
export function putFile(url: string, path: string, contentType: string, size: number, onProgress: (fraction: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const target = new URL(url)
    const send = target.protocol === 'https:' ? httpsRequest : httpRequest
    const req = send(target, { method: 'PUT', headers: { 'Content-Type': contentType, 'Content-Length': size } }, (res) => {
      res.resume()
      res.on('end', () => (res.statusCode && res.statusCode < 300 ? resolve() : reject(new Error(`Upload failed (${res.statusCode})`))))
    })
    req.on('error', (error) => reject(new Error(`Upload failed: ${error.message}`)))

    let sent = 0
    createReadStream(path)
      .on('data', (chunk) => {
        sent += chunk.length
        onProgress(size ? sent / size : 1)
      })
      .on('error', (error) => req.destroy(error))
      .pipe(req)
  })
}
