export interface ReplayControl {
  (): void;
  catalog(): Array<{ name: string; description: string; args: Record<string, unknown>; effect: string }>;
  read(): { loaded: boolean; playing: boolean; position: number; speed: number; duration: number; filename: string | null };
  validate(action: string, args?: Record<string, unknown>): { valid: boolean };
  execute(action: string, args?: Record<string, unknown>, context?: { fetch: typeof fetch }): Promise<unknown>;
}
export function mountReplayButton(host: HTMLElement, options?: { language?: string; viewer?: () => any; loadFile?: (path: string, context?: { fetch: typeof fetch }) => Promise<File> }): ReplayControl;
