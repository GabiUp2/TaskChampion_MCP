// Smithery CLI multipart upload requires global File (Node 20+).
const { File } = require('node:buffer');
if (typeof globalThis.File === 'undefined') {
  globalThis.File = File;
}
