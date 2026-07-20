import { execSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const type = process.argv[2];
if (!['patch', 'minor', 'major'].includes(type)) {
  console.error('Usage: bun scripts/bump-version.js [patch|minor|major]');
  process.exit(1);
}

// 1. Check if git status is clean
try {
  const status = execSync('git status --porcelain', { encoding: 'utf8' }).trim();
  if (status) {
    console.error('Error: Git working directory is not clean. Commit or stash your changes first.');
    console.error(status);
    process.exit(1);
  }
} catch (e) {
  console.error('Error checking git status:', e.message);
  process.exit(1);
}

// 2. Resolve package.json path safely
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const pkgPath = join(__dirname, '../package.json');

let pkg;
try {
  pkg = JSON.parse(readFileSync(pkgPath, 'utf8'));
} catch (e) {
  console.error('Error reading package.json:', e.message);
  process.exit(1);
}

const currentVersion = pkg.version;
if (!currentVersion) {
  console.error('Error: package.json does not have a version field.');
  process.exit(1);
}

// 3. Parse and increment SemVer
const parts = currentVersion.split('.').map(Number);
if (parts.length !== 3 || parts.some(isNaN)) {
  console.error(`Error: Invalid semver format in package.json: "${currentVersion}"`);
  process.exit(1);
}

let [major, minor, patch] = parts;
if (type === 'patch') {
  patch += 1;
} else if (type === 'minor') {
  minor += 1;
  patch = 0;
} else if (type === 'major') {
  major += 1;
  minor = 0;
  patch = 0;
}

const newVersion = `${major}.${minor}.${patch}`;

// 4. Update package.json
pkg.version = newVersion;
try {
  writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + '\n', 'utf8');
  console.log(`Updated package.json: ${currentVersion} -> ${newVersion}`);
} catch (e) {
  console.error('Error writing package.json:', e.message);
  process.exit(1);
}

// 5. Commit and tag
try {
  execSync(`git add package.json`, { stdio: 'inherit' });
  execSync(`git commit -m "chore(release): v${newVersion}"`, { stdio: 'inherit' });
  execSync(`git tag v${newVersion}`, { stdio: 'inherit' });
  console.log(`Successfully committed and tagged v${newVersion}`);
  console.log(`Run 'git push && git push --tags' to publish the release.`);
} catch (e) {
  console.error('Error during git commit/tag:', e.message);
  process.exit(1);
}
