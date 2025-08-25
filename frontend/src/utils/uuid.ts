export function generateUUID(): string {
  // Prefer native crypto.randomUUID if available
  if (typeof globalThis.crypto !== 'undefined') {
    if (typeof globalThis.crypto.randomUUID === 'function') {
      return globalThis.crypto.randomUUID();
    }
    if (typeof globalThis.crypto.getRandomValues === 'function') {
      const arr = new Uint8Array(16);
      globalThis.crypto.getRandomValues(arr);
      // RFC4122 version 4
      arr[6] = (arr[6] & 0x0f) | 0x40;
      arr[8] = (arr[8] & 0x3f) | 0x80;
      const toHex = (n: number) => n.toString(16).padStart(2, '0');
      const h = Array.from(arr, toHex).join('');
      return `${h.substring(0,8)}-${h.substring(8,12)}-${h.substring(12,16)}-${h.substring(16,20)}-${h.substring(20)}`;
    }
  }
  // Fallback - not cryptographically strong
  let uuid = '';
  for (let i = 0; i < 36; i++) {
    if (i === 8 || i === 13 || i === 18 || i === 23) {
      uuid += '-';
    } else if (i === 14) {
      uuid += '4';
    } else {
      const r = Math.random() * 16 | 0;
      uuid += (i === 19 ? (r & 0x3) | 0x8 : r).toString(16);
    }
  }
  return uuid;
}
