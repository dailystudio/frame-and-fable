import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'path';
import fs from 'fs';

function matchCharactersForTag(tag, characters) {
  if (!characters || characters.length === 0) return [];
  const explicit = tag.characters;
  if (explicit) {
    const list = Array.isArray(explicit) ? explicit : explicit.split(',').map(s => s.trim());
    const matched = characters.filter(c => list.some(e => e === c.name || e.includes(c.name) || c.name.includes(e)));
    if (matched.length > 0) return matched;
  }
  const promptText = tag.prompt || '';
  const contextText = tag.context_hint || '';
  const combined = `${promptText} ${contextText}`;

  const matched = [];
  for (const ch of characters) {
    const cname = ch.name || '';
    if (!cname) continue;
    const tokens = [cname];
    if (cname.includes('·')) {
      tokens.push(...cname.split('·').map(p => p.trim()).filter(p => p.length >= 2));
    }
    const role = ch.role || '';
    const enAliases = (role.match(/\b[A-Z][a-z]+\b/g) || []).filter(a => a.length >= 4 && !['Main', 'Character', 'Protagonist', 'Warrior', 'Healer', 'Wizard', 'Adventurer'].includes(a));
    tokens.push(...enAliases);

    if (tokens.some(tok => combined.includes(tok))) {
      matched.push(ch);
    }
  }
  return matched;
}

