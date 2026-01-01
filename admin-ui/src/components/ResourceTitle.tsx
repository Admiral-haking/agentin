import { Box, Chip, Typography } from '@mui/material';

type ResourceTitleProps = {
  title: string;
  subtitle?: string;
  tag?: string;
};

export const ResourceTitle = ({ title, subtitle, tag }: ResourceTitleProps) => (
  <Box sx={{ py: 1, textAlign: 'right' }}>
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <Typography variant="h5">{title}</Typography>
      {tag && (
        <Chip
          label={tag}
          size="small"
          sx={{ bgcolor: 'rgba(15, 139, 141, 0.12)', color: '#0a6e70' }}
        />
      )}
    </Box>
    {subtitle && (
      <Typography variant="body2" color="text.secondary">
        {subtitle}
      </Typography>
    )}
  </Box>
);
