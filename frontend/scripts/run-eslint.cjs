#!/usr/bin/env node
'use strict';

const { spawnSync } = require('node:child_process');
const path = require('node:path');

const eslintBin = path.join(
  process.cwd(),
  'node_modules',
  '.bin',
  process.platform === 'win32' ? 'eslint.cmd' : 'eslint'
);

const result = spawnSync(eslintBin, process.argv.slice(2), {
  stdio: 'inherit',
  env: { ...process.env, ESLINT_USE_FLAT_CONFIG: 'false' }
});

process.exit(result.status ?? 1);

