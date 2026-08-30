import { cpSync, existsSync } from 'node:fs';
import { spawn } from 'node:child_process';
import path from 'node:path';

const projectRoot = process.cwd();
const standaloneRoot = path.join(projectRoot, '.next', 'standalone');
const standaloneAppRoot = path.join(standaloneRoot, 'apps', 'web');
const staticSource = path.join(projectRoot, '.next', 'static');
const staticTarget = path.join(standaloneAppRoot, '.next', 'static');
const publicSource = path.join(projectRoot, 'public');
const publicTarget = path.join(standaloneAppRoot, 'public');

cpSync(staticSource, staticTarget, { recursive: true, force: true });
if (existsSync(publicSource)) {
  cpSync(publicSource, publicTarget, { recursive: true, force: true });
}

const server = spawn(process.execPath, [path.join(standaloneAppRoot, 'server.js')], {
  cwd: standaloneAppRoot,
  env: process.env,
  stdio: 'inherit',
});

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => server.kill(signal));
}

server.on('exit', code => process.exit(code ?? 1));
