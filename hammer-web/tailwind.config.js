/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/pages/**/*.html",
    "./app/static/src/**/*.js"
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter var', 'ui-sans-serif', 'system-ui', 'sans-serif', "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji"],
      },
      fontSize: {
        '2xs': '.625rem',
        '3xs': '.5rem',
        '4xs': '.375rem'
      },
    },
    /*colors: {
      primary: {
        light : "#2563eb"
      },
      secondary: {
        light : "#1f2937"
      },
      accent: {
        light: "#c7d2fe"
      },
      neutral: {
        light: "#67e8f9"
      },
      'base-100': {
        light: "#e5e7eb"
      },
      info: {
        light: "#67e8f9"
      },
      success: {
        light: "#6ee7b7"
      },
      warning: {
        light: "#facc15"
      },
      error: {
        light: "#f43f5e"
      },
    }*/
  },
  plugins: [],
}

