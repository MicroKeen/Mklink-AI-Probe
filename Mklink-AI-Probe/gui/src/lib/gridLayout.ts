import { GridStackEngine, type GridStackNode } from 'gridstack';

export interface GridGeometry { id: string; x: number; y: number; w: number; h: number }
export function gridGeometry(nodes: GridStackNode[]): GridGeometry[] {
  return nodes.map(({ id, x, y, w, h }) => ({ id: id!, x: x!, y: y!, w: w!, h: h! }));
}

// Use the same collision engine for Agent commands and pointer gestures.
export function moveGrid(items: GridGeometry[], target: GridGeometry): GridGeometry[] {
  const engine = new GridStackEngine({ column: 12, float: true });
  engine.batchUpdate();
  items.forEach(item => engine.addNode({ ...item }));
  engine.batchUpdate(false);
  const node = engine.nodes.find(item => item.id === target.id);
  if (!node) throw new Error('Layout item no longer exists');
  engine.moveNode(node, { ...target, resizing: target.w !== node.w || target.h !== node.h });
  return gridGeometry(engine.nodes);
}
