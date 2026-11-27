// MKLOG1. The footer indexes completed files. A missing footer can be recovered
// by walking the length-prefixed blocks without reading their sample payloads.
const LIMIT = 1024 * 1024;
const decoder = () => new TextDecoder('utf-8', { fatal: true });
const integer = Number.isSafeInteger;
const check = (condition, detail) => { if (!condition) throw new Error('MKLog: ' + detail); };

async function eachLine(blob, visit) {
  const reader = blob.stream().getReader(), utf = decoder();
  let pending = '';
  try {
    while (true) {
      const { value, done } = await reader.read();
      pending += done ? utf.decode() : utf.decode(value, { stream: true });
      let start = 0, end;
      while ((end = pending.indexOf('\n', start)) >= 0) {
        check(end - start <= LIMIT + 100, 'invalid index entry');
        visit(JSON.parse(pending.slice(start, end))); start = end + 1;
      }
      pending = pending.slice(start);
      check(pending.length <= LIMIT + 100, 'oversized index entry');
      if (done) break;
    }
    check(!pending, 'truncated index');
  } finally { await reader.cancel(); reader.releaseLock(); }
}

export async function openRecording(file, kind) {
  const header = 'MKLOG1 ' + kind + '\n';
  check(await file.slice(0, header.length).text() === header, 'unexpected recording type');
  let offset = header.length;
  const blocks = [];
  let complete = false;
  function add(size, length, meta) {
    check(integer(size) && size > 0 && size <= LIMIT && integer(length) && length > 0 && length <= LIMIT,
      'invalid block size');
    check(meta && Number.isFinite(meta.start) && Number.isFinite(meta.end) &&
      integer(meta.rows) && meta.rows > 0 && meta.rows <= 2048 && integer(meta.gap) &&
      meta.gap >= 0 && meta.gap <= 3 && typeof meta.loss === 'boolean' &&
      meta.tracks && !Array.isArray(meta.tracks) && typeof meta.tracks === 'object', 'invalid block metadata');
    check(meta.deflate_bytes === undefined || integer(meta.deflate_bytes) && meta.deflate_bytes > 0 &&
      meta.deflate_bytes <= LIMIT, 'invalid uncompressed size');
    const tracks = Object.entries(meta.tracks);
    check(tracks.length && tracks.every(([name, t]) => name.length && name.length <= 512 &&
      Array.isArray(t) && t.length === (kind === 'superwatch' ? 9 : 3) && t.every(Number.isFinite) &&
      integer(t[0]) && t[0] > 0 && t[0] <= meta.rows), 'invalid track index');
    if (kind === 'superwatch') {
      check(meta.end >= meta.start && (!blocks.length || meta.start >= blocks.at(-1).end),
        'sample timestamps moved backwards');
    }
    const start = offset + 8 + size;
    offset = start + length;
    check(integer(offset) && offset <= file.size, 'block exceeds file');
    blocks.push({ ...meta, offset: start, length });
  }
  const tail = new DataView(await file.slice(-16).arrayBuffer());
  if (tail.byteLength === 16 && new TextDecoder().decode(new Uint8Array(tail.buffer, 8)) === 'MKIDX1\r\n') {
    const index = Number(tail.getBigUint64(0, true));
    check(integer(index) && index >= offset + 8 && index < file.size - 16, 'invalid footer offset');
    let count = null;
    await eachLine(file.slice(index, file.size - 16), row => {
      if (count === null) {
        check(integer(row.blocks) && row.blocks >= 0 && typeof row.complete === 'boolean', 'invalid footer');
        count = row.blocks; complete = row.complete;
      } else {
        check(Array.isArray(row) && row.length === 4 && row[0] === offset, 'invalid block offset');
        add(row[1], row[2], row[3]);
      }
    });
    check(count === blocks.length && offset + 8 === index, 'inconsistent footer length');
  } else {
    while (offset + 8 <= file.size) {
      const prefix = new DataView(await file.slice(offset, offset + 8).arrayBuffer());
      const size = prefix.getUint32(0, true), length = prefix.getUint32(4, true);
      if (!size && !length) break;
      check(size > 0 && size <= LIMIT && length > 0 && length <= LIMIT, 'invalid block prefix');
      if (offset + 8 + size + length > file.size) break;
      add(size, length, JSON.parse(await file.slice(offset + 8, offset + 8 + size).text()));
    }
  }
  check(blocks.length, 'no recorded samples');
  async function payload(block) {
    const blob = file.slice(block.offset, block.offset + block.length);
    if (block.deflate_bytes === undefined) return blob;
    check(typeof DecompressionStream === 'function', 'this browser needs DecompressionStream support to read compressed recordings');
    const reader = blob.stream().pipeThrough(new DecompressionStream('deflate')).getReader();
    const chunks = [];
    let size = 0;
    try {
      for (;;) {
        const {value, done} = await reader.read();
        if (done) break;
        size += value.byteLength;
        check(size <= block.deflate_bytes, 'uncompressed data exceeds indexed size');
        chunks.push(value);
      }
      check(size === block.deflate_bytes, 'incomplete compressed block');
      return new Blob(chunks);
    } finally { await reader.cancel(); reader.releaseLock(); }
  }
  return { blocks, complete, payload };
}
