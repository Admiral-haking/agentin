import { AppBar } from 'react-admin';
import { Box, Chip, Typography } from '@mui/material';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';

export const AdminAppBar = () => (
  <AppBar>
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <Typography variant="h6">
        پنل مدیریت هوشمند
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
      <Chip
        label="هوش فعال"
        size="small"
        icon={<AutoAwesomeRoundedIcon sx={{ color: '#fff' }} fontSize="small" />}
        sx={{
          bgcolor: 'rgba(255,255,255,0.16)',
          color: '#fff',
          borderColor: 'rgba(255,255,255,0.3)',
          '& .MuiChip-icon': { color: '#fff' },
        }}
        variant="outlined"
      />
    </Box>
  </AppBar>
);
