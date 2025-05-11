const fs = require('fs');
const path = require('path');
const archiver = require('archiver');

// Lambda functions to build
const functions = [
  'auth',
  'matchmaking',
  'saveGame',
  'leaderboard'
];

// Create build directory if it doesn't exist
const buildDir = path.join(__dirname, 'build');
if (!fs.existsSync(buildDir)) {
  fs.mkdirSync(buildDir);
}

// Build each function
functions.forEach(functionName => {
  console.log(`Building ${functionName}...`);
  
  // Create zip file
  const output = fs.createWriteStream(path.join(buildDir, `${functionName}.zip`));
  const archive = archiver('zip', {
    zlib: { level: 9 } // Maximum compression
  });
  
  // Listen for errors
  archive.on('error', (err) => {
    throw err;
  });
  
  // Pipe archive data to the file
  archive.pipe(output);
  
  // Add the function file
  archive.file(path.join(__dirname, 'lambda', `${functionName}.js`), { name: `${functionName}.js` });
  
  // Add node_modules (excluding dev dependencies)
  const packageJson = require('./package.json');
  const dependencies = packageJson.dependencies || {};
  
  Object.keys(dependencies).forEach(dep => {
    const depPath = path.join(__dirname, 'node_modules', dep);
    if (fs.existsSync(depPath)) {
      archive.directory(depPath, `node_modules/${dep}`);
    }
  });
  
  // Finalize the archive
  archive.finalize();
  
  output.on('close', () => {
    console.log(`${functionName}.zip created: ${archive.pointer()} bytes`);
  });
});

console.log('Build process started. Check build directory for output files.');
