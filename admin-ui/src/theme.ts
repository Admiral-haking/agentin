import { createTheme } from '@mui/material/styles';

export const appTheme = createTheme({
  direction: 'rtl',
  palette: {
    mode: 'light',
    primary: {
      main: '#0f8b8d',
      dark: '#0a6e70',
      light: '#5bc6c2',
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#ff8a5b',
      dark: '#e16f45',
      light: '#ffb595',
      contrastText: '#1a1a1a',
    },
    background: {
      default: '#f3f1eb',
      paper: '#ffffff',
    },
    text: {
      primary: '#121621',
      secondary: '#3a3f4f',
    },
  },
  shape: {
    borderRadius: 14,
  },
  typography: {
    fontFamily: '"Vazirmatn", "IBM Plex Sans", sans-serif',
    h1: { fontFamily: '"Vazirmatn", "Space Grotesk", sans-serif', fontWeight: 700 },
    h2: { fontFamily: '"Vazirmatn", "Space Grotesk", sans-serif', fontWeight: 700 },
    h3: { fontFamily: '"Vazirmatn", "Space Grotesk", sans-serif', fontWeight: 700 },
    h4: { fontFamily: '"Vazirmatn", "Space Grotesk", sans-serif', fontWeight: 700 },
    h5: { fontFamily: '"Vazirmatn", "Space Grotesk", sans-serif', fontWeight: 700 },
    h6: { fontFamily: '"Vazirmatn", "Space Grotesk", sans-serif', fontWeight: 700 },
    body1: { lineHeight: 1.8 },
    body2: { lineHeight: 1.7 },
  },
  components: {
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundImage: 'linear-gradient(135deg, #0f8b8d 0%, #1f4fd1 100%)',
          color: '#fff',
          boxShadow: '0 10px 30px rgba(15, 139, 141, 0.25)',
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundImage: 'linear-gradient(180deg, #f9f8f2 0%, #ffffff 100%)',
          borderRight: '1px solid rgba(18, 22, 33, 0.08)',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'linear-gradient(180deg, rgba(255,255,255,0.95) 0%, #ffffff 100%)',
          border: '1px solid rgba(18, 22, 33, 0.08)',
          boxShadow: '0 18px 40px rgba(18, 22, 33, 0.08)',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
          borderRadius: 12,
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          backgroundColor: '#fbfaf6',
        },
        notchedOutline: {
          borderColor: 'rgba(18, 22, 33, 0.16)',
        },
        input: {
          textAlign: 'start',
        },
      },
    },
    MuiInputBase: {
      styleOverrides: {
        root: {
          textAlign: 'start',
        },
        input: {
          textAlign: 'start',
          unicodeBidi: 'plaintext',
        },
      },
    },
    MuiTextField: {
      defaultProps: {
        inputProps: { dir: 'auto' },
      },
    },
    MuiFormLabel: {
      styleOverrides: {
        root: {
          textAlign: 'right',
          right: 0,
          left: 'auto',
          transformOrigin: 'top right',
        },
      },
    },
    MuiFormHelperText: {
      styleOverrides: {
        root: {
          textAlign: 'right',
        },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          backgroundColor: 'rgba(15, 139, 141, 0.08)',
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: {
          fontWeight: 700,
          textTransform: 'none',
          letterSpacing: '0',
          fontSize: '0.78rem',
          textAlign: 'start',
        },
        body: {
          textAlign: 'start',
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 600,
        },
      },
    },
  },
});
