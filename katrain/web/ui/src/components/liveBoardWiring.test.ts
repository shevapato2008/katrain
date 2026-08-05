import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { describe, expect, it } from 'vitest';

const liveBoardFiles = [
  '../galaxy/pages/GamePage.tsx',
  '../galaxy/pages/GameRoomPage.tsx',
  '../kiosk/pages/GamePage.tsx',
  '../ZenModeApp.tsx',
];

function boardElementsWithNavigate(relativePath: string): string[] {
  const fileUrl = new URL(relativePath, import.meta.url);
  const sourceText = readFileSync(fileUrl, 'utf8');
  const sourceFile = ts.createSourceFile(fileUrl.pathname, sourceText, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const violations: string[] = [];

  function visit(node: ts.Node): void {
    if (ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) {
      const tagName = node.tagName.getText(sourceFile);
      const isBoard = tagName === 'Board' || tagName === 'Board3D';
      const hasNavigate = node.attributes.properties.some(
        (attribute) => ts.isJsxAttribute(attribute) && attribute.name.getText(sourceFile) === 'onNavigate',
      );

      if (isBoard && hasNavigate) {
        const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
        violations.push(`${tagName} at line ${line + 1}`);
      }
    }

    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  return violations;
}

describe('live board wiring', () => {
  it.each(liveBoardFiles)('%s omits stone navigation from every Board and Board3D', (relativePath) => {
    expect(boardElementsWithNavigate(relativePath)).toEqual([]);
  });
});
