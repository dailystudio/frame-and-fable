import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'path';
import fs from 'fs';

function storybookOutputsPlugin() {
  const outputsDir = path.resolve(__dirname, '../outputs');
  const examplesDir = path.resolve(__dirname, '../examples');

  return {
    name: 'storybook-outputs-api',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
        const pathname = decodeURIComponent(url.pathname);

        // 1. GET /api/workspaces -> list of workspaces
        if (pathname === '/api/workspaces' && req.method === 'GET') {
          try {
            if (!fs.existsSync(outputsDir)) {
              res.setHeader('Content-Type', 'application/json; charset=utf-8');
              res.end(JSON.stringify({ workspaces: [] }));
              return;
            }

            const entries = fs.readdirSync(outputsDir, { withFileTypes: true });
            const workspaces = [];

            for (const entry of entries) {
              if (entry.isDirectory()) {
                const wsDir = path.join(outputsDir, entry.name);
                const charDir = path.join(wsDir, 'char-ref');
                const styleDir = path.join(wsDir, 'style-ref');
                const imagesDir = path.join(wsDir, 'images');
                const videosDir = path.join(wsDir, 'videos');

                let charCount = 0;
                let charImageCount = 0;
                if (fs.existsSync(charDir)) {
                  const chars = fs.readdirSync(charDir, { withFileTypes: true }).filter(d => d.isDirectory());
                  charCount = chars.length;
                  for (const c of chars) {
                    const cPath = path.join(charDir, c.name);
                    const imgs = fs.readdirSync(cPath).filter(f => /\.(png|jpe?g|webp)$/i.test(f));
                    charImageCount += imgs.length;
                  }
                }

                let styleCount = 0;
                if (fs.existsSync(styleDir)) {
                  const imgs = fs.readdirSync(styleDir).filter(f => /\.(png|jpe?g|webp)$/i.test(f));
                  styleCount = imgs.length;
                }

                let generatedImagesCount = 0;
                if (fs.existsSync(imagesDir)) {
                  generatedImagesCount = fs.readdirSync(imagesDir).filter(f => /\.(png|jpe?g|webp)$/i.test(f)).length;
                }

                let generatedVideosCount = 0;
                if (fs.existsSync(videosDir)) {
                  generatedVideosCount = fs.readdirSync(videosDir).filter(f => /\.(mp4|webm)$/i.test(f)).length;
                }

                const outputMd = path.join(wsDir, `${entry.name}-output.md`);
                const hasOutputMd = fs.existsSync(outputMd);

                workspaces.push({
                  stem: entry.name,
                  directory: wsDir,
                  charactersCount: charCount,
                  characterImagesCount: charImageCount,
                  styleImagesCount: styleCount,
                  generatedImagesCount,
                  generatedVideosCount,
                  hasOutputMd
                });
              }
            }

            res.setHeader('Content-Type', 'application/json; charset=utf-8');
            res.end(JSON.stringify({ workspaces }));
          } catch (err) {
            res.statusCode = 500;
            res.end(JSON.stringify({ error: String(err) }));
          }
          return;
        }

        // 2. GET /api/workspace/:stem -> full details
        if (pathname.startsWith('/api/workspace/') && req.method === 'GET') {
          const stem = pathname.slice('/api/workspace/'.length);
          const wsDir = path.join(outputsDir, stem);

          if (!fs.existsSync(wsDir)) {
            res.statusCode = 404;
            res.setHeader('Content-Type', 'application/json; charset=utf-8');
            res.end(JSON.stringify({ error: `Workspace '${stem}' not found` }));
            return;
          }

          try {
            // Load Characters
            let characters = [];
            const charDir = path.join(wsDir, 'char-ref');
            const charsJsonPath = path.join(charDir, 'characters.json');

            if (fs.existsSync(charsJsonPath)) {
              try {
                const parsed = JSON.parse(fs.readFileSync(charsJsonPath, 'utf-8'));
                characters = parsed.characters || [];
              } catch (e) {
                // fallback to directories
              }
            }

            // Fallback / complement from subdirectories
            if (fs.existsSync(charDir)) {
              const charDirs = fs.readdirSync(charDir, { withFileTypes: true }).filter(d => d.isDirectory());
              for (const cd of charDirs) {
                const existing = characters.find(c => c.name === cd.name);
                const cPath = path.join(charDir, cd.name);
                const imgs = fs.readdirSync(cPath).filter(f => /\.(png|jpe?g|webp)$/i.test(f));
                const cJsonPath = path.join(cPath, 'character.json');
                let cJson = {};
                if (fs.existsSync(cJsonPath)) {
                  try {
                    cJson = JSON.parse(fs.readFileSync(cJsonPath, 'utf-8'));
                  } catch (e) {}
                }

                if (!existing) {
                  characters.push({
                    name: cd.name,
                    role: cJson.role || 'Character',
                    visual_dna: cJson.visual_dna || '',
                    portrait_prompt: cJson.portrait_prompt || '',
                    images: imgs,
                    source: cJson.source || 'collected'
                  });
                } else if (!existing.images || existing.images.length === 0) {
                  existing.images = imgs;
                }
              }
            }

            // Load Style
            let style = {
              style_name: 'Default Style',
              style_prompt: '',
              reference_prompt: '',
              images: []
            };
            const styleDir = path.join(wsDir, 'style-ref');
            const styleJsonPath = path.join(styleDir, 'style.json');
            if (fs.existsSync(styleJsonPath)) {
              try {
                style = JSON.parse(fs.readFileSync(styleJsonPath, 'utf-8'));
              } catch (e) {}
            }
            if (fs.existsSync(styleDir)) {
              const styleImgs = fs.readdirSync(styleDir).filter(f => /\.(png|jpe?g|webp)$/i.test(f));
              if (styleImgs.length > 0 && (!style.images || style.images.length === 0)) {
                style.images = styleImgs;
              }
            }

            // Load Generated Media
            const imagesDir = path.join(wsDir, 'images');
            const generatedImages = [];
            if (fs.existsSync(imagesDir)) {
              const files = fs.readdirSync(imagesDir).filter(f => /\.(png|jpe?g|webp)$/i.test(f));
              for (const file of files) {
                const fPath = path.join(imagesDir, file);
                const stat = fs.statSync(fPath);
                generatedImages.push({
                  name: file,
                  id: path.parse(file).name,
                  sizeBytes: stat.size,
                  path: `images/${file}`,
                  assetUrl: `/api/asset/${stem}/images/${file}`
                });
              }
            }

            const videosDir = path.join(wsDir, 'videos');
            const generatedVideos = [];
            if (fs.existsSync(videosDir)) {
              const files = fs.readdirSync(videosDir).filter(f => /\.(mp4|webm)$/i.test(f));
              for (const file of files) {
                const fPath = path.join(videosDir, file);
                const stat = fs.statSync(fPath);
                generatedVideos.push({
                  name: file,
                  id: path.parse(file).name,
                  sizeBytes: stat.size,
                  path: `videos/${file}`,
                  assetUrl: `/api/asset/${stem}/videos/${file}`
                });
              }
            }

            // Load Markdown (output or example source)
            let markdownContent = '';
            let markdownType = 'none';
            const outputMdPath = path.join(wsDir, `${stem}-output.md`);
            const exampleMdPath = path.join(examplesDir, `${stem}.md`);

            if (fs.existsSync(outputMdPath)) {
              markdownContent = fs.readFileSync(outputMdPath, 'utf-8');
              markdownType = 'output';
            } else if (fs.existsSync(exampleMdPath)) {
              markdownContent = fs.readFileSync(exampleMdPath, 'utf-8');
              markdownType = 'example';
            } else {
              // search for any .md in wsDir
              const mdFiles = fs.readdirSync(wsDir).filter(f => f.endsWith('.md'));
              if (mdFiles.length > 0) {
                markdownContent = fs.readFileSync(path.join(wsDir, mdFiles[0]), 'utf-8');
                markdownType = 'workspace';
              }
            }

            // Extract tags from markdown if present
            const tags = [];
            const tagRegex = /<!--\s*storybook-media:\s*(\{.*?\})\s*-->/gs;
            let match;
            while ((match = tagRegex.exec(markdownContent)) !== null) {
              try {
                tags.push(JSON.parse(match[1]));
              } catch (e) {}
            }

            res.setHeader('Content-Type', 'application/json; charset=utf-8');
            res.end(JSON.stringify({
              stem,
              characters,
              style,
              generatedImages,
              generatedVideos,
              markdownContent,
              markdownType,
              tags
            }));
          } catch (err) {
            res.statusCode = 500;
            res.setHeader('Content-Type', 'application/json; charset=utf-8');
            res.end(JSON.stringify({ error: String(err) }));
          }
          return;
        }

        // 3. GET /api/asset/* -> static media streaming
        if (pathname.startsWith('/api/asset/')) {
          const relativeAsset = pathname.slice('/api/asset/'.length);
          const fullPath = path.join(outputsDir, relativeAsset);

          if (!fs.existsSync(fullPath) || !fs.statSync(fullPath).isFile()) {
            res.statusCode = 404;
            res.end('Asset not found');
            return;
          }

          const ext = path.extname(fullPath).toLowerCase();
          const mimeTypes = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.webp': 'image/webp',
            '.gif': 'image/gif',
            '.mp4': 'video/mp4',
            '.webm': 'video/webm',
            '.md': 'text/markdown; charset=utf-8',
            '.json': 'application/json; charset=utf-8'
          };

          const contentType = mimeTypes[ext] || 'application/octet-stream';
          res.setHeader('Content-Type', contentType);
          res.setHeader('Cache-Control', 'public, max-age=3600');

          fs.createReadStream(fullPath).pipe(res);
          return;
        }

        next();
      });
    }
  };
}

export default defineConfig({
  plugins: [
    vue(),
    storybookOutputsPlugin()
  ],
  server: {
    port: 5173,
    open: true,
    fs: {
      allow: ['..']
    }
  }
});
