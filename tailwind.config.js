module.exports = {
  content: ["./templates/**/*.html"],
  theme: {
    extend: {
      colors: {
        ocean: { 400: '#22d3ee', 500: '#06b6d4', 600: '#0891b2' },
        teal:  { 400: '#2dd4bf', 500: '#14b8a6' },
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      }
    }
  },
  plugins: [],
}
