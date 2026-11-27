import { openRecording } from './recording_file.js';
import { lowerBound } from './superwatch_replay_data.js';
import { signalFormula } from './signal_formula.js';

// Keep the visible pixel envelope, the original raw values, and segment IDs.
function envelope(width, start, span, formula) {
  const buckets = new Map(), direct = [];
  let count = 0;
  const convert = formula ? signalFormula(formula) : value => value;
  return {
    add(time, value, segment) {
      const y = convert(value);
      if (!Number.isFinite(y)) return;
      const point = [time, value, segment], x = Math.max(0, Math.min(width - 1, Math.floor((time - start) / span * width)));
      if (++count <= width * 2) direct.push(point);
      const b = buckets.get(x);
      if (!b) buckets.set(x, { lo: point, hi: point, min: y, max: y });
      else {
        if (b.min > y) { b.min = y; b.lo = point; }
        if (b.max < y || b.min === b.max) { b.max = y; b.hi = point; }
      }
    },
    finish() {
      const points = count <= width * 2 ? direct : [...buckets.values()].flatMap(b =>
        b.lo === b.hi ? [b.lo] : b.lo[0] <= b.hi[0] ? [b.lo, b.hi] : [b.hi, b.lo]);
      return { points: points.map(p => p.slice(0, 2)), segments: points.map(p => p[2]) };
    },
  };
}

function lastStarted(entries, time) {
  let lo = 0, hi = entries.length;
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (entries[mid].track[1] <= time) lo = mid + 1;
    else hi = mid;
  }
  return lo - 1;
}

export async function indexedWaveform(file) {
  const recording = await openRecording(file, 'superwatch');
  const { blocks } = recording, origin = blocks[0].start, duration = blocks.at(-1).end - origin;
  const tracks = new Map(), cache = new Map();
  const ends = blocks.map(b => b.end);
  let rows = 0, values = 0;
  for (const [index, block] of blocks.entries()) {
    rows += block.rows;
    block.entries = [];
    for (const [name, track] of Object.entries(block.tracks)) {
      if (!tracks.has(name)) tracks.set(name, { entries: [], gaps: [], count: 0 });
      const channel = tracks.get(name), previous = channel.entries.at(-1);
      const gap = previous ? block.gap || (previous.index + 1 < index ? 2 : 0) : 0;
      const entry = { name, index, block, track, segment: (previous?.segment || 0) + Number(!!gap) };
      if (gap & 1) channel.gaps.push([previous.track[7], track[1]]);
      channel.entries.push(entry);
      block.entries.push(entry);
      channel.count += track[0]; values += track[0];
    }
  }
  async function raw(block) {
    if (cache.has(block)) return cache.get(block);
    // Allocate from the per-block counts. This avoids retaining the whole time
    // series or building the legacy CSV parser's per-channel plotting indexes.
    const channels = new Map(Object.entries(block.tracks).map(([name, track]) => [
      name, { times: new Float64Array(track[0]), values: new Float64Array(track[0]), count: 0 },
    ]));
    const text = await (await recording.payload(block)).text();
    let rows = 0, previous = block.start;
    for (const line of text.split('\n')) {
      if (!line) continue;
      const row = JSON.parse(line);
      if (row.event === 'discontinuity') continue;
      if (!Number.isFinite(row._t) || row._t < previous || row._t > block.end)
        throw new Error('Sample timestamp does not match the block index');
      previous = row._t; rows++;
      for (const [name, value] of Object.entries(row)) {
        if (name === '_t') continue;
        const channel = channels.get(name);
        if (!channel || channel.count >= channel.times.length || !Number.isFinite(value))
          throw new Error('Sample does not match the channel index');
        channel.times[channel.count] = row._t - block.start;
        channel.values[channel.count++] = value;
      }
    }
    if (block.rows !== rows || [...channels.values()].some(c => c.count !== c.times.length))
      throw new Error('Sample count does not match the block index');
    if (cache.size >= 4) cache.delete(cache.keys().next().value);
    const data = { origin: block.start, channels };
    cache.set(block, data);
    return data;
  }
  async function range(start, end, position, width, names, playing, formulas = {}, overview = false) {
    width = Math.min(2048, Math.max(1, Math.floor(width)));
    const span = Math.max(end - start, 1e-12), right = (playing ? Math.min(position, end) : end) + origin;
    const left = start + origin, at = position + origin;
    const selected = new Map();
    for (const name of names) {
      if (!tracks.has(name)) continue;
      const formula = Object.hasOwn(formulas, name) ? formulas[name] : '';
      selected.set(name, { formula, bins: envelope(width, start, span, formula) });
    }
    // Read each intersecting block at most once for all selected signals.
    for (let i = lowerBound(ends, left); i < blocks.length && blocks[i].start <= right; i++) {
      const block = blocks[i];
      let data;
      for (const { name, track: t, segment } of block.entries) {
        const out = selected.get(name);
        if (!out || t[1] > right || t[7] < left) continue;
        const samePixel = Math.floor((t[1]-left)/span*width) === Math.floor((t[7]-left)/span*width);
        if (overview || (!out.formula && t[1] >= left && t[7] <= right && samePixel)) {
          let last = null;
          for (const j of [1, 3, 5, 7].sort((a,b) => t[a]-t[b])) {
            if (t[j] !== last && t[j] >= left && t[j] <= right) out.bins.add(t[j]-origin, t[j+1], segment);
            last = t[j];
          }
        } else {
          data ??= await raw(block);
          const c = data.channels.get(name);
          if (!c) throw new Error('Channel missing from indexed block');
          const from = lowerBound(c.times, left - data.origin), to = lowerBound(c.times, right - data.origin, true);
          for (let j = from; j < to; j++) out.bins.add(c.times[j] + (data.origin-origin), c.values[j], segment);
        }
      }
    }
    const channels = [];
    for (const [name, out] of selected) {
      const { entries, gaps } = tracks.get(name);
      const columns = new Uint8Array(width);
      for (const [before, after] of gaps) {
        if (before >= right) break;
        if (after <= left) continue;
        const x = Math.max(0, Math.floor((before-left)/span*width));
        columns.fill(1, x, Math.min(width, Math.max(x+1, Math.ceil((after-left)/span*width))));
      }
      let latest = null;
      const current = entries[lastStarted(entries, at)];
      if (current) {
        if (current.track[7] <= at) latest = current.track[8];
        else if (!overview) {
          const data = await raw(current.block), c = data.channels.get(name);
          const i = lowerBound(c.times, at-data.origin, true)-1;
          if (i >= 0) latest = c.values[i];
        }
      }
      channels.push({ name, ...out.bins.finish(), columns, latest });
    }
    return { start, end, position, width, channels };
  }
  const channels = [...tracks].map(([name, c]) => ({ name, count: c.count }));
  const overview = await range(0, duration, duration, 512, [...tracks.keys()], false, {}, true);
  return { range, metadata: { duration, origin, rows, values, format: 'mklog', incomplete: !recording.complete,
    channels, overview: overview.channels } };
}
