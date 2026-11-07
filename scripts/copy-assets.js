// Copies what tsc does not handle into the build directory.
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');

fs.cpSync(path.join(root, 'src', 'static'), path.join(root, 'build', 'static'), { recursive: true });
