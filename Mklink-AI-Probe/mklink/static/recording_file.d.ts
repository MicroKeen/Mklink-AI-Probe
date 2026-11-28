export interface RecordingBlock {
  offset: number; length: number; start: number; end: number; rows: number;
  tracks: Record<string, number[]>; gap: number; loss: boolean;
}
export function openRecording(file: File, kind: string): Promise<{
  blocks: RecordingBlock[]; complete: boolean; payload(block: RecordingBlock): Promise<Blob>;
}>;
