// PostCSS config local para el frontend Vue 3 + Vite.
// Vacío intencionalmente: el frontend usa CSS plano (src/styles.css) sin
// Tailwind ni Autoprefixer. Esto evita que Vite cargue el postcss.config.mjs
// del directorio padre (que pertenece al proyecto Next.js del sandbox).
export default {
  plugins: [],
}
