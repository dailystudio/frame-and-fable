export async function getWorkspaces() {
  const res = await fetch('/api/workspaces');
  if (!res.ok) {
    throw new Error(`Failed to load workspaces: ${res.status} ${res.statusText}`);
  }
  const data = await res.json();
  return data.workspaces || [];
}

export async function getWorkspace(stem) {
  const res = await fetch(`/api/workspace/${encodeURIComponent(stem)}`);
  if (!res.ok) {
    throw new Error(`Failed to load workspace '${stem}': ${res.status} ${res.statusText}`);
  }
  return await res.json();
}

export function getAssetUrl(stem, relativePath) {
  if (!relativePath) return '';
  if (relativePath.startsWith('http://') || relativePath.startsWith('https://') || relativePath.startsWith('/api/asset/')) {
    return relativePath;
  }
  const cleanPath = relativePath.startsWith('/') ? relativePath.slice(1) : relativePath;
  return `/api/asset/${encodeURIComponent(stem)}/${cleanPath}`;
}

export function getCharImageUrl(stem, charName, imgName) {
  if (!imgName) return '';
  return `/api/asset/${encodeURIComponent(stem)}/char-ref/${encodeURIComponent(charName)}/${encodeURIComponent(imgName)}`;
}

export function getStyleImageUrl(stem, imgName) {
  if (!imgName) return '';
  return `/api/asset/${encodeURIComponent(stem)}/style-ref/${encodeURIComponent(imgName)}`;
}
