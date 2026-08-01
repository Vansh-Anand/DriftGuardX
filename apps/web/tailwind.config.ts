import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        background: "#111111",
        foreground: "#ffffff",
        primary: "#000000",
        mint: "#dcf6cc",
        muted: "#888888",
        card: "#1a1a1a",
        border: "#333333"
      },
      fontFamily: {
        sans: ['var(--font-outfit)', 'sans-serif'],
      },
      animation: {
        'fade-up': 'fadeUp 0.8s ease-out forwards',
        'zoom-in': 'zoomIn 0.8s ease-out forwards',
      },
      keyframes: {
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(40px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        zoomIn: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        }
      }
    },
  },
  plugins: [],
}
export default config
