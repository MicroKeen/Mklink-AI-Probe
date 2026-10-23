export type SignalFormula = (x: number) => number;
export function compileSignalFormula(source: string): SignalFormula;
export function signalFormula(source?: string): SignalFormula;
