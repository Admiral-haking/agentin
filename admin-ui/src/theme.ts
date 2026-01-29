import { createTheme } from '@mui/material/styles';

export const appTheme = createTheme({
  direction: 'rtl',
  palette: {
    mode: 'light',
    primary: {
      main: '#0f8b8d',
      dark: '#0b6f71',
      light: '#5bc6c2',
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#f28f54',
      dark: '#d87941',
      light: '#f6b485',
      contrastText: '#1f1f1f',
    },
    background: {
      default: '#f2f0ea',
      paper: '#ffffff',
    },
    text: {
      primary: '#151823',
      secondary: '#3a4153',
    },
    divider: 'rgba(18, 22, 33, 0.08)',
    success: { main: '#2f9f86' },
    warning: { main: '#f0a34a' },
    error: { main: '#d14c4c' },
    info: { main: '#3d6fab' },
  },
  shape: {
    borderRadius: 16,
  },
  typography: {
    fontFamily: '"Vazirmatn", "IBM Plex Sans", sans-serif',
    h1: { fontWeight: 700, letterSpacing: '-0.02em' },
    h2: { fontWeight: 700, letterSpacing: '-0.02em' },
    h3: { fontWeight: 700, letterSpacing: '-0.02em' },
    h4: { fontWeight: 700, letterSpacing: '-0.015em' },
    h5: { fontWeight: 700, letterSpacing: '-0.01em' },
    h6: { fontWeight: 700 },
    subtitle1: { fontWeight: 600 },
    subtitle2: { fontWeight: 600 },
    body1: { lineHeight: 1.8 },
    body2: { lineHeight: 1.7 },
  },
  components: {
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundImage: 'linear-gradient(135deg, #0f8b8d 0%, #1b3f7a 100%)',
          color: '#fff',
          boxShadow: '0 12px 32px rgba(15, 139, 141, 0.3)',
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundImage: 'linear-gradient(180deg, #fbfaf5 0%, #ffffff 100%)',
          borderRight: '1px solid rgba(18, 22, 33, 0.08)',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'linear-gradient(180deg, rgba(255,255,255,0.95) 0%, #ffffff 100%)',
          border: '1px solid rgba(18, 22, 33, 0.08)',
          boxShadow: '0 18px 42px rgba(18, 22, 33, 0.08)',
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 18,
          boxShadow: '0 22px 45px rgba(18, 22, 33, 0.08)',
        },
      },
    },
    MuiCardContent: {
      styleOverrides: {
        root: {
          padding: '20px 24px',
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
        contained: {
          boxShadow: '0 12px 26px rgba(15, 139, 141, 0.22)',
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
    MuiTableRow: {
      styleOverrides: {
        root: {
          transition: 'background-color 150ms ease',
          '&:hover': {
            backgroundColor: 'rgba(15, 139, 141, 0.06)',
          },
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
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          alignItems: 'center',
        },
      },
    },
    MuiLinearProgress: {
      styleOverrides: {
        root: {
          height: 8,
          borderRadius: 999,
        },
      },
    },
  },
});
