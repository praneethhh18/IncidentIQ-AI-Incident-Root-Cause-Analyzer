// Single source of truth for the backend base URL.
// Frontend modules import from here (instead of api.ts) when they need
// the URL without dragging in the whole api client + its types.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";
