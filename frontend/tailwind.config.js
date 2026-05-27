/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', '"Liberation Mono"', '"Courier New"', 'monospace'],
      },
      colors: {
        cyber: {
          bg: '#09090b',
          surface: '#18181b',
          border: '#27272a',
          text: '#d4d4d8',
          muted: '#71717a',
          wl: '#22d3ee',
          gl: '#d946ef',
          yes: '#10b981',
          no: '#f43f5e',
          warn: '#f59e0b',
        },
      },
      boxShadow: {
        'neon-cyan': '0 0 15px rgba(34, 211, 238, 0.12)',
        'neon-fuchsia': '0 0 15px rgba(217, 70, 239, 0.12)',
        'neon-cyan-lg': '0 0 30px rgba(34, 211, 238, 0.15)',
        'neon-fuchsia-lg': '0 0 30px rgba(217, 70, 239, 0.15)',
      },
      keyframes: {
        'neon-pulse': {
          '0%, 100%': { opacity: '1', filter: 'brightness(1)' },
          '50%': { opacity: '0.85', filter: 'brightness(1.3)' },
        },
        'glide-in': {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'neon-pulse': 'neon-pulse 2s ease-in-out infinite',
        'glide-in': 'glide-in 0.25s ease-out',
        'slide-up': 'slide-up 0.3s ease-out',
      },
    },
  },
  plugins: [],
}
