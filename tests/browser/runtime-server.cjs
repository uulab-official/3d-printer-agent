// Isolated real local servers for restart/recovery browser qualification.
// No printer, native slicer or live model provider is contacted.
const { spawn, execFile } = require('node:child_process');
const { promisify } = require('node:util');
const fs = require('node:fs/promises');
const net = require('node:net');
const path = require('node:path');

const runFile = promisify(execFile);
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

async function isolatedRuntime(testInfo) {
  const socket = net.createServer();
  await new Promise((resolve, reject) => {
    socket.once('error', reject);
    socket.listen(0, '127.0.0.1', resolve);
  });
  const port = socket.address().port;
  await new Promise((resolve, reject) => socket.close(error => error ? reject(error) : resolve()));
  const root = testInfo.outputPath('로컬 작업 데이터');
  const url = `http://127.0.0.1:${port}`;
  let child = null;
  let logs = '';
  const env = { ...process.env, PYTHONUNBUFFERED: '1', PPA_LLM_BASE_URL: '', PPA_LLM_MODEL: '',
    PPA_LLM_API_KEY: '', PPA_BAMBU_PATH: path.join(root, 'no-native-slicer') };

  async function start() {
    if (child) throw new Error('Isolated runtime already started');
    await fs.mkdir(root, { recursive: true });
    child = spawn('python', ['-m', 'print_agent', '--port', String(port), '--data-dir', root], {
      cwd: path.resolve(__dirname, '../..'), env, stdio: ['ignore', 'pipe', 'pipe'],
    });
    let launchError;
    child.once('error', error => { launchError = error; });
    for (const stream of [child.stdout, child.stderr]) stream.on('data', chunk => {
      logs = (logs + chunk.toString('utf8')).slice(-250000);
    });
    for (let count = 0; count < 150; count++) {
      if (launchError) throw launchError;
      if (child.exitCode !== null) throw new Error(`Isolated server exited ${child.exitCode}: ${logs.slice(-2500)}`);
      try {
        const response = await fetch(url + '/api/bootstrap', { signal: AbortSignal.timeout(1000) });
        if (response.ok) return await response.json();
      } catch { /* The child is still starting. */ }
      await pause(100);
    }
    throw new Error('Isolated server did not become ready');
  }

  async function stop() {
    if (!child) return;
    const processToStop = child;
    if (processToStop.exitCode === null) {
      const stopped = new Promise(resolve => processToStop.once('exit', resolve));
      processToStop.kill('SIGTERM');
      let timer;
      const graceful = await Promise.race([stopped.then(() => true), new Promise(resolve => {
        timer = setTimeout(() => resolve(false), 7000);
      })]);
      clearTimeout(timer);
      if (!graceful) {
        processToStop.kill('SIGKILL');
        await stopped;
        child = null;
        throw new Error('Isolated runtime did not shut down gracefully');
      }
    }
    child = null;
    await fs.writeFile(testInfo.outputPath('runtime-server.log'), logs);
  }

  async function seedInterruptedHistory() {
    if (child) throw new Error('Seed only while the isolated runtime is stopped');
    const script = [
      'import json, sys',
      'from pathlib import Path',
      'from print_agent.storage import JobStore',
      'store = JobStore(Path(sys.argv[1]))',
      'for number in range(102):',
      "    job_id, folder = store.reserve(request={'template':'tray','width':120})",
      "    store.fail(job_id, 'Browser synthetic failed attempt ' + str(number))",
      "interrupted, _ = store.reserve(request={'template':'tray','width':139})",
      "damaged, folder = store.reserve(request={'template':'tray','width':141})",
      "(folder / 'job.json').write_bytes(b'{synthetic interrupted record')",
      "print(json.dumps({'failed':102,'interrupted':interrupted,'damaged':damaged}))",
    ].join('\n');
    const result = await runFile('python', ['-c', script, root], {
      cwd: path.resolve(__dirname, '../..'), env, timeout: 30000, maxBuffer: 100000,
    });
    return JSON.parse(result.stdout);
  }

  return { root, url, start, stop, seedInterruptedHistory };
}

module.exports = { isolatedRuntime };
