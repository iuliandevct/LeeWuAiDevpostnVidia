const path = require('node:path');

module.exports = {
  uiPort: Number(process.env.NODE_RED_PORT || 1880),
  uiHost: '127.0.0.1',
  httpAdminRoot: '/admin',
  httpNodeRoot: '/',
  httpStatic: path.resolve(__dirname, '..', 'dist'),
  flowFile: 'flows.json',
  contextStorage: {
    default: { module: 'localfilesystem' },
    memoryOnly: { module: 'memory' },
  },
  editorTheme: {
    projects: { enabled: false },
    header: { title: 'FlowForge Nodes' },
    page: { title: 'FlowForge Node-RED' },
  },
  functionExternalModules: false,
  functionGlobalContext: {
    fs: require('node:fs'),
    path: require('node:path'),
    child_process: require('node:child_process'),
    env: process.env,
    projectRoot: path.resolve(__dirname, '..'),
  },
  functionTimeout: 15,
  logging: { console: { level: 'info', metrics: false, audit: false } },
};