function composeReferencePrompt(contextPrompt, stylePrompt, hasStyleImage, charRefs) {
  const sections = [];
  sections.push(
    `[TASK: BRAND-NEW SCENE ILLUSTRATION FROM SCRATCH]\n` +
    `Generate a completely new, original standalone illustration strictly depicting the SCENE DESCRIPTION below.\n` +
    `CRITICAL CONSTRAINTS:\n` +
    `- DO NOT edit, inpaint, crop, or modify the provided reference image(s).\n` +
    `- DO NOT copy the compositions, backgrounds, camera perspectives, or poses from the reference image(s).\n` +
    `- The environment, action, composition, and physical staging must originate 100% from the SCENE DESCRIPTION.`
  );

  const refRoles = ['[REFERENCE IMAGE ROLES]'];
  let currentImgIdx = 1;
  if (hasStyleImage) {
    refRoles.push(
      `- Reference Image ${currentImgIdx} (Artistic Style Reference):\n` +
      `  * Adopt ONLY the artistic medium, sculpted/painterly textures, color palette, lighting atmosphere, and visual aesthetic shown in Image ${currentImgIdx}.\n` +
      `  * Do NOT copy the specific objects, buildings, or layout of Image ${currentImgIdx}.`
    );
    currentImgIdx++;
  }

  for (const ch of (charRefs || [])) {
    const cname = ch.name || 'Character';
    refRoles.push(
      `- Reference Image ${currentImgIdx} (Character Identity Reference: ${cname}):\n` +
      `  * Maintain the exact character visual identity, facial features, hairstyle, clothing design, colors, and proportions of ${cname} from Image ${currentImgIdx}.\n` +
      `  * Place ${cname} naturally into this new scene, dynamically adopting the action, pose, and emotion specified in the SCENE DESCRIPTION.\n` +
      `  * Do NOT replicate the pose, camera framing, or background of Image ${currentImgIdx}.`
    );
    currentImgIdx++;
  }

  sections.push(refRoles.join('\n'));
  sections.push(`[SCENE DESCRIPTION & ACTION]\n${(contextPrompt || '').trim()}`);

  const charDnaItems = [];
  for (const ch of (charRefs || [])) {
    const cname = ch.name || '';
    const cdna = ch.visual_dna || '';
    if (cdna) {
      const shortDna = cdna.includes('.') ? cdna.split('.')[0].trim() : cdna.slice(0, 140).trim();
      charDnaItems.push(`- ${cname}: ${shortDna}`);
    }
  }
  if (charDnaItems.length > 0) {
    sections.push(`[CHARACTER VISUAL DNA HIGHLIGHTS]\n${charDnaItems.join('\n')}`);
  }

  if (stylePrompt && stylePrompt.trim()) {
    sections.push(`[ARTISTIC STYLE SPECIFICATION]\n${stylePrompt.trim()}`);
  }

  return sections.join('\n\n');
}

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

            // Load Markdown (output, workspace, examples, or tests)
            let markdownContent = '';
            let markdownType = 'none';
            const outputMdPath = path.join(wsDir, `${stem}-output.md`);
            const exampleMdPath = path.join(examplesDir, `${stem}.md`);
            const exampleCraftedPath = path.join(examplesDir, `${stem}_crafted.md`);
            const exampleStemCleanCrafted = path.join(examplesDir, `${stem.replace(/_zh$|_en$/, '')}_crafted.md`);
            const testsMdPath = path.resolve(__dirname, `../tests/${stem}.md`);

            if (fs.existsSync(outputMdPath)) {
              markdownContent = fs.readFileSync(outputMdPath, 'utf-8');
              markdownType = 'output';
            } else if (fs.existsSync(exampleMdPath)) {
              markdownContent = fs.readFileSync(exampleMdPath, 'utf-8');
              markdownType = 'example';
            } else if (fs.existsSync(exampleCraftedPath)) {
              markdownContent = fs.readFileSync(exampleCraftedPath, 'utf-8');
              markdownType = 'example';
            } else if (fs.existsSync(exampleStemCleanCrafted)) {
              markdownContent = fs.readFileSync(exampleStemCleanCrafted, 'utf-8');
              markdownType = 'example';
            } else if (fs.existsSync(testsMdPath)) {
              markdownContent = fs.readFileSync(testsMdPath, 'utf-8');
              markdownType = 'test';
            } else {
              const mdFiles = fs.readdirSync(wsDir).filter(f => f.endsWith('.md'));
              if (mdFiles.length > 0) {
                markdownContent = fs.readFileSync(path.join(wsDir, mdFiles[0]), 'utf-8');
                markdownType = 'workspace';
              }
            }

            // Extract tags with comprehensive parsing
            const rawTags = [];
            const jsonRegex = /<!--\s*storybook-media:\s*(\{.*?\})\s*-->/gs;
            let m;
            while ((m = jsonRegex.exec(markdownContent)) !== null) {
              try {
                rawTags.push({ ...JSON.parse(m[1]), _pos: m.index });
              } catch (e) {}
            }

            const kvRegex = /<!--\s*storybook-media\s+([^>]*?)\s*-->/gs;
            while ((m = kvRegex.exec(markdownContent)) !== null) {
              const content = m[1].trim();
              if (content.startsWith('{') || content.startsWith(':')) continue;
              const kvDict = { _pos: m.index };
              const attrRegex = /(\w+)=["'](.*?)["']/g;
              let am;
              while ((am = attrRegex.exec(content)) !== null) {
                kvDict[am[1]] = am[2];
              }
              if (kvDict.id || kvDict.type) {
                rawTags.push(kvDict);
              }
            }

            rawTags.sort((a, b) => (a._pos || 0) - (b._pos || 0));

            // Enrich tags with generated asset links
            const allGenerated = [...generatedImages, ...generatedVideos];
            const tags = rawTags.map(({ _pos, ...tag }) => {
              const tagId = tag.id || '';
              const tagType = tag.type || 'image';
              const matched = allGenerated.find(a =>
                a.id === tagId ||
                a.name.startsWith(tagId + '.') ||
                a.name.includes(tagId) ||
                (tag.asset && a.name === path.basename(tag.asset))
              );

              const matchedChars = matchCharactersForTag(tag, characters);
              const charRefsData = matchedChars.map(ch => {
                const cname = ch.name || '';
                const imgs = ch.images || [];
                const cImg = imgs.length > 0 ? imgs[0] : null;
                return {
                  name: cname,
                  role: ch.role || 'Character',
                  visual_dna: ch.visual_dna || '',
                  image: cImg,
                  assetUrl: cImg ? `/api/asset/${encodeURIComponent(stem)}/char-ref/${encodeURIComponent(cname)}/${encodeURIComponent(cImg)}` : null,
                  role_guide: `Character Identity Reference: ${cname} (Context Matched)`
                };
              });

              const styleImgs = style.images || [];
              const styleImg = styleImgs.length > 0 ? styleImgs[0] : null;
              const styleRefData = styleImg ? {
                name: styleImg,
                assetUrl: `/api/asset/${encodeURIComponent(stem)}/style-ref/${encodeURIComponent(styleImg)}`,
                style_name: style.style_name || 'Art Style',
                style_prompt: style.style_prompt || '',
                role: 'Style Reference (Always Active)'
              } : null;

              const composedPrompt = composeReferencePrompt(
                tag.prompt || '',
                style.style_prompt || '',
                !!styleImg,
                charRefsData
              );

              return {
                ...tag,
                type: tagType,
                section: tag.section || tag.title || 'Story Scene',
                prompt: tag.prompt || '',
                context_hint: tag.context_hint || '',
                isGenerated: !!matched,
                matchedAsset: matched || null,
                style_ref: styleRefData,
                character_refs: charRefsData,
                composed_prompt: composedPrompt,
                cli_command: `python3 storybook.py media generate outputs/${stem}/${stem}-output.md --id ${tagId}`
              };
            });

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
