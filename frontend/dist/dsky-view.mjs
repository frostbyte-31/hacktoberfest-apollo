/** Read-only display adapter. Original relay digits are never inferred from program stage. */
const FIELDS = Object.freeze({ PROG:'dsky-program', VERB:'dsky-verb', NOUN:'dsky-noun', R1:'dsky-r1', R2:'dsky-r2', R3:'dsky-r3' });
/**
 * @param {Document | Element} root
 * @param {Partial<Record<keyof typeof FIELDS, string>> | null} state
 */
export function renderDSKY(root, state) {
  for (const [field, id] of Object.entries(FIELDS)) {
    const element = root.querySelector(`#${id}`);
    if (element) element.textContent = typeof state?.[field] === 'string' ? state[field] : field.startsWith('R') ? '?????' : '??';
  }
  // Channel 010 digits do not provide decoded lamp/sign states in this export.
  // The illustration's ? indicators therefore remain unavailable, including COMP ACTY.
}
