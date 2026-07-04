// API base URL. In dev, Vite proxy forwards /api to http://localhost:8000.
// In production (Vercel), set VITE_API_URL to the deployed backend URL.
export const API_BASE = import.meta.env.VITE_API_URL || '/api'
