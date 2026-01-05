/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{html,ts}'],
  theme: {
    extend: {
      colors: {
        surface: {
          panel: 'var(--surface-panel)',
          muted: 'var(--surface-muted)',
          overlay: 'var(--surface-overlay)',
          border: 'var(--surface-border)',
        },
        brand: {
          primary: '#4f46e5',
          accent: '#22d3ee',
          ember: '#fbbf24',
          glow: '#f472b6',
        },
        status: {
          success: '#10b981',
          warning: '#f59e0b',
          danger: '#f43f5e',
        },
      },
      boxShadow: {
        panel: '0 25px 45px rgba(2, 6, 23, 0.55)',
        'panel-hover': '0 35px 60px rgba(2, 6, 23, 0.55)',
        ring: '0 0 0 3px rgba(99, 102, 241, 0.35)',
      },
      borderRadius: {
        card: '1rem',
        'card-lg': '1.25rem',
      },
      spacing: {
        18: '4.5rem',
        22: '5.5rem',
      },
    },
  },
  plugins: [],
};
