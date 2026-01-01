import { AppBar } from 'react-admin';
import { Box, Chip, Typography } from '@mui/material';

export const AdminAppBar = () => (
  <AppBar>
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <Typography variant="h6">
        پنل مدیریت تیم‌کور
      </Typography>
      <Chip
        label="آنلاین"
        size="small"
        sx={{
          bgcolor: 'rgba(255,255,255,0.2)',
          color: '#fff',
          borderColor: 'rgba(255,255,255,0.35)',
        }}
        variant="outlined"
      />
    </Box>
  </AppBar>
);
