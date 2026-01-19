#!/usr/bin/env node
'use strict';

const { spawnSync } = require('node:child_process');
const path = require('node:path');

const eslintEntry = path.join(process.cwd(), 'node_modules', 'eslint', 'bin', 'eslint.js');

const result = spawnSync(process.execPath, [eslintEntry, ...process.argv.slice(2)], {
  stdio: 'inherit',
  env: { ...process.env, ESLINT_USE_FLAT_CONFIG: 'false' }
});

process.exit(result.status ?? 1);

